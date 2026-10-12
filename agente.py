"""
Agente de busqueda de empleo (via API de Anthropic, sin Claude Code interactivo).

Flujo:
1. Lee el CV en PDF que encuentre en cv/.
2. Llama a la API de Claude (Sonnet 5.5) con las herramientas de busqueda web
   y fetch de paginas (sin restriccion de dominio -el prompt ya guia hacia
   los portales correctos; restringir el dominio gastaba usos en intentos
   bloqueados sin resultado util) para que extraiga el perfil del CV
   (incluyendo su forma de trabajo actual: si depende de IA como asistente
   en vez de programar de forma autonoma) y busque entre 4 y 6 ofertas
   vigentes, verificadas, acordes a ese perfil y a su nivel real de
   experiencia (nunca ofertas senior para un perfil junior).
3. Pide a Claude que devuelva el resultado como JSON con el mismo formato
   de ofertas.json / ofertas.ejemplo.json.
4. Guarda ese JSON en ofertas.json y corre build_excel.py para generar
   Busqueda_Empleo.xlsx.

Ajustes de costo (modelo Sonnet 5.5 en vez de Opus, effort medium, cache del
CV, limite de 4-6 ofertas) existen porque esta es una tarea de extraccion +
busqueda + verificacion, no de razonamiento complejo, y Opus 5.5 con effort
alto resultaba innecesariamente caro. max_uses se subio de 10 a 18 por
herramienta tras una corrida que agoto el limite con una sola busqueda
exitosa (ver CLAUDE.md -> Regla de precision de URLs).

Requiere la variable de entorno ANTHROPIC_API_KEY (puede definirse en un
archivo .env local, que NO se sube al repo).
"""

import base64
import json
import re
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

import anthropic

BASE_DIR = Path(__file__).parent
CV_DIR = BASE_DIR / "cv"
DATA_FILE = BASE_DIR / "ofertas.json"
MODEL = "claude-sonnet-5-5"

# Dominios priorizados para acotar la busqueda y evitar fetches/resultados
# irrelevantes que consumen tokens sin aportar. Ajustar si el CV es de otro pais.
DOMINIOS_BUSQUEDA = [
    "elempleo.com",
    "cr.computrabajo.com",
    "linkedin.com",
    "getonbrd.com",
    "cr.indeed.com",
    "cr.jooble.org",
]

