"""Parsea docs/SOURCES.md y genera input/laws_manifest.json.

No inventa URLs ni fuentes: cuando SOURCES.md no da un dato verificado,
el campo correspondiente queda en null para que el operador lo complete.
"""

import json
import re
from urllib.parse import urlparse

from config import BASE_DIR, INPUT_DIR

SOURCES_PATH = BASE_DIR / "docs" / "SOURCES.md"
MANIFEST_PATH = INPUT_DIR / "laws_manifest.json"

FALLBACK_DOMAIN = "congreso.gob.gt"

# Alias de nombres cortos -> nombre de portal tal como aparece en la tabla
# "Portales ancla" de SOURCES.md. Solo normaliza identificadores; el dominio
# real siempre se extrae del documento, nunca se inventa aquí.
ANCHOR_ALIASES = {
    "CENADOJ": "CENADOJ (OJ)",
    "OJ": "CENADOJ (OJ)",
    "BANGUAT": "Banco de Guatemala",
    "BANCO DE GUATEMALA": "Banco de Guatemala",
    "SIB": "SIB",
    "SAT": "SAT",
    "CONTRALORÍA": "Contraloría GC",
    "CONTRALORIA": "Contraloría GC",
    "CONGRESO": "Congreso",
    "TSE": "TSE",
    "MINTRAB": "MINTRAB",
    "IDPP": "IDPP Biblioteca",
    "WIPO LEX": "WIPO Lex",
    "WIPO": "WIPO Lex",
    "OIT NORMLEX": "OIT NORMLEX",
    "NORMLEX": "OIT NORMLEX",
    "OAS": "OAS",
}


def _quitar_parentesis(texto: str) -> str:
    return re.sub(r"\s*\([^()]*\)", "", texto).strip()


def _parse_anchor_table(lineas: list[str]) -> dict[str, str]:
    """Extrae {nombre_portal: dominio} de la tabla '## Portales ancla'."""
    idx = next(i for i, l in enumerate(lineas) if l.strip().startswith("## Portales ancla"))
    dominios = {}
    for celdas in _extraer_tabla(lineas, idx)[1:]:
        if len(celdas) < 2:
            continue
        portal, url_base_celda = celdas[0], celdas[1]
        spans = re.findall(r"`([^`]+)`", url_base_celda)
        if not spans:
            continue
        dominio = spans[0].split("/")[0].strip()
        if dominio:
            dominios[portal] = dominio
    return dominios


def _extraer_tabla(lineas: list[str], inicio: int) -> list[list[str]]:
    """Recolecta filas (como listas de celdas) de la tabla markdown que
    empieza debajo de la línea `inicio` (se ignora la fila separadora ---)."""
    filas = []
    en_tabla = False
    for linea in lineas[inicio + 1 :]:
        l = linea.strip()
        if l.startswith("|"):
            en_tabla = True
            celdas = [c.strip() for c in l.strip("|").split("|")]
            if not all(re.fullmatch(r"-+", c) for c in celdas):
                filas.append(celdas)
        elif en_tabla:
            break
    return filas


def _parse_urls_verificadas(texto: str) -> dict[str, str]:
    seccion = re.search(r"URLs individuales ya verificadas:\n(.*?)\n\n", texto, re.DOTALL)
    if not seccion:
        return {}
    resultado = {}
    for linea in seccion.group(1).splitlines():
        m = re.match(r"-\s*(.+?):\s*`([^`]+)`", linea.strip())
        if m:
            nombre, url = m.groups()
            resultado[_quitar_parentesis(nombre).lower()] = url
    return resultado


def _buscar_url_verificada(ley_limpia: str, urls_verificadas: dict[str, str]) -> str | None:
    return urls_verificadas.get(ley_limpia.strip().lower())


def _limpiar_fuente_token(celda: str) -> str | None:
    texto = re.sub(r"`[^`]*`", "", celda)
    texto = re.split(r"[(⚠;—]|✔", texto)[0]
    texto = texto.split("/")[0]
    texto = texto.strip(" .")
    return texto or None


def _fuente_a_dominio(celda: str, url_conocida: str | None, dominios_portal: dict[str, str]) -> str | None:
    token = _limpiar_fuente_token(celda)
    if not token:
        return urlparse(url_conocida).netloc if url_conocida else None
    primera_palabra = token.split()[0] if token.split() else token
    portal = ANCHOR_ALIASES.get(token.upper()) or ANCHOR_ALIASES.get(primera_palabra.upper())
    if portal:
        return dominios_portal.get(portal, portal)
    return dominios_portal.get(token)


def _parse_flags(celda: str | None) -> list[str]:
    if celda is None:
        return []
    celda = celda.strip()
    if celda in ("—", "-", ""):
        return []
    return [f.strip().lower() for f in re.split(r"[,/]", celda) if f.strip() and f.strip() not in ("—", "-")]


