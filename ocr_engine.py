"""
Motor OCR para transcripción de boletas.
Maneja texto impreso y manuscrito con asociación por etiquetas.
"""
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

from config import ETIQUETAS_CAMPOS, CAMPOS_BOLETA, OCR_CONFIG
from preprocesador import preprocesar_para_ocr
from schema import BoletaTranscrita


def _inicializar_easyocr():
    """Importación diferida de EasyOCR (pesado). Usa GPU si está disponible."""
    import easyocr
    gpu = OCR_CONFIG.get("gpu", True)
    return easyocr.Reader(OCR_CONFIG.get("languages", ["es", "en"]), gpu=gpu, verbose=False)


def _leer_texto(reader, img) -> list[tuple[list, str, float]]:
    """Wrapper de EasyOCR con parámetros desde OCR_CONFIG."""
    kwargs = {
        "detail": OCR_CONFIG.get("detail", 1),
        "paragraph": OCR_CONFIG.get("paragraph", False),
        "width_ths": OCR_CONFIG.get("width_ths", 0.7),
    }
    results = reader.readtext(img, **kwargs)
    min_conf = OCR_CONFIG.get("min_confidence", None)
    if min_conf is not None:
        results = [r for r in results if r[2] >= min_conf]
    return results


def _extraer_texto_ocr(ruta_imagen: Path, reader, modo_preproc: str = "raw") -> list[tuple[list, str, float]]:
    """
    Ejecuta OCR sobre imagen.
    modo_preproc: "raw" (sin CLAHE, mejor para fotos), "hibrido", "contraste"
    Prueba con imagen en COLOR - EasyOCR suele leer mejor que grises en fotos.
    """
    img = preprocesar_para_ocr(ruta_imagen, modo=modo_preproc, devolver_color=True)
    results = _leer_texto(reader, img)
    return [(bbox, text.strip(), conf) for bbox, text, conf in results]


def _normalizar_texto(s: str) -> str:
    s = s.strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return s


