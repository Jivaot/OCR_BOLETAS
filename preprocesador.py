"""
Preprocesamiento de imágenes para mejorar precisión de OCR en manuscritos.
- Ajuste de contraste y brillo
- Binarización adaptativa
- Corrección de inclinación
- Reducción de ruido
"""
import cv2
import numpy as np
from pathlib import Path
from PIL import Image


def cargar_imagen(ruta: str | Path) -> np.ndarray:
    """Carga imagen y la convierte a escala de grises."""
    img = cv2.imread(str(ruta))
    if img is None:
        raise ValueError(f"No se pudo cargar la imagen: {ruta}")
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def aumentar_contraste(img: np.ndarray, clip_limit: float = 2.0) -> np.ndarray:
    """Aplica CLAHE para mejorar contraste local (mejor para manuscritos)."""
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(8, 8))
    return clahe.apply(img)


def binarizar_adaptativa(img: np.ndarray, block_size: int = 11, c: int = 2) -> np.ndarray:
    """
    Binarización adaptativa - crucial para manuscritos con iluminación irregular.
    Preserva mejor el trazo manuscrito que Otsu en documentos mixtos.
    """
    return cv2.adaptiveThreshold(
        img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, block_size, c
    )


def reducir_ruido(img: np.ndarray) -> np.ndarray:
    """Reducción de ruido preservando bordes (importante para letras)."""
    return cv2.bilateralFilter(img, 9, 75, 75)


def morfologia_limpieza(img: np.ndarray) -> np.ndarray:
    """Operaciones morfológicas para limpiar pequeños artefactos."""
    kernel = np.ones((1, 1), np.uint8)
    return cv2.morphologyEx(img, cv2.MORPH_CLOSE, kernel)


def preprocesar_para_ocr(ruta: str | Path, modo: str = "raw", devolver_color: bool = False) -> np.ndarray:
    """
    Pipeline de preprocesamiento para boletas manuscritas/imprenta.
    
    modos:
    - "raw": sin CLAHE/denoise (MEJOR para fotos WhatsApp - el preprocesado degradaba)
    - "contraste": solo CLAHE
    - "hibrido": contraste + denoising
    - "binario": binarización adaptativa
    devolver_color: si True, retorna BGR (EasyOCR lee mejor fotos en color)
    """
    img = cv2.imread(str(ruta))
    if img is None:
        raise ValueError(f"No se pudo cargar: {ruta}")

    h, w = img.shape[:2]
    if max(h, w) > 2400:
        scale = 2400 / max(h, w)
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)

    if modo == "raw":
        return img if devolver_color else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if modo == "contraste":
        return aumentar_contraste(img)
    if modo == "binario":
        img = aumentar_contraste(img)
        img = reducir_ruido(img)
        return binarizar_adaptativa(img)
    img = aumentar_contraste(img, clip_limit=1.5)
    return reducir_ruido(img)


def guardar_preprocesada(img: np.ndarray, ruta_salida: str | Path) -> None:
    """Guarda imagen preprocesada para debug/verificación."""
    cv2.imwrite(str(ruta_salida), img)
