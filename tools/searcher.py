"""Busca leyes guatemaltecas usando Claude API con la herramienta de búsqueda web."""

import json
import os
import re

from anthropic import Anthropic
from rich.console import Console

from config import ANTHROPIC_MODEL, MAX_TOKENS_SEARCH

console = Console()

SYSTEM_PROMPT = """Eres un experto en legislación guatemalteca con conocimiento profundo del sistema jurídico del país.

Tu tarea es encontrar la mejor fuente disponible para descargar una ley guatemalteca en PDF con texto seleccionable (no escaneado).

## Contexto del sistema legal guatemalteco

Las leyes en Guatemala se publican como Decretos del Congreso (ej. "Decreto 106-63") y frecuentemente son reformadas por decretos posteriores. Existen dos tipos de documentos:
- Decreto original: el texto tal como fue aprobado, sin reformas integradas
- Versión consolidada: el texto actualizado con todas las reformas ya incorporadas

SIEMPRE preferir la versión consolidada si existe.

## Jerarquía de fuentes (de mayor a menor confiabilidad)

1. congreso.gob.gt — decretos originales, autoritativos pero sin reformas integradas
2. Ministerios sectoriales (.gob.gt) — versiones consolidadas de leyes de su ramo:
   - minfin.gob.gt → leyes tributarias y fiscales
   - minem.gob.gt → ley de minería, electricidad, hidrocarburos
   - mintrabajo.gob.gt → Código de Trabajo
   - mingob.gob.gt → leyes de seguridad y gobernación
   - mspas.gob.gt → leyes de salud
3. oj.gob.gt — Organismo Judicial, buena fuente para códigos procesales
4. legis.gt — compilador privado pero de alta calidad editorial, versiones consolidadas
5. Universidades guatemaltecas (url.edu.gt, usac.edu.gt) — fuentes aceptables
6. Otros sitios institucionales centroamericanos

## Lo que debes buscar

Al buscar una ley, intenta determinar:
- Su número de decreto (ej. Código Civil = Decreto 106-63)
- Si existen versiones consolidadas disponibles
- La fecha de la reforma más reciente que puedas identificar

## Señales de un PDF de calidad

- Descarga directa (.pdf en la URL)
- Fuente .gob.gt o institucional reconocida
- El título menciona "consolidado", "actualizado" o incluye año reciente
- Tamaño razonable (un código completo pesa entre 500KB y 5MB)

## Señales de un PDF problemático

- Proviene de blogs jurídicos sin identificación institucional
- URL de Google Drive o Dropbox sin origen claro
- Título sin número de decreto identificable
- Sitios que requieren login o pago

## Formato de respuesta

Devuelve ÚNICAMENTE un array JSON válido, sin texto antes ni después, sin bloques de código markdown:

[
  {
    "url": "https://...",
    "fuente": "Nombre descriptivo de la fuente",
    "confianza": "alta|media|baja",
    "tipo": "consolidada|original|desconocido",
    "notas": "Breve razón por la que elegiste esta fuente y cualquier advertencia relevante"
  }
]

Si no encuentras ninguna fuente confiable, devuelve un array vacío: []"""

_client = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY no está definida en el entorno")
        _client = Anthropic(api_key=api_key)
    return _client


def _extraer_json(texto: str) -> list[dict]:
    """Extrae el primer bloque JSON (lista) encontrado en el texto de respuesta."""
    texto = re.sub(r"```json|```", "", texto).strip()
    match = re.search(r"\[.*\]", texto, re.DOTALL)
    if not match:
        return []
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return []


def search_law(law_name: str) -> list[dict]:
    """Busca candidatos de PDF para una ley dada usando Claude + web search.

    Retorna una lista de dicts: {url, fuente, confianza, notas}, ordenada
    según la prioridad asignada por el modelo.
    """
    console.log(f"[bold cyan][THINK][/bold cyan] Buscando candidatos para: '{law_name}'")

    client = _get_client()

    response = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=MAX_TOKENS_SEARCH,
        system=SYSTEM_PROMPT,
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}],
        messages=[
            {
                "role": "user",
                "content": (
                    f"Busca la siguiente ley guatemalteca: {law_name}\n\n"
                    "Necesito el PDF con texto seleccionable, preferiblemente la versión "
                    "consolidada con todas las reformas integradas. "
                    "Busca también variantes del nombre por si la ley es conocida de otra forma."
                ),
            }
        ],
    )

    texto_final = ""
    for block in response.content:
        if getattr(block, "type", None) == "text":
            texto_final += block.text

    candidatos = _extraer_json(texto_final)

    if not candidatos:
        console.log(f"[bold red][THINK][/bold red] No se encontraron candidatos para '{law_name}'")
        return []

    console.log(f"[bold green][THINK][/bold green] {len(candidatos)} candidato(s) encontrado(s) para '{law_name}'")
    for c in candidatos:
        console.log(
            f"    -> [{c.get('tipo', '?')}] {c.get('url')} "
            f"(fuente={c.get('fuente')}, confianza={c.get('confianza')})"
        )

    return candidatos
