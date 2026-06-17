"""Orquestador principal de BuscadorLEX: loop think -> act -> observe."""

import sys

from rich.console import Console
from rich.table import Table

from config import LEYES_FILE, MAX_CANDIDATOS_POR_LEY
from tools.downloader import download_law
from tools.evaluator import evaluate_pdf
from tools.searcher import search_law

console = Console()


def _leer_leyes() -> list[str]:
    if not LEYES_FILE.exists():
        console.print(f"[bold red]No existe el archivo de entrada: {LEYES_FILE}[/bold red]")
        return []
    with open(LEYES_FILE, encoding="utf-8") as f:
        return [linea.strip() for linea in f if linea.strip()]


def procesar_ley(law_name: str) -> dict:
    """Ejecuta el ciclo think->act->observe para una sola ley.

    Retorna un dict con el resultado: {ley, estado, path, url}
    estado in {"descargada", "sin_texto", "pendiente"}
    """
    console.rule(f"[bold]{law_name}[/bold]")

    try:
        candidatos = search_law(law_name)
    except Exception as e:
        console.log(f"[bold red][THINK][/bold red] Error buscando '{law_name}': {e}")
        return {"ley": law_name, "estado": "pendiente", "path": None, "url": None}

    if not candidatos:
        return {"ley": law_name, "estado": "pendiente", "path": None, "url": None}

    mejor_sin_texto = None  # guarda el primer candidato descargable aunque no tenga texto

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
            metadata = {**candidato, **evaluacion}
            path = download_law(url, law_name, metadata)
            if path:
                return {"ley": law_name, "estado": "descargada", "path": path, "url": url}
            continue

        if mejor_sin_texto is None:
            mejor_sin_texto = (candidato, evaluacion)
        console.log(f"[OBSERVE] Sin texto seleccionable, probando el siguiente candidato: {url}")

    if mejor_sin_texto is not None:
        candidato, evaluacion = mejor_sin_texto
        url = candidato.get("url")
        metadata = {**candidato, **evaluacion}
        path = download_law(url, law_name, metadata)
        return {"ley": law_name, "estado": "sin_texto", "path": path, "url": url}

    return {"ley": law_name, "estado": "pendiente", "path": None, "url": None}


def generar_reporte(resultados: list[dict]) -> None:
    descargadas = [r for r in resultados if r["estado"] == "descargada"]
    sin_texto = [r for r in resultados if r["estado"] == "sin_texto"]
    pendientes = [r for r in resultados if r["estado"] == "pendiente"]

    console.rule("[bold]Reporte final[/bold]")

    tabla = Table(show_header=True, header_style="bold")
    tabla.add_column("Estado")
    tabla.add_column("Cantidad")
    tabla.add_column("Leyes")

    tabla.add_row("✅ Descargadas", str(len(descargadas)), ", ".join(r["ley"] for r in descargadas) or "-")
    tabla.add_row("⚠️ Sin texto (requieren OCR)", str(len(sin_texto)), ", ".join(r["ley"] for r in sin_texto) or "-")
    tabla.add_row("❌ No encontradas", str(len(pendientes)), ", ".join(r["ley"] for r in pendientes) or "-")

    console.print(tabla)


def main() -> None:
    leyes = _leer_leyes()
    if not leyes:
        console.print("[bold yellow]No hay leyes para procesar. Revisa input/leyes.txt[/bold yellow]")
        sys.exit(1)

    console.print(f"[bold]BuscadorLEX[/bold] — procesando {len(leyes)} ley(es)\n")

    resultados = []
    for law_name in leyes:
        resultado = procesar_ley(law_name)
        resultados.append(resultado)

    generar_reporte(resultados)


if __name__ == "__main__":
    main()
