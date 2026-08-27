"""Mordheim Combat Lab engine API."""
from .compiler import compile_fighter, validate_execution_contract
from .engine import simulate_duel
from .models import Characteristics, CompiledFighter, DuelRequest, DuelResult, FighterBuild, SimulationCancelled
__all__=["Characteristics","CompiledFighter","DuelRequest","DuelResult","FighterBuild","SimulationCancelled","compile_fighter","simulate_duel","validate_execution_contract"]
__version__="2.0.0a1"
