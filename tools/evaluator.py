"""Descarga un PDF candidato a memoria y evalúa si tiene texto seleccionable."""

import io
import re
from pathlib import Path

import httpx
from pdfminer.high_level import extract_text
from pdfminer.pdfpage import PDFPage
from rich.console import Console

from config import (
    COMENTADA_THRESHOLD,
    COMPILACION_MIN_DECRETOS,
    HTTP_MAX_RETRIES,
    HTTP_TIMEOUT_SECONDS,
    MIN_PDF_SIZE_KB,
    MIN_TEXTO_CHARS,
    PLAYWRIGHT_ENABLED,
    PLAYWRIGHT_TIMEOUT_MS,
)

_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

console = Console()

# --- Marcadores de jurisprudencia (ediciones "comentadas") ---
PATRON_GACETA = re.compile(r"Gaceta\s+No\.?\s*\d+", re.IGNORECASE)
PATRON_CC = re.compile(r"Corte\s+de\s+Constitucionalidad", re.IGNORECASE)
PATRON_EXPEDIENTE = re.compile(r"expediente\s+(?:n[uú]mero\s+|no\.?\s*)?\d+", re.IGNORECASE)
PATRON_APELACION_AMPARO = re.compile(r"apelaci[oó]n\s+de\s+sentencia\s+de\s+amparo", re.IGNORECASE)
PATRON_INCONSTITUCIONALIDAD = re.compile(r"inconstitucionalidad", re.IGNORECASE)

# --- Encabezados de decreto (para detectar compilaciones multi-ley) ---
# Sin re.IGNORECASE a propósito: en los PDFs de CENADOJ el encabezado que
# realmente abre un decreto nuevo aparece en mayúsculas ("DECRETO NÚMERO
# X-Y") y va seguido, a poca distancia, del preámbulo de promulgación
# ("EL CONGRESO DE LA REPÚBLICA..."). Las referencias cruzadas dentro del
# cuerpo del texto (derogaciones, reformas a otras leyes) citan el decreto
# en mayúscula/minúscula ("Decreto Número X-Y del Congreso de la
# República...") y nunca van seguidas de ese preámbulo — confirmado contra
# Código Penal y Código Procesal Penal individuales (que citan 10+ decretos
# ajenos sin ser compilaciones) vs. la Compilación de Leyes Penales real
# (~20 encabezados genuinos). Ver tools/test_detector.py.
PATRON_DECRETO_COMPILACION = re.compile(
    r"DECRETO\s+(?:N[ÚU]MERO|No\.?|DEL\s+CONGRESO(?:\s+DE\s+LA\s+REP[ÚU]BLICA)?)\s*[:\-]?\s*(\d{1,4}-\d{2,4})"
    r"[\s\S]{0,200}?\bEL\s+CONGRESO\s+DE\s+LA\s+REP[ÚU]BLICA\b"
)


def _contar_marcadores_comentada(texto: str) -> int:
    # "Corte de Constitucionalidad" e "inconstitucionalidad" se probaron y se
    # excluyeron del conteo: son vocabulario sustantivo normal en leyes que
    # regulan la propia CC/amparo (Ley de Amparo, Constitución Política), no
    # jurisprudencia citada, y producían falsos positivos. "expediente N°" sí
    # separa con margen >2x entre ediciones limpias y comentadas (ver
    # tools/test_detector.py).
    return (
        len(PATRON_GACETA.findall(texto))
        + len(PATRON_EXPEDIENTE.findall(texto))
        + len(PATRON_APELACION_AMPARO.findall(texto))
    )


def _es_comentada(texto: str, paginas: int) -> bool:
    """Detecta ediciones comentadas por densidad de marcadores de jurisprudencia CC."""
    if paginas <= 0:
        return False
    marcadores_por_pagina = _contar_marcadores_comentada(texto) / paginas
    return marcadores_por_pagina >= COMENTADA_THRESHOLD


def _es_compilacion(texto: str) -> bool:
    """Detecta si el PDF contiene varios decretos (leyes) distintos."""
    decretos = set(PATRON_DECRETO_COMPILACION.findall(texto))
    return len(decretos) >= COMPILACION_MIN_DECRETOS


