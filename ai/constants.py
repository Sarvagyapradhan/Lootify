"""
AI & Computer Vision Constants for Clash of Clans.
Defines classes, color palettes, and tactical priority modes.
"""

# Class labels for YOLO / Vision Object Detection
CLASSES = [
    "town_hall",           # 0
    "clan_castle",         # 1
    "gold_storage",        # 2
    "elixir_storage",      # 3
    "dark_elixir_storage", # 4
    "gold_mine",           # 5
    "elixir_collector",    # 6
    "dark_elixir_drill",   # 7
    "eagle_artillery",     # 8
    "inferno_tower",       # 9
    "x_bow",               # 10
    "air_defense",         # 11
    "mortar",              # 12
    "wizard_tower",        # 13
    "red_boundary"         # 14
]

CLASS_TO_ID = {name: i for i, name in enumerate(CLASSES)}
ID_TO_CLASS = {i: name for i, name in enumerate(CLASSES)}

# Vibrant BGR colors for bounding box visualization
CLASS_COLORS = {
    "town_hall": (0, 215, 255),           # Gold / Yellow
    "clan_castle": (255, 140, 0),         # Dark Orange
    "gold_storage": (0, 255, 255),        # Bright Yellow
    "elixir_storage": (255, 0, 255),      # Magenta
    "dark_elixir_storage": (50, 50, 50),  # Dark Charcoal
    "gold_mine": (50, 205, 50),           # Lime Green
    "elixir_collector": (205, 50, 205),   # Orchid / Violet
    "dark_elixir_drill": (80, 80, 80),    # Slate Gray
    "eagle_artillery": (0, 0, 255),       # Bright Red
    "inferno_tower": (0, 69, 255),        # Orange-Red
    "x_bow": (128, 0, 128),               # Purple
    "air_defense": (255, 215, 0),         # Gold
    "mortar": (180, 105, 255),            # Pink
    "wizard_tower": (255, 191, 0),        # Deep Sky Blue
    "red_boundary": (0, 0, 220)           # Red
}

# Tactical Strategy Modes
STRATEGY_LOOT_FIRST = "LOOT_FIRST"          # Focus on high-value Mines & Storages
STRATEGY_TH_RUSH = "TH_RUSH"                # Focus on Town Hall pathing
STRATEGY_WEAKEST_FLANK = "WEAKEST_FLANK"    # Attack side with least splash damage
STRATEGY_BALANCED = "BALANCED"              # Surround base with multi-flank dispersion
