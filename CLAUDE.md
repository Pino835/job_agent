# Agente de Búsqueda de Empleo

Agente genérico para automatizar (parcialmente) la búsqueda de empleo a partir de un CV en PDF, reduciendo el tiempo de revisar portales uno por uno manualmente.

Este proyecto está diseñado para funcionar con **cualquier CV**, no solo el del autor original. El perfil de búsqueda se deriva del PDF que el usuario coloque en `cv/`, no está hardcodeado en el código.

**Arquitectura:** el agente llama directamente a la API de Anthropic (`agente.py`, vía el SDK `anthropic` + `ANTHROPIC_API_KEY`), no depende de una sesión interactiva de Claude Code. Esto se decidió explícitamente porque el usuario ya tenía una API key de Anthropic con fondos y prefería que el proyecto la usara en vez de requerir Claude Code instalado/autenticado en la máquina de cada usuario que clone el repo.

## Objetivo

1. Leer el CV en PDF que se encuentre en la carpeta `cv/`.
2. Enviarlo a la API de Claude (modelo `claude-sonnet-5-5`) junto con las herramientas de búsqueda web (`web_search_20260209`) y fetch de páginas (`web_fetch_20260209`) habilitadas, acotadas a `DOMINIOS_BUSQUEDA`.
3. Claude extrae el perfil del candidato (roles objetivo, stack/skills, nivel de experiencia real, **forma de trabajo actual**), arma un **plan de búsqueda segmentado** (3-4 segmentos priorizados derivados del CV, con ubicación específica + remoto/híbrido por separado) y busca ofertas de empleo vigentes acordes a ese perfil, verificando el detalle de cada oferta individual (no solo listados).
4. Claude devuelve los resultados como JSON (mismo formato que `ofertas.ejemplo.json`), que el script guarda en `ofertas.json`.
5. El script ejecuta `build_excel.py` para generar `Busqueda_Empleo.xlsx` (puesto, empresa, categoría, nivel, ubicación/modalidad, descripción, fuente, URL) para que el usuario aplique manualmente.

## Regla de nivel de experiencia (importante)

**Nunca incluir ofertas cuyo nivel de seniority requerido supere el nivel real del candidato indicado en su CV**, aunque el título o stack coincida bien con el perfil.

- Esta regla está codificada directamente en el `SYSTEM_PROMPT` de `agente.py` — si se reescribe ese prompt, hay que preservar esta instrucción explícitamente.
- Priorizar palabras clave acordes al nivel real (ej. para perfiles junior: "junior", "trainee", "entry-level", "practicante", "intern", "L1", "sin experiencia previa requerida", "1-2 años").
- Si una oferta no indica años de experiencia, verificar el detalle antes de incluirla — no asumir el nivel solo por el título.
- El Excel siempre incluye una columna **"Nivel"** indicando el nivel de seniority detectado, para que el usuario pueda confirmarlo de un vistazo.
- Antecedente: en una corrida anterior (con el CV de referencia de este proyecto, que muestra experiencia limitada) se incluyeron por error ofertas senior; el usuario pidió retirarlas y reemplazarlas por opciones junior/entry-level verificadas. Desde entonces el filtro por nivel es obligatorio en cada corrida, y ahora vive en el prompt del sistema, no en instrucciones ad-hoc por conversación.

## Regla de forma de trabajo actual (importante, distinta del nivel de experiencia)

**El nivel de experiencia (junior/mid/senior) no es suficiente para filtrar correctamente.** Un candidato puede tener experiencia "junior" en años pero depender de herramientas de IA (ej. Claude Code) como asistente para programar, en vez de programar de forma totalmente autónoma. Esto es un eje de filtrado aparte:

- Si el CV describe que el candidato dirige/usa IA generativa como parte central de su flujo de trabajo actual (no solo como herramienta ocasional), el agente debe distinguir entre ofertas que encajan con ese modo de trabajo (automatización con IA, prompt engineering, AI enablement, soporte/QA con IA, roles que explícitamente mencionan herramientas de IA generativa) y ofertas que requieren programar de forma independiente como requisito central (Software Engineer, Full Stack Developer genérico, etc.), aunque el stack técnico coincida.
- Para las segundas, el agente debe o bien excluirlas, o bien incluirlas con una advertencia explícita en el campo `descripcion` (ej. "Este puesto puede requerir programar sin asistencia de IA; evalúa si te sientes listo antes de aplicar.").
- Antecedente: en la segunda corrida con API directa, el agente incluyó ofertas de ".NET Engineer" y "Full Stack Developer" que pedían programar de forma autónoma — no encajaban con la forma de trabajo real del usuario (depende de Claude Code como asistente). El usuario lo señaló explícitamente y se agregó esta regla al `SYSTEM_PROMPT` (Paso 1 y Paso 4 del prompt).

