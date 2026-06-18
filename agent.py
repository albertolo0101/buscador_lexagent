"""Orquestador principal de BuscadorLEX: loop think -> act -> observe, por batch."""

import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

import argparse
import json
from datetime import datetime, timezone

from rich.console import Console
from rich.table import Table

from config import LAWS_MANIFEST_FILE, LOGS_DIR, MAX_CANDIDATOS_POR_LEY
from tools.downloader import download_law
from tools.evaluator import evaluate_pdf
from tools.searcher import search_law

console = Console()


def _leer_manifest() -> dict[str, list[dict]]:
    if not LAWS_MANIFEST_FILE.exists():
        console.print(f"[bold red]No existe el manifiesto: {LAWS_MANIFEST_FILE}[/bold red]")
        return {}

    with open(LAWS_MANIFEST_FILE, encoding="utf-8") as f:
        entradas = json.load(f)

    por_batch: dict[str, list[dict]] = {}
    for entrada in entradas:
        por_batch.setdefault(entrada["batch"], []).append(entrada)

    return {batch: por_batch[batch] for batch in sorted(por_batch)}


def _preguntar_sn(pregunta: str) -> bool:
    respuesta = input(f"{pregunta} ").strip().lower()
    return respuesta in ("s", "si", "sí", "y", "yes")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="BuscadorLEX — agente de adquisición de leyes guatemaltecas")
    parser.add_argument("--batch", help="Procesa solo el batch indicado (ej. 1B)")
    parser.add_argument("--ley", help="Procesa solo la ley indicada dentro del batch (requiere --batch)")
    return parser.parse_args()


def _filtrar_por_ley(entradas: list[dict], nombre_ley: str) -> list[dict]:
    return [e for e in entradas if e["ley"].strip().lower() == nombre_ley.strip().lower()]


def procesar_ley(entrada: dict) -> dict:
    """Ejecuta el ciclo think->act->observe para una sola ley del manifiesto.

    Fase 1: intenta la url_conocida del manifiesto, si existe.
    Fase 2: cae a búsqueda web (search_law) si no había url_conocida, o si
    esta falló / resultó comentada / resultó compilación.

    Retorna la entrada original del manifiesto extendida con:
    {estado, path, url}. estado in {"descargada", "sin_texto", "pendiente"}
    """
    law_name = entrada["ley"]
    console.rule(f"[bold]{law_name}[/bold]")

    url_conocida = entrada.get("url_conocida")
    if url_conocida:
        console.log("[bold cyan][THINK][/bold cyan] Fase 1 — intentando URL conocida del manifiesto")
        console.log("[THINK] URL conocida en manifiesto, intentando fase 1...")

        try:
            evaluacion = evaluate_pdf(url_conocida)
        except Exception as e:
            console.log(f"[bold red][ACT][/bold red] Error evaluando URL conocida {url_conocida}: {e}")
            evaluacion = {"valido": False}

        if evaluacion["valido"] and evaluacion["tiene_texto"]:
            if evaluacion["es_comentada"]:
                console.log("[OBSERVE] URL conocida es comentada, pasando a fase 2")
            elif evaluacion["es_compilacion"]:
                console.log("[OBSERVE] URL conocida es compilación, pasando a fase 2")
            else:
                metadata = {**entrada, **evaluacion}
                path = download_law(url_conocida, law_name, metadata, pdf_bytes=evaluacion.get("pdf_bytes"))
                if path:
                    return {**entrada, "estado": "descargada", "path": path, "url": url_conocida, "razon": None}
                console.log("[OBSERVE] No se pudo guardar la URL conocida, pasando a fase 2")
        else:
            console.log("[OBSERVE] URL conocida falló (sin texto o inválida), pasando a fase 2")

    console.log("[bold cyan][THINK][/bold cyan] Fase 2 — buscando con web search")

    try:
        candidatos = search_law(law_name)
    except Exception as e:
        console.log(f"[bold red][THINK][/bold red] Error buscando '{law_name}': {e}")
        return {**entrada, "estado": "pendiente", "path": None, "url": None, "razon": None}

    if not candidatos:
        return {**entrada, "estado": "pendiente", "path": None, "url": None, "razon": None}

    mejor_sin_texto = None  # guarda el primer candidato descargable aunque no tenga texto
    hubo_rechazo_comentada = False
    hubo_rechazo_compilacion = False

    for candidato in candidatos[:MAX_CANDIDATOS_POR_LEY]:
        url = candidato.get("url")
        if not url:
            continue

        try:
            evaluacion = evaluate_pdf(url)
        except Exception as e:
            console.log(f"[bold red][ACT][/bold red] Error evaluando {url}: {e}")
            continue

        if not evaluacion["valido"]:
            console.log(f"[OBSERVE] Candidato inválido, probando el siguiente: {url}")
            continue

        if evaluacion["tiene_texto"]:
            if evaluacion["es_comentada"]:
                hubo_rechazo_comentada = True
                console.log("[OBSERVE] Rechazando por edición comentada, probando siguiente candidato")
                continue

            if evaluacion["es_compilacion"]:
                hubo_rechazo_compilacion = True
                console.log("[OBSERVE] Rechazando por compilación, probando siguiente candidato")
                continue

            metadata = {**candidato, **evaluacion}
            path = download_law(url, law_name, metadata, pdf_bytes=evaluacion.get("pdf_bytes"))
            if path:
                return {**entrada, "estado": "descargada", "path": path, "url": url, "razon": None}
            continue

        if mejor_sin_texto is None:
            mejor_sin_texto = (candidato, evaluacion)
        console.log(f"[OBSERVE] Sin texto seleccionable, probando el siguiente candidato: {url}")

    if mejor_sin_texto is not None:
        candidato, evaluacion = mejor_sin_texto
        url = candidato.get("url")
        metadata = {**candidato, **evaluacion}
        path = download_law(url, law_name, metadata, pdf_bytes=evaluacion.get("pdf_bytes"))
        return {**entrada, "estado": "sin_texto", "path": path, "url": url, "razon": None}

    razon = None
    if hubo_rechazo_comentada and hubo_rechazo_compilacion:
        razon = "comentada_y_compilacion"
    elif hubo_rechazo_comentada:
        razon = "solo_fuentes_comentadas"
    elif hubo_rechazo_compilacion:
        razon = "solo_compilaciones"

    return {**entrada, "estado": "pendiente", "path": None, "url": None, "razon": razon}


