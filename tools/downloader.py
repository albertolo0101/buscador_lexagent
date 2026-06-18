"""Descarga final de un PDF validado, con naming convention y metadata."""

import json
import re
import unicodedata
from datetime import datetime, timezone

import httpx
from rich.console import Console

from config import CORPUS_DIR, HTTP_MAX_RETRIES, HTTP_TIMEOUT_SECONDS

console = Console()

# Busca patrones tipo "Decreto 106-1963", "Decreto Número 2-89", "Decreto-Ley 17-73"
_PATRON_DECRETO = re.compile(r"decreto[\w\s\-]*?(\d{1,4})\s*-\s*(\d{2,4})", re.IGNORECASE)


def _slugificar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    texto = texto.lower().strip()
    texto = re.sub(r"[^a-z0-9\s]", "", texto)
    texto = re.sub(r"\s+", "_", texto)
    return texto


def _construir_nombre_archivo(law_name: str, metadata: dict) -> str:
    numero = metadata.get("numero")
    anio = metadata.get("anio") or metadata.get("año")

    if not numero or not anio:
        match = _PATRON_DECRETO.search(law_name) or _PATRON_DECRETO.search(metadata.get("notas", ""))
        if match:
            numero, anio_corto = match.group(1), match.group(2)
            anio = f"19{anio_corto}" if len(anio_corto) == 2 and int(anio_corto) > 30 else (
                f"20{anio_corto}" if len(anio_corto) == 2 else anio_corto
            )

    nombre_corto = _slugificar(law_name)

    if numero and anio:
        return f"decreto_{numero}_{anio}_{nombre_corto}.pdf"
    return f"{nombre_corto}.pdf"


def download_law(url: str, law_name: str, metadata: dict, pdf_bytes: bytes | None = None) -> str | None:
    """Descarga el PDF final, lo guarda en CORPUS_DIR junto con su metadata JSON.

    Si pdf_bytes ya viene con contenido (por ejemplo, porque el evaluador ya
    lo descargó —incluso vía el fallback de Playwright—), se usa directo y
    no se hace ninguna request HTTP nueva. Si es None, descarga vía httpx
    como antes.

    metadata debe incluir al menos: fuente, confianza (de searcher) y
    opcionalmente tiene_texto, paginas (de evaluator).
    Retorna el path del PDF guardado, o None si la descarga falló.
    """
    if pdf_bytes is not None:
        console.log("[bold cyan][DOWNLOAD][/bold cyan] Usando bytes ya descargados (sin re-fetch)")
        contenido = pdf_bytes
    else:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; BuscadorLEX/1.0)"}
        contenido = None

        for intento in range(1, HTTP_MAX_RETRIES + 1):
            try:
                with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS, follow_redirects=True, headers=headers) as client:
                    resp = client.get(url)
                    resp.raise_for_status()
                    contenido = resp.content
                    break
            except httpx.HTTPError as e:
                console.log(f"[yellow][DOWNLOAD][/yellow] Intento {intento}/{HTTP_MAX_RETRIES} falló para {url}: {e}")

        if contenido is None:
            console.log(f"[bold red][DOWNLOAD][/bold red] No se pudo descargar el PDF final de {url}")
            return None

    nombre_archivo = _construir_nombre_archivo(law_name, metadata)
    ruta_pdf = CORPUS_DIR / nombre_archivo
    ruta_pdf.write_bytes(contenido)

    metadata_completa = {
        "ley": law_name,
        "url_fuente": url,
        "fecha_descarga": datetime.now(timezone.utc).isoformat(),
        "tiene_texto": metadata.get("tiene_texto"),
        "paginas": metadata.get("paginas"),
        "confianza_fuente": metadata.get("confianza"),
        "fuente": metadata.get("fuente"),
    }

    ruta_json = ruta_pdf.with_suffix(".json")
    ruta_json.write_text(json.dumps(metadata_completa, ensure_ascii=False, indent=2), encoding="utf-8")

    console.log(f"[bold green][DOWNLOAD][/bold green] Guardado: {ruta_pdf.name}")
    return str(ruta_pdf)
