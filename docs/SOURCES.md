# SOURCES.md — Mapa de fuentes por batch para las ~121 leyes

> Documento de curación de fuentes. Alimenta `laws_manifest.json` (Fase 2.5).
> Regla de oro: **la calidad del PDF de origen determina la calidad de LexGT.**

---

## Reglas de calidad de fuentes (innegociables)

1. **PROHIBIDAS las ediciones "comentadas" / "con notas de jurisprudencia".**
   Las publicaciones de la Corte de Constitucionalidad, IDPP y el Código Civil
   CENADOJ 2025 intercalan fallos y citas de Gaceta dentro del texto legal —
   esto contamina la extracción (causa probable de fallos del primer lote).
   Si solo existe edición comentada: marcar `source_flags: ["comentada"]` en
   el manifiesto. El pipeline NO procesa comentadas por defecto.
2. **Compilaciones multi-ley NO se procesan directo.** La "Compilación de
   Leyes Penales" (CENADOJ, 4ª ed. 2025) trae Código Penal + Procesal Penal +
   varias leyes en un solo PDF. Preferir el PDF individual; si no existe,
   marcar `["compilacion"]` y partir manualmente antes de procesar.
3. **Preferir ediciones consolidadas/actualizadas** (reformas incorporadas con
   notas "Reformado por el Decreto X") sobre el decreto original: el pipeline
   está diseñado para eso (`amendment_note` es dato de primera clase). Las
   notas de REFORMA son bienvenidas; las notas de JURISPRUDENCIA no.
4. **Registrar siempre** en el manifiesto: `source_url`, `sha256`,
   `downloaded_at`, `source_flags` (comentada | compilacion | escaneada |
   desactualizada).
5. Leyes pre-1994 → `expected_profile: non_canonical`; pre-1985 probablemente
   `["escaneada"]` además.

## Portales ancla (verificados 2026-06-12)

| Portal | URL base | Cubre | Notas |
|---|---|---|---|
| CENADOJ (OJ) | `ww2.oj.gob.gt/es/QueEsOJ/EstructuraOJ/UnidadesAdministrativas/CentroAnalisisDocumentacionJudicial/pdfs/{Leyes,Codigos,Compilaciones}/` | Códigos base, leyes judiciales | Rutas estáticas. ⚠ Código Civil 2025 = COMENTADO; Compilaciones = multi-ley |
| Banco de Guatemala | `banguat.gob.gt/page/leyes-bancarias-y-financieras-2` → PDFs en `banguat.gob.gt/sites/default/files/banguat/leyes/` | Todo el bloque financiero | PDFs planos verificados (Ley Orgánica Banguat, Supervisión Financiera) |
| SIB | `sib.gob.gt/web/sib/normativa` | Financiero/bancario (alternativa a Banguat) | Muy curado |
| SAT | `portal.sat.gob.gt/portal/biblioteca-en-linea-sat/legislacion-tributaria/` | Todo el bloque tributario + "Histórico de Leyes Tributarias y sus Reformas" | Ancla del Batch 3 |
| Contraloría GC | `contraloria.gob.gt/imagenes/i_docs/i_leg_ley/` | Leyes administrativas/fiscalización | PDFs planos verificados (p.ej. LEY DE BANCOS...) — explorar el índice |
| Congreso | `congreso.gob.gt` (decretos / info legislativa) | Cualquier decreto (texto original, no consolidado) | Fallback universal; históricos = escaneos |
| TSE | `tse.org.gt` | Ley Electoral y de Partidos Políticos | Edición oficial del TSE |
| MINTRAB | `mintrabajo.gob.gt` | Código de Trabajo, leyes laborales | |
| IDPP Biblioteca | `idpp.gob.gt/images/Biblioteca-virtual/Leyes_y_Reglamentos/` | Leyes penales | ⚠ su Constitución es comentada — revisar cada PDF |
| WIPO Lex | `wipolex.wipo.int` (buscar Guatemala) | Convenios de París, Roma, Niza; leyes de PI | Ancla del Batch 6 |
| OIT NORMLEX | `ilo.org/dyn/normlex` | Convenios fundamentales OIT | Batch 6 |
| OAS | `oas.org/juridico/spanish/` | Versiones limpias antiguas (p.ej. Ley de Amparo 2002) | ⚠ verificar vigencia |

