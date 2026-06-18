"""Constantes de configuración para BuscadorLEX."""

from pathlib import Path

# --- Rutas ---
BASE_DIR = Path(__file__).resolve().parent
CORPUS_DIR = BASE_DIR / "corpus"
INPUT_DIR = BASE_DIR / "input"
LOGS_DIR = BASE_DIR / "logs"
LEYES_FILE = INPUT_DIR / "leyes.txt"
LAWS_MANIFEST_FILE = INPUT_DIR / "laws_manifest.json"

CORPUS_DIR.mkdir(exist_ok=True)
INPUT_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# --- Fuentes confiables (ordenadas por confiabilidad descendente) ---
FUENTES_CONFIABLES = [
    {"dominio": "congreso.gob.gt", "confianza": "alta", "descripcion": "Congreso de la República de Guatemala"},
    {"dominio": "minfin.gob.gt", "confianza": "alta", "descripcion": "Ministerio de Finanzas Públicas"},
    {"dominio": "minem.gob.gt", "confianza": "alta", "descripcion": "Ministerio de Energía y Minas"},
    {"dominio": "mintrabajo.gob.gt", "confianza": "alta", "descripcion": "Ministerio de Trabajo y Previsión Social"},
    {"dominio": "mp.gob.gt", "confianza": "alta", "descripcion": "Ministerio Público"},
    {"dominio": "gob.gt", "confianza": "alta", "descripcion": "Portal del Gobierno de Guatemala"},
    {"dominio": "oj.gob.gt", "confianza": "media", "descripcion": "Organismo Judicial"},
    {"dominio": "legis.gt", "confianza": "media", "descripcion": "Legis - compilador de legislación"},
]

# --- Claude API ---
ANTHROPIC_MODEL = "claude-sonnet-4-6"
MAX_TOKENS_SEARCH = 2048

# --- Timeouts y reintentos ---
HTTP_TIMEOUT_SECONDS = 30
HTTP_MAX_RETRIES = 3
PLAYWRIGHT_ENABLED = True
PLAYWRIGHT_TIMEOUT_MS = 30_000

# --- Validación de PDFs ---
MIN_PDF_SIZE_KB = 10
MIN_TEXTO_CHARS = 100  # mínimo de caracteres extraídos para considerar "tiene texto"
COMENTADA_THRESHOLD = 0.15  # marcadores de jurisprudencia por página
COMPILACION_MIN_DECRETOS = 3  # decretos distintos para considerar el PDF una compilación

# --- Candidatos a evaluar por ley ---
MAX_CANDIDATOS_POR_LEY = 5
