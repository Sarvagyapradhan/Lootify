"""
Real-Time Adaptive Learning & UI Model Knowledge Engine for Clash of Clans.
Learns button locations, UI shifts, wall upgrade costs, and building requirements
in real time from live gameplay. Persists learned knowledge across sessions.
"""

import os
import json
import time


class RealTimeLearner:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(RealTimeLearner, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, data_path="ai_data/realtime_knowledge.json"):
        if getattr(self, "_initialized", False):
            return
        self.data_path = data_path
        self.learned_coordinates = {}
        self.learned_wall_costs = {}
        self.learned_upgrades_catalog = {}
        self.max_seen_storages = {"gold": 0, "elixir": 0, "dark_elixir": 0}
        self.total_learning_events = 0
        self._load()
        self._initialized = True

    def _load(self):
        if os.path.exists(self.data_path):
            try:
                with open(self.data_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.learned_coordinates = data.get("learned_coordinates", {})
                    self.learned_wall_costs = data.get("learned_wall_costs", {})
                    self.learned_upgrades_catalog = data.get("learned_upgrades_catalog", {})
                    self.max_seen_storages = data.get("max_seen_storages", {"gold": 0, "elixir": 0, "dark_elixir": 0})
                    self.total_learning_events = data.get("total_learning_events", 0)
            except Exception as e:
                print(f"[RealTimeLearner] Load notice ({e}). Starting fresh memory.")
        else:
            self.save()

    def save(self):
        try:
            os.makedirs(os.path.dirname(self.data_path), exist_ok=True)
            data = {
                "learned_coordinates": self.learned_coordinates,
                "learned_wall_costs": self.learned_wall_costs,
                "learned_upgrades_catalog": self.learned_upgrades_catalog,
                "max_seen_storages": self.max_seen_storages,
                "total_learning_events": self.total_learning_events,
                "last_updated": time.time()
            }
            with open(self.data_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[RealTimeLearner] Save error: {e}")

    def learn_button_coordinate(self, name, coord, confidence=1.0):
        """
        Updates learned coordinates dynamically using exponential moving average.
        Adapts seamlessly to minor emulator resolution scaling or layout adjustments.
        """
        if not coord or len(coord) != 2:
            return

        cx, cy = int(coord[0]), int(coord[1])
        now = time.time()

        if name not in self.learned_coordinates:
            self.learned_coordinates[name] = {
                "x": cx,
                "y": cy,
                "count": 1,
                "last_confidence": float(confidence),
                "last_seen": now
            }
        else:
            prev = self.learned_coordinates[name]
            prev_x, prev_y = prev["x"], prev["y"]
            count = prev.get("count", 1)

            # Exponential Moving Average with higher weight for stable observations
            alpha = 0.25 if count > 5 else 0.5
            new_x = int(round((1.0 - alpha) * prev_x + alpha * cx))
            new_y = int(round((1.0 - alpha) * prev_y + alpha * cy))

            self.learned_coordinates[name] = {
                "x": new_x,
                "y": new_y,
                "count": count + 1,
                "last_confidence": float(confidence),
                "last_seen": now
            }

        self.total_learning_events += 1
        if self.total_learning_events % 5 == 0:
            self.save()

    def get_learned_coordinate(self, name):
        """Returns the dynamically learned (x, y) coordinate or None."""
        if name in self.learned_coordinates:
            info = self.learned_coordinates[name]
            return (info["x"], info["y"])
        return None

    def learn_wall_cost(self, wall_level, cost_dict):
        """
        Records the exact upgrade cost for a specific wall level
        (e.g. Level 9: {'gold': 200000, 'elixir': 200000}).
        """
        key = f"wall_level_{wall_level}"
        self.learned_wall_costs[key] = {
            "level": int(wall_level),
            "costs": cost_dict,
            "last_verified": time.time()
        }
        self.save()
        print(f"[RealTimeLearner] Learned upgrade cost for Wall Level {wall_level}: {cost_dict}")

    def get_wall_cost(self, wall_level):
        key = f"wall_level_{wall_level}"
        return self.learned_wall_costs.get(key, {}).get("costs", None)

    def learn_storage_reading(self, storages):
        """Learns and tracks maximum observed storages for capacity estimation."""
        if not storages:
            return
        updated = False
        max_limits = {"gold": 25000000, "elixir": 25000000, "dark_elixir": 500000}
        for res in ["gold", "elixir", "dark_elixir"]:
            val = storages.get(res, 0)
            limit = max_limits.get(res, 25000000)
            if 0 < val <= limit and val > self.max_seen_storages.get(res, 0):
                self.max_seen_storages[res] = val
                updated = True
        if updated:
            self.save()

    def learn_catalog_item(self, item_name, count, cost, resource_type):
        """Records an available upgrade from the Builder menu catalog."""
        self.learned_upgrades_catalog[item_name] = {
            "count": count,
            "cost": cost,
            "resource": resource_type,
            "timestamp": time.time()
        }
        self.save()


# Global Singleton instance
realtime_learner = RealTimeLearner()