def _descargar_bytes_playwright(url: str) -> bytes | None:
    """Descarga el PDF con un navegador real, para portales que bloquean
    httpx (403) pero permiten navegadores reales."""
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright

    pdf_bytes = None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent=_BROWSER_USER_AGENT, accept_downloads=True)
            page = context.new_page()

            def handle_response(response):
                nonlocal pdf_bytes
                if pdf_bytes is None and "pdf" in response.headers.get("content-type", ""):
                    try:
                        pdf_bytes = response.body()
                    except Exception:
                        pass  # el recurso puede no estar disponible si Chromium lo tomó como descarga

            page.on("response", handle_response)

            try:
                # Chromium headless trata la navegación directa a una URL de
                # PDF como una descarga, no como una página: page.goto()
                # lanza "Download is starting" en cuanto el navegador decide
                # descargar en vez de renderizar. Ese error hay que tragarlo
                # DENTRO del bloque "with" para que expect_download() pueda
                # seguir esperando el evento de descarga en su __exit__; si
                # se deja escapar, aborta el "with" entero y nunca se llega
                # a leer download_info.value.
                with page.expect_download(timeout=PLAYWRIGHT_TIMEOUT_MS) as download_info:
                    try:
                        page.goto(url, timeout=PLAYWRIGHT_TIMEOUT_MS)
                    except Exception:
                        pass
                ruta_temp = download_info.value.path()
                if ruta_temp:
                    pdf_bytes = Path(ruta_temp).read_bytes()
            except PlaywrightTimeoutError:
                pass  # no se disparó descarga; pudo haberse capturado vía el handler de respuestas
            except Exception as e:
                console.log(f"[yellow][ACT][/yellow] Playwright: error navegando a {url}: {e}")

            if pdf_bytes is None and url.lower().endswith(".pdf"):
                cookies = context.cookies()
                cookie_header = "; ".join(f"{c['name']}={c['value']}" for c in cookies)
                try:
                    resp = httpx.get(
                        url,
                        headers={"User-Agent": _BROWSER_USER_AGENT, "Cookie": cookie_header},
                        timeout=HTTP_TIMEOUT_SECONDS,
                        follow_redirects=True,
                    )
                    if resp.status_code == 200:
                        pdf_bytes = resp.content
                except Exception:
                    pass

            browser.close()
    except Exception as e:
        console.log(f"[bold red][ACT][/bold red] Playwright falló para {url}: {e}")
        return None

    return pdf_bytes


def _descargar_bytes(url: str) -> tuple[bytes | None, bool]:
    """Descarga bytes vía httpx; si TODOS los reintentos fallan con 403
    (no por timeout/SSL/otros códigos), intenta el fallback con Playwright.

    Retorna (contenido, via_playwright).
    """
    headers = {"User-Agent": "Mozilla/5.0 (compatible; BuscadorLEX/1.0)"}
    ultimos_errores: list[httpx.HTTPStatusError | None] = []

    for intento in range(1, HTTP_MAX_RETRIES + 1):
        try:
            with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS, follow_redirects=True, headers=headers) as client:
                resp = client.get(url)
                resp.raise_for_status()
                content_type = resp.headers.get("content-type", "")
                if "pdf" not in content_type and not url.lower().endswith(".pdf"):
                    console.log(f"[yellow][ACT][/yellow] URL no parece ser PDF (Content-Type: {content_type})")
                    return None, False
                return resp.content, False
        except httpx.HTTPStatusError as e:
            ultimos_errores.append(e)
            console.log(f"[yellow][ACT][/yellow] Intento {intento}/{HTTP_MAX_RETRIES} falló para {url}: {e}")
        except httpx.HTTPError as e:
            ultimos_errores.append(None)
            console.log(f"[yellow][ACT][/yellow] Intento {intento}/{HTTP_MAX_RETRIES} falló para {url}: {e}")

    todos_fueron_403 = bool(ultimos_errores) and all(
        e is not None and e.response.status_code == 403 for e in ultimos_errores
    )

    if todos_fueron_403 and PLAYWRIGHT_ENABLED:
        console.log(f"[yellow][ACT][/yellow] 403 detectado, intentando con Playwright: {url}")
        contenido = _descargar_bytes_playwright(url)
        if contenido:
            console.log(f"[green][ACT][/green] Playwright rescató el PDF: {url}")
            return contenido, True

    return None, False


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
        "es_comentada": False,
        "es_compilacion": False,
        "via_playwright": False,
    }

    console.log(f"[bold cyan][ACT][/bold cyan] Descargando candidato: {url}")
    contenido, via_playwright = _descargar_bytes(url)
    resultado["via_playwright"] = via_playwright

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
        resultado["es_comentada"] = _es_comentada(texto, resultado["paginas"])
        resultado["es_compilacion"] = _es_compilacion(texto)

        if resultado["es_comentada"]:
            console.log("[bold red][OBSERVE][/bold red] PDF detectado como edición COMENTADA — contiene jurisprudencia CC")
        if resultado["es_compilacion"]:
            console.log("[bold red][OBSERVE][/bold red] PDF detectado como COMPILACIÓN — contiene múltiples decretos")

        console.log(f"[bold green][OBSERVE][/bold green] {url} tiene texto seleccionable ({len(texto)} chars, {resultado['paginas']} pag.)")
    else:
        console.log(f"[bold yellow][OBSERVE][/bold yellow] {url} parece ser PDF escaneado (sin texto seleccionable)")

    return resultado