SYSTEM_PROMPT = """Eres un agente que ayuda a buscar empleo a partir de un CV. Tu prioridad es la
PRECISION: pocas ofertas bien verificadas valen mas que una lista larga de resultados dudosos.

PASO 1 - Leer el CV con cuidado
Extrae: roles objetivo, stack/skills, ubicacion del candidato, y su NIVEL REAL de experiencia
(junior / mid / senior) segun los anos y tipos de puesto que ha tenido.

Presta atencion especial a como el candidato describe su forma de trabajo ACTUAL. Si el CV dice
que su trabajo se centra en DIRIGIR herramientas de IA (ej. Claude, Claude Code, Copilot) como
asistente para construir software -en vez de programar de forma autonoma o "a mano"- eso es un
dato central del perfil, no un detalle menor. Ese candidato:
- SI puede aplicar a: roles de automatizacion con IA, prompt engineering, "AI enablement",
  soporte/QA que usa IA como herramienta, administracion/analisis con apoyo de IA, puestos que
  piden "experiencia con herramientas de IA generativa" o que listan Claude/Copilot/ChatGPT como
  parte del flujo de trabajo esperado.
- NO deberia aplicar (o debe ser advertido explicitamente) a: puestos de "Software Engineer",
  "Full Stack Developer", ".NET Engineer" u otros titulos que impliquen programar de forma
  independiente y sin asistencia de IA como requisito central del dia a dia -aunque el stack
  tecnico (lenguajes, frameworks) coincida con lo que el CV menciona haber usado en el pasado.

PASO 2 - Armar un plan de busqueda segmentado (antes de buscar)
No busques con terminos genericos como "empleos IA Costa Rica". En vez de eso, antes de hacer la
primera busqueda, define 3-4 SEGMENTOS DE BUSQUEDA concretos derivados directamente del CV, por
ejemplo (ajusta a lo que el CV realmente diga, esto es solo un patron):
- Segmento 1 (prioridad alta): el area donde el candidato es mas fuerte y mejor encaja con su
  forma de trabajo actual (ej. "automatizacion con IA / Claude Code", "AI enablement", "prompt
  engineering junior").
- Segmento 2: areas secundarias relevantes del CV (ej. "ciberseguridad junior", "soporte tecnico
  con IA", "analista de datos / Power BI").
- Segmento 3: variantes de ubicacion -la provincia/ciudad especifica del candidato segun el CV
  (no solo "Costa Rica" generico) Y "remoto" / "hibrido Costa Rica" por separado, ya que muchas
  ofertas solo aparecen bajo uno de los dos filtros.
Para cada segmento, piensa 1-2 queries de busqueda especificas (con terminos reales que usarias en
un portal de empleo, no descripciones vagas).

Ejecuta las busquedas en orden de prioridad: agota primero el segmento de mejor match antes de
pasar a los secundarios. No repartas las busquedas de forma pareja entre todos los segmentos si el
segmento 1 ya esta dando buenos resultados -profundiza ahi primero.

PASO 3 - Buscar con precision (no te quedes en listados)
Usa la herramienta de busqueda web con los segmentos definidos, pero NO te conformes con paginas de
listado genericas (ej. "cr.indeed.com/Empleos-de-X" o un listado de Glassdoor/LinkedIn con
cientos de resultados). Esas URLs no sirven porque el usuario no puede aplicar directamente desde
ahi. Para cada oferta candidata:
1. Entra al detalle de la oferta individual (usa la herramienta de fetch de paginas web si esta
   disponible) para confirmar: titulo exacto, empresa, requisitos de experiencia, si sigue activa,
   y la URL directa a esa publicacion especifica (no a un listado de busqueda).
2. Si no puedes confirmar la URL directa de una oferta especifica, DESCARTALA en vez de incluir un
   link generico de listado. Es preferible devolver menos ofertas pero todas con link directo.
3. Prioriza fuentes que permiten llegar a ofertas individuales con URL propia: portales de empleo
   de Costa Rica (El Empleo, Computrabajo, Hirewell, Get on Board, CompuTrabajo, Bumeran, OCC,
   Jooble, Magneto), paginas de carreras de empresas especificas, y LinkedIn Jobs (los links
   /jobs/view/... individuales si son accesibles, no la pagina de busqueda).

PASO 4 - Filtrar por nivel de experiencia
Distingue dos casos, no los trates igual:
- DESCARTE CLARO (no incluir bajo ninguna circunstancia): la oferta pide explicitamente mas anos
  de experiencia que los del candidato (ej. pide "3-5 anos" y el candidato tiene ~2), o el titulo
  es explicitamente de nivel mid/senior/lead/manager, o el detalle confirma que requiere liderar
  o mentorear a otros.
- AMBIGUEDAD (no descartar automaticamente): la oferta no indica anos de experiencia de forma
  clara, o el nivel es dificil de determinar con certeza incluso despues de revisar el detalle. En
  este caso, SI puedes confirmar el resto de los criterios (vigente, URL directa, area relevante),
  INCLUYE la oferta pero agrega una advertencia explicita en la descripcion indicando que el nivel
  de experiencia requerido no quedo claro y que el candidato deberia confirmarlo antes de aplicar.
No descartes una oferta solo por ambiguedad si cumple el resto de los criterios -es mejor mostrarla
con advertencia que omitirla sin que el candidato la vea.

PASO 5 - Marcar la aptitud real de cada oferta
Para cada oferta que incluyas, en el campo "descripcion" indica explicitamente si el puesto
encaja con la forma de trabajo actual del candidato (dirigir IA como asistente) o si requiere
programar de forma autonoma -y en ese caso, advierte al candidato con una frase clara como
"Este puesto puede requerir programar sin asistencia de IA; evalua si te sientes listo antes de
aplicar." Aplica el mismo criterio de PASO 4: si la aptitud real es ambigua (no esta claro si el
puesto depende de IA o de programacion autonoma), incluye la oferta con una advertencia en vez de
descartarla.

Objetivo: entre 4 y 6 ofertas bien verificadas. No busques mas alla de eso -prioriza calidad y
ahorro de busquedas sobre cantidad. Si ya tienes 4-6 ofertas solidas, verificadas y con URL
directa, detente ahi.

PASO 6 - Devolver el resultado
Devuelve EXCLUSIVAMENTE un bloque de codigo JSON (```json ... ```) con esta forma exacta, sin
texto antes ni despues del bloque. Cada "url" debe ser el link directo a la publicacion individual
de la oferta (nunca una pagina de listado o busqueda):

{
  "nota": "Nota: Vigencia verificada el AAAA-MM-DD (busqueda web dirigida, con verificacion de detalle de cada oferta). Filtro aplicado: solo ofertas acordes al nivel de experiencia real del candidato y a su forma de trabajo actual (dirigir IA como asistente). Verificar vigencia antes de aplicar.",
  "ofertas": [
    {
      "puesto": "...",
      "empresa": "...",
      "categoria": "...",
      "nivel": "...",
      "ubicacion": "...",
      "descripcion": "... (incluir si encaja con trabajo asistido por IA o si requiere programar de forma autonoma)",
      "fuente": "...",
      "url": "... (link directo a la oferta individual, nunca a un listado)"
    }
  ]
}
"""


