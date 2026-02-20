"""
Motor OCR para transcripción de boletas.
Maneja texto impreso y manuscrito con asociación por etiquetas.
"""
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

import cv2

from config import (
    ETIQUETAS_CAMPOS,
    OCR_CONFIG,
    BOLETA_TIPO_KEYWORDS,
    TIPO_DESCONOCIDO,
)
from preprocesador import preprocesar_para_ocr
from schema import BoletaTranscrita


STOPWORDS_RUIDO = {
    "firma",
    "nombre",
    "operador",
    "supervisado",
    "v b",
    "jefe de obra",
}


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
    """Ejecuta OCR sobre imagen con preprocesado indicado."""
    img = preprocesar_para_ocr(ruta_imagen, modo=modo_preproc, devolver_color=True)
    results = _leer_texto(reader, img)
    return [(bbox, text.strip(), conf) for bbox, text, conf in results if text and text.strip()]


def _extraer_texto_ocr_rotaciones(
    ruta_imagen: Path, reader, modo_preproc: str = "raw", rotaciones: tuple[int, ...] = (0, 180)
) -> list[tuple[list, str, float]]:
    """
    Ejecuta OCR en varias rotaciones y conserva la salida con mejor score estructural.
    Esto ayuda en fotos invertidas o inclinadas.
    """
    base = preprocesar_para_ocr(ruta_imagen, modo=modo_preproc, devolver_color=True)
    mejor_res: list[tuple[list, str, float]] = []
    mejor_score = -1.0

    for rot in rotaciones:
        if rot == 0:
            img = base
        elif rot == 180:
            img = cv2.rotate(base, cv2.ROTATE_180)
        elif rot == 90:
            img = cv2.rotate(base, cv2.ROTATE_90_CLOCKWISE)
        elif rot == 270:
            img = cv2.rotate(base, cv2.ROTATE_90_COUNTERCLOCKWISE)
        else:
            continue

        resultados = [(b, t.strip(), c) for b, t, c in _leer_texto(reader, img) if t and t.strip()]
        score = _puntuar_resultados(resultados) + sum(c for _, _, c in resultados[:20]) * 0.2
        if score > mejor_score:
            mejor_score = score
            mejor_res = resultados

    return mejor_res


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
    mapa = str.maketrans(
        {
            "O": "0",
            "o": "0",
            "I": "1",
            "l": "1",
            "|": "1",
            "Z": "2",
            "z": "2",
            "S": "5",
            "s": "5",
            "B": "8",
            "G": "6",
            "Q": "0",
        }
    )
    t = t.translate(mapa)
    t = re.sub(r"[^0-9]", "", t)
    if not t:
        return None
    return t


def _limpiar_valor(val: str) -> str:
    """Limpia caracteres residuales del OCR."""
    val = re.sub(r"[\|\{\}\[\]]", "", val)
    val = re.sub(r"\s+", " ", val).strip()
    return val


def _es_texto_ruido(val: str) -> bool:
    t = _normalizar_texto(val)
    if not t:
        return True
    return any(sw in t for sw in STOPWORDS_RUIDO)


def _asociar_campo(etiqueta: str, textos: list[tuple[list, str, float]]) -> tuple[Optional[str], float]:
    """
    Busca el valor que sigue a una etiqueta conocida.
    Considera valor a la derecha o debajo de la etiqueta.
    """
    etiqueta_lower = etiqueta.lower().rstrip(":")

    for i, (bbox, texto, conf) in enumerate(textos):
        texto_limpio = texto.strip()
        if not texto_limpio:
            continue

        if _match_etiqueta(texto_limpio, etiqueta_lower):
            if re.search(r"[:;]", texto_limpio):
                partes = re.split(r"[:;]", texto_limpio, maxsplit=1)
                if len(partes) == 2 and partes[1].strip() and not _es_texto_ruido(partes[1]):
                    return _limpiar_valor(partes[1].strip()), conf

            y_etiqueta = bbox[0][1]
            x_etiqueta_ini = bbox[0][0]
            x_etiqueta_end = bbox[1][0]
            candidatos = []
            for j, (bbox2, texto2, conf2) in enumerate(textos):
                if i == j:
                    continue
                t2 = texto2.strip()
                if not t2 or _es_texto_ruido(t2):
                    continue
                y_valor = bbox2[0][1]
                x_valor = bbox2[0][0]
                # Preferir misma fila a la derecha
                if abs(y_valor - y_etiqueta) < 45 and x_valor > x_etiqueta_end - 30:
                    candidatos.append((0, x_valor, abs(y_valor - y_etiqueta), t2, conf2))
                # Fallback: línea inmediatamente inferior y algo alineada en X
                elif 0 < (y_valor - y_etiqueta) < 70 and x_valor >= x_etiqueta_ini - 20:
                    candidatos.append((1, x_valor, abs(y_valor - y_etiqueta), t2, conf2))

            if candidatos:
                candidatos.sort(key=lambda c: (c[0], c[2], c[1]))
                best = candidatos[0]
                return _limpiar_valor(best[3]), best[4]

        if _match_etiqueta(texto_limpio[: len(etiqueta_lower) + 3], etiqueta_lower):
            resto = texto_limpio[len(etiqueta) :].strip()
            resto = resto.lstrip(": ")
            if resto and not _es_texto_ruido(resto):
                return _limpiar_valor(resto), conf

    return None, 0.0


