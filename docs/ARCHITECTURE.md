# Arquitectura de BuscadorLEX

Documento técnico de referencia. Para una introducción general al
proyecto, ver `README.md`.

## Diagrama del flujo

```
input/laws_manifest.json
        |
        v
  agent.py: procesar_ley(entrada)
        |
        v
  ¿tiene url_conocida? ----no----> Fase 2
        |
       sí
        v
  Fase 1: evaluate_pdf(url_conocida)
        |
        v
  ¿válido, con texto, ni comentada ni compilación? ----no----> Fase 2
        |
       sí
        v
  download_law(...) ---> corpus/*.pdf + corpus/*.json
        |
       (resuelto, fin)

  Fase 2: search_law(law_name)         [tools/searcher.py — Claude + web_search]
        |
        v
  candidatos[:MAX_CANDIDATOS_POR_LEY]
        |
        v
  para cada candidato, en orden:
    evaluate_pdf(url)                  [tools/evaluator.py]
      |
      +-- inválido / no descarga ---------------> probar el siguiente
      |
      +-- válido, sin texto seleccionable ------> guardar como "mejor_sin_texto"
      |                                            (solo se usa si nada más funciona)
      |
      +-- válido, con texto, es comentada ------> probar el siguiente (marca rechazo)
      |
      +-- válido, con texto, es compilación ----> probar el siguiente (marca rechazo)
      |
      +-- válido, con texto, limpio -------------> download_law(...) -> estado "descargada", fin
        |
        v (se agotaron los candidatos)
  ¿hubo un "mejor_sin_texto"? --sí--> download_law(...) -> estado "sin_texto", fin
        |
        no
        v
  estado "pendiente" (razón: solo_fuentes_comentadas | solo_compilaciones |
                              comentada_y_compilacion | sin razón si no hubo candidatos)
```

`evaluate_pdf` descarga el candidato vía `httpx`; si los reintentos fallan
todos con 403, intenta el fallback de Playwright (ver más abajo) antes de
darse por vencido con ese candidato.

## Módulos

### `agent.py`

Orquestador. No contiene lógica de evaluación ni de red propia: coordina
`searcher`, `evaluator` y `downloader`, y lleva el registro de resultados.

- `procesar_ley(entrada: dict) -> dict` — ejecuta el ciclo completo
  (Fase 1 + Fase 2) para una sola ley del manifiesto. Devuelve la entrada
  original extendida con `estado` (`"descargada"` | `"sin_texto"` |
  `"pendiente"`), `path`, `url` y `razon`.
- `_procesar_batch(batch, entradas) -> list[dict]` — corre
  `procesar_ley` sobre todas las entradas de un batch, imprime el reporte
  y lo persiste en `logs/`.
- `main()` — parsea argumentos (`--batch`, `--ley`), lee el manifiesto y
  decide si correr un batch puntual o todos en secuencia con confirmación
  interactiva entre cada uno.

### `tools/searcher.py`

Responsable de la Fase 2 (THINK). Expone:

- `search_law(law_name: str) -> list[dict]` — le pide a Claude
  (`ANTHROPIC_MODEL`, con la tool `web_search_20250305`) una lista de
  candidatos para la ley dada. El system prompt codifica la jerarquía de
  fuentes confiables (congreso.gob.gt, ministerios sectoriales, oj.gob.gt,
  legis.gt, universidades) y las señales de calidad/alerta que el modelo
  debe usar para priorizar. La respuesta esperada es un array JSON
  `[{url, fuente, confianza, tipo, notas}]`, que se extrae de la respuesta
  de texto con una regex tolerante a bloques markdown.

No descarga ni valida nada — solo decide *dónde buscar*.

### `tools/evaluator.py`

Responsable del ACT/OBSERVE de cada candidato. Expone:

- `evaluate_pdf(url: str) -> dict` — descarga el candidato a memoria,
  extrae texto con `pdfminer.six`, cuenta páginas con `PDFPage.get_pages`,
  y devuelve un diccionario con `valido`, `tiene_texto`, `paginas`,
  `texto_muestra`, `tamaño_kb`, `pdf_bytes`, `es_comentada`,
  `es_compilacion` y `via_playwright`.

Internamente usa `_descargar_bytes(url)` (httpx con reintentos y fallback
Playwright) y dos detectores de calidad, `_es_comentada` y
`_es_compilacion`, descritos abajo.

### `tools/downloader.py`

Responsable de la persistencia final. Expone:

