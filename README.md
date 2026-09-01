# Mordheim Combat Lab

Simulador de duelos cuerpo a cuerpo 1 contra 1 basado en una base de conocimiento versionada. La aplicación activa usa el motor vectorizado para los análisis y dispone de un motor modular escalar para reproducir y verificar reglas por fases.

## Empezar

Requiere Python 3.10 o posterior.

```powershell
python -m pip install -e ".[dev]"
python -m mordheim_combat_lab
```

```powershell
python -m mordheim_combat_lab ui
python -m mordheim_combat_lab validate
python -m mordheim_combat_lab verify
python -m mordheim_combat_lab audit
python -m mordheim_combat_lab benchmark -n 500000
python -m pytest -q
```

`validate` comprueba estructura y conexiones. `verify` ejecuta evidencia semántica independiente; `verify --require-complete` es la puerta estricta. `audit` genera en `outputs/audit/` un CSV con scope, implementación y evidencia por regla. El informe ejecutable, no una cifra copiada aquí, es la fuente del estado actual.

## Mapa del proyecto

- `sources/knowledge/`: reglas y datos consumidos por el runtime.
- `specs/`: contrato estructural, escenarios e interacciones de verificación.
- `domain/`: tipos y composición pura; `knowledge/` y `construction/`: carga y compilación.
- `combat/`: fases, motor modular y motor vectorizado.
- `verification/`: auditorías fuera del runtime de la UI.
- `application/`, `persistence/` y `ui/`: casos de uso, formatos y Tkinter.
- `archive/`: código histórico no mantenido ni empaquetado.

Consulte [la arquitectura](docs/architecture.md) y [las guías de tareas](docs/README.md).

## Distribución en Windows

```powershell
tools\windows\build_MordheimCombatLab_ONEFILE.bat
```

Incluye la aplicación activa y `sources/knowledge/`, pero no `specs/` ni `archive/`.
