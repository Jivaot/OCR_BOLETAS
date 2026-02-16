"""
OCR vía Celery - usa tu worker ocr.by_path.
Basado en tu detector de placas: envía imagen, recibe {best_valid, best_any, candidates}.
"""
import os
import uuid
from pathlib import Path
from typing import List, Tuple, Any

import cv2
import numpy as np

# Broker - debe coincidir con tu worker (ej: rabbitmq-ocr:5672 en Docker)
BROKER = os.environ.get("CELERY_BROKER_URL", "amqp://guest:guest@localhost:5672//")
BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "rpc://")
# Mismo SHARED_DIR que tu detector de placas para que el worker pueda leer
SHARED_DIR = os.environ.get("PLATE_SHARED_DIR", "/dev/shm/plates")
OCR_QUEUE = os.environ.get("OCR_QUEUE", "ocr_queue")
OCR_TIMEOUT = float(os.environ.get("OCR_TIMEOUT", "15.0"))

os.makedirs(SHARED_DIR, exist_ok=True)


def _get_celery_app():
    from celery import Celery
    app = Celery("boletas_ocr", broker=BROKER, backend=BACKEND)
    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
    )
    return app


def _save_crop_for_celery(img_bgr: np.ndarray) -> str:
    """Guarda crop BGR en SHARED_DIR, retorna path."""
    img = np.asarray(img_bgr)
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    if img.dtype != np.uint8:
        img = img.astype(np.uint8)
    fpath = os.path.join(SHARED_DIR, f"{uuid.uuid4().hex}.jpg")
    cv2.imwrite(fpath, img, [cv2.IMWRITE_JPEG_QUALITY, 90])
    return fpath


def leer_imagen_celery(ruta: Path) -> Tuple[List[Tuple[Any, str, float]], dict | None]:
    """
    Envía imagen a Celery OCR worker.
    Retorna: (resultados_formato_easyocr, raw_response)
    resultados = [(bbox_dummy, texto, conf), ...] para compatibilidad con _extraer_numero.
    Si falla: ([], raw_err).
    """
    ruta = Path(ruta)
    if not ruta.exists():
        return ([], {"error": f"Archivo no existe: {ruta}"})

    img = cv2.imread(str(ruta))
    if img is None:
        return ([], {"error": f"No se pudo cargar: {ruta}"})

    try:
        app = _get_celery_app()
        img_path = _save_crop_for_celery(img)
        async_res = app.send_task("ocr.by_path", args=[img_path], queue=OCR_QUEUE)
        res = async_res.get(timeout=OCR_TIMEOUT)
    except Exception as e:
        return ([], {"error": str(e)})

    if not isinstance(res, dict):
        return ([], {"raw": res})

    # Formato real del worker PaddleOCR: best_valid/best_any = {"text": "...", "score": ...}
    # candidates = [{"text": "...", "score": ..., "valid": ...}, ...]
    def _texto(v):
        if isinstance(v, str) and v.strip():
            return (v.strip(), 0.9)
        if isinstance(v, dict) and v.get("text"):
            return (str(v["text"]).strip(), float(v.get("score", 0.8)))
        return None

    textos = []
    seen = set()
    for key in ("best_valid", "best_any"):
        v = res.get(key)
        tup = _texto(v)
        if tup and tup[0] not in seen:
            textos.append(([[0, 0], [0, 0], [0, 0], [0, 0]], tup[0], tup[1]))
            seen.add(tup[0])
    for c in res.get("candidates") or []:
        tup = _texto(c) if isinstance(c, dict) else None
        if tup and tup[0] not in seen:
            textos.append(([[0, 0], [0, 0], [0, 0], [0, 0]], tup[0], tup[1]))
            seen.add(tup[0])

    return (textos, res)


def _texto_de_campo(v) -> str | None:
    """Extrae string de best_valid/best_any (dict o str)."""
    if isinstance(v, str) and v.strip():
        return v.strip()
    if isinstance(v, dict) and v.get("text"):
        return str(v["text"]).strip()
    return None


def extraer_reporte_de_respuesta_celery(res: dict) -> str | None:
    """
    Extrae número de reporte de la respuesta PaddleOCR.
    El worker filtra por placas chilenas (best_valid); para boletas usamos
    candidates que tiene todo lo que PaddleOCR leyó.
    """
    import re
    LARGOS = {4, 6, 7}

    def _parece_fecha(num: str) -> bool:
        if len(num) != 6:
            return False
        try:
            d, m = int(num[:2]), int(num[2:4])
            return 1 <= d <= 31 and 1 <= m <= 12
        except Exception:
            return False

    def _extraer_de_texto(t: str) -> str | None:
        if not t or not t.strip():
            return None
        m = re.search(r"N[°º\.\s]*(\d{3,7})", t, re.I)
        if m:
            num = re.sub(r"[^\d]", "", m.group(1))
            if len(num) in LARGOS and not _parece_fecha(num):
                return num
        num = re.sub(r"[^\d]", "", t)
        if len(num) in LARGOS and not _parece_fecha(num):
            return num
        return None

    for key in ("best_valid", "best_any"):
        v = _texto_de_campo(res.get(key))
        if v:
            r = _extraer_de_texto(v)
            if r:
                return r

    # Candidates ordenados por score - priorizar números de reporte
    for c in res.get("candidates") or []:
        t = _texto_de_campo(c) if isinstance(c, dict) else None
        if t:
            r = _extraer_de_texto(t)
            if r:
                return r
    return None
