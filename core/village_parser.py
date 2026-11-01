"""
Village Profile & Ground Truth Data Parser.
Integrates Supercell / Village JSON ground truth state:
- Player Tag & API Token management
- Exact Wall Inventory across all levels (Level 3/8, Level 10, Level 11, etc.)
- Active Builder Timers & countdown to next free builder
- Intelligent Wall Dumping Strategy: 'CHEAPEST_FIRST' (25 lower walls first) or 'SMART_HYBRID'
"""

import os
import json
import time

# Clash of Clans Data IDs
BUILDING_WALL_ID = 1000010
BUILDING_TOWN_HALL_ID = 1000000
BUILDING_TOWN_HALL_ALT_ID = 1000001

# Clash of Clans Town Hall base storage capacities (Gold, Elixir, Dark Elixir)
TOWN_HALL_STORAGE_CAPACITY = {
    1: {"gold": 1000, "elixir": 1000, "dark_elixir": 0},
    2: {"gold": 2500, "elixir": 2500, "dark_elixir": 0},
    3: {"gold": 10000, "elixir": 10000, "dark_elixir": 0},
    4: {"gold": 50000, "elixir": 50000, "dark_elixir": 0},
    5: {"gold": 100000, "elixir": 100000, "dark_elixir": 0},
    6: {"gold": 300000, "elixir": 300000, "dark_elixir": 0},
    7: {"gold": 500000, "elixir": 500000, "dark_elixir": 2500},
    8: {"gold": 750000, "elixir": 750000, "dark_elixir": 5000},
    9: {"gold": 1000000, "elixir": 1000000, "dark_elixir": 10000},
    10: {"gold": 1500000, "elixir": 1500000, "dark_elixir": 10000},
    11: {"gold": 2000000, "elixir": 2000000, "dark_elixir": 10000},
    12: {"gold": 2000000, "elixir": 2000000, "dark_elixir": 10000},
    13: {"gold": 2000000, "elixir": 2000000, "dark_elixir": 10000},
    14: {"gold": 2000000, "elixir": 2000000, "dark_elixir": 10000},
    15: {"gold": 2000000, "elixir": 2000000, "dark_elixir": 10000},
    16: {"gold": 2000000, "elixir": 2000000, "dark_elixir": 10000},
}

# Standard Storage building capacity per level (Gold Storage / Elixir Storage)
STORAGE_CAPACITY_PER_LEVEL = {
    1: 1500,
    2: 3000,
    3: 6000,
    4: 12000,
    5: 25000,
    6: 50000,
    7: 100000,
    8: 250000,
    9: 500000,
    10: 1000000,
    11: 1750000,
    12: 2000000,
    13: 2500000,
    14: 3000000,
    15: 3500000,
    16: 4000000,
    17: 4500000,
}

DARK_ELIXIR_STORAGE_PER_LEVEL = {
    1: 10000,
    2: 20000,
    3: 40000,
    4: 80000,
    5: 150000,
    6: 200000,
    7: 240000,
    8: 300000,
    9: 350000,
    10: 400000,
}

# Cost per wall level (approximate Clash of Clans values in Gold/Elixir)
# Note: Lower walls (Level <= 8) strictly accept Gold only. Level >= 9 accepts Gold or Elixir.
WALL_COST_TABLE = {
    1: {"cost": 1000, "resource": "GOLD"},
    2: {"cost": 4000, "resource": "GOLD"},
    3: {"cost": 10000, "resource": "GOLD"},
    4: {"cost": 25000, "resource": "GOLD"},
    5: {"cost": 50000, "resource": "GOLD"},
    6: {"cost": 75000, "resource": "GOLD"},
    7: {"cost": 75000, "resource": "GOLD"},
    8: {"cost": 75000, "resource": "GOLD"},
    9: {"cost": 200000, "resource": "BOTH"},
    10: {"cost": 500000, "resource": "BOTH"},
    11: {"cost": 1000000, "resource": "BOTH"},
    12: {"cost": 2000000, "resource": "BOTH"},
    13: {"cost": 3000000, "resource": "BOTH"},
    14: {"cost": 4000000, "resource": "BOTH"},
    15: {"cost": 6000000, "resource": "BOTH"},
    16: {"cost": 8000000, "resource": "BOTH"},
}