- `download_law(url, law_name, metadata, pdf_bytes=None) -> str | None` —
  construye el nombre de archivo (`decreto_<numero>_<año>_<slug>.pdf` si se
  puede inferir número y año de decreto, o `<slug>.pdf` si no), guarda el
  PDF en `CORPUS_DIR` y escribe un JSON de metadata junto a él. Si
  `pdf_bytes` ya viene con contenido (porque `evaluate_pdf` ya lo
  descargó), lo reutiliza sin volver a pedirlo por HTTP.

## Detección de ediciones comentadas: `_es_comentada()`

Las ediciones "comentadas" intercalan jurisprudencia de la Corte de
Constitucionalidad dentro del texto legal (citas de Gaceta, números de
expediente, resoluciones de amparo), lo cual contamina la extracción
posterior si se procesan como si fueran el texto limpio de la ley.

`_contar_marcadores_comentada(texto)` cuenta tres patrones por documento:

- `Gaceta\s+No\.?\s*\d+` — referencias a la Gaceta de la Corte de
  Constitucionalidad.
- `expediente\s+(?:n[uú]mero\s+|no\.?\s*)?\d+` — números de expediente
  judicial.
- `apelaci[oó]n\s+de\s+sentencia\s+de\s+amparo` — un tipo de resolución
  específico de la CC.

Dos patrones adicionales (`Corte de Constitucionalidad`,
`inconstitucionalidad`) se probaron y se descartaron del conteo: son
vocabulario sustantivo normal en leyes que regulan a la propia CC o el
amparo (Constitución Política, Ley de Amparo), y producían falsos
positivos en documentos limpios.

`_es_comentada(texto, paginas)` divide el conteo de marcadores entre el
número de páginas y compara contra `COMENTADA_THRESHOLD` (`0.15`
marcadores por página, definido en `config.py`). Ese umbral se calibró
corriendo `tools/test_detector.py` contra un set de URLs reales: códigos
limpios conocidos (Código Penal, Código de Trabajo, Código Procesal Penal,
Constitución Política, Ley de Amparo) frente al Código Civil CENADOJ
comentado. El script imprime el margen entre el máximo de marcadores/página
entre los casos limpios y el mínimo entre los comentados, y avisa si ese
margen es menor a 2x.

## Detección de compilaciones: `_es_compilacion()`

Algunos portales (notablemente CENADOJ) publican compilaciones que
agrupan varios decretos distintos en un solo PDF — por ejemplo, la
"Compilación de Leyes Penales" mezcla Código Penal + Procesal Penal +
varias leyes conexas. Procesar ese PDF como si fuera una sola ley
rompería el modelo de datos de `lex-extractor`.

El detector se basa en el regex `PATRON_DECRETO_COMPILACION`:

```python
DECRETO\s+(?:N[ÚU]MERO|No\.?|DEL\s+CONGRESO(?:\s+DE\s+LA\s+REP[ÚU]BLICA)?)\s*[:\-]?\s*(\d{1,4}-\d{2,4})
[\s\S]{0,200}?\bEL\s+CONGRESO\s+DE\s+LA\s+REP[ÚU]BLICA\b
```