## Regla de precisión de URLs (importante)

**Las URLs deben apuntar a la publicación individual de la oferta, nunca a una página de listado o búsqueda genérica** (ej. `cr.indeed.com/Empleos-de-X` o un listado de Glassdoor con cientos de resultados no sirven — el usuario no puede aplicar directamente desde ahí).

- El agente debe usar la herramienta `web_fetch` para entrar al detalle de cada oferta candidata y confirmar: título exacto, requisitos, vigencia, y la URL directa.
- Si no se puede confirmar una URL directa, la oferta debe descartarse en vez de incluirse con un link genérico — menos ofertas pero todas accionables es mejor que una lista larga inútil.
- Antecedente: en la segunda corrida, el agente devolvió URLs de listados genéricos porque se quedó sin usos de `web_search` (`max_uses: 15`) antes de verificar el detalle de cada oferta. Se subió el límite a `max_uses: 30` en ambas herramientas y se añadió `web_fetch_20260209` explícitamente para resolver esto (luego bajado a 10/10 por costo — ver sección de optimización de costos).
- **Antecedente 2 — `allowed_domains` fue contraproducente:** tras agregar la segmentación de búsqueda (abajo) y bajar `max_uses` a 10, una corrida devolvió **0 ofertas** — la nota del propio agente explicó que "la herramienta de búsqueda agotó su límite de uso después de una sola consulta exitosa" y que `web_fetch` no pudo abrir ninguna página. Causa: `allowed_domains` (aplicado tanto a `web_search` como a `web_fetch`) bloqueaba intentos sobre dominios fuera de la lista, y cada intento bloqueado consumía igual un "uso" del contador de `max_uses` sin producir resultado. Combinado con el plan de 3-4 segmentos (6-8 queries planeadas) más fetches de verificación, el presupuesto se agotó casi de inmediato. **Solución aplicada:** se quitó `allowed_domains` por completo (el prompt ya guía al modelo hacia los portales correctos sin necesidad de bloquear el resto) y se subió `max_uses` de 10 a 18 en ambas herramientas — un punto medio entre el 30 original (caro) y el 10 que resultó insuficiente una vez sumada la segmentación.
- **Antecedente 3 — filtro demasiado estricto con ambigüedad, y presupuesto aún corto:** con `max_uses: 18` y sin `allowed_domains`, una corrida sí llegó a verificar 9 ofertas candidatas (el agente ya no se quedaba sin presupuesto de inmediato), pero descartó TODAS — algunas por motivos claros (pedían 3-5 años, nivel mid/senior, expiradas/cerradas), pero al menos una (QA Analyst en Zaelot) fue descartada solo por "no indicar seniority claro", y otra (AI Automation Engineer en Blupax) quedó sin revisar por falta de presupuesto. Dos causas distintas reforzándose: (1) el Paso 4 original trataba "ambigüedad de nivel" igual que "descarte claro", perdiendo ofertas potencialmente válidas; (2) 18 seguía siendo insuficiente para el volumen de verificación del plan de 3 segmentos. **Solución aplicada:** el Paso 4 ahora distingue explícitamente DESCARTE CLARO (pide más años de los que tiene el candidato, título mid/senior/lead — nunca incluir) de AMBIGÜEDAD (nivel no está claro ni siquiera tras revisar el detalle — incluir igual, pero con advertencia explícita en la descripción). La regla de precisión de URL directa se mantiene estricta sin excepción (eso sí es un descarte obligatorio si no se puede confirmar). `max_uses` subió de 18 a 24 en ambas herramientas.

## Regla de segmentación de búsqueda (importante, afecta precisión bajo presupuesto bajo de `max_uses`)

