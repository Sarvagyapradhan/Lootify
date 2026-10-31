"""
Clash of Clans Automation Bot - Main Controller & Entrypoint.
Provides full automation loop and individual test modes for Hero Abilities,
Wall Dumping, Quick Train, and Loot OCR scanning.
"""

import os
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
import sys
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
import yaml

from core.adb_client import ADBController
from core.screen_capture import ScreenCapture
from vision.detector import UIDetector
from vision.ocr_reader import LootOCRReader
from bot.attack_engine import AttackEngine
from bot.wall_upgrader import WallUpgrader
from bot.maintenance import BaseMaintenance
from bot.state_machine import BotStateMachine


def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def load_yaml(relative_path):
    full_path = os.path.join(get_base_dir(), relative_path)
    if not os.path.exists(full_path):
        print(f"[Error] Config file not found: {full_path}")
        return {}
    with open(full_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def print_banner():
    print("""
====================================================================
           CLASH OF CLANS ADVANCED FARMING BOT
   - Hero Equipment & Ability Timers
   - Multi-Recipe Army Deployment
   - Fast Loot Matchmaking Scanner
   - Full-Storage Wall Dumping
   - Quick Train & Village Maintenance
====================================================================
""")


def main():
    if "--cli" not in sys.argv:
        try:
            import gui
            gui.main()
            return
        except Exception as e:
            print(f"[Launcher] GUI launch encountered error ({e}). Falling back to interactive CLI...")

    print_banner()

    # 1. Load Configurations
    settings = load_yaml("config/settings.yaml")
    heroes_cfg = load_yaml("config/heroes.yaml")
    recipes_cfg = load_yaml("config/army_recipes.yaml")

    emu_cfg = settings.get("emulator", {})
    adb_host = emu_cfg.get("adb_host", "127.0.0.1")
    adb_port = emu_cfg.get("adb_port", 21503)
    custom_adb = emu_cfg.get("custom_adb_path", None)
    title_pattern = emu_cfg.get("window_title_pattern", "LDPlayer|MEmu|BlueStacks")

    # 2. Initialize Subsystems
    print("[Init] Connecting to ADB controller...")
    adb = ADBController(host=adb_host, port=adb_port, custom_adb_path=custom_adb)

    print("[Init] Initializing high-speed screen capture engine...")
    capture = ScreenCapture(target_title_pattern=title_pattern, adb_controller=adb)

    print("[Init] Loading UI detector & OCR reader...")
    detector = UIDetector()
    ocr = LootOCRReader()

    print("[Init] Initializing Bot Action Engines...")
    attack_engine = AttackEngine(adb, detector, heroes_cfg, recipes_cfg, global_config=settings)
    wall_upgrader = WallUpgrader(adb, detector, settings, screen_capture=capture, ocr_reader=ocr)
    maintenance = BaseMaintenance(adb, detector, settings)

    fsm = BotStateMachine(
        adb_controller=adb,
        screen_capture=capture,
        ui_detector=detector,
        ocr_reader=ocr,
        attack_engine=attack_engine,
        wall_upgrader=wall_upgrader,
        maintenance_module=maintenance,
        global_config=settings
    )

    # 3. Interactive Menu or Auto-Start
    print("\nSelect an Operation:")
    print("  [1] Start Full Automated Farming Loop")
    print("  [2] Test Hero Deployment & Ability Delay Timers")
    print("  [3] Test Screen Capture & Loot OCR Scanner")
    print("  [4] Test Wall Dumping Routine via Builder Menu")
    print("  [5] Test Base Maintenance (Quick Train & Harvest)")
    print("  [6] Exit")

    choice = input("\nEnter choice [1-6] (Default is 1): ").strip() or "1"

    if choice == "1":
        fsm.start()

    elif choice == "2":
        recipe = settings.get("maintenance", {}).get("active_recipe_name", "Sneaky_Goblins_Farming")
        print(f"\n[Test] Running hero deployment test with recipe '{recipe}'...")
        attack_engine._deploy_heroes_with_ability_timers({"heroes": ["barbarian_king", "archer_queen", "grand_warden", "royal_champion"]})
        print("[Test] Hero test complete.")

    elif choice == "3":
        print("\n[Test] Capturing screen and testing OCR...")
        frame = capture.get_frame(target_size=(1280, 720))
        screen_type = ocr.detect_screen(frame)
        print(f"[Screen Detection] Current Screen: {screen_type}")
        if screen_type == "HOME_VILLAGE":
            storages = ocr.read_village_storages(frame)
            print(f"[Village Storages] Gold: {storages['gold']:,} | Elixir: {storages['elixir']:,} | Dark Elixir: {storages['dark_elixir']:,}")
        elif screen_type == "DISCONNECTED":
            print("[Village Status] Inactivity / Disconnection modal detected! Auto-recovery will reload.")
        else:
            loot = ocr.read_search_loot(frame)
            print(f"[Available Raid Loot] Gold: {loot['gold']:,} | Elixir: {loot['elixir']:,} | Dark Elixir: {loot['dark_elixir']:,}")
        capture.save_debug_screenshot("test_screen_capture.png")

    elif choice == "4":
        print("\n[Test] Testing wall dumping routine via Builder Menu...")
        frame = capture.get_frame(target_size=(1280, 720))
        storages = ocr.read_village_storages(frame)
        print(f"[Village Storages] Gold: {storages.get('gold', 0):,} | Elixir: {storages.get('elixir', 0):,}")
        wall_upgrader.check_and_dump_resources(storages_dict=storages, force=True)

    elif choice == "5":
        print("\n[Test] Testing Quick Train and base maintenance...")
        maintenance.run_all_maintenance()

    elif choice == "6":
        print("Exiting.")
        sys.exit(0)


if __name__ == "__main__":
    main()
