# Si algo sale mal – qué hacer

## Sale vacío (0 boletas exportadas)

1. **Revisar el log**: `output/transcripcion_live.log` – ahí se ve qué se transcribió.
2. **Probar sin deduplicación**: `python3 main.py --sin-deduplicacion --reprocesar`
3. **Imágenes dañadas o ilegibles**: Comprueba que las fotos estén nítidas y bien iluminadas.

## Transcribe con errores (typos, campos mal)

- **Corrección manual** en el Excel generado.
- Las columnas se pueden editar normalmente.
- La columna "Imagen Origen" permite cotejar con la imagen original.

## Lo interrumpiste (Ctrl+C)

- Desde la última versión, **se guarda lo ya transcrito**.
- Verás: `[Interrumpido] Guardadas N boletas en: output/...xlsx`
- No se pierden las boletas procesadas hasta ese momento.

## Errores en algunas imágenes

- Al final el script muestra: "Errores en X imagen(es)".
- Las que sí se transcribieron bien se exportan igualmente.
- Las que fallaron se listan en el log con `[ERROR]`.

## El Excel está en blanco o incompleto

- Ubicación: `transcripcion_boletas/output/Seguimiento_Maquinarias_YYYYMMDD_HHMMSS.xlsx`
- La hoja "SEGUIMIENTO MAQUINARIAS" es donde van los datos.
- Si no hay filas nuevas, es que no hubo boletas válidas (N° reporte, patente, operador, etc.).
