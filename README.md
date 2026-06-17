# BuscadorLEX

Agente que busca, evalúa y descarga leyes guatemaltecas en PDF, listas para
procesarse en batch con [lex-extractor](../../PDFtoSQLapp/pdf-sql-LEX/lex-extractor).

El agente sigue un ciclo `think -> act -> observe` por cada ley:

1. **THINK** (`tools/searcher.py`): usa Claude (con la herramienta de
   búsqueda web) para encontrar URLs candidatas a PDFs oficiales.
2. **ACT** (`tools/evaluator.py`): descarga cada candidato a memoria y
   verifica con `pdfminer.six` si el PDF tiene texto seleccionable.
3. **OBSERVE**: si el candidato tiene texto, se descarga de forma definitiva
   (`tools/downloader.py`). Si no, se prueba el siguiente candidato. Si
   ninguno funciona, la ley queda marcada como pendiente.

Al final del proceso se imprime un reporte resumen con leyes descargadas,
leyes descargadas sin texto (candidatas a OCR) y leyes no encontradas.

## Instalación

```bash
# 1. Crear y activar un entorno virtual
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS/Linux

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Instalar navegadores de Playwright (necesario para portales con
#    protección anti-scraping)
playwright install chromium

# 4. Configurar la API key de Anthropic
copy .env.example .env        # Windows
cp .env.example .env          # macOS/Linux
# Edita .env y agrega tu ANTHROPIC_API_KEY
```

La API key se lee desde la variable de entorno `ANTHROPIC_API_KEY`. Nunca la
hardcodees en el código. Puedes definirla en un archivo `.env` (no se sube
al repositorio, ver `.gitignore`) y cargarla con `python-dotenv` o
exportarla manualmente en tu shell:

```bash
export ANTHROPIC_API_KEY=sk-ant-...   # macOS/Linux
$env:ANTHROPIC_API_KEY="sk-ant-..."   # PowerShell
```

## Uso

1. Edita `input/leyes.txt` y agrega una ley por línea:

   ```
   Código Civil
   Código de Trabajo
   Ley del Organismo Judicial
   Código Penal
   Ley de Minería
   ```

2. Ejecuta el agente:

   ```bash
   python agent.py
   ```

3. Revisa los resultados en `corpus/`: cada ley descargada genera un par de
   archivos:

   ```
   corpus/decreto_106_1963_codigo_civil.pdf
   corpus/decreto_106_1963_codigo_civil.json
   ```

   El JSON de metadata incluye la ley, la URL fuente, fecha de descarga,
   si tiene texto seleccionable, número de páginas y la confianza asignada
   a la fuente.

4. Al terminar, el agente imprime un reporte con tres categorías:
   - ✅ Descargadas exitosamente (con texto seleccionable)
   - ⚠️ Descargadas pero sin texto (requieren OCR)
   - ❌ No encontradas (quedaron pendientes)

## Estructura del proyecto

```
buscador_lexagent/
├── agent.py              # orquestador principal — loop think→act→observe
├── tools/
│   ├── searcher.py       # busca la ley usando Claude API + web search
│   ├── evaluator.py      # descarga PDF candidato y verifica calidad
│   └── downloader.py     # descarga final + naming convention + metadata
├── corpus/                # salida — PDFs + JSONs de metadata
├── input/leyes.txt        # lista de leyes a procesar
├── logs/                  # logs de ejecución
├── config.py               # constantes: fuentes, timeouts, rutas
└── requirements.txt
```

## Notas

- El agente es tolerante a fallos: si una ley falla en cualquier paso,
  se loguea y continúa con la siguiente.
- No usa `asyncio` — todo es síncrono para facilitar el debugging.
- Los PDFs y JSONs generados en `corpus/` no se versionan (ver
  `.gitignore`); solo se mantiene la carpeta vía `.gitkeep`.