def generar_reporte(resultados: list[dict], titulo: str = "Reporte") -> None:
    descargadas = [r for r in resultados if r["estado"] == "descargada"]
    sin_texto = [r for r in resultados if r["estado"] == "sin_texto"]
    pendientes = [r for r in resultados if r["estado"] == "pendiente"]

    console.rule(f"[bold]{titulo}[/bold]")

    tabla = Table(show_header=True, header_style="bold")
    tabla.add_column("Estado")
    tabla.add_column("Cantidad")
    tabla.add_column("Leyes")

    tabla.add_row("Descargadas", str(len(descargadas)), ", ".join(r["ley"] for r in descargadas) or "-")
    tabla.add_row("Sin texto (requieren OCR)", str(len(sin_texto)), ", ".join(r["ley"] for r in sin_texto) or "-")
    tabla.add_row("No encontradas", str(len(pendientes)), ", ".join(r["ley"] for r in pendientes) or "-")

    console.print(tabla)


def _guardar_reporte_batch(batch: str, resultados: list[dict]) -> None:
    reporte = {
        "batch": batch,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total": len(resultados),
        "descargadas": [r for r in resultados if r["estado"] == "descargada"],
        "sin_texto": [r for r in resultados if r["estado"] == "sin_texto"],
        "pendientes": [r for r in resultados if r["estado"] == "pendiente"],
    }

    timestamp_archivo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    ruta = LOGS_DIR / f"reporte_batch_{batch}_{timestamp_archivo}.json"
    ruta.write_text(json.dumps(reporte, ensure_ascii=False, indent=2), encoding="utf-8")
    console.log(f"[bold green]Reporte de batch guardado:[/bold green] {ruta}")


def _procesar_batch(batch: str, entradas: list[dict]) -> list[dict]:
    console.print(f"\n[bold]Procesando batch {batch}[/bold] — {len(entradas)} ley(es)\n")

    resultados = [procesar_ley(entrada) for entrada in entradas]

    generar_reporte(resultados, titulo=f"Reporte batch {batch}")
    _guardar_reporte_batch(batch, resultados)

    return resultados


def main() -> None:
    args = _parse_args()
    manifest = _leer_manifest()

    if not manifest:
        console.print("[bold yellow]No hay leyes para procesar. Revisa input/laws_manifest.json[/bold yellow]")
        sys.exit(1)

    console.print("[bold]BuscadorLEX[/bold]\n")

    resultados_totales: list[dict] = []

    if args.batch:
        if args.batch not in manifest:
            disponibles = ", ".join(manifest.keys())
            console.print(f"[bold red]Batch '{args.batch}' no existe. Disponibles: {disponibles}[/bold red]")
            sys.exit(1)

        entradas = manifest[args.batch]
        if args.ley:
            entradas = _filtrar_por_ley(entradas, args.ley)
            if not entradas:
                console.print(f"[bold red]No se encontró la ley '{args.ley}' en el batch {args.batch}.[/bold red]")
                sys.exit(1)

        resultados_totales = _procesar_batch(args.batch, entradas)
        generar_reporte(resultados_totales, titulo="Resumen acumulado")
        return

    console.print("[bold]Batches disponibles:[/bold]")
    for batch, entradas in manifest.items():
        console.print(f"  {batch}: {len(entradas)} ley(es)")

    if not _preguntar_sn("\n¿Procesar todos los batches en secuencia? [s/N]"):
        batch_elegido = input("¿Qué batch quieres correr? ").strip()
        if batch_elegido not in manifest:
            console.print(f"[bold red]Batch '{batch_elegido}' no existe.[/bold red]")
            sys.exit(1)
        resultados_totales = _procesar_batch(batch_elegido, manifest[batch_elegido])
        generar_reporte(resultados_totales, titulo="Resumen acumulado")
        return

    batches = list(manifest.keys())
    for i, batch in enumerate(batches):
        resultados_totales += _procesar_batch(batch, manifest[batch])

        es_ultimo = i == len(batches) - 1
        if not es_ultimo:
            siguiente = batches[i + 1]
            if not _preguntar_sn(f"\n¿Continuar con batch {siguiente}? [s/N]"):
                console.print("[bold yellow]Ejecución interrumpida por el usuario.[/bold yellow]")
                break

    generar_reporte(resultados_totales, titulo="Resumen acumulado")


if __name__ == "__main__":
    main()
