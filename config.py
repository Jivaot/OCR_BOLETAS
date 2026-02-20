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
    "numero_reporte": ["N°", "Nº", "N.", "N° Report", "N° REPORT"],
    "camion": ["Camión:", "Camion:", "Maquinaria:", "Servicio:", "Equipo:"],
    "patente": ["Patente:", "PATENTE"],
    "operador": ["Operador:", "Operario:", "Nombre y Firma Operador"],
    "obra": ["Obra:", "Empresa:", "Proveedor:", "Faena:"],
    "tipo_faena": ["Tipo de Faena:", "Tipo Faena:", "Actividad desarrollada:", "Rol Camino"],
    "horarios": ["Horarios:", "Mañana", "Tarde", "Inicial", "Final"],
    "observaciones": ["Observaciones:", "OBSERVACIONES"],
}

# Hojas de la plantilla - nombres exactos del documento Excel
HOJA_MAQUINARIAS = "SEGUIMIENTO MAQUINARIAS"
HOJA_ARIDOS = "SEGUIMIENTO_ARIDOS"
HOJA_MOV_TIERRA = "SEGUIMIENTO_MOV. TIERRA"

# Tipos de boleta (clasificación por encabezado OCR)
TIPO_MAQUINARIA = "maquinaria"
TIPO_ARIDOS = "aridos"
TIPO_MOV_TIERRA = "mov_tierra"
TIPO_DESCONOCIDO = "desconocido"

BOLETA_TIPO_HOJA = {
    TIPO_MAQUINARIA: HOJA_MAQUINARIAS,
    TIPO_ARIDOS: HOJA_ARIDOS,
    TIPO_MOV_TIERRA: HOJA_MOV_TIERRA,
}

# Palabras clave para detectar el formato de boleta.
# Se evalúan sobre texto OCR normalizado (sin acentos, minúsculas).
BOLETA_TIPO_KEYWORDS = {
    TIPO_MAQUINARIA: [
        "reporte diario",
        "agroindustrial",
        "transporte y arriendo",
        "horas minimas",
    ],
    TIPO_ARIDOS: [
        "aridos",
        "carga",
        "camion tolva",
        "m3",
    ],
    TIPO_MOV_TIERRA: [
        "asfaltos del maule",
        "reporte diario de maquinaria",
        "actividad desarrollada",
        "rol camino",
    ],
}

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
    "preproc_mode": "auto",
    "preproc_try_modes": ["raw", "contraste", "hibrido", "binario"],
    # Rotaciones a probar para robustez en fotos invertidas
    "ocr_rotations": [0, 180],
    # Etiquetas con OCR imperfecto
    "fuzzy_labels": True,
    "fuzzy_threshold": 0.78,
}

# Umbral mínimo para registrar una boleta en salida
MIN_CONFIANZA_BOLETA = 0.20
