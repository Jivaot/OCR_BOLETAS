"""
Configuración del sistema de transcripción de boletas.
Rutas, columnas esperadas y parámetros de OCR.
"""
from pathlib import Path

# Rutas base
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
IMAGENES_DIR = PROJECT_ROOT / "Imagenes"
PLANTILLA_EXCEL = PROJECT_ROOT / "Plantilla" / "Seguimiento Maquinarias-aridos-excavaciones.xlsx"
# Plantilla con datos transcritos (si existe)
PLANTILLA_CON_DATOS = PROJECT_ROOT / "Plantilla" / "Seguimiento Maquinarias-aridos-excavaciones(1).xlsx"
OUTPUT_DIR = BASE_DIR / "output"
DB_TRANSCRIPCIONES = BASE_DIR / "transcripciones_registro.json"

# Extensiones de imagen soportadas (PDF requiere conversión externa)
EXTENSIONES_IMAGEN = {".jpeg", ".jpg", ".png", ".bmp", ".tiff", ".tif"}

# Campos de la boleta REPORTE DIARIO (orden lógico para extracción)
CAMPOS_BOLETA = [
    "fecha_dia",
    "fecha_mes", 
    "fecha_anio",
    "numero_reporte",
    "camion",
    "patente",
    "operador",
    "obra",
    "tipo_faena",
    "horarios",
    "observaciones",
]

# Etiquetas impresas que preceden cada campo (para asociar texto OCR)
ETIQUETAS_CAMPOS = {
    "numero_reporte": ["N°", "Nº", "N."],
    "camion": ["Camión:", "Camion:"],
    "patente": ["Patente:"],
    "operador": ["Operador:"],
    "obra": ["Obra:"],
    "tipo_faena": ["Tipo de Faena:", "Tipo Faena:"],
    "horarios": ["Horarios:"],
    "observaciones": ["Observaciones:"],
}

# Hojas de la plantilla - nombres exactos del documento Excel
HOJA_MAQUINARIAS = "SEGUIMIENTO MAQUINARIAS"
HOJA_ARIDOS = "SEGUIMIENTO_ARIDOS"
HOJA_MOV_TIERRA = "SEGUIMIENTO_MOV. TIERRA"

# Columnas de cada hoja en la plantilla (orden B a K para Maquinarias)
COLUMNAS_MAQUINARIAS = [
    "N° Report",
    "Fecha",
    "Operador",
    "Proveedor",
    "Patente",
    "Maquina",
    "Hora Inicial",
    "Hora Final",
    "Horas Trabajadas",
    "Observación",
]

# Mapeo: campo boleta → columna plantilla Maquinarias
MAPEO_MAQUINARIAS = {
    "numero_reporte": "N° Report",
    "fecha": "Fecha",
    "operador": "Operador",
    "obra": "Proveedor",
    "patente": "Patente",
    "camion": "Maquina",
    "hora_inicial": "Hora Inicial",
    "hora_final": "Hora Final",
    "horas_trabajadas": "Horas Trabajadas",
    "observaciones": "Observación",
}

# Parámetros OCR - optimizados para manuscrito
# gpu=False: GTX 750 Ti (sm_50) no compatible con PyTorch actual (requiere sm_70+)
OCR_CONFIG = {
    "languages": ["es", "en"],
    "gpu": False,
    "detail": 1,
    "paragraph": False,
    "min_confidence": 0.1,
    "width_ths": 0.7,
    # Preprocesamiento: raw | contraste | hibrido | binario | auto
    "preproc_mode": "raw",
    "preproc_try_modes": ["raw", "contraste", "hibrido", "binario"],
    # Etiquetas con OCR imperfecto
    "fuzzy_labels": True,
    "fuzzy_threshold": 0.78,
}