**El agente no debe buscar con términos genéricos ("empleos IA Costa Rica").** Con `max_uses` bajo (10 por herramienta, ver optimización de costos), cada búsqueda desperdiciada en un término vago reduce directamente cuántas ofertas se pueden verificar bien.

- Antes de la primera búsqueda, el `SYSTEM_PROMPT` (Paso 2) pide al modelo armar un **plan de búsqueda segmentado**: 3-4 segmentos concretos derivados del CV (ej. área de mejor match primero, luego áreas secundarias, luego variantes de ubicación), cada uno con 1-2 queries específicas en vez de una búsqueda ambigua.
- La ubicación debe segmentarse explícitamente: la provincia/ciudad específica del candidato según el CV **y** "remoto"/"híbrido Costa Rica" por separado, ya que muchas ofertas solo aparecen bajo uno de los dos filtros.
- El orden de ejecución debe priorizar el segmento de mejor match — si ya está dando buenos resultados, profundizar ahí antes de repartir búsquedas de forma pareja entre todos los segmentos.
- Motivo: el usuario pidió explícitamente que la búsqueda fuera "más segmentada" y considerara su CV de forma más específica (no términos genéricos), después de notar que el agente podía mejorar la precisión con las pocas búsquedas disponibles bajo el presupuesto de costos ajustado.

## Modo de ejecución

**Bajo demanda** (no programado/automático). El usuario dispara la búsqueda de dos formas:

1. Ejecutando `python agente.py` directamente.
2. Ejecutando `buscar_empleo.bat` (doble clic en Windows), que corre `py agente.py` en la carpeta del proyecto.

Ambas requieren que `ANTHROPIC_API_KEY` esté definida en `.env` (ver `.env.ejemplo`).

## Estructura del proyecto

- `cv/` — carpeta donde el usuario coloca su CV en PDF. **Excluida de git** (`.gitignore`) porque contiene datos personales. Incluye `cv/README.md` con instrucciones.
- `agente.py` — script que llama a la API de Anthropic: lee el primer PDF que encuentra en `cv/`, lo envía junto con el `SYSTEM_PROMPT` y las herramientas `web_search_20260209` + `web_fetch_20260209` (acotadas a `DOMINIOS_BUSQUEDA`, `max_uses: 10` cada una, `max_content_tokens: 3000` en el fetch), parsea el JSON de la respuesta, lo guarda en `ofertas.json` y ejecuta `build_excel.py`. Modelo `claude-sonnet-5-5`, `effort: medium`, CV cacheado con `cache_control`.
- `build_excel.py` — script Python (openpyxl) **genérico**: lee `ofertas.json` y genera `Busqueda_Empleo.xlsx` con formato consistente. No contiene datos hardcodeados de ningún candidato. Se puede ejecutar de forma independiente si `ofertas.json` ya existe.
- `ofertas.ejemplo.json` — plantilla del formato esperado de datos (sí se sube al repo, sin datos reales).
- `ofertas.json` — resultados de la búsqueda más reciente, generado por `agente.py`. **Excluido de git** porque contiene datos derivados del CV personal del usuario.
- `Busqueda_Empleo.xlsx` — salida generada a partir de `ofertas.json`. **Excluido de git** por la misma razón.
- `buscar_empleo.bat` — atajo para ejecutar `agente.py` con doble clic en Windows.
- `.env.ejemplo` — plantilla de variables de entorno (sin key real). Sí se sube al repo.
- `.env` — contiene la `ANTHROPIC_API_KEY` real del usuario. **Excluido de git.**
- `.gitignore` — excluye `cv/*.pdf`, `ofertas.json`, `Busqueda_Empleo.xlsx`, `.env` para que ningún dato personal ni credencial se suba al repositorio.
- `requirements.txt` — dependencias: `openpyxl`, `anthropic`, `pypdf`, `python-dotenv`.
- `CLAUDE.md` — este archivo.

## Cómo ejecutar una búsqueda nueva

1. Colocar el CV en PDF dentro de `cv/` (si aún no está).
2. Confirmar que `.env` tiene una `ANTHROPIC_API_KEY` válida.
3. Ejecutar `python agente.py` (o doble clic en `buscar_empleo.bat`).
4. El script se encarga de todo: lee el CV, busca, guarda `ofertas.json`, genera el Excel. Confirmar que `Busqueda_Empleo.xlsx` se regeneró correctamente (el script imprime cuántas ofertas incluyó).

