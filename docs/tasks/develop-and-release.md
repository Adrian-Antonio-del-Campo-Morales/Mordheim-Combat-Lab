# Desarrollar y distribuir

```powershell
python -m pip install -e ".[dev]"
python -m pytest -q
python -m mordheim_combat_lab validate
python -m mordheim_combat_lab verify
```

`verify` admite pendientes; `--require-complete` no. Mida con `benchmark` y construya Windows con `tools\windows\build_MordheimCombatLab_ONEFILE.bat`.

Terminado cuando pasan tests y validación, el estado semántico no retrocede y el paquete contiene la KB pero no especificaciones ni archivo histórico.
