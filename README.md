# BuscadorLEX

## ¿Qué es BuscadorLEX?

BuscadorLEX es un agente autónomo que busca, evalúa y descarga leyes
guatemaltecas en formato PDF, con el objetivo de alimentar el pipeline de
[lex-extractor](../../PDFtoSQLapp/pdf-sql-LEX/lex-extractor). Es una
herramienta interna construida para SIS / LexGT: dado un listado curado de
leyes (Constitución, códigos, decretos sectoriales, convenios
internacionales, etc.), el agente intenta localizar la mejor fuente
disponible para cada una — preferiblemente la versión consolidada con
reformas integradas — y la descarga únicamente si el PDF cumple un conjunto
de reglas de calidad pensadas para no contaminar la extracción posterior.

## Arquitectura

El punto de partida de cada corrida es `input/laws_manifest.json`, que
actúa como fuente de verdad: contiene una entrada por ley con su nombre,
el batch al que pertenece, una posible `url_conocida` (URL ya verificada
manualmente) y metadata de curación (`fuente_primaria`, `flags_esperados`,
`fuentes_fallback`) derivada de `docs/SOURCES.md` por
`tools/manifest_builder.py`.

Por cada ley, `agent.py` ejecuta un ciclo `think -> act -> observe` con dos
fases:

- **Fase 1 (URL conocida)**: si el manifiesto ya tiene una `url_conocida`
  para la ley, el agente la descarga directo a memoria y la evalúa. Si pasa
  todas las reglas de calidad, se guarda y la ley queda resuelta sin tocar
  la Fase 2.
- **Fase 2 (web search)**: si no había URL conocida, o la de la Fase 1
  falló / resultó comentada / resultó compilación, el agente usa
  `tools/searcher.py` para pedirle a Claude (con la herramienta de búsqueda
  web) una lista de candidatos ordenada por confiabilidad. Evalúa cada
  candidato en orden hasta encontrar uno válido o agotar la lista
  (`MAX_CANDIDATOS_POR_LEY`, 5 por defecto).

Cada candidato pasa por `tools/evaluator.py`, que lo descarga en memoria y
aplica tres criterios de calidad antes de aceptarlo: debe tener texto
seleccionable (no ser un escaneo), no debe ser una edición comentada con
jurisprudencia de la Corte de Constitucionalidad, y no debe ser una
compilación que mezcle varios decretos en un solo PDF. Si el candidato no
tiene texto seleccionable pero es el único disponible, el agente lo
descarga igual y la ley queda marcada como `sin_texto` (candidata a OCR)
en vez de descartarla por completo.

Para los portales que devuelven 403 ante peticiones HTTP normales (pero sí
sirven el PDF a un navegador real), el evaluador activa un fallback con
Playwright: lanza Chromium headless, navega a la URL y captura el PDF ya
sea por el evento de descarga del navegador o por la respuesta HTTP con
content-type PDF. Este fallback solo se intenta cuando **todos** los
reintentos fallaron específicamente con 403 — errores de SSL, timeout u
otros códigos no lo disparan.

Una vez que un candidato pasa la evaluación, `tools/downloader.py` lo
persiste en `corpus/` junto con un JSON de metadata. Como el evaluador ya
descargó los bytes del PDF para poder analizarlo (incluso si fue vía
Playwright), el downloader los reutiliza directamente — no hace una
segunda petición HTTP al mismo recurso.

## Resultados del corpus inicial

La corrida inicial se ejecutó en 6 batches (1A se separó de 1B por ser el
bloque constitucional, de máximo cuidado). Resultado por batch, contando
como éxito solo las leyes con PDF de texto seleccionable ya en el corpus:

| Batch | Leyes | Descargadas | Sin texto (requieren OCR) | Pendientes | Éxito |
|---|---|---|---|---|---|
| 1A — Bloque constitucional | 5 | 5 | 0 | 0 | 100.0% |
| 1B — Códigos base y leyes orgánicas | 11 | 10 | 1 | 0 | 90.9% |
| 2 — Financiero | 16 | 16 | 0 | 0 | 100.0% |
| 3 — Tributario | 18 | 18 | 0 | 0 | 100.0% |
| 4 — Históricos sin portal especializado | 14 | 11 | 1 | 2 | 78.6% |
| 5 — Portales institucionales | 51 | 50 | 1 | 0 | 98.0% |
| 6 — Instrumentos internacionales | 6 | 6 | 0 | 0 | 100.0% |
| **Total** | **121** | **116** | **3** | **2** | **95.9%** |

**Resultado global: 116/121 (95.9%)** de las leyes del manifiesto quedaron
en el corpus con texto seleccionable, listas para `lex-extractor`. Las 3
leyes "sin texto" tienen un PDF descargado pero escaneado (requieren OCR
antes de procesarse); las 2 "pendientes" no encontraron ningún candidato
descargable. Ver `docs/PENDING.md` para el detalle caso por caso.