### Regenerar solo el Excel (sin volver a buscar)

Si `ofertas.json` ya existe y solo se quiere regenerar el Excel (p. ej. tras editar `ofertas.json` a mano):

```
py build_excel.py
```

## Decisiones y contexto relevante

- El proyecto se hizo público en GitHub (`github.com/Pino835/job_agent`) para funcionar como plantilla reutilizable con cualquier CV, no solo el del autor original — por eso los datos personales y de búsqueda se separaron del código.
- El CV de referencia usado durante el desarrollo pertenece a un perfil orientado a IA/Automatización/Prompt Engineering (dirigir Claude Code como diferenciador) y Ciberseguridad junior, con experiencia limitada — de ahí que el filtro de nivel de experiencia sea una regla central del proyecto, no un detalle opcional.
- **Cambio de arquitectura (de Claude Code interactivo a API directa):** la primera versión del proyecto usaba `buscar_empleo.bat` para abrir una sesión de Claude Code con un prompt predefinido. Se migró a llamar directamente a la API de Anthropic (`agente.py`) porque el usuario ya tenía una API key con fondos propios y prefería no depender de tener Claude Code instalado/autenticado. Esto hace que el proyecto sea más portable para quien clone el repo (solo necesita Python + una API key), a cambio de que cada corrida consuma créditos de esa key directamente.
- La API key se gestiona vía `.env` (cargado con `python-dotenv`), nunca hardcodeada ni pasada por el chat — se pidió al usuario que la pegara directamente en el archivo con un editor de texto, no en la conversación.

## Optimización de costos (importante)

Esta tarea (leer un CV, buscar ofertas, verificar detalles, devolver JSON) es extracción + búsqueda + verificación, no razonamiento de frontera — no justifica el modelo ni el esfuerzo más caros disponibles. Configuración actual en `agente.py`:

- **Modelo:** `claude-sonnet-5-5` (no Opus) — mitad de precio por token, suficiente para esta tarea.
- **Effort:** `medium` (no `high`) — el filtrado ya está bien especificado en el prompt, no requiere razonamiento profundo adicional.
- **`max_uses`:** 10 en `web_search` y 10 en `web_fetch` (antes 30/30) — evita exploración excesiva; el prompt pide explícitamente 4-6 ofertas, no "todas las que encuentres".
- **`allowed_domains` (`DOMINIOS_BUSQUEDA`):** acota la búsqueda a portales de empleo conocidos (elempleo.com, Computrabajo, LinkedIn, Get on Board, Indeed CR, Jooble CR) en vez de dejar que el modelo explore libremente — reduce fetches irrelevantes. Ajustar esta lista si el CV es de otro país.
- **`max_content_tokens: 3000`** en `web_fetch` — una oferta de empleo no necesita el HTML completo de la página, con un resumen de ~3000 tokens alcanza para extraer título/requisitos/URL.
- **`cache_control` en el documento del CV** — si se corre el agente varias veces en la misma sesión/día, el PDF no cambia; cachearlo evita pagar su costo completo en cada corrida repetida.
- **Objetivo explícito de 4-6 ofertas** en el prompt — limita cuánto "explora" el modelo antes de decidir que ya tiene suficiente.

Si en el futuro se nota que el resultado pierde calidad con esta configuración (muy pocas ofertas, URLs incorrectas, etc.), subir primero `max_uses` antes que el modelo o el effort — normalmente el cuello de botella es cuántas búsquedas/fetches tiene disponibles, no la capacidad del modelo.

## Pendiente / posibles mejoras futuras

- Evaluar si automatizar la ejecución periódica (scheduler) tiene sentido más adelante; por ahora se prefirió modo bajo demanda.
- Si algún portal bloquea la herramienta de búsqueda web del modelo, considerar instrucciones adicionales en el `SYSTEM_PROMPT` para alternar de fuente, o ajustar `DOMINIOS_BUSQUEDA`.
- Agregar manejo de errores más granular en `agente.py` (p.ej. reintentos si `extraer_json` falla por una respuesta mal formada).
- Considerar agregar un modo "dry run" que no gaste tokens de la API para pruebas de la parte de generación del Excel (ya cubierto parcialmente por poder correr `build_excel.py` solo).
