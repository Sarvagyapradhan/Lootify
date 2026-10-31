"""
AI & Machine Learning Subsystem for Clash of Clans Autonomous Farming.
"""

from ai.constants import (
    CLASSES,
    CLASS_COLORS,
    STRATEGY_LOOT_FIRST,
    STRATEGY_TH_RUSH,
    STRATEGY_WEAKEST_FLANK,
    STRATEGY_BALANCED
)
from ai.ai_detector import AIDetector
from ai.tactical_planner import TacticalPlanner
from ai.dataset_recorder import DatasetRecorder

__all__ = [
    "CLASSES",
    "CLASS_COLORS",
    "STRATEGY_LOOT_FIRST",
    "STRATEGY_TH_RUSH",
    "STRATEGY_WEAKEST_FLANK",
    "STRATEGY_BALANCED",
    "AIDetector",
    "TacticalPlanner",
    "DatasetRecorder"
]
