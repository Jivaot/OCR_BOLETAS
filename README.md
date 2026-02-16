# Sistema de Transcripción de Boletas

Transcripción automática de boletas (Reportes Diarios) con soporte para **texto manuscrito e imprenta**, pensado para las ~80 imágenes en la carpeta `Imagenes/`.

## Características

- **OCR manuscrito + imprenta**: Usa EasyOCR con preprocesamiento para mejorar precisión en letra manuscrita.
- **Plantilla definida**: Campos extraídos: Fecha, N° Reporte, Camión, Patente, Operador, Obra, Tipo de Faena, Horarios, Observaciones.
- **Deduplicación**: Evita repetición de datos usando N° reporte + fecha + patente como clave única.
- **Exportación Excel**: Alineada con la plantilla de seguimiento maquinaria/áridos/movimientos tierra.

## Instalación

### Si pip no está instalado (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install python3-pip
```

### Instalar dependencias

```bash
cd transcripcion_boletas
pip3 install -r requirements.txt
```

O con entorno virtual (recomendado):

```bash
python3 -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Uso

### Procesar todas las imágenes

```bash
python main.py
```

### Probar con pocas imágenes primero

```bash
python main.py --solo-probar 3
```

### Probar distintos preprocesamientos

```bash
python main.py --preproc auto
```

### Reprocesar desde cero (ignorar registro de duplicados)

```bash
python main.py --reprocesar
```

### Sin deduplicación

```bash
python main.py --sin-deduplicacion
```

### Validar qué boletas faltan transcribir

Si ya tienes la mayoría transcrita en la plantilla y quieres saber cuáles faltan:

```bash
# Analizar imágenes vs plantilla (muestra transcritas vs faltantes)
python validar_boletas.py

# Renombrar imágenes a reporte_NUMERO.ext
python validar_boletas.py --renombrar

# Guardar lista de faltantes en archivo
python validar_boletas.py --exportar-faltantes output/faltantes.txt

# Imágenes en otra carpeta
python validar_boletas.py --imagenes /ruta/a/mis/imagenes
```

Coloca las imágenes en `boletas/Imagenes/` antes de ejecutar.

## Estructura

```
transcripcion_boletas/
├── config.py          # Rutas, columnas, etiquetas
├── schema.py          # BoletaTranscrita (dataclass)
├── preprocesador.py   # Mejora de imágenes para OCR
├── ocr_engine.py      # Motor OCR y asociación por etiquetas
├── deduplicador.py    # Evitar repetición de datos
├── exportador_excel.py# Exportar según plantilla
├── main.py            # Pipeline principal
├── validar_boletas.py # Valida transcritas vs faltantes, renombra imágenes
├── requirements.txt
├── output/            # Excel generados
└── transcripciones_registro.json  # Registro de duplicados
```

## Mejorar precisión en manuscritos

1. **Iluminación**: Imágenes bien iluminadas y sin sombras.
2. **Enfoque**: Evitar fotos borrosas.
3. **Perspectiva**: Tomar la foto perpendicular al documento.
4. **Calidad**: Resolución mínima ~1000px en el lado largo.

Para mayor precisión en manuscritos difíciles, se puede integrar **Google Document AI** o **Azure Form Recognizer** (requieren API keys) reemplazando el motor en `ocr_engine.py`.
