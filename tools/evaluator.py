"""Descarga un PDF candidato a memoria y evalúa si tiene texto seleccionable."""

import io

import httpx
from pdfminer.high_level import extract_text
from pdfminer.pdfpage import PDFPage
from rich.console import Console

from config import HTTP_MAX_RETRIES, HTTP_TIMEOUT_SECONDS, MIN_PDF_SIZE_KB, MIN_TEXTO_CHARS

console = Console()


def _descargar_bytes(url: str) -> bytes | None:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; BuscadorLEX/1.0)"}
    for intento in range(1, HTTP_MAX_RETRIES + 1):
        try:
            with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS, follow_redirects=True, headers=headers) as client:
                resp = client.get(url)
                resp.raise_for_status()
                content_type = resp.headers.get("content-type", "")
                if "pdf" not in content_type and not url.lower().endswith(".pdf"):
                    console.log(f"[yellow][ACT][/yellow] URL no parece ser PDF (Content-Type: {content_type})")
                    return None
                return resp.content
        except httpx.HTTPError as e:
            console.log(f"[yellow][ACT][/yellow] Intento {intento}/{HTTP_MAX_RETRIES} falló para {url}: {e}")
    return None


def evaluate_pdf(url: str) -> dict:
    """Descarga el PDF en memoria y evalúa su calidad.

    Retorna: {url, tiene_texto, paginas, texto_muestra, tamaño_kb, valido}
    """
    resultado = {
        "url": url,
        "tiene_texto": False,
        "paginas": 0,
        "texto_muestra": "",
        "tamaño_kb": 0,
        "valido": False,
        "pdf_bytes": None,
    }

    console.log(f"[bold cyan][ACT][/bold cyan] Descargando candidato: {url}")
    contenido = _descargar_bytes(url)

    if contenido is None:
        console.log(f"[bold red][OBSERVE][/bold red] No se pudo descargar {url}")
        return resultado

    tamaño_kb = len(contenido) // 1024
    resultado["tamaño_kb"] = tamaño_kb

    if tamaño_kb < MIN_PDF_SIZE_KB:
        console.log(f"[bold red][OBSERVE][/bold red] PDF demasiado pequeño ({tamaño_kb}KB) en {url}")
        return resultado

    resultado["pdf_bytes"] = contenido

    try:
        texto = extract_text(io.BytesIO(contenido))
    except Exception as e:
        console.log(f"[bold red][OBSERVE][/bold red] No se pudo parsear PDF en {url}: {e}")
        return resultado

    texto = texto.strip()
    resultado["paginas"] = texto.count("\f") + 1 if texto else 0

    try:
        num_paginas = sum(1 for _ in PDFPage.get_pages(io.BytesIO(contenido)))
    except Exception:
        num_paginas = resultado["paginas"]  # fallback al método anterior
    resultado["paginas"] = num_paginas

    resultado["texto_muestra"] = texto[:300]
    resultado["tiene_texto"] = len(texto) >= MIN_TEXTO_CHARS
    resultado["valido"] = True

    if resultado["tiene_texto"]:
        console.log(f"[bold green][OBSERVE][/bold green] {url} tiene texto seleccionable ({len(texto)} chars, {resultado['paginas']} pag.)")
    else:
        console.log(f"[bold yellow][OBSERVE][/bold yellow] {url} parece ser PDF escaneado (sin texto seleccionable)")

    return resultado
