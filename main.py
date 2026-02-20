#!/usr/bin/env python3
"""
Pipeline principal de transcripción de boletas.
Procesa imágenes de Imagenes/, aplica OCR manuscrito+imprenta,
deduplica y exporta a Excel según plantilla.
"""
import argparse
import sys
from pathlib import Path

# Asegurar que el directorio del script está en el path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from tqdm import tqdm

from config import IMAGENES_DIR, EXTENSIONES_IMAGEN, OUTPUT_DIR, MIN_CONFIANZA_BOLETA
from ocr_engine import transcribir_boleta, _inicializar_easyocr
from schema import BoletaTranscrita
from deduplicador import Deduplicador
from exportador_excel import exportar_a_excel


def listar_imagenes(directorio: Path) -> list[Path]:
    """Lista archivos de imagen válidos (excluyendo subcarpetas de WhatsApp)."""
    imagenes = []
    for ext in EXTENSIONES_IMAGEN:
        imagenes.extend(directorio.glob(f"*{ext}"))
    # Excluir carpeta de archivos adjuntos de WhatsApp
    imagenes = [p for p in imagenes if "WhatsApp_files" not in str(p)]
    return sorted(imagenes)


def ejecutar_pipeline(
    imagenes_dir: Path = IMAGENES_DIR,
    filtrar_duplicados: bool = True,
    limpiar_registro: bool = False,
    verbose: bool = False,
    modo_preproc: str | None = None,
) -> list[BoletaTranscrita]:
    """
    Ejecuta el pipeline completo:
    1. Lista imágenes
    2. Inicializa OCR
    3. Transcribe cada imagen
    4. Deduplica
    5. Retorna boletas válidas
    """
    imagenes = listar_imagenes(imagenes_dir)
    if not imagenes:
        print(f"No se encontraron imágenes en {imagenes_dir}")
        return []
    
    print(f"Encontradas {len(imagenes)} imágenes de boletas.")
    from config import OCR_CONFIG
    gpu = OCR_CONFIG.get("gpu", False)
    print(f"Motor OCR: {'GPU' if gpu else 'CPU'} (gpu={gpu})")
    print("Inicializando motor OCR (puede tardar ~30 s la primera vez)...")
    reader = _inicializar_easyocr()
    
    dedup = Deduplicador()
    if limpiar_registro:
        dedup.limpiar_registro()
        print("Registro de deduplicación limpiado.")
    
    boletas: list[BoletaTranscrita] = []
    global _boletas_parciales
    _boletas_parciales = boletas
    errores = []
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    log_file = OUTPUT_DIR / "transcripcion_live.log"
    log_file.write_text("", encoding="utf-8")  # Limpiar para nueva ejecución
    
    pbar = tqdm(imagenes, desc="Transcribiendo")
    for ruta in pbar:
        try:
            b = transcribir_boleta(ruta, reader=reader, modo_preproc=modo_preproc)
            b.imagen_origen = ruta.name
            es_valida = b.es_valida()
            if es_valida and b.confianza_promedio >= MIN_CONFIANZA_BOLETA:
                boletas.append(b)
                info = f"Tipo:{b.tipo_boleta or '-'} | N°{b.numero_reporte or '-'} | Patente:{b.patente or '-'} | Operador:{b.operador or '-'} | Camion:{b.camion or '-'} | Conf:{b.confianza_promedio:.2f}"
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(f"[{ruta.name}] → {info}\n")
                if verbose:
                    tqdm.write(f"  [{ruta.name[:35]}...] → {info}")
            else:
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(
                        f"[DESCARTADA {ruta.name}] valida={es_valida} conf={b.confianza_promedio:.2f} tipo={b.tipo_boleta or '-'}\n"
                    )
        except Exception as e:
            errores.append((ruta.name, str(e)))
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"[ERROR {ruta.name}] {e}\n")
            if verbose:
                tqdm.write(f"  [ERROR] {ruta.name}: {e}")
    
    if errores:
        print(f"\nErrores en {len(errores)} imagen(es):")
        for nombre, msg in errores[:5]:
            print(f"  - {nombre}: {msg}")
        if len(errores) > 5:
            print(f"  ... y {len(errores) - 5} más.")
    
    if filtrar_duplicados and boletas:
        antes = len(boletas)
        boletas = dedup.filtrar_duplicados(boletas, registrar_nuevas=True)
        duplicados = antes - len(boletas)
        if duplicados > 0:
            print(f"Eliminados {duplicados} duplicado(s).")
    
    return boletas


def main():
    parser = argparse.ArgumentParser(
        description="Transcripción de boletas (manuscrito + imprenta) a Excel"
    )
    parser.add_argument(
        "--imagenes",
        type=Path,
        default=IMAGENES_DIR,
        help="Directorio con imágenes de boletas",
    )
    parser.add_argument(
        "--sin-deduplicacion",
        action="store_true",
        help="No filtrar duplicados",
    )
    parser.add_argument(
        "--reprocesar",
        action="store_true",
        help="Limpiar registro y reprocesar todo",
    )
    parser.add_argument(
        "--solo-probar",
        type=int,
        metavar="N",
        help="Procesar solo las primeras N imágenes (prueba)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Mostrar lo transcrito en consola mientras corre",
    )
    parser.add_argument(
        "--preproc",
        type=str,
        default=None,
        choices=["raw", "contraste", "hibrido", "binario", "auto"],
        help="Modo de preprocesamiento para OCR (sobrescribe config)",
    )
    args = parser.parse_args()
    
    imagenes = listar_imagenes(args.imagenes)
    if not imagenes:
        print(f"No hay imágenes en {args.imagenes}")
        return
    
    tmpdir = None
    if args.solo_probar:
        imagenes = imagenes[: args.solo_probar]
        import tempfile
        import shutil
        tmpdir = Path(tempfile.mkdtemp())
        for p in imagenes:
            shutil.copy(p, tmpdir / p.name)
        imagenes_dir = tmpdir
    else:
        imagenes_dir = args.imagenes
    
    boletas = ejecutar_pipeline(
        imagenes_dir=imagenes_dir,
        filtrar_duplicados=not args.sin_deduplicacion,
        limpiar_registro=args.reprocesar,
        verbose=args.verbose,
        modo_preproc=args.preproc,
    )
    
    if not boletas:
        print("No se obtuvieron boletas válidas para exportar.")
        print("  → Revisa output/transcripcion_live.log para ver qué se leyó")
        print("  → Prueba: python3 main.py --sin-deduplicacion --reprocesar")
        return
    
    ruta_excel = exportar_a_excel(boletas)
    print(f"\nExportadas {len(boletas)} boletas a: {ruta_excel}")
    
    if tmpdir and tmpdir.exists():
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    main()