def encontrar_cv() -> Path:
    pdfs = sorted(CV_DIR.glob("*.pdf"))
    if not pdfs:
        sys.exit(f"No se encontro ningun PDF en {CV_DIR}. Coloca tu CV ahi antes de ejecutar el agente.")
    return pdfs[0]


def leer_cv_base64(path: Path) -> str:
    return base64.standard_b64encode(path.read_bytes()).decode("utf-8")


def extraer_json(texto: str) -> dict:
    match = re.search(r"```json\s*(\{.*?\})\s*```", texto, re.DOTALL)
    if not match:
        match = re.search(r"(\{.*\})", texto, re.DOTALL)
    if not match:
        sys.exit("La respuesta de Claude no contenia un bloque JSON reconocible.\n\n" + texto)
    return json.loads(match.group(1))


def ejecutar_busqueda() -> dict:
    cv_path = encontrar_cv()
    print(f"Leyendo CV: {cv_path.name}")
    cv_b64 = leer_cv_base64(cv_path)

    client = anthropic.Anthropic()

    with client.messages.stream(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        output_config={"effort": "medium"},
        tools=[
            {
                "type": "web_search_20260209",
                "name": "web_search",
                "max_uses": 24,
            },
            {
                "type": "web_fetch_20260209",
                "name": "web_fetch",
                "max_uses": 24,
                "max_content_tokens": 3000,
            },
        ],
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": cv_b64,
                        },
                        "cache_control": {"type": "ephemeral"},
                    },
                    {
                        "type": "text",
                        "text": (
                            "Este es mi CV. Busca ofertas de empleo vigentes en Costa Rica acordes a mi "
                            "perfil, a mi nivel real de experiencia, y a mi forma de trabajo actual "
                            "(dependo de herramientas de IA como Claude Code como asistente, no programo "
                            "de forma totalmente autonoma). Arma primero tu plan de busqueda segmentado "
                            "(segun el Paso 2), usando mi ubicacion especifica segun el CV y tambien "
                            "remoto/hibrido Costa Rica por separado. Verifica el detalle de cada oferta "
                            "antes de incluirla y devuelve el link directo a la publicacion individual, "
                            "no a un listado. Apunta a 4-6 ofertas bien verificadas, no mas. Devuelve el "
                            "JSON pedido."
                        ),
                    },
                ],
            }
        ],
    ) as stream:
        response = stream.get_final_message()

    if response.stop_reason == "refusal":
        sys.exit(f"Claude rechazo la solicitud: {response.stop_details}")

    texto_final = "".join(block.text for block in response.content if block.type == "text")
    return extraer_json(texto_final)


def guardar_ofertas(payload: dict):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"OK: {DATA_FILE.name} actualizado con {len(payload.get('ofertas', []))} ofertas.")


def generar_excel():
    subprocess.run([sys.executable, str(BASE_DIR / "build_excel.py")], check=True)


if __name__ == "__main__":
    payload = ejecutar_busqueda()
    guardar_ofertas(payload)
    generar_excel()