URLs individuales ya verificadas:
- Ley del Organismo Judicial (actualizada 2024): `http://ww2.oj.gob.gt/es/QueEsOJ/EstructuraOJ/UnidadesAdministrativas/CentroAnalisisDocumentacionJudicial/pdfs/Leyes/Ley_OJ.pdf`
- Ley Orgánica del Banco de Guatemala: `https://banguat.gob.gt/sites/default/files/banguat/leyes/2013/ley_organica_banco_de_guatemala.pdf`
- Ley de Supervisión Financiera: `https://banguat.gob.gt/sites/default/files/banguat/leyes/2013/ley_supervision_financiera.pdf`
- Ley de Bancos y Grupos Financieros (Contraloría, plano): `https://www.contraloria.gob.gt/imagenes/i_docs/i_leg_ley/LEY%20DE%20BANCOS%20Y%20GRUPOS%20FINANCIEROS.pdf`

---

## Batch 1A — Bloque constitucional (5 leyes) — sub-bloque de máximo cuidado

Todas pre-1994 (varias pre-1986): `expected_profile: non_canonical`. Las
ediciones disponibles suelen ser COMENTADAS — buscar texto simple.

| Ley | Fuente sugerida | Flags probables |
|---|---|---|
| Constitución Política | CENADOJ / Congreso (⚠ CC e IDPP son comentadas) | comentada-riesgo |
| Ley de Amparo, Exhibición Personal y de Constitucionalidad (Dto 1-86 ANC) | CENADOJ; OAS como respaldo | comentada-riesgo |
| Ley Electoral y de Partidos Políticos (Dto 1-85 ANC) | TSE (edición oficial actualizada) | — |
| Ley de Emisión del Pensamiento (Dto 9, 1966) | Congreso / CENADOJ | escaneada |
| Ley de Orden Público (Dto 7, 1965) | Congreso / CENADOJ | escaneada |

## Batch 1B — Códigos base y leyes orgánicas judiciales (Base principal restante)

Fuente primaria: CENADOJ `pdfs/Codigos` y `pdfs/Leyes`.

| Ley | Fuente | Flags |
|---|---|---|
| Código Civil | CENADOJ ⚠ ed. 2025 es COMENTADA — buscar edición simple o alternativa (Infile/Congreso) | comentada |
| Código Procesal Civil y Mercantil | CENADOJ Codigos | — |
| Código Penal | CENADOJ ⚠ vive en Compilación Penal — buscar individual | compilacion |
| Código Procesal Penal | CENADOJ (existe individual 2011; verificar más reciente) | — |
| Código de Comercio | CENADOJ / Registro Mercantil | — |
| Código de Notariado | CENADOJ / CANG | — |
| Código de Trabajo | MINTRAB | — |
| Ley del Organismo Judicial | ✔ URL verificada arriba | — |
| Ley del Organismo Legislativo | Congreso | — |
| Ley del Organismo Ejecutivo | Congreso / SEGEPLAN | — |
| Ley de lo Contencioso Administrativo | Contraloría / Congreso | — |

## Batch 2 — Financiero (Banguat/SIB)

Fuente primaria: Banguat "Leyes Bancarias y Financieras"; SIB normativa como espejo.

Ley Monetaria · Ley de Bancos y Grupos Financieros (✔ URL Contraloría) ·
Ley Orgánica del Banco de Guatemala (✔) · Ley de Supervisión Financiera (✔) ·
Ley de Sociedades Financieras Privadas · Ley de Almacenes Generales de
Depósito · Ley de Actividad Aseguradora · Ley del Mercado de Valores y
Mercancías · Ley de Tarjetas de Crédito · Ley de Libre Negociación de
Divisas · Ley de Garantías Mobiliarias · Ley de Leasing · Ley de los
Contratos de Factoraje y de Descuento · Ley de Insolvencia · Ley contra el
Lavado de Dinero u otros Activos (SIB/IVE) · Ley para Prevenir y Reprimir el
Financiamiento del Terrorismo (SIB/IVE).

⚠ Sociedades Financieras Privadas (Dto-Ley 208, 1964) y Almacenes Generales
(Dto 1746, 1968): pre-1994 → non_canonical, posible escaneo.

## Batch 3 — Tributario (SAT)

Fuente primaria: SAT Legislación Tributaria. Tablas densas → al final del despliegue.

Código Tributario · Ley del IVA · Ley de Actualización Tributaria (ISR) ·
Ley del Impuesto de Solidaridad · Ley del Impuesto Único sobre Inmuebles ·
Ley sobre el Impuesto de Herencias, Legados y Donaciones (1947 ⚠ escaneada) ·
Ley Orgánica de la SAT · Ley Nacional de Aduanas · Ley contra la Defraudación
y Contrabando Aduanero · Disposiciones Legales para el Fortalecimiento de la
Administración Tributaria · Disposiciones para el Fortalecimiento del Sistema
Tributario y el Combate a la Defraudación · Impuesto Bebidas Alcohólicas ·
Impuesto Específico Cemento · Impuesto Petróleo y Combustibles · Impuesto
Bebidas Gaseosas/Isotónicas/Jugos · Ley de Simplificación, Actualización e
Incorporación Tributaria · Ley de Fomento y Desarrollo de la Actividad
Exportadora y de Maquila · Ley de Zonas Francas.