def _construir_entrada(
    ley_cruda: str,
    batch: str,
    fuente_celda: str,
    flags_celda: str | None,
    urls_verificadas: dict[str, str],
    dominios_portal: dict[str, str],
) -> dict:
    ley = _quitar_parentesis(ley_cruda)
    url_conocida = _buscar_url_verificada(ley, urls_verificadas)
    fuente_primaria = _fuente_a_dominio(fuente_celda, url_conocida, dominios_portal)
    fuentes_fallback = [] if fuente_primaria == FALLBACK_DOMAIN else [FALLBACK_DOMAIN]
    return {
        "ley": ley,
        "batch": batch,
        "fuente_primaria": fuente_primaria,
        "url_conocida": url_conocida,
        "flags_esperados": _parse_flags(flags_celda),
        "fuentes_fallback": fuentes_fallback,
    }


def _dividir_leyes(parrafo: str) -> list[str]:
    nombres = []
    for crudo in re.split(r"\s*·\s*", parrafo):
        nombre = crudo.strip().strip(".").strip()
        if nombre:
            nombres.append(nombre)
    return nombres


def _procesar_batch_tabla(
    lineas: list[str],
    encabezado: str,
    batch: str,
    urls_verificadas: dict[str, str],
    dominios_portal: dict[str, str],
    leyes_en_celda: bool = False,
) -> list[dict]:
    idx = next(i for i, l in enumerate(lineas) if l.strip().startswith(encabezado))
    filas = _extraer_tabla(lineas, idx)[1:]  # quita la fila de encabezado de la tabla
    entradas = []
    for celdas in filas:
        if leyes_en_celda:
            _, fuente_celda, leyes_celda = celdas[0], celdas[1], celdas[2]
            for ley_cruda in _dividir_leyes(leyes_celda):
                entradas.append(
                    _construir_entrada(ley_cruda, batch, fuente_celda, None, urls_verificadas, dominios_portal)
                )
        else:
            ley_cruda, fuente_celda, flags_celda = celdas[0], celdas[1], celdas[2]
            entradas.append(
                _construir_entrada(ley_cruda, batch, fuente_celda, flags_celda, urls_verificadas, dominios_portal)
            )
    return entradas


def _extraer_seccion(texto: str, encabezado: str) -> str:
    patron = re.compile(rf"^{re.escape(encabezado)}.*?$\n(.*?)(?=^## |\Z)", re.DOTALL | re.MULTILINE)
    m = patron.search(texto)
    return m.group(1) if m else ""


def _extraer_fuente_primaria_prosa(seccion_texto: str) -> str | None:
    m = re.search(r"Fuente primaria:\s*([^.;]+)", seccion_texto)
    if not m:
        return None
    m2 = re.search(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]+", m.group(1))
    return m2.group(0) if m2 else None


def _extraer_parrafo_leyes(seccion_texto: str) -> str:
    parrafos = re.split(r"\n\s*\n", seccion_texto.strip())
    candidatos = [p for p in parrafos if "·" in p and not p.strip().startswith("⚠")]
    return " ".join(p.replace("\n", " ") for p in candidatos)


def _procesar_batch_prosa(
    texto: str,
    encabezado: str,
    batch: str,
    urls_verificadas: dict[str, str],
    dominios_portal: dict[str, str],
) -> list[dict]:
    seccion = _extraer_seccion(texto, encabezado)
    fuente_token = _extraer_fuente_primaria_prosa(seccion) or ""
    parrafo = _extraer_parrafo_leyes(seccion)
    return [
        _construir_entrada(ley_cruda, batch, fuente_token, None, urls_verificadas, dominios_portal)
        for ley_cruda in _dividir_leyes(parrafo)
    ]


def construir_manifest() -> list[dict]:
    texto = SOURCES_PATH.read_text(encoding="utf-8")
    lineas = texto.splitlines()

    urls_verificadas = _parse_urls_verificadas(texto)
    dominios_portal = _parse_anchor_table(lineas)

    entradas = []
    entradas += _procesar_batch_tabla(lineas, "## Batch 1A", "1A", urls_verificadas, dominios_portal)
    entradas += _procesar_batch_tabla(lineas, "## Batch 1B", "1B", urls_verificadas, dominios_portal)
    entradas += _procesar_batch_prosa(texto, "## Batch 2", "2", urls_verificadas, dominios_portal)
    entradas += _procesar_batch_prosa(texto, "## Batch 3", "3", urls_verificadas, dominios_portal)
    entradas += _procesar_batch_prosa(texto, "## Batch 4", "4", urls_verificadas, dominios_portal)
    entradas += _procesar_batch_tabla(
        lineas, "## Batch 5", "5", urls_verificadas, dominios_portal, leyes_en_celda=True
    )
    entradas += _procesar_batch_prosa(texto, "## Batch 6", "6", urls_verificadas, dominios_portal)
    return entradas


def main() -> None:
    entradas = construir_manifest()
    MANIFEST_PATH.write_text(json.dumps(entradas, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Leyes parseadas: {len(entradas)}")
    print(f"Manifiesto guardado en: {MANIFEST_PATH}")
    print("\nSample (3 entradas):")
    print(json.dumps(entradas[:3], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
