#!/usr/bin/env python3
"""
Diagnóstico: procesa SOLO la primera imagen y muestra TODO lo que ve el OCR.
Sirve para entender por qué transcribe mal.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import IMAGENES_DIR, EXTENSIONES_IMAGEN, ETIQUETAS_CAMPOS, HOJA_MAQUINARIAS, COLUMNAS_MAQUINARIAS


def listar_imagenes(directorio: Path):
    imagenes = []
    for ext in EXTENSIONES_IMAGEN:
        imagenes.extend(directorio.glob(f"*{ext}"))
    imagenes = [p for p in imagenes if "WhatsApp_files" not in str(p)]
    return sorted(imagenes)


def main():
    imagenes = listar_imagenes(IMAGENES_DIR)
    if not imagenes:
        print("No hay imágenes.")
        return

    ruta = imagenes[0]
    print("=" * 70)
    print(f"IMAGEN: {ruta.name}")
    print("=" * 70)

    print("\nInicializando OCR...")
    from ocr_engine import _inicializar_easyocr, _extraer_texto_ocr, _leer_texto
    reader = _inicializar_easyocr()

    from preprocesador import preprocesar_para_ocr
    from ocr_engine import transcribir_boleta
    from exportador_excel import _boleta_a_fila_maquinarias
    from config import OCR_CONFIG

    modos = OCR_CONFIG.get("preproc_try_modes", ["raw", "contraste", "hibrido", "binario"])
    mejor_modo = None
    mejor_campos = -1

    for idx, modo in enumerate(modos, start=1):
        img = preprocesar_para_ocr(ruta, modo=modo, devolver_color=True)
        print(f"(modo: {modo}, color BGR, shape={img.shape})")
        results = _leer_texto(reader, img)

        print("\n" + "=" * 70)
        print(f"{idx}. {modo.upper()} OCR - Todo lo que EasyOCR detectó (texto | confianza | posición)")
        print("=" * 70)
        for i, (bbox, texto, conf) in enumerate(results):
            y, x = bbox[0][1], bbox[0][0]
            print(f"  [{i:2d}] conf={conf:.2f} y={y:.0f} x={x:.0f} | \"{texto}\"")

        b = transcribir_boleta(ruta, reader=reader, modo_preproc=modo)
        b.imagen_origen = ruta.name
        campos_ok = sum(
            1 for v in [
                b.fecha_completa(), b.numero_reporte, b.camion, b.patente, b.operador,
                b.obra, b.tipo_faena, b.horarios, b.observaciones
            ] if v
        )
        if campos_ok > mejor_campos:
            mejor_campos = campos_ok
            mejor_modo = modo

        print("\n" + "=" * 70)
        print("CAMPOS EXTRAÍDOS por nuestra lógica")
        print("=" * 70)
        print(f"  Fecha:       {b.fecha_completa() or '(vacío)'}")
        print(f"  N° Reporte:  {b.numero_reporte or '(vacío)'}")
        print(f"  Camión:      {b.camion or '(vacío)'}")
        print(f"  Patente:     {b.patente or '(vacío)'}")
        print(f"  Operador:    {b.operador or '(vacío)'}")
        print(f"  Obra:        {b.obra or '(vacío)'}")
        print(f"  Tipo Faena:  {b.tipo_faena or '(vacío)'}")
        print(f"  Horarios:    {b.horarios or '(vacío)'}")
        print(f"  Observac.:   {b.observaciones or '(vacío)'}")

        fila = _boleta_a_fila_maquinarias(b)
        print("\n" + "=" * 70)
        print("FILA que se escribiría en Excel (hoja SEGUIMIENTO MAQUINARIAS)")
        print("=" * 70)
        for col, val in zip(COLUMNAS_MAQUINARIAS, fila):
            print(f"  {col}: \"{val}\"")

    print("\n" + "=" * 70)
    print("Hoja destino:", HOJA_MAQUINARIAS)
    print("Mejor modo sugerido:", mejor_modo or "(sin datos)")
    print("=" * 70)


if __name__ == "__main__":
    main()
