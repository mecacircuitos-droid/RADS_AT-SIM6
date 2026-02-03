# RADS-AT Simulator (Bell 412 – Tracking & Balance)

Este proyecto es una **simulación** del flujo de trabajo del RADS-AT con una UI tipo CADU (LCD + teclado). Está pensado para practicar:

- **MEASURE**: seleccionar tipo de aeronave, introducir matrícula (tail number), elegir plan de vuelo, elegir test state y lanzar la adquisición.
- **DISPLAY**: ver resultados (track y vibración) de las adquisiciones simuladas.
- **DIAGS**: generar sugerencias de corrección (reglas simples de simulación).
- **MANAGER**: estado de la sesión y reset.

> Nota: Los valores y correcciones son **didácticos**/simulados, no buscan sustituir procedimientos reales.

---

## Ejecutar

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate

pip install -r requirements.txt
streamlit run app.py
```

---

## Navegación rápida

- **F1** → MEASURE
- **F2** → DISPLAY
- **F3** → DIAGS
- **F4** → MANAGER
- **▲/▼** → mover selección
- **DO** → entrar/aceptar
- **QUIT** → volver / limpiar (en MEASURE)

---

## Estructura del código

- `rads/core.py` → modelo de estado, LCD y teclas
- `rads/ui/` → render del dispositivo y helpers
- `rads/menus/measurement.py` → flujo completo de MEASURE
- `rads/menus/display.py` → pantallas de resultados
- `rads/menus/diags.py` → sugerencias de corrección
- `rads/menus/manager.py` → utilidades de sesión
- `rads/models/` → simulación y reglas de diagnóstico

---

## Siguiente paso

Cuando quieras, en **MEASURE** podemos:
- ajustar la lista exacta de flight plans / test states del Bell 412 que estés usando,
- añadir más pantallas intermedias (por ejemplo “Setup Wizard”, “Acquire Progress”, “Next test required”, etc.),
- y hacer que **DISPLAY** y **DIAGS** se parezcan todavía más al original.
