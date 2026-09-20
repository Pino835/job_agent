# Agente de Búsqueda de Empleo

Agente genérico para automatizar (parcialmente) la búsqueda de empleo a partir de un CV en PDF, reduciendo el tiempo de revisar portales uno por uno manualmente.

Este proyecto está diseñado para funcionar con **cualquier CV**, no solo el del autor original. El perfil de búsqueda se deriva del PDF que el usuario coloque en `cv/`, no está hardcodeado en el código.

## Objetivo

1. Leer el CV en PDF que se encuentre en la carpeta `cv/`.
2. Extraer el perfil del candidato: roles objetivo, stack/skills, nivel de experiencia real (junior/mid/senior).
3. Buscar ofertas de empleo relacionadas usando búsqueda web dirigida (WebSearch/WebFetch).
4. Guardar los resultados en `ofertas.json` (ver formato en `ofertas.ejemplo.json`).
5. Ejecutar `build_excel.py` para generar `Busqueda_Empleo.xlsx` (puesto, empresa, categoría, nivel, ubicación/modalidad, descripción, fuente, URL) para que el usuario aplique manualmente.

## Regla de nivel de experiencia (importante)

**Nunca incluir ofertas cuyo nivel de seniority requerido supere el nivel real del candidato indicado en su CV**, aunque el título o stack coincida bien con el perfil.

- Al buscar y filtrar resultados, priorizar explícitamente palabras clave acordes al nivel real (ej. para perfiles junior: "junior", "trainee", "entry-level", "practicante", "intern", "L1", "sin experiencia previa requerida", "1-2 años").
- Si una oferta no indica años de experiencia, **verificar el detalle de la oferta (WebFetch) antes de incluirla** — no asumir el nivel solo por el título.
- Incluir siempre una columna **"Nivel"** en el Excel indicando el nivel de seniority detectado, para que el usuario pueda confirmarlo de un vistazo.
- Antecedente: en una corrida anterior (con el CV de referencia de este proyecto, que muestra experiencia limitada) se incluyeron por error ofertas senior; el usuario pidió retirarlas y reemplazarlas por opciones junior/entry-level verificadas. Desde entonces el filtro por nivel es obligatorio en cada corrida.

## Portales priorizados

- Portales locales del país del candidato (ej. elempleo.com, Computrabajo) — ajustar según el CV.
- Computrabajo — **nota:** ha bloqueado WebFetch en pruebas realizadas (devuelve contenido vacío); si sigue fallando, omitir o buscar vía WebSearch en vez de fetch directo.
- LinkedIn Jobs — buena cobertura pero WebFetch solo trae ~10 resultados por página/búsqueda; puede ser necesario paginar o refinar la query.
- Fuentes adicionales cuando aportan valor: Get on Board (getonbrd.com, buen fit para roles remotos LatAm), otros portales regionales (verificar vigencia, las ofertas pueden expirar rápido).

## Modo de ejecución

**Bajo demanda** (no programado/automático). El usuario dispara la búsqueda de dos formas:

1. Pidiéndolo directamente en una conversación con Claude Code.
2. Ejecutando `buscar_empleo.bat` (doble clic), que abre Claude Code en esta carpeta con el prompt de búsqueda ya preparado (lee el CV desde `cv/`, actualiza `ofertas.json` y regenera el Excel).

## Estructura del proyecto

- `cv/` — carpeta donde el usuario coloca su CV en PDF. **Excluida de git** (`.gitignore`) porque contiene datos personales. Incluye `cv/README.md` con instrucciones.
- `build_excel.py` — script Python (openpyxl) **genérico**: lee `ofertas.json` y genera `Busqueda_Empleo.xlsx` con formato consistente. No contiene datos hardcodeados de ningún candidato.
- `ofertas.ejemplo.json` — plantilla del formato esperado de datos (sí se sube al repo, sin datos reales).
- `ofertas.json` — resultados de la búsqueda más reciente, generado en cada corrida. **Excluido de git** porque contiene datos derivados del CV personal del usuario.
- `Busqueda_Empleo.xlsx` — salida generada a partir de `ofertas.json`. **Excluido de git** por la misma razón.
- `buscar_empleo.bat` — lanza Claude Code con el prompt de búsqueda predefinido (genérico, no menciona un CV específico).
- `.gitignore` — excluye `cv/*.pdf`, `ofertas.json` y `Busqueda_Empleo.xlsx` para que ningún dato personal se suba al repositorio.
- `CLAUDE.md` — este archivo.

## Cómo ejecutar una búsqueda nueva

1. Colocar el CV en PDF dentro de `cv/` (si aún no está).
2. Leer el CV y extraer perfil (roles, skills, nivel de experiencia).
3. Buscar ofertas vigentes con WebSearch/WebFetch según el perfil y los portales de arriba, aplicando siempre el filtro de nivel de experiencia.
4. Escribir/actualizar `ofertas.json` con el mismo formato que `ofertas.ejemplo.json` (incluir campo `nota` con fecha de verificación de vigencia).
5. Ejecutar: `py build_excel.py` (requiere `openpyxl`; instalar con `py -m pip install openpyxl` si falta).
6. Confirmar que `Busqueda_Empleo.xlsx` se regeneró correctamente (el script imprime cuántas ofertas incluyó).

## Decisiones y contexto relevante

- El proyecto se hizo público en GitHub (`github.com/Pino835/job_agent`) para funcionar como plantilla reutilizable con cualquier CV, no solo el del autor original — por eso los datos personales y de búsqueda se separaron del código.
- El CV de referencia usado durante el desarrollo pertenece a un perfil orientado a IA/Automatización/Prompt Engineering (dirigir Claude Code como diferenciador) y Ciberseguridad junior, con experiencia limitada — de ahí que el filtro de nivel de experiencia sea una regla central del proyecto, no un detalle opcional.
- No existe scraping automatizado programado: cada corrida requiere invocar a Claude explícitamente (por conversación o vía el `.bat`), ya que la búsqueda depende del razonamiento de Claude sobre los resultados, no de un pipeline fijo.

## Pendiente / posibles mejoras futuras

- Evaluar si automatizar la ejecución periódica (scheduler) tiene sentido más adelante; por ahora se prefirió modo bajo demanda.
- Si Computrabajo sigue bloqueando el acceso, considerar alternativas (RSS si existe, o buscar vía WebSearch con `site:` del portal).
- Revisar si conviene separar el flujo en "búsqueda" (genera `ofertas.json`) y "regeneración de Excel" (`build_excel.py`) como comandos/skills independientes e invocables por separado.
- Considerar agregar un `requirements.txt` (openpyxl) para facilitar el setup a otros usuarios que clonen el repo.