def _similaridad(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _match_etiqueta(texto: str, etiqueta: str) -> bool:
    t_norm = _normalizar_texto(texto)
    e_norm = _normalizar_texto(etiqueta)
    if not t_norm or not e_norm:
        return False
    if e_norm in t_norm:
        return True
    mapa = str.maketrans({"0": "o", "1": "i", "2": "z", "5": "s", "6": "g", "8": "b"})
    t_alt = t_norm.translate(mapa)
    if e_norm in t_alt:
        return True
    if len(t_norm) == len(e_norm):
        dif = sum(1 for a, b in zip(t_norm, e_norm) if a != b)
        if dif <= 1:
            return True
    if not OCR_CONFIG.get("fuzzy_labels", False):
        return False
    th = OCR_CONFIG.get("fuzzy_threshold", 0.78)
    if len(e_norm) <= 3:
        th = min(th, 0.65)
    if len(t_norm) <= len(e_norm) + 4:
        return _similaridad(t_norm, e_norm) >= th or _similaridad(t_alt, e_norm) >= th
    prefix = t_norm[: len(e_norm) + 2]
    prefix_alt = t_alt[: len(e_norm) + 2]
    return _similaridad(prefix, e_norm) >= th or _similaridad(prefix_alt, e_norm) >= th


def _normalizar_numero_token(token: str) -> Optional[str]:
    t = token.strip()
    if not t:
        return None
    mapa = str.maketrans({
        "O": "0", "o": "0",
        "I": "1", "l": "1", "|": "1",
        "Z": "2", "z": "2",
        "S": "5", "s": "5",
        "B": "8",
        "G": "6",
        "Q": "0",
    })
    t = t.translate(mapa)
    t = re.sub(r"[^0-9]", "", t)
    if not t:
        return None
    return t


def _asociar_campo(etiqueta: str, textos: list[tuple[list, str, float]]) -> tuple[Optional[str], float]:
    """
    Busca el valor que sigue a una etiqueta conocida.
    Considera proximidad en Y (misma fila) para asociar.
    """
    etiqueta_lower = etiqueta.lower().rstrip(":")
    
    for i, (bbox, texto, conf) in enumerate(textos):
        texto_limpio = texto.strip()
        if not texto_limpio:
            continue
        
        # ¿Este texto contiene la etiqueta?
        if _match_etiqueta(texto_limpio, etiqueta_lower):
            # El valor puede estar en el mismo texto (ej: "Camión: Aljibe")
            if re.search(r"[:;]", texto_limpio):
                partes = re.split(r"[:;]", texto_limpio, maxsplit=1)
                if len(partes) == 2 and partes[1].strip():
                    return _limpiar_valor(partes[1].strip()), conf
            
            # O en el siguiente elemento (misma línea o línea siguiente)
            y_etiqueta = bbox[0][1]
            x_etiqueta_end = bbox[1][0]
            candidatos = []
            for j, (bbox2, texto2, conf2) in enumerate(textos):
                if i == j:
                    continue
                y_valor = bbox2[0][1]
                x_valor = bbox2[0][0]
                # Misma fila (tolerancia en Y) y a la derecha de la etiqueta
                if abs(y_valor - y_etiqueta) < 40 and x_valor > x_etiqueta_end - 30:
                    candidatos.append((x_valor, texto2.strip(), conf2))
            
            if candidatos:
                candidatos.sort(key=lambda c: c[0])
                return _limpiar_valor(candidatos[0][1]), candidatos[0][2]
        
        # Caso: valor y etiqueta en mismo blob (ej: "Patente: FN1411")
        if _match_etiqueta(texto_limpio[: len(etiqueta_lower) + 3], etiqueta_lower):
            resto = texto_limpio[len(etiqueta):].strip()
            resto = resto.lstrip(": ")
            if resto:
                return _limpiar_valor(resto), conf
    
    return None, 0.0


def _limpiar_valor(val: str) -> str:
    """Limpia caracteres residuales del OCR."""
    val = re.sub(r"[\|\{\}\[\]]", "", val)
    val = re.sub(r"\s+", " ", val).strip()
    return val


def _extraer_fecha_reporte(textos: list[tuple[list, str, float]]) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Extrae DIA, MES, AÑO de la caja de fecha del reporte.
    Busca números de 1-2 dígitos cerca de "DIA", "MES", "AÑO" o "REPORT".
    """
    dia, mes, anio = None, None, None
    etiquetas_fecha = {"dia", "mes", "ano"}
    pos_etiquetas = {}
    numeros = []

    for i, (bbox, texto, _) in enumerate(textos):
        t_norm = _normalizar_texto(texto)
        for et in etiquetas_fecha:
            if _match_etiqueta(t_norm, et):
                pos_etiquetas[et] = bbox
        num = _normalizar_numero_token(texto)
        if num and 1 <= len(num) <= 2:
            numeros.append((num, bbox))

    def _candidato_cerca(bbox_et):
        y_et = bbox_et[0][1]
        x_et_end = bbox_et[1][0]
        candidatos = []
        for num, bbox in numeros:
            y = bbox[0][1]
            x = bbox[0][0]
            if abs(y - y_et) < 50 and x > x_et_end - 20:
                candidatos.append((x, num))
        if candidatos:
            candidatos.sort(key=lambda c: c[0])
            return candidatos[0][1]
        return None

    if pos_etiquetas:
        dia = _candidato_cerca(pos_etiquetas.get("dia")) if pos_etiquetas.get("dia") else None
        mes = _candidato_cerca(pos_etiquetas.get("mes")) if pos_etiquetas.get("mes") else None
        anio = _candidato_cerca(pos_etiquetas.get("ano")) if pos_etiquetas.get("ano") else None
        if dia or mes or anio:
            return dia, mes, anio

    # Fallback: primeros números en el encabezado
    numeros_2dig = []
    for i, (bbox, texto, _) in enumerate(textos[:25]):
        num = _normalizar_numero_token(texto)
        if num and 1 <= len(num) <= 2:
            numeros_2dig.append((i, num, bbox[0][0], bbox[0][1]))

    numeros_2dig.sort(key=lambda x: (x[3], x[2]))
    if len(numeros_2dig) >= 3:
        dia = numeros_2dig[0][1]
        mes = numeros_2dig[1][1]
        anio = numeros_2dig[2][1]
    return dia, mes, anio


def _extraer_numero_reporte(textos: list[tuple[list, str, float]]) -> tuple[Optional[str], float]:
    """Extrae N° reporte (ej: 0250, 0251)."""
    for bbox, texto, conf in textos:
        m = re.search(r"N[°º\.\?]?\s*(\d{3,5})", texto, re.I)
        if m:
            return m.group(1).strip(), conf
        num = _normalizar_numero_token(texto)
        if num and len(num) == 4:
            return num, conf
    return None, 0.0


def _puntuar_resultados(resultados: list[tuple[list, str, float]]) -> int:
    score = 0
    for _, texto, _ in resultados:
        for campo, etiquetas in ETIQUETAS_CAMPOS.items():
            for et in etiquetas:
                if _match_etiqueta(texto, et):
                    score += 1
                    break
    num, _ = _extraer_numero_reporte(resultados)
    dia, mes, anio = _extraer_fecha_reporte(resultados)
    if num:
        score += 2
    if dia and mes:
        score += 2
    if anio:
        score += 1
    return score


def transcribir_boleta(ruta_imagen: str | Path, reader=None, modo_preproc: Optional[str] = None) -> BoletaTranscrita:
    """
    Transcribe una boleta completa desde imagen.
    Retorna BoletaTranscrita con todos los campos extraídos.
    """
    ruta = Path(ruta_imagen)
    if not ruta.exists():
        raise FileNotFoundError(f"Imagen no encontrada: {ruta}")
    
    if reader is None:
        reader = _inicializar_easyocr()
    
    modo = modo_preproc or OCR_CONFIG.get("preproc_mode", "raw")
    if modo == "auto":
        best = None
        best_score = -1
        for m in OCR_CONFIG.get("preproc_try_modes", ["raw", "contraste", "hibrido", "binario"]):
            res = _extraer_texto_ocr(ruta, reader, modo_preproc=m)
            score = _puntuar_resultados(res)
            if score > best_score:
                best_score = score
                best = res
        resultados = best or _extraer_texto_ocr(ruta, reader, modo_preproc="raw")
    else:
        resultados = _extraer_texto_ocr(ruta, reader, modo_preproc=modo)
    
    # Extraer fecha
    dia, mes, anio = _extraer_fecha_reporte(resultados)
    
    # Extraer N° reporte
    num_reporte, conf_num = _extraer_numero_reporte(resultados)
    
    # Extraer campos por etiqueta
    campos_extraidos = {}
    confianzas = []
    
    for campo, etiquetas in ETIQUETAS_CAMPOS.items():
        for et in etiquetas:
            val, conf = _asociar_campo(et, resultados)
            if val:
                campos_extraidos[campo] = val
                if conf > 0:
                    confianzas.append(conf)
                break
    
    # Construir boleta
    boleta = BoletaTranscrita(
        fecha_dia=dia,
        fecha_mes=mes,
        fecha_anio=anio,
        numero_reporte=num_reporte,
        camion=campos_extraidos.get("camion"),
        patente=campos_extraidos.get("patente"),
        operador=campos_extraidos.get("operador"),
        obra=campos_extraidos.get("obra"),
        tipo_faena=campos_extraidos.get("tipo_faena"),
        horarios=campos_extraidos.get("horarios"),
        observaciones=campos_extraidos.get("observaciones"),
        imagen_origen=ruta.name,
        confianza_promedio=sum(confianzas) / len(confianzas) if confianzas else 0.0,
    )
    
    return boleta