class VillageProfile:
    def __init__(self, json_path=None):
        self.json_path = json_path or os.path.join(os.path.dirname(os.path.dirname(__file__)), "config/village_data.json")
        self.config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config/settings.yaml")
        self.data = {}
        self.tag = ""
        self.api_token = ""
        self.timestamp = 0
        self.walls = {}  # {level: count}
        self.busy_builders = []  # list of {"building_id": int, "timer": int, "finish_timestamp": float}
        self.town_hall_lvl = 11
        self.total_builders = self._read_total_builders()
        self.load()

    def _read_total_builders(self):
        """Reads user configured unlocked builders from settings.yaml (defaults to 3)."""
        if os.path.exists(self.config_path):
            try:
                import yaml
                with open(self.config_path, "r", encoding="utf-8") as yf:
                    cfg = yaml.safe_load(yf) or {}
                return cfg.get("village_profile", {}).get("total_builders", 3)
            except Exception:
                return 3
        return 3

    def load(self):
        """Loads and parses the village JSON file."""
        if not os.path.exists(self.json_path):
            return False

        try:
            with open(self.json_path, "r", encoding="utf-8") as f:
                self.data = json.load(f)

            self.tag = self.data.get("tag", "")
            self.api_token = self.data.get("api_token", "")
            self.timestamp = self.data.get("timestamp", int(time.time()))

            # Parse buildings: find walls, town hall, and builder timers
            self.walls = {}
            self.busy_builders = []
            now = time.time()

            for b in self.data.get("buildings", []):
                bid = b.get("data")
                lvl = b.get("lvl", 0)
                cnt = b.get("cnt", 1)
                timer = b.get("timer", 0)

                if bid == BUILDING_WALL_ID:
                    self.walls[lvl] = cnt
                elif bid in (BUILDING_TOWN_HALL_ID, BUILDING_TOWN_HALL_ALT_ID) and (cnt == 1 or bid == BUILDING_TOWN_HALL_ALT_ID):
                    self.town_hall_lvl = lvl

                if timer > 0:
                    finish_time = self.timestamp + timer
                    # Only add if timer is still actively running in the future
                    if finish_time > now:
                        self.busy_builders.append({
                            "building_id": bid,
                            "lvl": lvl,
                            "timer_seconds": timer,
                            "finish_time": finish_time
                        })

            self.busy_builders.sort(key=lambda b: b["timer_seconds"])
            return True
        except Exception as e:
            print(f"[VillageProfile] Error loading {self.json_path}: {e}")
            return False

    def sync_with_live_detector(self, builder_info):
        """
        Synchronizes village profile with live screen telemetry.
        Caps busy builders and reconciles active timers so ground truth from live screen is maintained.
        """
        if not builder_info or not isinstance(builder_info, dict):
            return
        tot = builder_info.get("total")
        if tot and tot > 0:
            self.total_builders = tot
        free = builder_info.get("free")
        if free is not None:
            self.live_free_builders = free
            max_busy = max(0, self.total_builders - free)
            now = time.time()
            active_busy = [b for b in self.busy_builders if b.get("finish_time", 0) > now]
            if len(active_busy) > max_busy:
                self.busy_builders = active_busy[:max_busy]
            elif free >= self.total_builders:
                self.busy_builders = []

    def clear_builder_timers(self):
        """Resets all builder timers, marking all builders as free."""
        self.busy_builders = []
        if os.path.exists(self.json_path):
            try:
                with open(self.json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for b in data.get("buildings", []):
                    if "timer" in b:
                        del b["timer"]
                with open(self.json_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
            except Exception as e:
                print(f"[VillageProfile] Error clearing timers in JSON: {e}")

    def set_manual_builder_timer(self, seconds):
        """Sets a manual builder countdown timer in seconds from now."""
        self.busy_builders = [{
            "building_id": 9999999,
            "lvl": 1,
            "timer_seconds": seconds,
            "finish_time": time.time() + seconds
        }]

    def get_wall_summary(self):
        """
        Returns structured summary of walls:
        {
            "total": 300,
            "maxed": 21,
            "upgradeable": 279,
            "breakdown": {3: 25, 10: 254, 11: 21},
            "cheapest_level": 3,
            "cheapest_count": 25
        }
        """
        total = sum(self.walls.values())
        max_lvl = max(self.walls.keys()) if self.walls else 11
        maxed = self.walls.get(max_lvl, 0)
        upgradeable = total - maxed

        sorted_lvls = sorted(self.walls.keys())
        cheapest_lvl = sorted_lvls[0] if sorted_lvls else None
        cheapest_cnt = self.walls.get(cheapest_lvl, 0) if cheapest_lvl else 0

        return {
            "total": total,
            "maxed": maxed,
            "upgradeable": upgradeable,
            "breakdown": self.walls,
            "cheapest_level": cheapest_lvl,
            "cheapest_count": cheapest_cnt
        }

    def get_next_builder_free_seconds(self):
        """Returns the number of seconds until the earliest busy builder finishes dynamically."""
        if not self.busy_builders:
            return 0
        now = time.time()
        for b in self.busy_builders:
            rem = int(b["finish_time"] - now)
            if rem > 0:
                return rem
        return 0

    def get_busy_builder_count(self):
        """Returns the number of currently busy builders dynamically based on finish times."""
        now = time.time()
        return sum(1 for b in self.busy_builders if b["finish_time"] > now)

    def get_free_builder_count(self):
        """Returns the number of free builders dynamically based on live detector or active timers."""
        if hasattr(self, "live_free_builders") and self.live_free_builders is not None:
            return self.live_free_builders
        return max(0, self.total_builders - self.get_busy_builder_count())

    def get_recommended_wall_target(self, avail_gold, avail_elixir, strategy="CHEAPEST_FIRST"):
        """
        Recommends whether to upgrade the lower walls (Gold-only) or Level 10 walls (Gold/Elixir).
        Returns dict:
        {
            "target_level": int,
            "resource": "GOLD" | "ELIXIR" | "BOTH",
            "cost_per_wall": int,
            "can_accept_elixir": bool,
            "reason": str
        }
        """
        summary = self.get_wall_summary()
        cheapest_lvl = summary.get("cheapest_level")
        cheapest_cnt = summary.get("cheapest_count", 0)

        # In user's village: level 3 represents the 25 lower walls (75,000 Gold only)
        # Level 10 represents the 254 Level 10 walls (500,000 Gold or Elixir)
        # If Elixir is full or overflowing (>= 500k and > Gold * 1.3 or >= 3.5M), prioritize Elixir wall dump!
        # Lower walls (Level < 9) reject Elixir, so Level 10 walls must be targeted for Elixir.
        if avail_elixir >= 500000 and (avail_elixir > avail_gold * 1.3 or avail_elixir >= 3500000):
            return {
                "target_level": 10,
                "resource": "ELIXIR",
                "cost_per_wall": 500000,
                "can_accept_elixir": True,
                "reason": f"Elixir is full/dominant ({avail_elixir:,}). Upgrading Level 10 walls with Elixir."
            }

        if strategy == "CHEAPEST_FIRST":
            if cheapest_lvl is not None and cheapest_lvl < 9 and cheapest_cnt > 0:
                cost = WALL_COST_TABLE.get(cheapest_lvl, {}).get("cost", 75000)
                if avail_gold >= cost:
                    return {
                        "target_level": cheapest_lvl,
                        "resource": "GOLD",
                        "cost_per_wall": cost,
                        "can_accept_elixir": False,
                        "reason": f"Cheapest First: Upgrading lower wall ({cheapest_cnt} remaining) with Gold ({cost:,} each)."
                    }
                elif avail_elixir >= 200000:
                    # Gold cannot afford lower wall, but excess Elixir is available
                    # Must target Level 9+ walls because lower walls reject Elixir
                    return {
                        "target_level": 10,
                        "resource": "ELIXIR",
                        "cost_per_wall": 500000,
                        "can_accept_elixir": True,
                        "reason": "Gold low for lower wall, spending excess Elixir on Level 10 walls."
                    }

        # Default / Fallback: Level 10 walls
        res = "ELIXIR" if avail_elixir > avail_gold else "GOLD"
        return {
            "target_level": 10,
            "resource": res,
            "cost_per_wall": 500000,
            "can_accept_elixir": True,
            "reason": f"Targeting Level 10 walls with {res}."
        }

    def calculate_storage_capacities_from_buildings(self):
        """
        Dynamically calculates exact storage capacities for Gold, Elixir, and Dark Elixir
        from actual building levels (Town Hall + Gold Storages + Elixir Storages + DE Storages).
        Automatically recalculates whenever storages are upgraded!
        """
        th_lvl = self.town_hall_lvl or 11
        th_caps = TOWN_HALL_STORAGE_CAPACITY.get(th_lvl, TOWN_HALL_STORAGE_CAPACITY[11])

        total_g = th_caps["gold"]
        total_e = th_caps["elixir"]
        total_de = th_caps.get("dark_elixir", 10000)

        gold_storage_found = False
        elixir_storage_found = False

        for b in self.data.get("buildings", []):
            bid = b.get("data")
            lvl = b.get("lvl", 0)
            cnt = b.get("cnt", 1)

            # 1000005: Gold Storage
            if bid == 1000005:
                gold_storage_found = True
                cap_per = STORAGE_CAPACITY_PER_LEVEL.get(lvl, 1750000)
                total_g += cap_per * cnt

            # 1000003: Elixir Storage
            elif bid == 1000003:
                elixir_storage_found = True
                cap_per = STORAGE_CAPACITY_PER_LEVEL.get(lvl, 1750000)
                total_e += cap_per * cnt

            # 1000020: Dark Elixir Storage
            elif bid == 1000020:
                cap_de = DARK_ELIXIR_STORAGE_PER_LEVEL.get(lvl, 40000)
                total_de += cap_de * cnt

        if not gold_storage_found or not elixir_storage_found:
            per_storage = STORAGE_CAPACITY_PER_LEVEL.get(th_lvl, 1750000)
            total_g = th_caps["gold"] + 4 * per_storage
            total_e = th_caps["elixir"] + 4 * per_storage
            total_de = 350000

        return {"gold": total_g, "elixir": total_e, "dark_elixir": total_de}

    def get_max_storage_capacities(self):
        """
        Calculates and returns lively maximum storage capacities for Gold, Elixir, and Dark Elixir.
        Considers building upgrades, realtime OCR peak values, and user ground truth.
        """
        calc = self.calculate_storage_capacities_from_buildings()

        # Check explicit JSON ground truth if present
        json_g = 0
        json_e = 0
        json_de = 0
        if self.data:
            explicit_caps = self.data.get("storage_capacities") or self.data.get("max_storages")
            if explicit_caps and isinstance(explicit_caps, dict):
                json_g = explicit_caps.get("gold", 0)
                json_e = explicit_caps.get("elixir", 0)
                json_de = explicit_caps.get("dark_elixir", 0)

        # Check Realtime Learner peak OCR observations
        learned_g = 0
        learned_e = 0
        learned_de = 0
        try:
            from ai.realtime_learner import realtime_learner
            learned = realtime_learner.max_seen_storages
            learned_g = learned.get("gold", 0)
            learned_e = learned.get("elixir", 0)
            learned_de = min(500000, learned.get("dark_elixir", 350000)) if learned.get("dark_elixir", 0) > 0 else 100000
        except Exception:
            pass

        # Check settings.yaml
        cfg_g = 0
        cfg_e = 0
        cfg_de = 0
        if os.path.exists(self.config_path):
            try:
                import yaml
                with open(self.config_path, "r", encoding="utf-8") as yf:
                    cfg = yaml.safe_load(yf) or {}
                s_cfg = cfg.get("storages", {})
                cfg_g = s_cfg.get("max_gold_capacity", 0)
                cfg_e = s_cfg.get("max_elixir_capacity", 0)
                cfg_de = s_cfg.get("max_dark_elixir_capacity", 350000)
            except Exception:
                pass

        # Live Dynamic Capacity: max of calculated from upgraded buildings, JSON, settings, and live learned OCR
        max_g = max(calc["gold"], json_g, learned_g, cfg_g)
        max_e = max(calc["elixir"], json_e, learned_e, cfg_e)
        max_de = max(calc["dark_elixir"], json_de, learned_de, cfg_de)

        return {
            "gold": int(max_g),
            "elixir": int(max_e),
            "dark_elixir": int(max_de),
            "source": "live_upgraded"
        }

    def update_live_reading(self, storages):
        """
        Lively updates max capacities in real time when higher storage values or 100% full text are observed.
        """
        if not storages or not isinstance(storages, dict):
            return
        try:
            from ai.realtime_learner import realtime_learner
            realtime_learner.learn_storage_reading(storages)
        except Exception:
            pass

    def is_storage_near_limit(self, current_storages, threshold_pct=0.80, estimated_raid_loot=None):
        """
        Evaluates whether current village storages meet or exceed full capacity threshold OR
        if upcoming additions (e.g. estimated raid loot) will cause storages to overflow and waste loot.

        Args:
            current_storages: dict with {"gold": int, "elixir": int, "gold_full": bool, "elixir_full": bool}
            threshold_pct: float (e.g. 0.80 for 80% full)
            estimated_raid_loot: dict with {"gold": int, "elixir": int} (e.g. {"gold": 450000, "elixir": 450000})

        Returns:
            bool: True if wall dumping should be performed before raiding to prevent loot overflow.
        """
        if not current_storages:
            return False

        # Live OCR 100% full text indicator (red text on storage bar)
        if current_storages.get("gold_full") or current_storages.get("elixir_full"):
            return True

        caps = self.get_max_storage_capacities()
        max_g = caps.get("gold", 5500000)
        max_e = caps.get("elixir", 5500000)

        curr_g = current_storages.get("gold", 0)
        curr_e = current_storages.get("elixir", 0)

        # Spendable check: need at least 30,000 in one resource to dump walls
        if curr_g < 30000 and curr_e < 30000:
            return False

        # Check 1: Current storage already exceeds percentage threshold (e.g. 80%)
        if (curr_g >= max_g * threshold_pct) or (curr_e >= max_e * threshold_pct):
            return True

        # Check 2: Will adding upcoming raid loot exceed max storage capacity?
        if estimated_raid_loot and isinstance(estimated_raid_loot, dict):
            incoming_g = estimated_raid_loot.get("gold", 0)
            incoming_e = estimated_raid_loot.get("elixir", 0)
            if (curr_g + incoming_g >= max_g) or (curr_e + incoming_e >= max_e):
                return True

        return False


# Global singleton
village_profile = VillageProfile()
