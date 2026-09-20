# Job Agent

Agente que usa Claude Code para automatizar parte de la búsqueda de empleo: lee tu CV, busca ofertas relevantes en portales de empleo y genera un Excel con puesto, descripción y URL para que apliques manualmente.

No reemplaza el proceso de aplicar, pero elimina el paso de revisar portal por portal manualmente.

## Cómo funciona

1. Colocas tu CV en PDF dentro de la carpeta `cv/`.
2. Le pides a Claude Code (en esta carpeta) que ejecute la búsqueda — directamente en el chat, o con doble clic en `buscar_empleo.bat`.
3. Claude Code lee tu CV, busca ofertas acordes a tu perfil **y a tu nivel real de experiencia** (nunca te va a sugerir puestos senior si tu CV muestra poca experiencia), y guarda los resultados en `ofertas.json`.
4. Se ejecuta `build_excel.py`, que genera `Busqueda_Empleo.xlsx` con las ofertas encontradas.

## Requisitos

- [Claude Code](https://claude.com/claude-code) instalado y accesible en el PATH (`claude --version` debe funcionar).
- Python 3 con las dependencias de `requirements.txt`:
  ```
  pip install -r requirements.txt
  ```

## Uso

1. Clona este repositorio.
2. Coloca tu CV en PDF dentro de `cv/` (revisa `cv/README.md`).
3. Ejecuta `buscar_empleo.bat` (Windows) o pídele a Claude Code en el chat: *"Ejecuta el agente de búsqueda de empleo usando el CV en cv/"*.
4. Abre `Busqueda_Empleo.xlsx` cuando termine.

## Estructura

```
cv/                    -> coloca aquí tu CV en PDF (no se sube al repo)
ofertas.ejemplo.json   -> formato esperado de los datos de ofertas
ofertas.json           -> resultados de tu última búsqueda (no se sube al repo)
build_excel.py         -> genera el Excel a partir de ofertas.json
buscar_empleo.bat       -> atajo para lanzar la búsqueda con Claude Code
CLAUDE.md              -> contexto e instrucciones detalladas para Claude Code
```

## Privacidad

Tu CV y los resultados de tus búsquedas (`cv/*.pdf`, `ofertas.json`, `Busqueda_Empleo.xlsx`) están excluidos vía `.gitignore` y nunca se suben al repositorio.
