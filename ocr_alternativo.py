"""
Conector para OCR alternativo.
- leer_imagen(): EasyOCR (default)
- leer_imagen_celery(): tu worker Celery ocr.by_path
"""
from pathlib import Path
from typing import List, Tuple, Any

# Formato: list[(bbox, texto, confianza)]
# bbox = [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
# texto = str
# confianza = float 0-1


def leer_imagen(ruta: Path, use_celery: bool = False) -> List[Tuple[Any, str, float]]:
    """
    Retorna: [(bbox, texto, conf), ...]
    use_celery=True: envía a worker Celery ocr.by_path (requiere CELERY_BROKER_URL).
    """
    if use_celery:
        from ocr_celery import leer_imagen_celery
        resultados, _ = leer_imagen_celery(ruta)
        return resultados
    # EasyOCR (default):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from config import OCR_CONFIG
    from preprocesador import preprocesar_para_ocr
    import easyocr

    reader = easyocr.Reader(
        OCR_CONFIG.get("languages", ["es", "en"]),
        gpu=OCR_CONFIG.get("gpu", False),
        verbose=False,
    )
    img = preprocesar_para_ocr(ruta, modo="raw", devolver_color=True)
    results = reader.readtext(img, detail=1, paragraph=False)
    return [(b, t.strip(), c) for b, t, c in results if t.strip()]


# Si usas pytesseract, ejemplo:
# def leer_imagen(ruta):
#     import pytesseract
#     from PIL import Image
#     img = Image.open(ruta)
#     data = pytesseract.image_to_data(img, lang='spa', output_type=pytesseract.Output.DICT)
#     out = []
#     for i, text in enumerate(data['text']):
#         if text.strip():
#             x,y,w,h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
#             bbox = [[x,y], [x+w,y], [x+w,y+h], [x,y+h]]
#             conf = data['conf'][i]/100.0
#             out.append((bbox, text.strip(), conf))
#     return out
