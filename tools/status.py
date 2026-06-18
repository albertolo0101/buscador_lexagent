"""Genera un resumen consolidado del estado del corpus a partir de logs/.

Lee todos los reportes de batch (logs/reporte_batch_*.json), consolida cada
ley por su resultado más reciente, y la cruza contra input/laws_manifest.json
para detectar leyes que nunca se intentaron.

Uso: python tools/status.py
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.table import Table

from config import LAWS_MANIFEST_FILE, LOGS_DIR


def _cargar_manifest() -> list[dict]:
    with open(LAWS_MANIFEST_FILE, encoding="utf-8") as f:
        return json.load(f)


def _consolidar_logs() -> dict[str, dict]:
    """Lee todos los reportes de batch y devuelve {ley: entrada_mas_reciente}.

    Si una ley aparece en varios reportes (porque se re-corrió con --ley),
    se queda con la entrada del reporte de timestamp más reciente.
    """
    consolidado: dict[str, dict] = {}
    timestamps: dict[str, datetime] = {}

    for ruta in sorted(LOGS_DIR.glob("reporte_batch_*.json")):
        try:
            reporte = json.loads(ruta.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        ts_reporte = datetime.fromisoformat(reporte["timestamp"])

        for categoria in ("descargadas", "sin_texto", "pendientes"):
            for entrada in reporte.get(categoria, []):
                ley = entrada["ley"]
                if ley not in timestamps or ts_reporte > timestamps[ley]:
                    timestamps[ley] = ts_reporte
                    consolidado[ley] = entrada

    return consolidado


def _razon_legible(entrada: dict) -> str:
    razon = entrada.get("razon")
    if razon:
        return razon
    if entrada["estado"] == "sin_texto":
        return "sin_texto"
    return "no_encontrada"


def main() -> None:
    console = Console(record=True, width=220)

    manifest = _cargar_manifest()
    total_manifest = len(manifest)
    leyes_manifest = {e["ley"]: e for e in manifest}

    consolidado = _consolidar_logs()

    descargadas = [e for e in consolidado.values() if e["estado"] == "descargada"]
    pendientes = [e for e in consolidado.values() if e["estado"] != "descargada"]
    sin_procesar = [e for ley, e in leyes_manifest.items() if ley not in consolidado]

    descargadas.sort(key=lambda e: (e["batch"], e["ley"]))
    pendientes.sort(key=lambda e: (e["batch"], e["ley"]))
    sin_procesar.sort(key=lambda e: (e["batch"], e["ley"]))

    console.print(f"\nDESCARGADAS ({len(descargadas)})", style="bold green")
    tabla_descargadas = Table(show_header=True, header_style="bold")
    tabla_descargadas.add_column("Batch")
    tabla_descargadas.add_column("Ley")
    tabla_descargadas.add_column("Archivo")
    for e in descargadas:
        nombre_archivo = Path(e["path"]).name if e.get("path") else "?"
        tabla_descargadas.add_row(e["batch"], e["ley"], nombre_archivo)
    console.print(tabla_descargadas)

    console.print(f"\nPENDIENTES ({len(pendientes)})", style="bold yellow")
    tabla_pendientes = Table(show_header=True, header_style="bold")
    tabla_pendientes.add_column("Batch")
    tabla_pendientes.add_column("Ley")
    tabla_pendientes.add_column("Razón")
    for e in pendientes:
        tabla_pendientes.add_row(e["batch"], e["ley"], _razon_legible(e))
    console.print(tabla_pendientes)

    console.print(f"\nSIN PROCESAR ({len(sin_procesar)})", style="bold red")
    tabla_sin_procesar = Table(show_header=True, header_style="bold")
    tabla_sin_procesar.add_column("Batch")
    tabla_sin_procesar.add_column("Ley")
    for e in sin_procesar:
        tabla_sin_procesar.add_row(e["batch"], e["ley"])
    console.print(tabla_sin_procesar)

    resumen = (
        f"\nCorpus: {len(descargadas)} descargadas / {len(pendientes)} pendientes / "
        f"{len(sin_procesar)} sin procesar de {total_manifest} totales"
    )
    console.print(resumen, style="bold")

    timestamp_archivo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    ruta_status = LOGS_DIR / f"status_{timestamp_archivo}.txt"
    ruta_status.write_text(console.export_text(), encoding="utf-8")
    console.print(f"\nGuardado en: {ruta_status}")


if __name__ == "__main__":
    main()
