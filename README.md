# Mordheim Combat Lab

Motor Monte Carlo vectorizado para duelos cuerpo a cuerpo 1 contra 1. El núcleo
se basa exclusivamente en IDs y contratos de la base de conocimiento. La
interfaz gráfica anterior y sus utilidades de exportación se conservan como
referencia de migración. No se lanzan por defecto: se adaptarán al contrato
tipado de esta KB en una entrega posterior.

## Estado

- 48 bandas Mordheim: 315 perfiles de duelo compilables y 1 elemento no combatiente excluido explícitamente (Plague Cart).
- 33 bandas de la colección Trollheim: 218 perfiles compilables bajo el mismo ruleset Mordheim.
- API tipada: `FighterBuild`, `CompiledFighter`, `DuelRequest` y `DuelResult`.
- Contrato ejecutable no vacío para cada mecánica del catálogo de combate.
- Efectos condicionales y persistentes para armas, defensas, materiales,
  preparaciones, venenos, habilidades, heridas y recuperación.
- Características aleatorias de perfil resueltas por fila de simulación.
- Equipo fijo, ataques naturales, listas de equipo, categorías de habilidades y
  restricciones normalizadas aplicados durante la compilación.
- Un único motor NumPy vectorizado, reproducible, por lotes y cancelable.
- Mordheim y Trollheim son colecciones de bandas; ambas reutilizan el ruleset de combate Mordheim.
- Las reglas innatas Trollheim normalizadas reutilizan los mismos operadores de
  armadura, carga, regeneración, prioridad, penetración y heridas.
- Todas las referencias de equipo resuelven a una mecánica compartida o a una
  clasificación explícita fuera del alcance del duelo.

## Uso

```python
from mordheim_combat_lab import Characteristics, DuelRequest, FighterBuild, compile_fighter, simulate_duel
stats = Characteristics(3, 3, 3, 1, 3, 1)
first = compile_fighter(FighterBuild("mordheim", stats, main_weapon_id="weapon.sword"))
second = compile_fighter(FighterBuild("mordheim", stats, main_weapon_id="weapon.mace"))
result = simulate_duel(DuelRequest(first, second, simulations=100_000, seed=42))

# Una banda de la colección Trollheim reutiliza el ruleset Mordheim.
trollheim_fighter = compile_fighter(FighterBuild(
    "mordheim",
    band_id="trollheim-mercenaries",
    profile_id="mercenary-captain",
    collection="trollheim",
))
```

## Comprobaciones

```powershell
python tools\validate_knowledge.py
python -m pytest -q
python tools\benchmark_engine.py -n 500000
```