## Instalación

```bash
git clone <url-del-repo>
cd buscador_lexagent
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
# Agregar ANTHROPIC_API_KEY en .env
```

## Uso

```bash
# Ver estado del corpus
python tools/status.py

# Correr un batch completo
python agent.py --batch 1B

# Correr una ley específica
python agent.py --batch 2 --ley "Ley de Bancos y Grupos Financieros"

# Ver todos los batches disponibles
python agent.py
```

Sin argumentos, `agent.py` lista los batches disponibles y pregunta si se
quieren correr todos en secuencia (con confirmación entre cada uno) o
elegir uno puntual. Cada batch genera un reporte JSON en `logs/` con las
leyes descargadas, sin texto y pendientes; `tools/status.py` consolida
todos esos reportes (quedándose con el resultado más reciente por ley) y
los cruza contra el manifiesto para mostrar también las leyes que nunca
se han intentado.

## Reglas de calidad del corpus

El agente aplica tres reglas antes de aceptar cualquier PDF candidato:

1. **El PDF debe tener texto seleccionable.** Se extrae el texto con
   `pdfminer.six`; si el resultado tiene menos de `MIN_TEXTO_CHARS`
   caracteres, se asume que es un escaneo sin OCR y el candidato no pasa
   (aunque puede guardarse como último recurso, marcado `sin_texto`).
2. **Se rechaza si es una edición comentada.** Las publicaciones que
   intercalan jurisprudencia de la Corte de Constitucionalidad dentro del
   texto legal (citas de Gaceta, números de expediente, apelaciones de
   amparo) contaminan la extracción posterior. El agente cuenta esos
   marcadores por página y rechaza el PDF si supera un umbral de densidad.
3. **Se rechaza si es una compilación de múltiples decretos.** Algunos
   portales publican varios decretos distintos (por ejemplo, Código Penal
   + Procesal Penal + leyes conexas) en un único PDF. El agente detecta
   encabezados de decreto repetidos junto con el preámbulo de promulgación
   y rechaza el PDF si encuentra tres o más decretos distintos.

El detalle de cómo funciona cada detector está en `docs/ARCHITECTURE.md`.

## Estructura del proyecto

```
buscador_lexagent/
├── agent.py                  # orquestador principal — loop think->act->observe por batch
├── config.py                 # constantes: rutas, fuentes confiables, timeouts, umbrales
├── tools/
│   ├── searcher.py           # Fase 2 — busca candidatos con Claude API + web search
│   ├── evaluator.py          # descarga candidato a memoria, valida calidad, fallback Playwright
│   ├── downloader.py         # descarga final + naming convention + metadata JSON
│   ├── manifest_builder.py   # genera input/laws_manifest.json a partir de docs/SOURCES.md
│   ├── status.py             # consolida logs/reporte_batch_*.json contra el manifiesto
│   └── test_detector.py      # calibración de los detectores de comentada/compilación contra URLs reales
├── input/
│   ├── laws_manifest.json    # fuente de verdad: una entrada por ley con batch, fuente y URL conocida
│   └── leyes.txt             # lista plana de leyes, vestigio de una versión anterior; no la usa agent.py
├── corpus/                   # salida — PDF + JSON de metadata por ley (no se versiona)
├── logs/                     # reportes JSON por batch + snapshots de status.py (no se versiona)
├── docs/
│   ├── SOURCES.md            # mapa de fuentes por batch, curado a mano
│   ├── ARCHITECTURE.md       # documento técnico del flujo y los módulos
│   └── PENDING.md            # seguimiento de leyes que no se resolvieron automáticamente
└── requirements.txt
```

## Pendientes conocidos

Cinco leyes del manifiesto no quedaron resueltas en la corrida inicial:

- **Procedimiento Relativo al Hallazgo de Bienes Mostrencos** (batch 4): la
  búsqueda no devolvió ningún candidato descargable.
- **Ley Reguladora de las Áreas de Reservas Territoriales del Estado**
  (batch 4): todos los candidatos encontrados eran ediciones comentadas.
- **Ley de Nacionalidad** (batch 4): se descargó un decreto de 1966 desde
  congreso.gob.gt, pero es un escaneo sin texto seleccionable.
- **Ley de lo Contencioso Administrativo** (batch 1B): se descargó el
  Decreto 119-96 desde congreso.gob.gt, pero también es un escaneo sin
  texto seleccionable.
- **Propiedad Industrial** (batch 5): se descargó el Decreto 57-2000 desde
  congreso.gob.gt, también escaneado, sin texto seleccionable.

El detalle de cada caso, con su causa exacta y una resolución sugerida,
está en `docs/PENDING.md`.
