# Verificar reglas

1. Consulte `python -m mordheim_combat_lab verify --inventory`.
2. Añada en `specs/semantic/` fuente, interpretación, categoría, casos, interacción y huellas revisadas.
3. Cubra activación, no activación, límites y consumo; use mini-secuencias solo para estado o flujo.
4. Declare dados y decisiones exactos; use fracciones para distribuciones.
5. Añada una mutación detectada por comportamiento, no solo por el mismo campo compilado.
6. Ejecute `python -m pytest tests/verification/test_semantics.py -q` y `python -m mordheim_combat_lab verify --json`.

Si falta un ruling, marque pendiente. Terminado cuando la obligación, dependencias, interacciones y mutaciones están aprobadas.
