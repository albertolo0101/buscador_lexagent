"""Test de calibración de los detectores de edición comentada y compilación.

Corre contra URLs verificadas reales (códigos individuales limpios, una
edición comentada conocida y una compilación conocida) para confirmar que
COMENTADA_THRESHOLD / COMPILACION_MIN_DECRETOS separan ambos grupos.

Uso: python -m tools.test_detector
"""

import io

from pdfminer.high_level import extract_text
from pdfminer.pdfpage import PDFPage
from rich.console import Console
from rich.table import Table

from config import COMENTADA_THRESHOLD
from tools.evaluator import (
    _contar_marcadores_comentada,
    _descargar_bytes,
    _es_comentada,
    _es_compilacion,
)

console = Console()

# Cada caso define el campo que se evalúa (es_comentada o es_compilacion)
# contra su valor esperado. Ambos detectores se calculan e imprimen para
# cada URL, pero solo ese campo cuenta para el resumen final PASS/FAIL.
CASOS = [
    {
        "nombre": "Código Penal",
        "url": "http://ww2.oj.gob.gt/es/QueEsOJ/EstructuraOJ/UnidadesAdministrativas/CentroAnalisisDocumentacionJudicial/pdfs/Codigos/Codigo%20Penal_CENADOJ%202024.pdf",
        "campo_esperado": "es_comentada",
        "valor_esperado": False,
    },
    {
        "nombre": "Código de Trabajo",
        "url": "http://ww2.oj.gob.gt/es/QueEsOJ/EstructuraOJ/UnidadesAdministrativas/CentroAnalisisDocumentacionJudicial/pdfs/Codigos/CodigoTrabajo_CENADOJ.pdf",
        "campo_esperado": "es_comentada",
        "valor_esperado": False,
    },
    {
        "nombre": "Código Procesal Penal",
        "url": "http://ww2.oj.gob.gt/es/queesoj/estructuraoj/unidadesadministrativas/centroanalisisdocumentacionjudicial/pdfs/Codigos/Codigo%20Procesal%20Penal_CENADOJ%202024.pdf",
        "campo_esperado": "es_comentada",
        "valor_esperado": False,
    },
    {
        "nombre": "Constitución Política",
        "url": "https://www.congreso.gob.gt/assets/uploads/secciones/pdf/16e67-constitucion-politica-de-la-republica-de-guatemala.pdf",
        "campo_esperado": "es_comentada",
        "valor_esperado": False,
    },
    {
        "nombre": "Ley de Amparo",
        "url": "https://www.congreso.gob.gt/assets/uploads/secciones/pdf/7e55a-ley-de-amparo-exhibicion-personal-y-de-constitucionalidad.pdf",
        "campo_esperado": "es_comentada",
        "valor_esperado": False,
    },
    {
        "nombre": "Código Civil CENADOJ (comentado)",
        "url": "http://ww2.oj.gob.gt/es/QueEsOJ/EstructuraOJ/UnidadesAdministrativas/CentroAnalisisDocumentacionJudicial/pdfs/Codigos/CodigoCivilComentado_CENADOJ.pdf",
        "campo_esperado": "es_comentada",
        "valor_esperado": True,
    },
    {
        "nombre": "Compilación Leyes Penales 4a Ed",
        "url": "http://ww2.oj.gob.gt/es/QueEsOJ/EstructuraOJ/UnidadesAdministrativas/CentroAnalisisDocumentacionJudicial/pdfs/Compilaciones/Compilacion%20de%20Leyes%20Penales_CENADOJ%204aEd.pdf",
        "campo_esperado": "es_compilacion",
        "valor_esperado": True,
    },
]


