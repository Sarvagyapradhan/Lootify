"""
Tactical Attack Planner powered by Computer Vision & AI.
Evaluates enemy base composition, loot centroids, defense heatmaps,
and red line boundaries to generate optimal troop deployment vectors.
"""

from ai.constants import (
    STRATEGY_LOOT_FIRST,
    STRATEGY_TH_RUSH,
    STRATEGY_WEAKEST_FLANK,
    STRATEGY_BALANCED
)


class TacticalPlanner:
    def __init__(self, default_strategy=STRATEGY_LOOT_FIRST):
        self.strategy = default_strategy
        
        # Standard 1280x720 outer perimeter deployment corridors
        # (Guaranteed deployable field coordinates outside the red zone)
        self.CORRIDORS = {
            "TOP_LEFT": [(220, 200), (360, 160), (500, 140)],
            "TOP_RIGHT": [(780, 140), (920, 160), (1060, 200)],
            "BOTTOM_RIGHT": [(1060, 510), (920, 540), (780, 560)],
            "BOTTOM_LEFT": [(500, 560), (360, 540), (220, 510)],
            "CORNERS": [(200, 160), (1080, 160), (1080, 530), (200, 530)]
        }

    def set_strategy(self, strategy_name):
        self.strategy = strategy_name
        print(f"[TacticalPlanner] Active strategy switched to: {self.strategy}")

    def plan_attack(self, detections, base_center=(640, 350)):
        """
        Analyzes detected base objects and produces an optimal attack plan.
        Returns a dict:
        {
            "strategy": str,
            "target_center": (x, y),
            "drop_points": [(x, y), ...],
            "spell_drop_point": (x, y),
            "tactical_arrows": [((start_x, start_y), (end_x, end_y)), ...]
        }
        """
        loot_targets = []
        th_target = None
        splash_defenses = []
        red_boundaries = []

        for d in detections:
            cname = d["class"]
            center = d.get("center", (640, 350))
            if cname in ["gold_mine", "elixir_collector", "dark_elixir_drill", "gold_storage", "elixir_storage", "dark_elixir_storage"]:
                loot_targets.append(center)
            elif cname == "town_hall":
                th_target = center
            elif cname in ["mortar", "wizard_tower", "eagle_artillery", "inferno_tower"]:
                splash_defenses.append(center)
            elif cname == "red_boundary":
                red_boundaries.append(d)

        # 1. Determine Focal Target based on Strategy
        if self.strategy == STRATEGY_TH_RUSH and th_target:
            primary_target = th_target
        elif loot_targets and self.strategy in [STRATEGY_LOOT_FIRST, STRATEGY_BALANCED]:
            # Weighted average centroid of all loot sources
            tx = int(sum(pt[0] for pt in loot_targets) / len(loot_targets))
            ty = int(sum(pt[1] for pt in loot_targets) / len(loot_targets))
            primary_target = (tx, ty)
        elif th_target:
            primary_target = th_target
        else:
            primary_target = base_center

        # 2. Select Optimal Flank / Drop Vectors
        optimal_flanks, drop_points, tactical_arrows = self._calculate_vectors(
            primary_target, splash_defenses, red_boundaries, base_center
        )

        # 3. Spell Targeting
        # Spells drop directly onto the target cluster / core
        spell_point = primary_target

        return {
            "strategy": self.strategy,
            "target_center": primary_target,
            "optimal_flanks": optimal_flanks,
            "drop_points": drop_points,
            "spell_drop_point": spell_point,
            "tactical_arrows": tactical_arrows
        }

    def _calculate_vectors(self, target, defenses, red_boundaries, base_center):
        """
        Calculates the safest, highest-impact deployment corridors.
        """
        cx, cy = base_center
        tx, ty = target

        # Direction vector from base center to target
        dx = tx - cx
        dy = ty - cy

        # Determine closest corridor flank
        scores = {
            "TOP_LEFT": 0.0,
            "TOP_RIGHT": 0.0,
            "BOTTOM_RIGHT": 0.0,
            "BOTTOM_LEFT": 0.0
        }

        # Flank scoring: higher score if corridor is closer to the target
        if dx <= 0 and dy <= 0:
            scores["TOP_LEFT"] += 3.0
            scores["BOTTOM_LEFT"] += 1.0
            scores["TOP_RIGHT"] += 1.0
        elif dx >= 0 and dy <= 0:
            scores["TOP_RIGHT"] += 3.0
            scores["TOP_LEFT"] += 1.0
            scores["BOTTOM_RIGHT"] += 1.0
        elif dx >= 0 and dy >= 0:
            scores["BOTTOM_RIGHT"] += 3.0
            scores["TOP_RIGHT"] += 1.0
            scores["BOTTOM_LEFT"] += 1.0
        else:
            scores["BOTTOM_LEFT"] += 3.0
            scores["TOP_LEFT"] += 1.0
            scores["BOTTOM_RIGHT"] += 1.0

        # Penalize flanks heavy in splash defenses if WEAKEST_FLANK strategy is set
        if self.strategy == STRATEGY_WEAKEST_FLANK:
            for d in defenses:
                p_flank = self._point_to_flank(d, base_center)
                if p_flank in scores:
                    scores[p_flank] -= 1.5

        # Rank flanks by score
        ranked_flanks = sorted(scores.keys(), key=lambda f: scores[f], reverse=True)

        if self.strategy == STRATEGY_BALANCED:
            # Multi-flank surrounding attack (all 4 sides)
            chosen_flanks = ["TOP_LEFT", "TOP_RIGHT", "BOTTOM_RIGHT", "BOTTOM_LEFT"]
        elif self.strategy in [STRATEGY_LOOT_FIRST, STRATEGY_TH_RUSH]:
            # Focus on primary flank + adjacent secondary flank
            chosen_flanks = ranked_flanks[:2]
        else:
            chosen_flanks = ranked_flanks[:1]

        # Gather drop points
        drop_points = []
        for flank in chosen_flanks:
            drop_points.extend(self.CORRIDORS[flank])

        # Generate directional arrows pointing from drop points toward the target
        tactical_arrows = []
        for flank in chosen_flanks:
            start_p = self.CORRIDORS[flank][1]  # corridor midpoint
            # Arrow towards the target
            tactical_arrows.append((start_p, target))

        return chosen_flanks, drop_points, tactical_arrows

    def _point_to_flank(self, pt, center):
        x, y = pt
        cx, cy = center
        if x <= cx and y <= cy:
            return "TOP_LEFT"
        elif x > cx and y <= cy:
            return "TOP_RIGHT"
        elif x > cx and y > cy:
            return "BOTTOM_RIGHT"
        return "BOTTOM_LEFT"
