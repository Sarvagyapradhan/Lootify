"""
Game Knowledge Base & Definition Memory for Clash of Clans AI.
Stores tactical definitions, field vocabulary, priority roles, and verified
user annotations in 'ai_data/game_knowledge.json'.
"""

import os
import json

DEFAULT_DEFINITIONS = {
    "town_hall": {
        "name": "Town Hall",
        "role": "CORE_TARGET",
        "priority": 10,
        "description": "Primary base core. Destruction grants 1 star and massive loot.",
        "notes": "Core building in center of base, critical tactical target."
    },
    "clan_castle": {
        "name": "Clan Castle",
        "role": "CORE_DEFENSE",
        "priority": 9,
        "description": "Holds defensive clan troops and treasury resources.",
        "notes": "Lure defensive troops or trigger early with high HP troops."
    },
    "gold_storage": {
        "name": "Gold Storage",
        "role": "HIGH_VALUE_LOOT",
        "priority": 8,
        "description": "Vats containing stored gold. Primary objective for gold farming.",
        "notes": "Target with Goblin/Barbarian clusters outside splash zones."
    },
    "elixir_storage": {
        "name": "Elixir Storage",
        "role": "HIGH_VALUE_LOOT",
        "priority": 8,
        "description": "Glass vats containing stored elixir. Essential for army training.",
        "notes": "High hitpoint loot target."
    },
    "dark_elixir_storage": {
        "name": "Dark Elixir Storage",
        "role": "CRITICAL_LOOT",
        "priority": 10,
        "description": "Deep black rectangular storage holding Dark Elixir for heroes.",
        "notes": "Highest priority resource target for hero upgrades."
    },
    "gold_mine": {
        "name": "Gold Mine",
        "role": "PERIPHERY_LOOT",
        "priority": 6,
        "description": "Extracts gold on base perimeter. High loot when full.",
        "notes": "Usually placed outside walls, easy pickings for barch/sneaky goblins."
    },
    "elixir_collector": {
        "name": "Elixir Collector",
        "role": "PERIPHERY_LOOT",
        "priority": 6,
        "description": "Pumps elixir from the ground on perimeter.",
        "notes": "Usually on outer ring, high loot reward when uncollected."
    },
    "dark_elixir_drill": {
        "name": "Dark Elixir Drill",
        "role": "PERIPHERY_LOOT",
        "priority": 7,
        "description": "Extracts dark elixir on base edges.",
        "notes": "Top value collector target."
    },
    "eagle_artillery": {
        "name": "Eagle Artillery",
        "role": "HEAVY_SPLASH_DEFENSE",
        "priority": 9,
        "description": "Long-range map-wide defense activated after 180-200 housing spaces deployed.",
        "notes": "Avoid triggering too early with mass deployment."
    },
    "inferno_tower": {
        "name": "Inferno Tower",
        "role": "HIGH_DAMAGE_DEFENSE",
        "priority": 9,
        "description": "Melts tanks (single target) or fries swarms (multi-target).",
        "notes": "Freeze spell priority target."
    },
    "x_bow": {
        "name": "X-Bow",
        "role": "RAPID_FIRE_DEFENSE",
        "priority": 7,
        "description": "Rapid-fire mechanical defense, ground or air-and-ground.",
        "notes": "Long range defensive zone."
    },
    "air_defense": {
        "name": "Air Defense",
        "role": "ANTI_AIR_DEFENSE",
        "priority": 8,
        "description": "Rocket battery devastating against dragons, balloons, healers.",
        "notes": "High threat to flying units."
    },
    "mortar": {
        "name": "Mortar",
        "role": "SPLASH_DEFENSE",
        "priority": 7,
        "description": "Fires explosive shells killing barch/goblins in clusters.",
        "notes": "Blind spot directly around base."
    },
    "wizard_tower": {
        "name": "Wizard Tower",
        "role": "SPLASH_DEFENSE",
        "priority": 8,
        "description": "Fires area-of-effect magical blasts at ground and air units.",
        "notes": "Primary threat to sneaky goblins and barch swarms."
    },
    "red_boundary": {
        "name": "Red Boundary Line",
        "role": "DEPLOYMENT_BORDER",
        "priority": 10,
        "description": "The forbidden red boundary outline around enemy buildings.",
        "notes": "Troops CANNOT be placed inside this boundary. Bot drops 20px outside it."
    }
}


class GameKnowledgeBase:
    def __init__(self, data_file="ai_data/game_knowledge.json"):
        self.data_file = data_file
        self.definitions = dict(DEFAULT_DEFINITIONS)
        self.annotations_history = []
        self._load()

    def _load(self):
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    saved_defs = data.get("definitions", {})
                    self.definitions.update(saved_defs)
                    self.annotations_history = data.get("annotations_history", [])
            except Exception as e:
                print(f"[KnowledgeBase] Load notice ({e}). Initialized default knowledge.")
        else:
            self.save()

    def save(self):
        os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
        data = {
            "definitions": self.definitions,
            "annotations_history": self.annotations_history,
            "total_definitions": len(self.definitions),
            "total_user_annotations": len(self.annotations_history)
        }
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_definition(self, class_key):
        return self.definitions.get(class_key, {
            "name": class_key.replace("_", " ").title(),
            "role": "FIELD_OBJECT",
            "priority": 5,
            "description": f"Custom field object: {class_key}",
            "notes": ""
        })

    def set_definition(self, class_key, name, description, role="CUSTOM", priority=5, notes=""):
        self.definitions[class_key] = {
            "name": name,
            "role": role,
            "priority": int(priority),
            "description": description,
            "notes": notes
        }
        self.save()

    def record_annotation(self, image_file, class_name, bbox, notes=""):
        entry = {
            "image": os.path.basename(image_file),
            "class": class_name,
            "bbox": bbox,
            "notes": notes
        }
        self.annotations_history.append(entry)
        self.save()

    def get_stats(self):
        return {
            "definitions_count": len(self.definitions),
            "annotations_count": len(self.annotations_history)
        }
