"""Top-level rework tabs and their migration boundaries."""

from .analysis import ANALYSIS_TAB_KEYS
from .configuration import CONFIGURATION_TAB_KEYS
from .weapons import WeaponAnalysisTab
from .equipment import EquipmentAnalysisTab
from .improvements import ImprovementAnalysisTab

__all__ = ["ANALYSIS_TAB_KEYS", "CONFIGURATION_TAB_KEYS", "EquipmentAnalysisTab", "ImprovementAnalysisTab", "WeaponAnalysisTab"]