def _extraer_fecha_reporte(textos: list[tuple[list, str, float]]) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Extrae DIA, MES, AÑO de la caja de fecha del reporte."""
    dia, mes, anio = None, None, None
    etiquetas_fecha = {"dia", "mes", "ano"}
    pos_etiquetas = {}
    numeros = []

    for bbox, texto, _ in textos:
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
            if abs(y - y_et) < 55 and x > x_et_end - 25:
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

    numeros_2dig = []
    for i, (bbox, texto, _) in enumerate(textos[:30]):
        num = _normalizar_numero_token(texto)
        if num and 1 <= len(num) <= 2:
            numeros_2dig.append((i, num, bbox[0][0], bbox[0][1]))

    numeros_2dig.sort(key=lambda x: (x[3], x[2]))
    if len(numeros_2dig) >= 3:
        dia, mes, anio = numeros_2dig[0][1], numeros_2dig[1][1], numeros_2dig[2][1]
    return dia, mes, anio


def _extraer_numero_reporte(textos: list[tuple[list, str, float]]) -> tuple[Optional[str], float]:
    """Extrae N° reporte (acepta 3 a 7 dígitos; prioriza patrón con etiqueta N°)."""
    candidatos = []
    for bbox, texto, conf in textos:
        m = re.search(r"N\s*[°º\.?]?\s*(\d{3,7})", texto, re.I)
        if m:
            candidatos.append((m.group(1).strip(), conf + 0.15))
            continue

        num = _normalizar_numero_token(texto)
        if num and 4 <= len(num) <= 7:
            y = bbox[0][1] if bbox else 9999
            bonus = 0.1 if y < 260 else 0.0
            candidatos.append((num, conf + bonus))

    if not candidatos:
        return None, 0.0

    candidatos.sort(key=lambda x: x[1], reverse=True)
    return candidatos[0]


def _puntuar_resultados(resultados: list[tuple[list, str, float]]) -> int:
    score = 0
    for _, texto, _ in resultados:
        for etiquetas in ETIQUETAS_CAMPOS.values():
            if any(_match_etiqueta(texto, et) for et in etiquetas):
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


def _detectar_tipo_boleta(resultados: list[tuple[list, str, float]]) -> str:
    """Clasifica tipo de boleta según palabras clave en el OCR completo."""
    texto = " ".join(t for _, t, _ in resultados if t).lower()
    texto_norm = _normalizar_texto(texto)
    puntajes = {}

    for tipo, keywords in BOLETA_TIPO_KEYWORDS.items():
        score = 0
        for kw in keywords:
            if _normalizar_texto(kw) in texto_norm:
                score += 1
        puntajes[tipo] = score

    mejor_tipo = max(puntajes, key=puntajes.get) if puntajes else TIPO_DESCONOCIDO
    if puntajes.get(mejor_tipo, 0) == 0:
        return TIPO_DESCONOCIDO
    return mejor_tipo


def _limpiar_patente(valor: Optional[str]) -> Optional[str]:
    if not valor:
        return valor
    t = re.sub(r"[^A-Za-z0-9]", "", valor.upper())
    if not t:
        return None
    m = re.search(r"([A-Z]{2,4}\d{2,4})", t)
    return m.group(1) if m else t


def _limpiar_horarios(valor: Optional[str]) -> Optional[str]:
    if not valor:
        return valor
    texto = valor.replace(";", " ").replace("-", " ")
    tiempos = re.findall(r"\d{1,2}:\d{2}|\d{3,4}", texto)
    if not tiempos:
        return _limpiar_valor(valor)
    return " - ".join(tiempos[:4])


def _postprocesar_campos(campos: dict[str, str]) -> dict[str, str]:
    out = dict(campos)
    if "patente" in out:
        out["patente"] = _limpiar_patente(out.get("patente")) or ""
    if "horarios" in out:
        out["horarios"] = _limpiar_horarios(out.get("horarios")) or ""

    for k in ("operador", "obra", "camion", "tipo_faena", "observaciones"):
        if k in out:
            v = _limpiar_valor(out[k])
            out[k] = "" if _es_texto_ruido(v) else v

    return {k: v for k, v in out.items() if v}


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
    rotaciones = tuple(OCR_CONFIG.get("ocr_rotations", [0, 180]))

    if modo == "auto":
        best = None
        best_score = -1.0
        for m in OCR_CONFIG.get("preproc_try_modes", ["raw", "contraste", "hibrido", "binario"]):
            res = _extraer_texto_ocr_rotaciones(ruta, reader, modo_preproc=m, rotaciones=rotaciones)
            score = _puntuar_resultados(res) + sum(c for _, _, c in res[:20]) * 0.2
            if score > best_score:
                best_score = score
                best = res
        resultados = best or _extraer_texto_ocr_rotaciones(ruta, reader, modo_preproc="raw", rotaciones=rotaciones)
    else:
        resultados = _extraer_texto_ocr_rotaciones(ruta, reader, modo_preproc=modo, rotaciones=rotaciones)

    dia, mes, anio = _extraer_fecha_reporte(resultados)
    num_reporte, _ = _extraer_numero_reporte(resultados)

    campos_extraidos: dict[str, str] = {}
    confianzas = []

    for campo, etiquetas in ETIQUETAS_CAMPOS.items():
        for et in etiquetas:
            val, conf = _asociar_campo(et, resultados)
            if val:
                campos_extraidos[campo] = val
                if conf > 0:
                    confianzas.append(conf)
                break

    campos_extraidos = _postprocesar_campos(campos_extraidos)
    tipo_boleta = _detectar_tipo_boleta(resultados)

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
        tipo_boleta=tipo_boleta,
        imagen_origen=ruta.name,
        confianza_promedio=sum(confianzas) / len(confianzas) if confianzas else 0.0,
    )

    return boleta
