# PENDING.md — Leyes no resueltas en la corrida inicial

Seguimiento de las 5 leyes del manifiesto que no quedaron con un PDF de
texto seleccionable en `corpus/` tras la corrida inicial de los 6 batches
(116/121 = 95.9%, ver `README.md`). Las causas están verificadas contra
`logs/reporte_batch_*.json` y, donde aplica, contra el JSON de metadata
real en `corpus/`; no se reproducen aquí afirmaciones que no estén
respaldadas por esos archivos.

| Ley | Batch | Causa | Resolución sugerida |
|---|---|---|---|
| Procedimiento Relativo al Hallazgo de Bienes Mostrencos | 4 | La búsqueda web (Fase 2) no devolvió ningún candidato descargable (`razon: null`, sin URLs evaluadas). El log no registra qué fuentes consideró o descartó el modelo antes de devolver una lista vacía. | Buscar la fuente manualmente y, si solo existe en HTML, copiar el texto a mano o convertirlo a PDF con texto seleccionable antes de añadir una `url_conocida` al manifiesto. |
| Ley Reguladora de las Áreas de Reservas Territoriales del Estado | 4 | Todos los candidatos que devolvió la búsqueda web tenían texto pero fueron rechazados por el detector de ediciones comentadas (`razon: solo_fuentes_comentadas`). El log no conserva los dominios de esos candidatos. | Buscar específicamente una edición no comentada (por ejemplo, directamente en `congreso.gob.gt` o en el portal de OCRET si publica el decreto) en vez de depender de la búsqueda web genérica. |
| Ley de Nacionalidad | 4 | Se descargó un candidato (Decreto 1613, 1966, vía `congreso.gob.gt/assets/uploads/info_legislativo/decretos/1966/gtdcx16131966.pdf`) que pasó la validación de "único disponible" pero no tiene texto seleccionable: es un escaneo de 4 páginas. Confirmado contra `corpus/decreto_86_1996_ley_de_nacionalidad.json` (`"tiene_texto": false`). | Aplicar OCR (p. ej. con `tesseract`) sobre el PDF ya descargado en `corpus/`. |
| Ley de lo Contencioso Administrativo | 1B | Se descargó el Decreto 119-96 (`congreso.gob.gt/assets/uploads/info_legislativo/decretos/1996/gtdcx119-1996.pdf`), también un escaneo sin texto seleccionable (4 páginas). Confirmado contra `corpus/decreto_98_1997_ley_de_lo_contencioso_administrativo.json` (`"tiene_texto": false`). | Aplicar OCR sobre el PDF ya descargado, o reintentar la búsqueda priorizando una fuente alternativa con texto seleccionable antes de aceptar el escaneo de Congreso. |
| Propiedad Industrial | 5 | Se descargó el Decreto 57-2000 (`congreso.gob.gt/assets/uploads/info_legislativo/decretos/2000/gtdcx00572000.pdf`), un escaneo de 14 páginas sin texto seleccionable. Confirmado contra `corpus/decreto_11_2006_propiedad_industrial.json` (`"tiene_texto": false`). Ningún PDF del corpus actual proviene de `portal.rpi.gob.gt` (ver `docs/SOURCES.md`). | Aplicar OCR sobre el PDF ya descargado, o buscar la ley directamente en WIPO Lex (ancla ya verificada para el batch 6 de instrumentos internacionales) como fuente alternativa con texto seleccionable. |

## Cómo se verificó cada causa

- Las columnas "Causa" para Ley de Nacionalidad, Ley de lo Contencioso
  Administrativo y Propiedad Industrial están confirmadas leyendo el JSON
  de metadata correspondiente en `corpus/`, que registra `url_fuente`,
  `paginas` y `tiene_texto` para el PDF efectivamente guardado.
- Las columnas "Causa" para Bienes Mostrencos y Áreas de Reservas
  Territoriales se basan únicamente en el campo `razon` del reporte de
  batch (`logs/reporte_batch_4_*.json`); ese campo es lo único que
  `agent.py` persiste sobre por qué una ley quedó pendiente — no guarda
  las URLs de los candidatos rechazados ni el texto de la respuesta de
  Claude en la Fase 2.
