"""
Finite State Machine (FSM) Coordinator for Clash of Clans Bot.
Features Non-Deterministic Behavioral Pathways, Human Reading Latencies,
and Organic Session/Fatigue Management to counter behavioral anti-cheat analysis.
"""

import time
import random
import numpy as np
from enum import Enum, auto
from core.humanizer import Humanizer
from core.user_intervention import UserInterventionMonitor
from core.village_parser import village_profile
from ai.realtime_learner import realtime_learner


class BotState(Enum):
    IDLE = auto()
    HOME_VILLAGE = auto()
    CHECK_WALL_DUMP = auto()
    MAINTENANCE = auto()
    MATCHMAKING = auto()
    ATTACKING = auto()
    RETURNING_HOME = auto()
    SESSION_BREAK = auto()
    USER_INTERVENTION = auto()


class BotStateMachine:
    def __init__(self, adb_controller, screen_capture, ui_detector, ocr_reader,
                 attack_engine, wall_upgrader, maintenance_module, global_config):
        self.adb = adb_controller
        self.capture = screen_capture
        self.detector = ui_detector
        self.ocr = ocr_reader
        self.attack_engine = attack_engine
        self.wall_upgrader = wall_upgrader
        self.maintenance = maintenance_module
        self.cfg = global_config
        self.humanizer = Humanizer()
        if self.attack_engine:
            self.attack_engine.fsm = self
        if self.wall_upgrader:
            self.wall_upgrader.fsm = self

        self.current_state = BotState.HOME_VILLAGE
        self.is_running = False
        self.is_paused = False
        self.total_attacks_completed = 0
        self._last_storages = {}
        self.attacks_since_last_wall_dump = 0
        self.session_start_time = time.time()
        self.on_state_change = None
        self.on_stats_update = None

        # Human Manual Intervention Monitor
        interv_cfg = self.cfg.get("humanization", {})
        self.intervention_monitor = UserInterventionMonitor(
            adb_controller=self.adb,
            screen_capture=self.capture,
            idle_resume_seconds=interv_cfg.get("user_idle_resume_seconds", 0.8),
            enabled=interv_cfg.get("enable_user_intervention", False)
        )
        self.intervention_monitor.on_intervention_start = self._on_user_intervention_start

    def set_state(self, new_state):
        self.current_state = new_state
        if self.on_state_change:
            try:
                self.on_state_change(new_state.name)
            except Exception:
                pass

    def sleep_interruptible(self, seconds, step=0.1):
        """Sleeps in small increments, responding immediately to pause or stop requests."""
        elapsed = 0.0
        while elapsed < seconds:
            if not self.is_running:
                return False
            while self.is_paused and self.is_running:
                time.sleep(0.1)
            time.sleep(min(step, seconds - elapsed))
            elapsed += step
        return self.is_running

    def check_abort(self):
        """Checks if current state execution should abort due to pause, stop, or user intervention."""
        if not self.is_running:
            return True
        # In active combat (ATTACKING), the bot must deploy troops swiftly without pausing
        if self.current_state != BotState.ATTACKING:
            if hasattr(self, "intervention_monitor") and self.intervention_monitor and self.intervention_monitor.is_human_active:
                if self.current_state != BotState.USER_INTERVENTION:
                    self.set_state(BotState.USER_INTERVENTION)
                return True
        while self.is_paused and self.is_running:
            time.sleep(0.1)
        return not self.is_running

    def is_storage_full(self, storages):
        """
        Evaluates whether current village storages meet or exceed full capacity threshold OR
        if upcoming additions (e.g. estimated raid loot) will cause storages to overflow and waste loot.
        """
        if not storages:
            return False
        # Red text alert on storage bar in Clash of Clans indicates 100% full capacity
        if storages.get("gold_full") or storages.get("elixir_full"):
            return True

        w_cfg = self.cfg.get("wall_dump", {})
        mm_cfg = self.cfg.get("matchmaking", {})
        full_pct = min(0.95, max(0.60, w_cfg.get("storage_full_percentage", 80) / 100.0))

        # Check upcoming raid loot additions
        raid_loot = {
            "gold": mm_cfg.get("min_gold", 450000),
            "elixir": mm_cfg.get("min_elixir", 450000)
        }

        # Check via village_profile cascade (JSON ground truth -> Realtime learner -> Settings -> TH table)
        return village_profile.is_storage_near_limit(
            storages,
            threshold_pct=full_pct,
            estimated_raid_loot=raid_loot
        )

    def pause(self):
        self.is_paused = not self.is_paused
        status = "PAUSED" if self.is_paused else "RESUMED"
        print(f"[FSM] Bot {status}.")
        if self.on_state_change:
            try:
                self.on_state_change("PAUSED" if self.is_paused else self.current_state.name)
            except Exception:
                pass
        return self.is_paused

    def start(self):
        """Starts the main bot execution loop."""
        self.is_running = True
        self.is_paused = False
        if self.attack_engine:
            self.attack_engine.abort_requested = False
        if self.wall_upgrader:
            self.wall_upgrader.abort_requested = False
        self.session_start_time = time.time()
        if hasattr(self, "intervention_monitor") and self.intervention_monitor:
            self.intervention_monitor.start()

        print("\n=======================================================")
        print(">>> CLASH OF CLANS FARMING BOT ENGINE STARTED <<<")
        print(">>> ANTI-DETECTION: Humanized Biometrics & Markov FSM Active <<<")
        print("=======================================================\n")
        self.set_state(BotState.HOME_VILLAGE)

        while self.is_running:
            if self.is_paused:
                time.sleep(0.2)
                continue
            try:
                # 1. Evaluate Session Health (Anti-Fatigue / Human Sleep/Break Cycle)
                if self._check_session_break_needed():
                    self.current_state = BotState.SESSION_BREAK

                if not self.is_running:
                    break

                if self.current_state == BotState.HOME_VILLAGE:
                    self._handle_home_village()

                elif self.current_state == BotState.CHECK_WALL_DUMP:
                    self._handle_wall_dump()

                elif self.current_state == BotState.MAINTENANCE:
                    self._handle_maintenance()

                elif self.current_state == BotState.MATCHMAKING:
                    self._handle_matchmaking()

                elif self.current_state == BotState.ATTACKING:
                    self._handle_attacking()

                elif self.current_state == BotState.RETURNING_HOME:
                    self._handle_returning_home()

                elif self.current_state == BotState.SESSION_BREAK:
                    self._handle_session_break()

                elif self.current_state == BotState.USER_INTERVENTION:
                    self._handle_user_intervention()

            except KeyboardInterrupt:
                print("\n[FSM] Bot interrupted by user. Stopping safely.")
                self.stop()
                break
            except Exception as e:
                print(f"[FSM] Exception in loop: {e}. Recovering in 3 seconds...")
                self.sleep_interruptible(3.0)
                self.set_state(BotState.HOME_VILLAGE)

    def stop(self):
        self.is_running = False
        self.is_paused = False
        if hasattr(self, "intervention_monitor") and self.intervention_monitor:
            self.intervention_monitor.stop()
        if self.attack_engine:
            self.attack_engine.abort_requested = True
        if self.wall_upgrader:
            self.wall_upgrader.abort_requested = True
        self.set_state(BotState.HOME_VILLAGE)
        print("[FSM] Bot stopped.")

    def _on_user_intervention_start(self):
        if self.is_running and not self.is_paused and self.current_state != BotState.USER_INTERVENTION:
            self.set_state(BotState.USER_INTERVENTION)

    def _handle_user_intervention(self):
        """
        Safely yields control while the user manually clicks/plays on the emulator.
        Once the user is idle for 2.0 seconds, inspects active screen and resumes cleanly.
        """
        print("[FSM] User manual play active. Bot automation standing by...")
        while self.is_running and not self.is_paused:
            if hasattr(self, "intervention_monitor") and self.intervention_monitor.check_is_idle():
                print("\n[UserIntervention] User idle resumed. Identifying active screen to resume automation...")
                time.sleep(0.1)
                frame = self.capture.get_frame(target_size=(1280, 720))
                screen = self.ocr.detect_screen(frame) if self.ocr else "HOME_VILLAGE"
                print(f"[UserIntervention] Screen detected: {screen}. Resuming execution...")

                self.intervention_monitor.clear_intervention()

                # Check if we are on an enemy matchmaking base (Next button present)
                has_next = (
                    self.detector.find_template(frame, "next_button", threshold=0.58) is not None
                    or (hasattr(self.detector, "check_next_button") and self.detector.check_next_button(frame) is not None)
                )

                if has_next or screen == "MATCHMAKING":
                    # We are on an enemy raid search screen! Inspect loot first!
                    loot = self.ocr.read_search_loot(frame) if self.ocr else {}
                    g = loot.get("gold", 0)
                    e = loot.get("elixir", 0)
                    de = loot.get("dark_elixir", 0)

                    mm_cfg = self.cfg.get("matchmaking", {})
                    min_g = mm_cfg.get("min_gold", 450000)
                    min_e = mm_cfg.get("min_elixir", 450000)
                    min_de = mm_cfg.get("min_dark_elixir", 500)
                    logic = mm_cfg.get("match_logic", "AND").upper()

                    meets_criteria = False
                    if logic == "AND":
                        meets_criteria = (g >= min_g and e >= min_e and de >= min_de)
                    else:
                        meets_criteria = (g >= min_g or e >= min_e)

                    print(f"[UserIntervention] Base Loot: Gold: {g:,} | Elixir: {e:,} | DE: {de:,} (Req: G>={min_g:,}, E>={min_e:,}, Logic={logic})")

                    if meets_criteria:
                        print("[UserIntervention] >>> Base meets raid criteria! Commencing attack... <<<")
                        self.set_state(BotState.ATTACKING)
                    else:
                        print("[UserIntervention] >>> Base loot below criteria. Skipping target and resuming matchmaking... <<<")
                        next_pos = self.detector.find_template(frame, "next_button", threshold=0.58) or (1166, 540)
                        self.adb.tap(next_pos[0], next_pos[1])
                        time.sleep(0.4)
                        self.set_state(BotState.MATCHMAKING)
                    return

                elif screen == "ATTACKING":
                    # Check if Next button is still present (scouting base before any troops dropped)
                    has_next = self.detector.find_template(frame, "next_button", threshold=0.58) is not None
                    if has_next:
                        loot = self.ocr.read_search_loot(frame) if self.ocr else {}
                        g = loot.get("gold", 0)
                        e = loot.get("elixir", 0)
                        de = loot.get("dark_elixir", 0)
                        mm_cfg = self.cfg.get("matchmaking", {})
                        min_g = mm_cfg.get("min_gold", 450000)
                        min_e = mm_cfg.get("min_elixir", 450000)
                        min_de = mm_cfg.get("min_dark_elixir", 500)
                        logic = mm_cfg.get("match_logic", "AND").upper()
                        meets_criteria = (g >= min_g and e >= min_e and de >= min_de) if logic == "AND" else (g >= min_g or e >= min_e)
                        if (g > 0 or e > 0) and not meets_criteria:
                            print("[UserIntervention] Scouted base with low loot. Skipping target via Next button...")
                            next_pos = self.detector.find_template(frame, "next_button", threshold=0.58) or (1166, 540)
                            self.adb.tap(next_pos[0], next_pos[1])
                            time.sleep(0.5)
                            self.set_state(BotState.MATCHMAKING)
                            return

                    # Ongoing battle confirmed (troops active on map)
                    print("[UserIntervention] Ongoing battle confirmed. Resuming battle execution...")
                    self.set_state(BotState.ATTACKING)
                    return
                elif screen in ["MY_ARMY_WINDOW", "ATTACK_MENU"]:
                    self.set_state(BotState.MATCHMAKING)
                    return
                elif screen == "BATTLE_RESULTS":
                    print("[UserIntervention] Battle Results screen detected. Tapping 'Return Home' at (640, 605)...")
                    self.adb.tap(640, 605)
                    # Poll for transition to Home Village
                    for _ in range(12):
                        time.sleep(0.4)
                        f_home = self.capture.get_frame(target_size=(1280, 720))
                        if f_home is not None and (
                            self.detector.find_template(f_home, "attack_button", threshold=0.60)
                            or self.detector.find_template(f_home, "build_button", threshold=0.60)
                        ):
                            print("[UserIntervention] Successfully confirmed back at Home Village.")
                            break
                    self.set_state(BotState.HOME_VILLAGE)
                    return
                star_pos = self.detector.check_star_bonus_popup(frame)
                if star_pos:
                    print(f"[UserIntervention] 'Star Bonus received!' modal detected. Tapping 'Okay' at {star_pos}...")
                    self.adb.tap(star_pos[0], star_pos[1])
                    time.sleep(1.0)
                    self.set_state(BotState.HOME_VILLAGE)
                    return
                elif screen == "MODAL_POPUP":
                    cancel_pos = self.detector.check_modal_popup(frame) or (515, 470)
                    self.adb.tap(cancel_pos[0], cancel_pos[1])
                    time.sleep(0.8)
                    self.set_state(BotState.HOME_VILLAGE)
                    return
                else:
                    self.set_state(BotState.HOME_VILLAGE)
                    return

            time.sleep(0.2)

    def _check_session_break_needed(self):
        """Prevents 24/7 robotic uptimes. Triggers organic coffee/rest breaks."""
        h_cfg = self.cfg.get("humanization", {})
        if not h_cfg.get("enable_session_breaks", True):
            return False

        elapsed_mins = (time.time() - self.session_start_time) / 60.0
        max_mins = h_cfg.get("session_length_minutes", 90)
        # Add slight natural deviation (+/- 15 mins)
        target_mins = max_mins + random.uniform(-10, 15)
        return elapsed_mins >= target_mins

    def _handle_session_break(self):
        h_cfg = self.cfg.get("humanization", {})
        break_mins = h_cfg.get("break_length_minutes", 25) + random.uniform(-5, 10)
        print(f"\n[Anti-Detection] >>> TRIGGERING ORGANIC SESSION BREAK ({break_mins:.1f} mins) <<<")
        print("[Anti-Detection] Closing active input to mimic human stepping away...")
        time.sleep(break_mins * 60)
        self.session_start_time = time.time()
        print("[Anti-Detection] Break concluded. Resuming farming session.")
        self.set_state(BotState.HOME_VILLAGE)

    def _check_and_handle_disconnect(self):
        """Detects if game was disconnected, dimmed, or shows Reload Game prompt."""
        frame = self.capture.get_frame(target_size=(1280, 720))
        if frame is None:
            return False

        # If Star Bonus modal is active, the game is 100% connected
        if self.detector.check_star_bonus_popup(frame) is not None:
            return False

        # If any known game screen is active, game is 100% connected
        if hasattr(self, "ocr") and self.ocr:
            active_screen = self.ocr.detect_screen(frame)
            if active_screen in ["HOME_VILLAGE", "MY_ARMY_WINDOW", "ATTACK_MENU", "MATCHMAKING", "ATTACKING", "BATTLE_RESULTS"]:
                return False

        # If screen is dimmed (mean brightness < 45), tap neutral grass to un-dim Android/emulator
        if np.mean(frame) < 45:
            self.adb.tap_empty_grass()
            self.sleep_interruptible(0.5)
            frame = self.capture.get_frame(target_size=(1280, 720))

        reload_pos = self.detector.check_disconnect_or_reload(frame)
        if reload_pos:
            print(f"\n[FSM] Inactivity or disconnection modal detected at {reload_pos}! Auto-reloading game...")
            self.adb.tap(reload_pos[0], reload_pos[1])
            self.sleep_interruptible(4.0)
            self.adb.launch_game()
            self.sleep_interruptible(5.0)
            self.set_state(BotState.HOME_VILLAGE)
            return True
        return False

    def _handle_home_village(self):
        if self._check_and_handle_disconnect():
            return
        if self.check_abort():
            return

        print("\n[State: HOME_VILLAGE] At village screen.")
        self.sleep_interruptible(self.humanizer.get_reaction_delay())
        if self.check_abort():
            return

        # Ensure home village frame is fully loaded and stabilized (not black or in transition)
        frame = self.capture.get_frame(target_size=(1280, 720))
        for _ in range(8):
            if frame is not None and np.mean(frame) > 45:
                # If neutral HUD elements (attack button, build hammer) are present
                if self.detector.find_template(frame, "attack_button", threshold=0.60) or self.detector.find_template(frame, "build_button", threshold=0.60):
                    break
            self.sleep_interruptible(0.35)
            frame = self.capture.get_frame(target_size=(1280, 720))

        # Check for Star Bonus / League Reward popup modal
        star_pos = self.detector.check_star_bonus_popup(frame)
        if star_pos:
            print(f"[HomeVillage] 'Star Bonus received!' modal detected! Tapping 'Okay' at {star_pos}...")
            self.adb.tap(star_pos[0], star_pos[1])
            self.sleep_interruptible(1.0)
            frame = self.capture.get_frame(target_size=(1280, 720))

        # Check active screen to verify we are genuinely at Home Village
        # If Home Village landmarks (attack button or build button) are already visible, we are 100% at HOME_VILLAGE
        has_home_hud = (
            self.detector.find_template(frame, "attack_button", threshold=0.55) is not None
            or self.detector.find_template(frame, "build_button", threshold=0.58) is not None
        )
        if not has_home_hud:
            active_screen = self.ocr.detect_screen(frame) if self.ocr else "HOME_VILLAGE"
            if active_screen == "BATTLE_RESULTS":
                print("[HomeVillage] Detected active Battle Results screen. Returning home cleanly...")
                self.attack_engine.surrender_and_return_home()
                return
            elif active_screen == "ATTACKING":
                print("[HomeVillage] Detected unended combat screen. Surrendering cleanly to return home...")
                self.attack_engine.surrender_and_return_home()
                return
            elif active_screen == "MATCHMAKING":
                print("[HomeVillage] Detected active matchmaking search. Switching to MATCHMAKING state.")
                self.set_state(BotState.MATCHMAKING)
                return

        storages = self.ocr.read_village_storages(frame)
        # If storages read 0 | 0, retry once after a short settle delay to avoid transient fade errors
        if storages.get("gold", 0) == 0 and storages.get("elixir", 0) == 0:
            self.sleep_interruptible(0.6)
            frame = self.capture.get_frame(target_size=(1280, 720))
            storages = self.ocr.read_village_storages(frame)

        caps = village_profile.get_max_storage_capacities()
        max_g = caps.get("gold", 5504500)
        max_e = caps.get("elixir", 5503000)

        if storages.get("gold_full") and storages.get("gold", 0) < max_g * 0.9:
            storages["gold"] = max_g
        if storages.get("elixir_full") and storages.get("elixir", 0) < max_e * 0.9:
            storages["elixir"] = max_e

        realtime_learner.learn_storage_reading(storages)
        gold_tag = " (FULL)" if storages.get("gold_full") else ""
        elixir_tag = " (FULL)" if storages.get("elixir_full") else ""
        print(f"[HomeVillage] Current Storages - Gold: {storages.get('gold', 0):,}{gold_tag} | Elixir: {storages.get('elixir', 0):,}{elixir_tag}")
        self._last_storages = storages
        if self.on_stats_update:
            try:
                self.on_stats_update(storages)
            except Exception:
                pass

        bot_mode = self.cfg.get("general", {}).get("bot_mode", "BOTH").upper()
        w_cfg = self.cfg.get("wall_dump", {})
        wall_enabled = w_cfg.get("enabled", True)

        # Storage capacity and depletion checks
        pct_g = storages.get("gold", 0) / max(1, max_g)
        pct_e = storages.get("elixir", 0) / max(1, max_e)
        storage_is_full = self.is_storage_full(storages) or (pct_g >= 0.90 and pct_e >= 0.90)

        min_wall_cost = getattr(self.wall_upgrader, "_last_selected_wall_cost", 500000) or 500000
        avail_g = max(0, storages.get("gold", 0) - max(2000, w_cfg.get("keep_gold_reserve", 2000)))
        avail_e = max(0, storages.get("elixir", 0) - w_cfg.get("keep_elixir_reserve", 0))
        can_afford_wall = (avail_g >= min_wall_cost or avail_e >= min_wall_cost)
        above_depletion_reserve = (pct_g > 0.15 or pct_e > 0.15)

        # 1. ONLY_ATTACK mode check: STOP attacks if storages are almost full!
        if bot_mode == "ONLY_ATTACK":
            wall_enabled = False
            if storage_is_full:
                print(f"[HomeVillage] 🛑 Storages are full (Gold: {storages.get('gold', 0):,} ({pct_g:.1%}), Elixir: {storages.get('elixir', 0):,} ({pct_e:.1%})). Halting bot safely to prevent wasting raid loot.")
                self.stop()
                return

        # 2. ONLY_WALL_DUMP mode check: STOP bot if storages are depleted to reserve (around 10-20%) or cannot afford wall
        if bot_mode == "ONLY_WALL_DUMP":
            if not can_afford_wall or not above_depletion_reserve:
                print(f"[HomeVillage] 🧱 'Only Wall Dump' mode: Storages depleted to reserve (Gold: {storages.get('gold', 0):,} ({pct_g:.1%}), Elixir: {storages.get('elixir', 0):,} ({pct_e:.1%})). Cannot afford additional wall ({min_wall_cost:,}). Halting bot safely.")
                self.stop()
                return

        stop_on_busy = w_cfg.get("stop_if_builders_busy", True)
        trigger_mode = w_cfg.get("dump_trigger_mode", "WHEN_FULL").upper()
        dump_n = w_cfg.get("dump_every_n_attacks", 5)

        should_dump_walls = False
        if wall_enabled:
            if bot_mode == "ONLY_WALL_DUMP":
                should_dump_walls = can_afford_wall and above_depletion_reserve
            elif storage_is_full:
                should_dump_walls = True
            elif trigger_mode == "WHEN_FULL":
                should_dump_walls = storage_is_full
            elif trigger_mode == "EVERY_N_ATTACKS":
                should_dump_walls = (self.attacks_since_last_wall_dump >= dump_n) and can_afford_wall
            elif trigger_mode == "HYBRID":
                should_dump_walls = (storage_is_full or self.attacks_since_last_wall_dump >= dump_n) and can_afford_wall
            else:
                should_dump_walls = storage_is_full

        if should_dump_walls:
            builders_busy = self.detector.has_zero_free_builders(frame)
            if builders_busy:
                print(f"[HomeVillage] 🛑 Wall dump condition reached (mode: {bot_mode}, attacks={self.attacks_since_last_wall_dump}/{dump_n}), but all builders are busy!")
                if storage_is_full and stop_on_busy:
                    print("[HomeVillage] Halting bot to prevent wasting farmed raid loot. Free up a builder or spend resources.")
                    self.stop()
                    return
            else:
                reason = "Only Wall Dump Mode" if bot_mode == "ONLY_WALL_DUMP" else ("Storages Full" if storage_is_full else f"Every {dump_n} Attacks ({self.attacks_since_last_wall_dump} completed)")
                print(f"[HomeVillage] Free builder available! Prioritizing Wall Upgrades ({reason}) before any attack...")
                self.set_state(BotState.CHECK_WALL_DUMP)
                return

        # If in 'ONLY_WALL_DUMP' mode, do NOT attack!
        if bot_mode == "ONLY_WALL_DUMP":
            print("[HomeVillage] 'Only Wall Dump' mode: Wall dump complete. Halting bot safely.")
            self.stop()
            return

        # 2. Check minimum Gold for matchmaking (single match search costs 1,700 Gold)
        SEARCH_COST_PER_MATCH = 1700
        cur_gold = storages.get("gold", 0) if storages else (self._last_storages.get("gold", 0) if hasattr(self, "_last_storages") and self._last_storages else 0)
        if cur_gold > 0 and cur_gold < SEARCH_COST_PER_MATCH:
            print(f"[HomeVillage] ⚠️ Insufficient Gold: Current Gold storage has {cur_gold:,}, but a single matchmaking search costs {SEARCH_COST_PER_MATCH:,} Gold!")
            print("[HomeVillage] Cannot start matchmaking. Collecting from gold mines and resting...")
            self.sleep_interruptible(3.0)
            self.set_state(BotState.HOME_VILLAGE)
            return

        # 3. Base Maintenance or Matchmaking
        maint_enabled = self.cfg.get("maintenance", {}).get("enabled", False)
        if maint_enabled:
            self.set_state(BotState.MAINTENANCE)
        else:
            self.set_state(BotState.MATCHMAKING)

    def _handle_wall_dump(self):
        if self._check_and_handle_disconnect():
            return
        if self.check_abort():
            return

        bot_mode = self.cfg.get("general", {}).get("bot_mode", "BOTH").upper()
        print("[State: CHECK_WALL_DUMP] Checking village storages for wall dumping...")
        frame = self.capture.get_frame(target_size=(1280, 720))
        storages = self.ocr.read_village_storages(frame) if self.ocr else {}
        caps = village_profile.get_max_storage_capacities()
        max_g = caps.get("gold", 5504500)
        max_e = caps.get("elixir", 5503000)
        if storages.get("gold_full") and storages.get("gold", 0) < max_g * 0.9:
            storages["gold"] = max_g
        if storages.get("elixir_full") and storages.get("elixir", 0) < max_e * 0.9:
            storages["elixir"] = max_e

        gold_tag = " (FULL)" if storages.get("gold_full") else ""
        elixir_tag = " (FULL)" if storages.get("elixir_full") else ""
        print(f"[WallUpgrader] Current Storages - Gold: {storages.get('gold', 0):,}{gold_tag} | Elixir: {storages.get('elixir', 0):,}{elixir_tag}")
        if self.on_stats_update:
            try:
                self.on_stats_update(storages)
            except Exception:
                pass

        # Check builder availability
        if self.detector.has_zero_free_builders(frame):
            print("[WallUpgrader] 0 free builders available (all builders busy).")
            if self.is_storage_full(storages) and self.cfg.get("wall_dump", {}).get("stop_if_builders_busy", True):
                print("[WallUpgrader] 🛑 Storages are full and builders are busy. Stopping bot.")
                self.stop()
                return
            else:
                self.set_state(BotState.MATCHMAKING)
                return

        # Loop wall dump cycles until excess resources are fully spent on walls
        dump_cycles = 0
        max_cycles = 15
        w_cfg = self.cfg.get("wall_dump", {})

        while self.is_running and dump_cycles < max_cycles:
            if self.check_abort():
                return
            result = self.wall_upgrader.check_and_dump_resources(storages_dict=storages, force=True)
            dump_cycles += 1
            if self.check_abort():
                return

            is_success = bool(result and (result.get("success", False) if isinstance(result, dict) else result))

            # Deduct spent resources from locally tracked storages if batch succeeded
            if isinstance(result, dict) and result.get("success"):
                res_key = result.get("resource", "GOLD").lower()
                spent_amt = result.get("spent_amount", 0)
                storages[res_key] = max(0, storages.get(res_key, 0) - spent_amt)
                print(f"[WallUpgrader] Batch {dump_cycles}: Successfully upgraded {result.get('walls_upgraded', 1)} wall(s) using {result.get('resource')}.")

            # Re-check storages cleanly from home village screen
            self.sleep_interruptible(1.2)
            self.adb.tap_empty_grass()
            self.sleep_interruptible(0.6)

            frame_after = self.capture.get_frame(target_size=(1280, 720))
            storages_after = self.ocr.read_village_storages(frame_after)

            # Avoid false zeros if screen was mid-transition or HUD closing
            if storages_after.get("gold", 0) == 0 and storages_after.get("elixir", 0) == 0:
                self.sleep_interruptible(0.8)
                frame_after = self.capture.get_frame(target_size=(1280, 720))
                storages_after = self.ocr.read_village_storages(frame_after)

            if storages_after.get("gold", 0) > 50000 or storages_after.get("elixir", 0) > 50000:
                storages = storages_after

            if self.on_stats_update:
                try:
                    self.on_stats_update(storages)
                except Exception:
                    pass

            avail_g = max(0, storages.get("gold", 0) - max(2000, w_cfg.get("keep_gold_reserve", 2000)))
            avail_e = max(0, storages.get("elixir", 0) - w_cfg.get("keep_elixir_reserve", 0))

            if self.detector.has_zero_free_builders(frame_after):
                print("[WallUpgrader] All builders became busy. Ending wall dump loop.")
                break

            caps = village_profile.get_max_storage_capacities()
            max_g = caps.get("gold", 5504500)
            max_e = caps.get("elixir", 5503000)
            pct_g = storages.get("gold", 0) / max(1, max_g)
            pct_e = storages.get("elixir", 0) / max(1, max_e)
            min_wall_cost = getattr(self.wall_upgrader, "_last_selected_wall_cost", 500000) or 500000

            can_afford_wall = (avail_g >= min_wall_cost or avail_e >= min_wall_cost)
            above_reserve = (pct_g > 0.15 or pct_e > 0.15)

            if not is_success or not can_afford_wall or not above_reserve:
                print(f"[WallUpgrader] Wall dump cycle complete: Storages at reserve (Gold: {storages.get('gold', 0):,} ({pct_g:.1%}), Elixir: {storages.get('elixir', 0):,} ({pct_e:.1%})). Next wall cost: {min_wall_cost:,}.")
                if bot_mode == "ONLY_WALL_DUMP":
                    print("[WallUpgrader] 'Only Wall Dump' mode active. Halting bot safely (all affordable walls upgraded).")
                    self.stop()
                    return
                else:
                    print("[FSM] >>> Transitioning to ATTACK to raid and fill storages! <<<")
                    break
            else:
                print(f"[WallUpgrader] Additional excess resources remaining (Avail Gold: {avail_g:,}, Avail Elixir: {avail_e:,}). Continuing wall dump batch ({dump_cycles}/{max_cycles})...")

        self._last_storages = storages
        self.attacks_since_last_wall_dump = 0

        bot_mode = self.cfg.get("general", {}).get("bot_mode", "BOTH").upper()
        if bot_mode == "ONLY_WALL_DUMP":
            print("[WallUpgrader] 'Only Wall Dump' mode active. Halting bot safely.")
            self.stop()
            return

        maint_enabled = self.cfg.get("maintenance", {}).get("enabled", False)
        if maint_enabled:
            self.set_state(BotState.MAINTENANCE)
        else:
            self.set_state(BotState.MATCHMAKING)

    def _handle_maintenance(self):
        if self._check_and_handle_disconnect():
            return

        maint_enabled = self.cfg.get("maintenance", {}).get("enabled", False)
        if maint_enabled:
            print("[State: MAINTENANCE] Executing quick train and collector harvesting...")
            self.maintenance.run_all_maintenance()
        else:
            print("[State: MAINTENANCE] Base maintenance disabled in configuration. Skipping to Matchmaking.")

        self.set_state(BotState.MATCHMAKING)

    def _handle_matchmaking(self, is_manual_test=False):
        if self._check_and_handle_disconnect():
            return
        if self.check_abort():
            return

        # Check if storages are almost full before starting an attack
        bot_mode = self.cfg.get("general", {}).get("bot_mode", "BOTH").upper()
        if hasattr(self, "_last_storages") and self._last_storages and not is_manual_test:
            if self.is_storage_full(self._last_storages):
                # Verify with a fresh frame before aborting to avoid false positives from stale or transient caches
                frame_chk = self.capture.get_frame(target_size=(1280, 720)) if self.capture else None
                if frame_chk is not None and self.ocr:
                    fresh_st = self.ocr.read_village_storages(frame_chk)
                    if fresh_st.get("gold", 0) > 0 or fresh_st.get("elixir", 0) > 0:
                        self._last_storages = fresh_st
                if self.is_storage_full(self._last_storages):
                    print(f"[Matchmaking] 🛑 Storages are full (Gold: {self._last_storages.get('gold', 0):,}, Elixir: {self._last_storages.get('elixir', 0):,})! Stopping attack to prevent wasting loot.")
                    if bot_mode == "BOTH":
                        print("[Matchmaking] Transitioning to Wall Dump to sink excess loot before raiding.")
                        self.set_state(BotState.CHECK_WALL_DUMP)
                        return
                    else:
                        print("[Matchmaking] 'Only Attack' mode active and storages full. Halting bot safely.")
                        self.stop()
                        return

        # Check Gold balance and calculate maximum possible search skips (1,700 Gold per match search)
        SEARCH_COST_PER_MATCH = 1700
        cur_gold = self._last_storages.get("gold", 0) if hasattr(self, "_last_storages") and self._last_storages else 0
        if cur_gold > 0 and cur_gold < SEARCH_COST_PER_MATCH:
            print(f"[Matchmaking] 🛑 Insufficient Gold for matchmaking: Storage has {cur_gold:,} Gold, but a single attack search costs {SEARCH_COST_PER_MATCH:,} Gold!")
            print("[Matchmaking] Cannot initiate attack. Returning to Home Village to collect from mines.")
            self.set_state(BotState.HOME_VILLAGE)
            return

        is_emergency_gold_raid = False
        if cur_gold > 0:
            max_affordable_skips = max(1, cur_gold // SEARCH_COST_PER_MATCH)
            if max_affordable_skips <= 1:
                is_emergency_gold_raid = True
                print(f"[Matchmaking] ⚠️ LOW-GOLD WARNING: Storage has {cur_gold:,} Gold (affords ONLY 1 search). EMERGENCY RAID MODE: Will attack the FIRST base to farm gold!")
            else:
                print(f"[Matchmaking] Gold balance: {cur_gold:,} -> Affords up to {max_affordable_skips} search skips ({SEARCH_COST_PER_MATCH:,} Gold per search).")

        print("\n[State: MATCHMAKING] Starting fast search for target base...")
        # Check if we are already on an enemy base with Next button (e.g. after cloud search or resume)
        frame_entry = self.capture.get_frame(target_size=(1280, 720))
        already_on_target = False
        if frame_entry is not None:
            is_home = (
                self.detector.find_template(frame_entry, "attack_button", threshold=0.62) is not None
                or self.detector.find_template(frame_entry, "build_button", threshold=0.62) is not None
            )
            if not is_home:
                next_pos = self.detector.check_next_button(frame_entry)
                end_pos = self.detector.find_template(frame_entry, "end_battle_button", threshold=0.65)
                loot_test = self.ocr.read_search_loot(frame_entry) if hasattr(self, "ocr") and self.ocr else {}
                has_loot = (loot_test.get("gold", 0) > 0 or loot_test.get("elixir", 0) > 0)
                if next_pos and (end_pos or has_loot):
                    print("[Matchmaking] Already on target search screen. Skipping menu navigation and evaluating loot directly...")
                    already_on_target = True

        if not already_on_target:
            # Check if My Army confirmation window is open (e.g. user left it open or viewed army)
            if frame_entry is not None:
                screen_entry = self.ocr.detect_screen(frame_entry) if hasattr(self, "ocr") and self.ocr else ""
                army_pos = self.detector.find_template(frame_entry, "army_attack_button", threshold=0.60)
                if screen_entry == "MY_ARMY_WINDOW" or army_pos is not None:
                    target_army = army_pos or (1131, 642)
                    print(f"[Matchmaking] 'My Army' window detected. Tapping green 'Attack!' button at {target_army}...")
                    self.adb.tap(target_army[0], target_army[1])
                    self.sleep_interruptible(1.2)
                    frame_entry = self.capture.get_frame(target_size=(1280, 720))

            # 1. Clear any active selection or dialog
            self.adb.tap_empty_grass()
            self.sleep_interruptible(0.2)
            if self.check_abort():
                return

            # 2. Dismiss any open entity toolbar before tapping Battle button
            self.adb.tap_empty_grass()
            self.sleep_interruptible(0.3)

            find_pos = None
            for attempt in range(3):
                if self.check_abort():
                    return
                frame = self.capture.get_frame(target_size=(1280, 720))
                attack_pos = self.detector.find_template(frame, "attack_button") or self.detector.get_calibrated_coord("attack_button") or (82, 640)
                # Strict Clan War exclusion safeguard: Battle button is at x: 35..120, y: 620..680. Clan War is at (55, 500).
                if attack_pos[1] < 620 or attack_pos[0] < 35 or attack_pos[0] > 125:
                    attack_pos = (82, 640)
                print(f"[Matchmaking] Tapping Attack button at {attack_pos} (attempt {attempt + 1}/3)...")
                rand_ax = attack_pos[0] + random.randint(-6, 6)
                rand_ay = attack_pos[1] + random.randint(-6, 6)
                self.adb.tap(rand_ax, rand_ay, min_delay=0.08, max_delay=0.15)

                # Fast poll for Multiplayer Attack menu window (every 60ms, up to 1.0s)
                find_pos = None
                for _ in range(16):
                    if self.check_abort():
                        return
                    self.sleep_interruptible(0.06)
                    frame_menu = self.capture.get_frame(target_size=(1280, 720))
                    if frame_menu is None:
                        continue

                    # Direct color check for orange 'Find a Match' button (x: 180..280, y: 520..570)
                    crop_btn = frame_menu[520:570, 180:280]
                    if crop_btn.size > 0:
                        orange_px = np.sum((crop_btn[:, :, 2] > 190) & (crop_btn[:, :, 1] > 110) & (crop_btn[:, :, 0] < 80))
                        if orange_px > 180:
                            find_pos = (218, 545)
                            break

                    find_pos = self.detector.find_template(frame_menu, "find_match_button")
                    if find_pos:
                        break

                    modal_btn = self.detector.check_modal_popup(frame_menu)
                    if modal_btn:
                        print(f"[Matchmaking] Modal popup detected. Dismissing at {modal_btn}...")
                        self.adb.tap(modal_btn[0], modal_btn[1])
                        self.sleep_interruptible(0.2)
                        self.adb.send_keyevent(4)
                        continue

                if find_pos:
                    break

            find_pos = find_pos or self.detector.get_calibrated_coord("find_match_button") or (218, 545)
            print(f"[Matchmaking] Tapping 'Find a Match' button at {find_pos}...")
            find_x = find_pos[0] + random.randint(-8, 8)
            find_y = find_pos[1] + random.randint(-5, 5)
            self.adb.tap(find_x, find_y, min_delay=0.08, max_delay=0.15)

            # 4. Fast check for My Army Confirmation window or immediate matchmaking start
            for _ in range(6):
                if self.check_abort():
                    return
                frame_army = self.capture.get_frame(target_size=(1280, 720))
                if frame_army is not None:
                    # Check if matchmaking already transitioned to enemy base or clouds
                    loot_early = self.ocr.read_search_loot(frame_army) if self.ocr else {}
                    crop_early_next = frame_army[490:600, 1060:1270]
                    is_orange_next = (crop_early_next.size > 0 and np.sum((crop_early_next[:, :, 2] > 185) & (crop_early_next[:, :, 1] > 110) & (crop_early_next[:, :, 0] < 90)) >= 120)
                    if loot_early.get("gold", 0) > 0 or is_orange_next:
                        break

                    army_btn = self.detector.check_army_attack_btn(frame_army)
                    if army_btn:
                        print(f"[Matchmaking] Confirming Army Attack button at {army_btn}...")
                        army_x = army_btn[0] + random.randint(-8, 8)
                        army_y = army_btn[1] + random.randint(-5, 5)
                        self.adb.tap(army_x, army_y, min_delay=0.08, max_delay=0.15)
                        self.sleep_interruptible(0.2)
                        break

                    modal_army = self.detector.check_modal_popup(frame_army)
                    if modal_army:
                        print(f"[Matchmaking] Modal detected on army window. Dismissing at {modal_army}...")
                        self.adb.tap(modal_army[0], modal_army[1])
                        self.sleep_interruptible(0.2)
                        self.adb.send_keyevent(4)

                self.sleep_interruptible(0.06)

            # 5. Check if already on enemy base; otherwise poll for clouds to clear
            frame = self.capture.get_frame(target_size=(1280, 720))
            clouds_cleared = False
            if frame is not None:
                loot_test = self.ocr.read_search_loot(frame) if self.ocr else {}
                crop_next = frame[490:600, 1060:1270]
                has_orange = (crop_next.size > 0 and np.sum((crop_next[:, :, 2] > 185) & (crop_next[:, :, 1] > 110) & (crop_next[:, :, 0] < 90)) >= 120)
                if loot_test.get("gold", 0) > 0 or has_orange:
                    clouds_cleared = True

            if not clouds_cleared:
                print("[Matchmaking] Waiting for matchmaking clouds to clear...")
                for c_idx in range(120):
                    if self.check_abort():
                        return
                    frame = self.capture.get_frame(target_size=(1280, 720))
                    if frame is None:
                        self.sleep_interruptible(0.06)
                        continue

                    # Fast Check 1: Raid loot digits appearing in top-left (<4ms)
                    loot_test = self.ocr.read_search_loot(frame) if self.ocr else {}
                    if loot_test.get("gold", 0) > 0 or loot_test.get("elixir", 0) > 0:
                        clouds_cleared = True
                        break

                    # Fast Check 2: Direct color detection of 'Next' button (orange rect at 1060..1270, 490..600)
                    crop_next = frame[490:600, 1060:1270]
                    if crop_next.size > 0:
                        orange_pixels = np.sum((crop_next[:, :, 2] > 185) & (crop_next[:, :, 1] > 110) & (crop_next[:, :, 0] < 90))
                        if orange_pixels >= 120:
                            clouds_cleared = True
                            break

                    # Fast Check 3: Direct color detection of 'End Battle' button (red rect at 15..170, 530..610)
                    crop_end = frame[530:610, 15:170]
                    if crop_end.size > 0:
                        red_pixels = np.sum((crop_end[:, :, 2] > 160) & (crop_end[:, :, 1] < 75) & (crop_end[:, :, 0] < 75))
                        if red_pixels >= 100:
                            clouds_cleared = True
                            break

                    # Modals checked occasionally to eliminate lag
                    if c_idx % 8 == 0 and c_idx > 0:
                        modal_pop = self.detector.check_modal_popup(frame)
                        if modal_pop:
                            print(f"[Matchmaking] Modal detected during search transition. Dismissing at {modal_pop}...")
                            self.adb.tap(modal_pop[0], modal_pop[1])
                            self.sleep_interruptible(0.2)
                            self.adb.send_keyevent(4)

                    self.sleep_interruptible(0.06)

            if not clouds_cleared:
                print("[Matchmaking] Notice: Clouds took too long to clear. Escaping back to Home Village...")
                self.adb.send_keyevent(4)
                self.sleep_interruptible(0.6)
                self.adb.send_keyevent(4)
                self.sleep_interruptible(1.0)
                self.set_state(BotState.HOME_VILLAGE)
                return

        mm_cfg = self.cfg.get("matchmaking", {})
        min_g = mm_cfg.get("min_gold", 500000)
        min_e = mm_cfg.get("min_elixir", 500000)
        min_de = mm_cfg.get("min_dark_elixir", 4000)
        logic = mm_cfg.get("match_logic", "OR").upper()
        max_skips = mm_cfg.get("max_search_skips", 60)
        # Dynamically cap search limit based on multiples of 1,700 Gold available
        if cur_gold > 0:
            max_affordable_skips = max(1, cur_gold // SEARCH_COST_PER_MATCH)
            search_limit = min(max_skips, max_affordable_skips)
        else:
            search_limit = 5 if is_manual_test else max_skips

        skips = 0
        while (self.is_running or is_manual_test) and skips < search_limit:
            if self.check_abort():
                return
            if self._check_and_handle_disconnect():
                return

            # Stabilized Raid Loot Reading: Ensure digits are fully loaded and settled
            gold, elixir, de = 0, 0, 0
            for attempt in range(12):
                if self.check_abort():
                    return
                frame = self.capture.get_frame(target_size=(1280, 720))
                if frame is not None:
                    # Immediate check: if user clicked Cancel or screen is back at Home Village, abort cleanly
                    if self.detector.find_template(frame, "attack_button", threshold=0.68) or self.detector.find_template(frame, "build_button", threshold=0.68):
                        print("[Matchmaking] Detected Home Village screen (attack/matchmaking was cancelled). Safely returning to HOME_VILLAGE.")
                        self.set_state(BotState.HOME_VILLAGE)
                        return

                    loot_test = self.ocr.read_search_loot(frame) if self.ocr else {}
                    gt, et, dt = loot_test.get("gold", 0), loot_test.get("elixir", 0), loot_test.get("dark_elixir", 0)

                    # If digits are detected, verify stability 120ms later to prevent reading partial rolling animations
                    if gt > 0 or et > 0:
                        self.sleep_interruptible(0.12)
                        frame_v = self.capture.get_frame(target_size=(1280, 720))
                        loot_v = self.ocr.read_search_loot(frame_v) if self.ocr else {}
                        gv, ev, dv = loot_v.get("gold", 0), loot_v.get("elixir", 0), loot_v.get("dark_elixir", 0)
                        # Pick the larger / fully settled reading
                        gold = max(gt, gv)
                        elixir = max(et, ev)
                        de = max(dt, dv)
                        break

                self.sleep_interruptible(0.08)
            else:
                if frame is not None:
                    loot = self.ocr.read_search_loot(frame) if self.ocr else {}
                    gold = loot.get("gold", 0)
                    elixir = loot.get("elixir", 0)
                    de = loot.get("dark_elixir", 0)

            print(f"[Scanner] Target #{skips + 1}: Gold: {gold:,} | Elixir: {elixir:,} | Dark Elixir: {de:,}")

            meets_criteria = False
            if is_emergency_gold_raid:
                # Emergency mode: cannot afford to skip! Attack Target #1 immediately to farm gold!
                meets_criteria = (gold > 0 or elixir > 0 or de > 0)
                if meets_criteria:
                    print(f"[Scanner] >>> EMERGENCY LOW-GOLD RAID! Attacking Target #{skips + 1} immediately (Gold: {gold:,}, Elixir: {elixir:,}) to recover gold balance! <<<")
            elif skips >= (search_limit - 1):
                # Last affordable search skip reached! Attack this base to prevent running out of gold!
                meets_criteria = (gold > 0 or elixir > 0)
                if meets_criteria:
                    print(f"[Scanner] >>> LAST AFFORDABLE SKIP REACHED (Target #{skips + 1})! Attacking to prevent zero-gold lockout (Gold: {gold:,}, Elixir: {elixir:,})! <<<")
            else:
                if logic == "AND":
                    meets_criteria = (gold >= min_g and elixir >= min_e and de >= min_de)
                else:
                    meets_criteria = (gold >= min_g or elixir >= min_e) and (de >= min_de)

            if meets_criteria and (gold > 0 or elixir > 0):
                if not is_emergency_gold_raid and skips < (search_limit - 1):
                    print(f"[Scanner] >>> TARGET ACCEPTED! Meets criteria (Gold: {gold:,}, Elixir: {elixir:,}, DE: {de:,}) <<<")
                self.sleep_interruptible(0.2)
                if is_manual_test:
                    print("[Manual Test] Target verified! Safely ending test and returning home...")
                    self._handle_returning_home()
                    return
                else:
                    self.set_state(BotState.ATTACKING)
                    return

            # Fast Skip base: tap 'Next' with humanized glance
            if self.check_abort():
                return
            quick_pause = random.uniform(0.08, 0.14)
            self.sleep_interruptible(quick_pause)
            if self.check_abort():
                return

            next_pos = self.detector.find_template(frame, "next_button", threshold=0.58) or self.detector.get_calibrated_coord("next_button") or (1166, 540)
            print(f"[Scanner] Skipping base #{skips + 1}. Tapping 'Next' at {next_pos}...")
            rand_nx = next_pos[0] + random.randint(-8, 8)
            rand_ny = next_pos[1] + random.randint(-6, 6)
            self.adb.tap(rand_nx, rand_ny, min_delay=0.06, max_delay=0.12)
            skips += 1

            # 1. Wait for matchmaking transition to start: old Next button disappears or clouds roll in (at least 350ms)
            self.sleep_interruptible(0.35)

            # 2. Wait for clouds to clear and new base HUD to appear
            for _ in range(80):
                if self.check_abort():
                    return
                frame_next = self.capture.get_frame(target_size=(1280, 720))
                if frame_next is None:
                    self.sleep_interruptible(0.06)
                    continue

                # Cloud check: center crop must NOT be white cloud
                center_crop = frame_next[250:470, 450:830]
                cb, cg, cr = float(np.mean(center_crop[:, :, 0])), float(np.mean(center_crop[:, :, 1])), float(np.mean(center_crop[:, :, 2]))
                is_cloud = (cb > 175 and cg > 175 and cr > 175 and center_crop.std() < 28)

                # Orange Next button check on new base
                crop_n = frame_next[490:600, 1060:1270]
                has_orange_next = (crop_n.size > 0 and np.sum((crop_n[:, :, 2] > 185) & (crop_n[:, :, 1] > 110) & (crop_n[:, :, 0] < 90)) >= 120)

                # Red End battle check
                crop_e = frame_next[530:610, 15:170]
                has_red_end = (crop_e.size > 0 and np.sum((crop_e[:, :, 2] > 160) & (crop_e[:, :, 1] < 75) & (crop_e[:, :, 0] < 75)) >= 100)

                if (has_orange_next or has_red_end) and not is_cloud:
                    break

                self.sleep_interruptible(0.06)

        print(f"[Scanner] Search limit reached ({skips} skips). Returning home to reset.")
        self._handle_returning_home()
        if not is_manual_test:
            self.set_state(BotState.RETURNING_HOME)

    def _handle_attacking(self):
        if self.check_abort():
            return
        frame = self.capture.get_frame(target_size=(1280, 720))
        if frame is not None and (self.detector.find_template(frame, "attack_button", threshold=0.68) or self.detector.find_template(frame, "build_button", threshold=0.68)):
            print("[State: ATTACKING] Detected Home Village (battle was cancelled by user). Returning to HOME_VILLAGE.")
            self.set_state(BotState.HOME_VILLAGE)
            return

        # Check if screen is an unended/depleted combat session without Next button
        has_next = (
            self.detector.find_template(frame, "next_button", threshold=0.58) is not None
            or (hasattr(self.detector, "check_next_button") and self.detector.check_next_button(frame) is not None)
        )
        if not has_next:
            loot = self.ocr.read_search_loot(frame) if self.ocr else {}
            g = loot.get("gold", 0)
            e = loot.get("elixir", 0)
            if (g > 0 or e > 0) and g < 100000 and e < 100000:
                print(f"[AttackEngine] Safety Interlock: Combat screen has depleted loot (Gold: {g:,}, Elixir: {e:,}). Surrendering cleanly to return home...")
                self.attack_engine.surrender_and_return_home()
                self.set_state(BotState.HOME_VILLAGE)
                return

        print("\n[State: ATTACKING] Executing battle attack plan...")
        recipe_name = self.cfg.get("maintenance", {}).get("active_recipe_name", "Sneaky_Goblins_Farming")
        self.attack_engine.execute_recipe_attack(recipe_name=recipe_name)
        self.total_attacks_completed += 1
        self.attacks_since_last_wall_dump += 1
        print(f"[State: ATTACKING] Battle completed! Total raids so far: {self.total_attacks_completed} (Since wall dump: {self.attacks_since_last_wall_dump})")
        self.set_state(BotState.HOME_VILLAGE)

    def _handle_returning_home(self):
        print("[State: RETURNING_HOME] Returning to home village...")
        if self.attack_engine:
            self.attack_engine.surrender_and_return_home()
        else:
            self.adb.tap_empty_grass()
        self.set_state(BotState.HOME_VILLAGE)