def _evaluar(nombre: str, url: str) -> dict | None:
    console.print(f"\n[bold]{nombre}[/bold]")
    console.print(f"  {url}")

    contenido, _ = _descargar_bytes(url)
    if contenido is None:
        console.print("  [bold red]No se pudo descargar.[/bold red]")
        return None

    try:
        texto = extract_text(io.BytesIO(contenido)).strip()
    except Exception as e:
        console.print(f"  [bold red]No se pudo extraer texto: {e}[/bold red]")
        return None

    paginas = sum(1 for _ in PDFPage.get_pages(io.BytesIO(contenido)))
    marcadores = _contar_marcadores_comentada(texto)
    marcadores_por_pagina = marcadores / paginas if paginas else 0.0

    es_comentada = _es_comentada(texto, paginas)
    es_compilacion = _es_compilacion(texto)

    console.print(f"  Páginas: {paginas} | Caracteres: {len(texto)}")
    console.print(f"  Marcadores totales: {marcadores} | marcadores/página: {marcadores_por_pagina:.3f}")
    console.print(f"  es_comentada   = {es_comentada}")
    console.print(f"  es_compilacion = {es_compilacion}")

    return {
        "paginas": paginas,
        "chars": len(texto),
        "marcadores": marcadores,
        "marcadores_por_pagina": marcadores_por_pagina,
        "es_comentada": es_comentada,
        "es_compilacion": es_compilacion,
    }


def main() -> None:
    resultados = []
    aciertos = 0
    fallos = 0
    densidades_negativas = []  # marcadores/página de los casos que esperaban es_comentada=False

    for caso in CASOS:
        medicion = _evaluar(caso["nombre"], caso["url"])
        if medicion is None:
            fallos += 1
            console.print("  [bold red]-> FAIL (no se pudo evaluar)[/bold red]")
            resultados.append({**caso, "medicion": None, "paso": False})
            continue

        valor_real = medicion[caso["campo_esperado"]]
        paso = valor_real == caso["valor_esperado"]
        aciertos += int(paso)
        fallos += int(not paso)

        veredicto = "[bold green]PASS[/bold green]" if paso else "[bold red]FAIL[/bold red]"
        console.print(
            f"  {caso['campo_esperado']} esperado={caso['valor_esperado']} real={valor_real} -> {veredicto}"
        )

        if caso["campo_esperado"] == "es_comentada" and not caso["valor_esperado"]:
            densidades_negativas.append(medicion["marcadores_por_pagina"])
            if not paso:
                console.print(
                    f"  [bold yellow]AVISO: caso limpio detectado como comentada -- "
                    f"tenía {medicion['marcadores_por_pagina']:.3f} marcadores/página[/bold yellow]"
                )

        resultados.append({**caso, "medicion": medicion, "paso": paso})

    console.rule("[bold]Resumen[/bold]")
    tabla = Table(show_header=True, header_style="bold")
    tabla.add_column("Caso")
    tabla.add_column("Campo")
    tabla.add_column("Esperado")
    tabla.add_column("Real")
    tabla.add_column("Marc./pág.")
    tabla.add_column("Resultado")

    for r in resultados:
        m = r["medicion"]
        real = m[r["campo_esperado"]] if m else "—"
        densidad = f"{m['marcadores_por_pagina']:.3f}" if m else "—"
        tabla.add_row(
            r["nombre"],
            r["campo_esperado"],
            str(r["valor_esperado"]),
            str(real),
            densidad,
            "PASS" if r["paso"] else "FAIL",
        )

    console.print(tabla)

    total = len(CASOS)
    console.print(f"\nPASS: {aciertos}/{total}")
    console.print(f"FAIL: {fallos}/{total}")
    console.print(f"Threshold actual: {COMENTADA_THRESHOLD}")

    if densidades_negativas:
        positivos = [
            r["medicion"]["marcadores_por_pagina"]
            for r in resultados
            if r["medicion"] and r["campo_esperado"] == "es_comentada" and r["valor_esperado"]
        ]
        max_negativo = max(densidades_negativas)
        console.print(f"\nMáximo marcadores/página entre casos limpios: {max_negativo:.3f}")
        if positivos:
            min_positivo = min(positivos)
            console.print(f"Mínimo marcadores/página entre casos comentados: {min_positivo:.3f}")
            margen = (min_positivo / max_negativo) if max_negativo > 0 else float("inf")
            console.print(f"Margen actual (positivo mínimo / negativo máximo): {margen:.2f}x")
            if margen < 2:
                console.print(
                    "[bold yellow]AVISO: margen menor a 2x -- el threshold no separa con suficiente holgura.[/bold yellow]"
                )


if __name__ == "__main__":
    main()
