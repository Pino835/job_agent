# Job Agent

Agente que usa la API de Claude (Anthropic) para automatizar parte de la búsqueda de empleo: lee tu CV, busca ofertas relevantes en la web y genera un Excel con puesto, descripción y URL para que apliques manualmente.

No reemplaza el proceso de aplicar, pero elimina el paso de revisar portal por portal manualmente.

## Cómo funciona

1. Colocas tu CV en PDF dentro de la carpeta `cv/`.
2. Corres `agente.py` (directamente o con doble clic en `buscar_empleo.bat`).
3. El script envía tu CV a la API de Claude junto con la herramienta de búsqueda web habilitada. Claude extrae tu perfil, busca ofertas vigentes acordes a ese perfil **y a tu nivel real de experiencia** (nunca te va a sugerir puestos senior si tu CV muestra poca experiencia), y devuelve los resultados.
4. El script guarda esos resultados en `ofertas.json` y ejecuta `build_excel.py`, que genera `Busqueda_Empleo.xlsx`.

## Requisitos

- Una **API key de Anthropic** con fondos/créditos (se obtiene en [console.anthropic.com](https://console.anthropic.com)).
- Python 3 con las dependencias de `requirements.txt`:
  ```
  pip install -r requirements.txt
  ```

## Configuración de la API key

1. Copia `.env.ejemplo` a `.env`:
   ```
   copy .env.ejemplo .env
   ```
2. Abre `.env` y pega tu key:
   ```
   ANTHROPIC_API_KEY=sk-ant-tu-key-real
   ```
3. **Nunca subas `.env` al repo** — ya está excluido en `.gitignore`.

## Uso

1. Clona este repositorio.
2. Coloca tu CV en PDF dentro de `cv/` (revisa `cv/README.md`).
3. Configura tu `.env` (ver arriba).
4. Ejecuta `buscar_empleo.bat` (Windows) o `python agente.py` directamente.
5. Abre `Busqueda_Empleo.xlsx` cuando termine.

## Estructura

```
cv/                    -> coloca aquí tu CV en PDF (no se sube al repo)
agente.py              -> llama a la API de Claude: lee el CV, busca ofertas y guarda ofertas.json
ofertas.ejemplo.json   -> formato esperado de los datos de ofertas
ofertas.json           -> resultados de tu última búsqueda (no se sube al repo)
build_excel.py         -> genera el Excel a partir de ofertas.json
buscar_empleo.bat      -> atajo para ejecutar agente.py con doble clic
.env.ejemplo           -> plantilla de variables de entorno (sin key real)
.env                   -> tu API key real (no se sube al repo)
CLAUDE.md              -> contexto e instrucciones detalladas del proyecto
```

## Costo

Cada ejecución consume créditos de tu API key de Anthropic (llamadas al modelo + uso de la herramienta de búsqueda web). El costo depende de cuántas búsquedas haga el agente por corrida.

## Privacidad

Tu CV, tu API key y los resultados de tus búsquedas (`cv/*.pdf`, `.env`, `ofertas.json`, `Busqueda_Empleo.xlsx`) están excluidos vía `.gitignore` y nunca se suben al repositorio.