## Batch 4 — Históricos / sin portal especializado (Congreso, Diario CA)

Leyes viejas, alta probabilidad de escaneo → procesar al final, OCR forzado.

Procedimiento Relativo al Hallazgo de Bienes Mostrencos · Ley de Titulación
Supletoria (1979) · Ley de Inquilinato · Ley General de Caza · Ley de
Expropiación (1948) · Ley de Tribunales de Familia (1964) · Ley del Tribunal
de Cuentas · Ley del Tribunal de Conflictos de Jurisdicción · Libro III del
Comercio Marítimo (Código de Comercio 1942) · Ley de Universidades Privadas ·
Ley de Colegiación Profesional Obligatoria · Código de Ética Profesional
(CANG — ⚠ no es decreto del Congreso: normativa gremial) · Ley de Clases
Pasivas Civiles del Estado · Ley de Nacionalidad (1966) · Ley Reguladora de
las Áreas de Reservas Territoriales del Estado.

## Batch 5 — Portales institucionales (administrativo, penal, civil moderno, laboral)

| Sub-bloque | Fuente primaria | Leyes |
|---|---|---|
| Fiscalización/Estado | Contraloría `i_leg_ley` | Ley Orgánica CGC · Probidad y Responsabilidades · Contrataciones del Estado · Ley Orgánica del Presupuesto · Acceso a la Información Pública · Antejuicio · Descentralización · Consejos de Desarrollo · Código Municipal · Comisiones de Postulación · Simplificación de Requisitos y Trámites |
| Penal institucional | MP / IDPP / INACIF / MINGOB (⚠ revisar comentadas en IDPP) | Ley Orgánica del MP · Ley Orgánica del INACIF · Régimen Penitenciario · Servicio Público de Defensa Penal · Protección de Sujetos Procesales · Femicidio · Violencia Sexual y Trata · Violencia Intrafamiliar · Delincuencia Organizada · Narcoactividad · Armas y Municiones · Extinción de Dominio · Extradición · Control Telemático · PINA (Protección Integral Niñez) |
| Civil moderno | RENAP / IGM / CNA / MICIVI / MAGA / MIDES | RENAP · Código de Migración · Adopciones · Vivienda · Aviación Civil · Pesca y Acuicultura · ONGs · Cooperativas (INACOP) · Tercera Edad · Aporte Adulto Mayor · Dignificación de la Mujer |
| Laboral | MINTRAB / ONSEC / IGSS / OJ / Congreso | Servicio Civil · Servicio Municipal · Servicio Civil OJ · Servicio Civil OL · Sindicalización y Huelga · Ley Orgánica IGSS |
| Economía/PI | MINECO / RPI / DIACO / Banguat | Propiedad Industrial · Derecho de Autor · Protección al Consumidor · Fortalecimiento al Emprendimiento · Comunicaciones y Firmas Electrónicas · Registro de Información Catastral (RIC) · Ley Orgánica USAC (USAC) · PGN (Ley Orgánica) |

## Batch 6 — Instrumentos internacionales (WIPO Lex / NORMLEX / OAS)

Numeración no guatemalteca → hint de prompt específico (Fase 2.5.2).

Convenio de París (WIPO Lex) · Convenio de Roma (WIPO Lex) · Clasificación
Internacional de Niza (WIPO — ⚠ es una clasificación, no una ley con
artículos: evaluar si entra al pipeline o se modela aparte) · Convención de
Viena sobre el Derecho de los Tratados (ONU/OAS) · Convenios Fundamentales
de la OIT (NORMLEX — ⚠ son 8-10 convenios: decidir si una entrada por
convenio) · Código de Derecho Internacional Privado / Bustamante (OAS, 1928
⚠ escaneada probable).

---

## Flujo de trabajo de curación

1. El operador (o el arquitecto, vía búsqueda web) localiza la URL del PDF y
   la pega en `laws_manifest.json` (`source_url` + `source_flags`).
2. `uv run python main.py fetch-sources --batch N` descarga, valida y
   registra checksums (Tarea 2.5.4 del ROADMAP).
3. El triaje (Tarea 2.5.2) confirma native/scanned y ajusta expectativas.
4. Cualquier ley cuya única fuente sea comentada/compilación queda en el
   manifiesto con su flag, visible como pendiente-de-mejor-fuente.