Busca un encabezado de decreto ("DECRETO NÚMERO X-Y") seguido, a poca
distancia (200 caracteres), del preámbulo de promulgación ("EL CONGRESO DE
LA REPÚBLICA..."). Esa combinación específica es la que realmente abre un
decreto nuevo dentro del PDF.

El regex se construyó deliberadamente **sin** `re.IGNORECASE`: en los PDFs
de CENADOJ, el encabezado que abre un decreto nuevo aparece en mayúsculas,
mientras que las referencias cruzadas dentro del cuerpo del texto
(derogaciones, reformas a otras leyes) citan el decreto en mayúscula y
minúscula ("Decreto Número X-Y del Congreso de la República...") y nunca
van seguidas del preámbulo de promulgación. Esto se confirmó contra el
Código Penal y el Código Procesal Penal individuales — que citan diez o
más decretos ajenos sin ser compilaciones — frente a la Compilación de
Leyes Penales real, que contiene unos veinte encabezados genuinos.

`_es_compilacion(texto)` junta los números de decreto encontrados en un
`set` (para no contar dos veces el mismo decreto si aparece repetido) y
considera que el PDF es una compilación si hay `COMPILACION_MIN_DECRETOS`
(3, en `config.py`) o más decretos distintos.

Ambos detectores se validan juntos en `tools/test_detector.py`, que corre
contra las URLs reales mencionadas arriba y reporta PASS/FAIL por caso.

## Fallback de Playwright

`PLAYWRIGHT_ENABLED` en `config.py` controla si el fallback está activo.
Se activa **únicamente** cuando todos los reintentos de `httpx`
(`HTTP_MAX_RETRIES`, 3 por defecto) fallaron específicamente con
status 403 — no se activa ante timeouts, errores SSL ni otros códigos
HTTP, porque en esos casos un navegador real probablemente tampoco
resolvería el problema y el costo de lanzar Chromium no se justifica.

`_descargar_bytes_playwright(url)` lanza Chromium headless con un
user-agent de navegador real y captura el PDF por dos vías:

1. **Evento de descarga**: Chromium headless trata la navegación directa
   a una URL de PDF como una descarga (no como una página para renderizar).
   `page.goto(url)` lanza la excepción "Download is starting" en cuanto el
   navegador decide descargar — esa excepción se traga *dentro* del bloque
   `with page.expect_download(...)` para que el manejador de descargas
   pueda seguir esperando el evento en su `__exit__`. Si se deja escapar
   fuera del `with`, este aborta por completo y nunca se llega a leer
   `download_info.value`.
2. **Captura por respuesta HTTP**: en paralelo, un handler registrado con
   `page.on("response", ...)` intenta capturar el cuerpo de cualquier
   respuesta cuyo `content-type` incluya "pdf", por si el recurso se
   renderiza en vez de descargarse.

Si ninguna de las dos vías funcionó y la URL termina en `.pdf`, hay un
tercer intento: se toman las cookies de la sesión de Playwright (que ya
pasó el desafío anti-scraping del portal) y se hace una petición `httpx`
directa reutilizando esas cookies.

## El campo `via_playwright`

`evaluate_pdf` incluye `via_playwright: bool` en su resultado para indicar
si el PDF se obtuvo a través del fallback de Playwright en vez de una
petición HTTP directa. Sirve como señal de diagnóstico: permite saber, sin
revisar logs línea por línea, qué leyes dependieron de un portal que
bloquea scraping convencional — información útil si ese portal cambia su
protección y el fallback empieza a fallar también.

## Schema de `laws_manifest.json`

Cada entrada es un objeto con estos campos:

| Campo | Tipo | Descripción |
|---|---|---|
| `ley` | `str` | Nombre de la ley, tal como aparece en `docs/SOURCES.md` (sin paréntesis aclaratorios). |
| `batch` | `str` | Identificador del batch (`"1A"`, `"1B"`, `"2"`...`"6"`). Determina el orden de procesamiento sugerido en `agent.py`. |
| `fuente_primaria` | `str \| null` | Dominio sugerido como mejor fuente, inferido de la columna "Fuente" de `SOURCES.md` por `manifest_builder.py`. No se usa actualmente en la lógica de `agent.py` — es metadata de referencia para quien cura el manifiesto. |
| `url_conocida` | `str \| null` | URL ya verificada manualmente. Si está presente, `agent.py` la intenta en la Fase 1 antes de caer a búsqueda web. |
| `flags_esperados` | `list[str]` | Advertencias esperadas para esa ley (p. ej. `"comentada-riesgo"`, `"escaneada"`), extraídas de la columna de flags en `SOURCES.md`. Es metadata informativa; `agent.py` no la consulta para cambiar su comportamiento. |
| `fuentes_fallback` | `list[str]` | Dominios alternativos sugeridos si la fuente primaria falla (normalmente `["congreso.gob.gt"]`). Tampoco se consulta actualmente en `agent.py` — la Fase 2 delega esa decisión a la búsqueda web de Claude. |

El manifiesto se regenera con `python -m tools.manifest_builder`, que
parsea `docs/SOURCES.md` y nunca inventa una URL o dominio que no esté
explícito en ese documento: si no hay dato verificado, el campo queda en
`null`.

## Formato del corpus

Cada ley resuelta produce un par de archivos en `corpus/`, con el mismo
nombre base:

```
corpus/decreto_106_1963_codigo_civil.pdf
corpus/decreto_106_1963_codigo_civil.json
```

El nombre de archivo es `decreto_<numero>_<año>_<slug-del-nombre>.pdf`
cuando `tools/downloader.py` puede inferir número y año de decreto (del
nombre de la ley o de las notas del candidato, vía el regex
`_PATRON_DECRETO`); si no puede, usa solo `<slug-del-nombre>.pdf`.

El JSON de metadata contiene:

```json
{
  "ley": "Código Civil",
  "url_fuente": "https://...",
  "fecha_descarga": "2026-06-17T18:04:48...+00:00",
  "tiene_texto": true,
  "paginas": 312,
  "confianza_fuente": "alta",
  "fuente": "Nombre descriptivo de la fuente"
}
```
