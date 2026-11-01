"""
ClashBot Autonomous Farming Suite - Streamlined Edition.
High-performance, elegant dark-themed control suite with live village telemetry,
emulator viewfinder, real-time activity streaming, and simple, intuitive controls.
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
import time
import yaml
import queue
import threading
import tkinter as tk
from tkinter import messagebox, filedialog
import customtkinter as ctk
from PIL import Image
import cv2

from core.adb_client import ADBController
from core.screen_capture import ScreenCapture
from vision.detector import UIDetector
from vision.ocr_reader import LootOCRReader
from bot.attack_engine import AttackEngine
from bot.wall_upgrader import WallUpgrader
from bot.maintenance import BaseMaintenance
from bot.state_machine import BotStateMachine, BotState
from core.village_parser import village_profile
from core.power_manager import PowerManager


def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


# Color Palette
BG_DARK = "#0b0f19"
PANEL_DARK = "#111827"
CARD_BG = "#1f2937"
CARD_BORDER = "#374151"
ACCENT_GOLD = "#f59e0b"
ACCENT_ELIXIR = "#ec4899"
ACCENT_DE = "#818cf8"
ACCENT_GREEN = "#10b981"
ACCENT_RED = "#ef4444"
TEXT_MAIN = "#f9fafb"
TEXT_MUTED = "#9ca3af"


class QueueStream:
    """Thread-safe stdout / stderr redirector to a queue."""
    def __init__(self, log_queue):
        self.log_queue = log_queue

    def write(self, text):
        if text:
            self.log_queue.put(text)

    def flush(self):
        pass


class ClashBotApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Appearance & Geometry
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")
        self.title("Lootify - Clash of Clans Autonomous AI Farming Suite")
        self.geometry("1140x740")
        self.minsize(980, 640)
        self.configure(fg_color=BG_DARK)

        # Config file path
        self.config_path = os.path.join(get_base_dir(), "config/settings.yaml")
        self.cfg = self._load_config()

        # Engine Modules
        self.adb = ADBController(
            host=self.cfg.get("emulator", {}).get("adb_host", "127.0.0.1"),
            port=self.cfg.get("emulator", {}).get("adb_port", 21503),
            custom_adb_path=self.cfg.get("emulator", {}).get("custom_adb_path"),
            jitter_radius=self.cfg.get("humanization", {}).get("click_jitter_radius", 5)
        )
        self.capture = ScreenCapture(
            target_title_pattern=self.cfg.get("emulator", {}).get("window_title_pattern", "MEmu"),
            adb_controller=self.adb
        )
        self.detector = UIDetector()
        self.ocr = LootOCRReader()
        heroes_path = os.path.join(get_base_dir(), "config/heroes.yaml")
        recipes_path = os.path.join(get_base_dir(), "config/army_recipes.yaml")
        heroes_cfg = {}
        if os.path.exists(heroes_path):
            with open(heroes_path, "r", encoding="utf-8") as f:
                heroes_cfg = yaml.safe_load(f) or {}
        recipes_cfg = {}
        if os.path.exists(recipes_path):
            with open(recipes_path, "r", encoding="utf-8") as f:
                recipes_cfg = yaml.safe_load(f) or {}

        self.attack_engine = AttackEngine(self.adb, self.detector, heroes_cfg, recipes_cfg, global_config=self.cfg)
        self.wall_upgrader = WallUpgrader(self.adb, self.detector, self.cfg, screen_capture=self.capture, ocr_reader=self.ocr)
        self.maintenance = BaseMaintenance(self.adb, self.detector, self.cfg)
        self.fsm = BotStateMachine(
            adb_controller=self.adb,
            screen_capture=self.capture,
            ui_detector=self.detector,
            ocr_reader=self.ocr,
            attack_engine=self.attack_engine,
            wall_upgrader=self.wall_upgrader,
            maintenance_module=self.maintenance,
            global_config=self.cfg
        )

        # Threading & Control
        self.bot_thread = None
        self.log_queue = queue.Queue()
        self.auto_refresh_view = tk.BooleanVar(value=True)
        self.show_tap_markers = tk.BooleanVar(value=True)
        self.last_preview_time = 0
        self._vf_updating = False

        # Stats state
        self.stat_gold = tk.StringVar(value="--")
        self.stat_gold_sub = tk.StringVar(value="Max: 5,504,500 • --%")
        self.stat_elixir = tk.StringVar(value="--")
        self.stat_elixir_sub = tk.StringVar(value="Max: 5,503,000 • --%")
        self.stat_de = tk.StringVar(value="--")
        self.stat_de_sub = tk.StringVar(value="Max: 100,000 • --%")
        self.stat_builders = tk.StringVar(value="--")
        self.stat_builders_sub = tk.StringVar(value="-- Busy • Next in: --")
        self.stat_raids = tk.StringVar(value="0")
        self.stat_bot_state = tk.StringVar(value="IDLE")

        # Redirect standard output
        self.orig_stdout = sys.stdout
        self.queue_stream = QueueStream(self.log_queue)
        sys.stdout = self.queue_stream

        # Wire FSM callbacks
        self.fsm.on_state_change = self._on_fsm_state_change
        self.fsm.on_stats_update = self._on_fsm_stats_update

        # Build Clean UI Layout
        self._build_layout()
        self._show_tab("dashboard")

        # Start periodic pollers
        self.after(100, self._process_log_queue)
        self.after(1000, self._tick_builder_countdown)
        self.after(1200, self._periodic_viewfinder_update)
        self.after(2000, self._periodic_telemetry_loop)
        self.after(500, self._initial_telemetry_fetch)

    def _load_config(self):
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"[Config] Error loading settings.yaml: {e}")
        return {}

    def _save_config(self):
        self._read_ui_into_config()
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                yaml.dump(self.cfg, f, default_flow_style=False, sort_keys=False)
            messagebox.showinfo("Success", "Settings successfully saved!")
            print("[Config] Settings saved to configuration file.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {e}")

    # ================= UI LAYOUT BUILDER =================
    def _build_layout(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # 1. Left Navigation Sidebar
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0, fg_color=PANEL_DARK, border_width=1, border_color=CARD_BORDER)
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        # Brand / Logo Header
        brand_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand_frame.pack(fill="x", padx=16, pady=(20, 16))
        title_lbl = ctk.CTkLabel(brand_frame, text="⚔️ LOOTIFY", font=ctk.CTkFont(size=20, weight="bold"), text_color=ACCENT_GOLD)
        title_lbl.pack(anchor="w")
        sub_lbl = ctk.CTkLabel(brand_frame, text="Autonomous AI Farming", font=ctk.CTkFont(size=11), text_color=TEXT_MUTED)
        sub_lbl.pack(anchor="w")

        # Navigation Buttons (Simple & Clean: Dashboard, Settings, Logs)
        self.nav_buttons = {}
        tabs = [
            ("dashboard", "📊  Dashboard"),
            ("settings", "⚙️  Settings"),
            ("logs", "📜  Activity Logs")
        ]
        for key, label in tabs:
            btn = ctk.CTkButton(
                self.sidebar, text=label, anchor="w",
                font=ctk.CTkFont(size=14, weight="normal"),
                fg_color="transparent", text_color=TEXT_MAIN,
                hover_color=CARD_BG, height=42, corner_radius=8,
                command=lambda k=key: self._show_tab(k)
            )
            btn.pack(fill="x", padx=12, pady=4)
            self.nav_buttons[key] = btn

        # Sidebar Bottom Card: Connection Status
        bottom_box = ctk.CTkFrame(self.sidebar, fg_color=CARD_BG, corner_radius=10, border_width=1, border_color=CARD_BORDER)
        bottom_box.pack(side="bottom", fill="x", padx=12, pady=16)
        
        self.adb_status_dot = ctk.CTkLabel(bottom_box, text="●", text_color=ACCENT_GREEN, font=ctk.CTkFont(size=14))
        self.adb_status_dot.grid(row=0, column=0, padx=(10, 4), pady=(8, 2), sticky="w")
        self.adb_status_lbl = ctk.CTkLabel(bottom_box, text="MEmu (21503)", font=ctk.CTkFont(size=12, weight="bold"), text_color=TEXT_MAIN)
        self.adb_status_lbl.grid(row=0, column=1, padx=2, pady=(8, 2), sticky="w")

        ping_btn = ctk.CTkButton(
            bottom_box, text="Ping Device", height=26, font=ctk.CTkFont(size=11),
            fg_color="#374151", hover_color="#4b5563",
            command=self._test_adb_connection
        )
        ping_btn.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(4, 8))

        # 2. Main Right Container
        self.main_container = ctk.CTkFrame(self, fg_color=BG_DARK, corner_radius=0)
        self.main_container.grid(row=0, column=1, sticky="nsew", padx=14, pady=14)
        self.main_container.grid_rowconfigure(1, weight=1)
        self.main_container.grid_columnconfigure(0, weight=1)

        # Top Control Bar (Status Badge & Master Controls)
        self._build_top_control_bar()

        # Tab Content Frame
        self.tab_container = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.tab_container.grid(row=1, column=0, sticky="nsew", pady=(12, 0))
        self.tab_container.grid_rowconfigure(0, weight=1)
        self.tab_container.grid_columnconfigure(0, weight=1)

        # Initialize Clean Tab Views
        self.tab_views = {}
        self._init_dashboard_tab()
        self._init_settings_tab()
        self._init_logs_tab()

    def _build_top_control_bar(self):
        top_bar = ctk.CTkFrame(self.main_container, fg_color=PANEL_DARK, corner_radius=12, border_width=1, border_color=CARD_BORDER, height=56)
        top_bar.grid(row=0, column=0, sticky="ew")
        top_bar.grid_columnconfigure(1, weight=1)

        # Left: Live Status Pill
        status_box = ctk.CTkFrame(top_bar, fg_color=CARD_BG, corner_radius=20, border_width=1, border_color=CARD_BORDER)
        status_box.grid(row=0, column=0, padx=14, pady=8, sticky="w")
        self.status_pill_dot = ctk.CTkLabel(status_box, text="●", text_color=TEXT_MUTED, font=ctk.CTkFont(size=14))
        self.status_pill_dot.pack(side="left", padx=(10, 4), pady=4)
        self.status_pill_text = ctk.CTkLabel(status_box, textvariable=self.stat_bot_state, font=ctk.CTkFont(size=12, weight="bold"), text_color=TEXT_MAIN)
        self.status_pill_text.pack(side="left", padx=(0, 12), pady=4)

        # Right: Master Action Buttons
        btn_box = ctk.CTkFrame(top_bar, fg_color="transparent")
        btn_box.grid(row=0, column=2, padx=14, pady=8, sticky="e")

        self.btn_start = ctk.CTkButton(
            btn_box, text="▶  START BOT", width=125, height=36,
            fg_color=ACCENT_GREEN, hover_color="#059669", font=ctk.CTkFont(size=13, weight="bold"),
            command=self._start_bot_thread
        )
        self.btn_start.pack(side="left", padx=5)

        self.btn_pause = ctk.CTkButton(
            btn_box, text="⏸  PAUSE", width=95, height=36,
            fg_color="#374151", hover_color="#4b5563", font=ctk.CTkFont(size=13, weight="bold"),
            command=self._toggle_pause_bot
        )
        self.btn_pause.pack(side="left", padx=5)

        self.btn_stop = ctk.CTkButton(
            btn_box, text="⏹  STOP", width=95, height=36,
            fg_color=ACCENT_RED, hover_color="#dc2626", font=ctk.CTkFont(size=13, weight="bold"),
            command=self._stop_bot_thread
        )
        self.btn_stop.pack(side="left", padx=5)

        btn_save = ctk.CTkButton(
            btn_box, text="💾 Save", width=90, height=36,
            fg_color="#2563eb", hover_color="#1d4ed8", font=ctk.CTkFont(size=12, weight="bold"),
            command=self._save_config
        )
        btn_save.pack(side="left", padx=(8, 0))

    def _show_tab(self, key):
        for k, view in self.tab_views.items():
            view.grid_forget()
            self.nav_buttons[k].configure(fg_color="transparent", font=ctk.CTkFont(size=14, weight="normal"))
        
        if key in self.tab_views:
            self.tab_views[key].grid(row=0, column=0, sticky="nsew")
            self.nav_buttons[key].configure(fg_color=CARD_BG, font=ctk.CTkFont(size=14, weight="bold"))

    # ================= TAB 1: DASHBOARD =================
    def _init_dashboard_tab(self):
        tab = ctk.CTkFrame(self.tab_container, fg_color="transparent")
        self.tab_views["dashboard"] = tab

        # 1. Row of 4 Metric Cards
        metrics_frame = ctk.CTkFrame(tab, fg_color="transparent")
        metrics_frame.pack(fill="x", pady=(0, 12))
        for col in range(4):
            metrics_frame.grid_columnconfigure(col, weight=1)

        self._create_metric_card(metrics_frame, 0, "🪙  VILLAGE GOLD", self.stat_gold, self.stat_gold_sub, ACCENT_GOLD)
        self._create_metric_card(metrics_frame, 1, "🧪  VILLAGE ELIXIR", self.stat_elixir, self.stat_elixir_sub, ACCENT_ELIXIR)
        self._create_metric_card(metrics_frame, 2, "💧  DARK ELIXIR", self.stat_de, self.stat_de_sub, ACCENT_DE)
        self._create_metric_card(metrics_frame, 3, "👷  BUILDERS STATUS", self.stat_builders, self.stat_builders_sub, ACCENT_GREEN)

        # Operating Mode Banner: 3-way Segmented Button
        mode_box = ctk.CTkFrame(tab, fg_color=PANEL_DARK, corner_radius=10, border_width=1, border_color=CARD_BORDER)
        mode_box.pack(fill="x", pady=(0, 10), padx=2)

        lbl_mode = ctk.CTkLabel(mode_box, text="🎯 Operating Mode:", font=ctk.CTkFont(size=12, weight="bold"), text_color=TEXT_MAIN)
        lbl_mode.pack(side="left", padx=(14, 8), pady=6)

        cur_mode = self.cfg.get("general", {}).get("bot_mode", "BOTH")
        self.mode_var = ctk.StringVar(value=cur_mode)
        self.seg_bot_mode = ctk.CTkSegmentedButton(
            mode_box,
            values=["BOTH", "ONLY_ATTACK", "ONLY_WALL_DUMP"],
            variable=self.mode_var,
            command=self._on_mode_changed,
            font=ctk.CTkFont(size=12, weight="bold"),
            selected_color="#2563eb",
            selected_hover_color="#1d4ed8"
        )
        self.seg_bot_mode.pack(side="left", padx=8, pady=6)

        descriptions = {
            "BOTH": "(⚔️+🧱 Attacks bases & dumps excess loot into walls)",
            "ONLY_ATTACK": "(⚔️ Continuously raids bases; wall dump strictly disabled)",
            "ONLY_WALL_DUMP": "(🧱 Dumps Gold & Elixir into walls; attacks strictly disabled)"
        }
        self.lbl_mode_desc = ctk.CTkLabel(
            mode_box,
            text=descriptions.get(cur_mode, "(⚔️+🧱 Attacks bases & dumps excess loot into walls)"),
            font=ctk.CTkFont(size=11),
            text_color=TEXT_MUTED
        )
        self.lbl_mode_desc.pack(side="left", padx=10, pady=6)

        # Ground Truth Village Telemetry Banner
        wall_sum = village_profile.get_wall_summary()
        self.builder_remaining_seconds = village_profile.get_next_builder_free_seconds()
        hrs = self.builder_remaining_seconds // 3600
        mins = (self.builder_remaining_seconds % 3600) // 60
        secs = self.builder_remaining_seconds % 60
        builder_txt = f"{hrs:02d}h {mins:02d}m {secs:02d}s" if self.builder_remaining_seconds > 0 else "Free"

        gt_frame = ctk.CTkFrame(tab, fg_color=PANEL_DARK, corner_radius=10, border_width=1, border_color=CARD_BORDER)
        gt_frame.pack(fill="x", pady=(0, 10), padx=2)

        lbl_tag = ctk.CTkLabel(
            gt_frame,
            text=f"🏰 Village: {village_profile.tag or '#G9JGYV2CL'} (TH11 • {getattr(village_profile, 'total_builders', 3)} Builders)",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#38bdf8"
        )
        lbl_tag.pack(side="left", padx=14, pady=8)

        lbl_walls = ctk.CTkLabel(
            gt_frame,
            text=f"🧱 Walls: {wall_sum.get('maxed', 21)} Maxed | {wall_sum.get('breakdown', {}).get(10, 254)} Lvl 10 | {wall_sum.get('cheapest_count', 25)} Lower (Cheapest First)",
            font=ctk.CTkFont(size=12),
            text_color="#e2e8f0"
        )
        lbl_walls.pack(side="left", padx=14, pady=8)

        self.lbl_bld = ctk.CTkLabel(
            gt_frame,
            text=f"⏳ Next Builder Free In: {builder_txt}",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=ACCENT_GOLD
        )
        self.lbl_bld.pack(side="right", padx=14, pady=8)

        # 2. Main Dashboard Split
        split_frame = ctk.CTkFrame(tab, fg_color="transparent")
        split_frame.pack(fill="both", expand=True)
        split_frame.grid_columnconfigure(0, weight=3)
        split_frame.grid_columnconfigure(1, weight=2)
        split_frame.grid_rowconfigure(0, weight=1)

        # Left: Live Viewfinder Box
        view_card = ctk.CTkFrame(split_frame, fg_color=PANEL_DARK, corner_radius=12, border_width=1, border_color=CARD_BORDER)
        view_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        view_header = ctk.CTkFrame(view_card, fg_color="transparent")
        view_header.pack(fill="x", padx=14, pady=10)
        ctk.CTkLabel(view_header, text="📹 Live Emulator Viewfinder", font=ctk.CTkFont(size=14, weight="bold"), text_color=TEXT_MAIN).pack(side="left")

        ctk.CTkButton(view_header, text="🔄 Refresh Now", width=95, height=26, font=ctk.CTkFont(size=11), command=self._refresh_viewfinder).pack(side="right")
        ctk.CTkCheckBox(view_header, text="Auto-Refresh", variable=self.auto_refresh_view, font=ctk.CTkFont(size=12)).pack(side="right", padx=(8, 8))
        ctk.CTkCheckBox(view_header, text="Show Taps", variable=self.show_tap_markers, font=ctk.CTkFont(size=12)).pack(side="right", padx=(8, 0))

        self.viewfinder_lbl = ctk.CTkLabel(view_card, text="Connecting to Emulator Framebuffer...", fg_color="#000000", corner_radius=8)
        self.viewfinder_lbl.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        # Right: Live Activity Stream Card (expanded to full height, duplicate switches removed)
        right_card = ctk.CTkFrame(split_frame, fg_color=PANEL_DARK, corner_radius=12, border_width=1, border_color=CARD_BORDER)
        right_card.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        log_hdr = ctk.CTkFrame(right_card, fg_color="transparent")
        log_hdr.pack(fill="x", padx=14, pady=(12, 6))
        ctk.CTkLabel(log_hdr, text="📋 Live Activity Stream", font=ctk.CTkFont(size=14, weight="bold"), text_color=TEXT_MAIN).pack(side="left")

        self.mini_log_box = ctk.CTkTextbox(right_card, fg_color=CARD_BG, font=ctk.CTkFont(family="Consolas", size=11), text_color="#d1d5db")
        self.mini_log_box.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    def _create_metric_card(self, parent, col, title, text_var, sub_text_var, accent_color):
        card = ctk.CTkFrame(parent, fg_color=PANEL_DARK, corner_radius=12, border_width=1, border_color=CARD_BORDER)
        card.grid(row=0, column=col, sticky="ew", padx=5)
        ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=11, weight="bold"), text_color=TEXT_MUTED).pack(anchor="w", padx=14, pady=(10, 2))
        val_lbl = ctk.CTkLabel(card, textvariable=text_var, font=ctk.CTkFont(size=19, weight="bold"), text_color=accent_color)
        val_lbl.pack(anchor="w", padx=14, pady=(0, 2))
        sub_lbl = ctk.CTkLabel(card, textvariable=sub_text_var, font=ctk.CTkFont(size=11), text_color="#94a3b8")
        sub_lbl.pack(anchor="w", padx=14, pady=(0, 10))

    # ================= TAB 2: SETTINGS =================
    def _init_settings_tab(self):
        tab = ctk.CTkScrollableFrame(self.tab_container, fg_color="transparent")
        self.tab_views["settings"] = tab

        mm_cfg = self.cfg.get("matchmaking", {})
        w_cfg = self.cfg.get("wall_dump", {})
        c_cfg = self.cfg.get("combat", {})
        e_cfg = self.cfg.get("emulator", {})

        # Card 0: Master Operating Mode
        c0 = ctk.CTkFrame(tab, fg_color=PANEL_DARK, corner_radius=12, border_width=1, border_color=CARD_BORDER)
        c0.pack(fill="x", pady=6)
        ctk.CTkLabel(c0, text="🎯 Master Operating Mode", font=ctk.CTkFont(size=15, weight="bold"), text_color=ACCENT_GOLD).pack(anchor="w", padx=16, pady=(12, 6))

        row_m = ctk.CTkFrame(c0, fg_color="transparent")
        row_m.pack(fill="x", padx=16, pady=(0, 12))
        ctk.CTkLabel(row_m, text="Active Bot Mode:", width=180, anchor="w", font=ctk.CTkFont(size=13)).pack(side="left")
        self.seg_settings_mode = ctk.CTkSegmentedButton(
            row_m,
            values=["BOTH", "ONLY_ATTACK", "ONLY_WALL_DUMP"],
            variable=self.mode_var,
            command=self._on_mode_changed,
            font=ctk.CTkFont(size=12, weight="bold"),
            selected_color="#2563eb",
            selected_hover_color="#1d4ed8"
        )
        self.seg_settings_mode.pack(side="left", padx=8)

        # Card 1: Matchmaking Loot Filters
        c1 = ctk.CTkFrame(tab, fg_color=PANEL_DARK, corner_radius=12, border_width=1, border_color=CARD_BORDER)
        c1.pack(fill="x", pady=6)
        ctk.CTkLabel(c1, text="🎯 Matchmaking & Dead Village Loot Filters", font=ctk.CTkFont(size=15, weight="bold"), text_color=ACCENT_GOLD).pack(anchor="w", padx=16, pady=(12, 8))

        # Search Logic Mode
        row_logic = ctk.CTkFrame(c1, fg_color="transparent")
        row_logic.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(row_logic, text="Search Logic Mode:", width=180, anchor="w", font=ctk.CTkFont(size=13)).pack(side="left")
        self.opt_match_logic = ctk.CTkOptionMenu(
            row_logic,
            values=[
                "Total Sum (Gold + Elixir >= Min)",
                "OR (Gold OR Elixir >= Min)",
                "AND (Both Gold & Elixir >= Min)",
                "Dark Elixir Only",
                "Smart Balanced (Hybrid)"
            ],
            width=260,
            font=ctk.CTkFont(size=12)
        )
        saved_logic = mm_cfg.get("match_logic", "TOTAL_SUM").upper()
        if "AND" in saved_logic:
            self.opt_match_logic.set("AND (Both Gold & Elixir >= Min)")
        elif "OR" in saved_logic and "SUM" not in saved_logic and "TOTAL" not in saved_logic:
            self.opt_match_logic.set("OR (Gold OR Elixir >= Min)")
        elif "DE" in saved_logic:
            self.opt_match_logic.set("Dark Elixir Only")
        elif "SMART" in saved_logic:
            self.opt_match_logic.set("Smart Balanced (Hybrid)")
        else:
            self.opt_match_logic.set("Total Sum (Gold + Elixir >= Min)")
        self.opt_match_logic.pack(side="left", padx=8)

        # Min Total Loot (Gold + Elixir sum, default 600,000 / 6 lakh)
        row_tot = ctk.CTkFrame(c1, fg_color="transparent")
        row_tot.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(row_tot, text="Min Total Loot (6 Lakh):", width=180, anchor="w", font=ctk.CTkFont(size=13)).pack(side="left")
        self.ent_min_total_loot = ctk.CTkEntry(row_tot, width=150)
        self.ent_min_total_loot.insert(0, str(mm_cfg.get("min_total_loot", 600000)))
        self.ent_min_total_loot.pack(side="left", padx=8)
        ctk.CTkLabel(row_tot, text="Gold + Elixir sum (Dead Base Target)", text_color=TEXT_MUTED, font=ctk.CTkFont(size=11)).pack(side="left", padx=4)

        # Min Gold
        row_g = ctk.CTkFrame(c1, fg_color="transparent")
        row_g.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(row_g, text="Minimum Gold:", width=180, anchor="w", font=ctk.CTkFont(size=13)).pack(side="left")
        self.ent_min_gold = ctk.CTkEntry(row_g, width=150)
        self.ent_min_gold.insert(0, str(mm_cfg.get("min_gold", 300000)))
        self.ent_min_gold.pack(side="left", padx=8)

        # Min Elixir
        row_e = ctk.CTkFrame(c1, fg_color="transparent")
        row_e.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(row_e, text="Minimum Elixir:", width=180, anchor="w", font=ctk.CTkFont(size=13)).pack(side="left")
        self.ent_min_elixir = ctk.CTkEntry(row_e, width=150)
        self.ent_min_elixir.insert(0, str(mm_cfg.get("min_elixir", 300000)))
        self.ent_min_elixir.pack(side="left", padx=8)

        # Min Dark Elixir
        row_de = ctk.CTkFrame(c1, fg_color="transparent")
        row_de.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(row_de, text="Minimum Dark Elixir:", width=180, anchor="w", font=ctk.CTkFont(size=13)).pack(side="left")
        self.ent_min_de = ctk.CTkEntry(row_de, width=150)
        self.ent_min_de.insert(0, str(mm_cfg.get("min_dark_elixir", 1500)))
        self.ent_min_de.pack(side="left", padx=8)

        # Resource Preference
        row_pref = ctk.CTkFrame(c1, fg_color="transparent")
        row_pref.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(row_pref, text="Resource Preference:", width=180, anchor="w", font=ctk.CTkFont(size=13)).pack(side="left")
        self.opt_resource_pref = ctk.CTkOptionMenu(
            row_pref,
            values=["Balanced (Equal Weight)", "Prefer Gold", "Prefer Elixir", "Prefer Dark Elixir"],
            width=220,
            font=ctk.CTkFont(size=12)
        )
        saved_pref = mm_cfg.get("resource_preference", "BALANCED").upper()
        if "GOLD" in saved_pref:
            self.opt_resource_pref.set("Prefer Gold")
        elif "ELIXIR" in saved_pref and "DARK" not in saved_pref:
            self.opt_resource_pref.set("Prefer Elixir")
        elif "DARK" in saved_pref or "DE" in saved_pref:
            self.opt_resource_pref.set("Prefer Dark Elixir")
        else:
            self.opt_resource_pref.set("Balanced (Equal Weight)")
        self.opt_resource_pref.pack(side="left", padx=8)

        # Dark Elixir Priority Switch
        row_de_opts = ctk.CTkFrame(c1, fg_color="transparent")
        row_de_opts.pack(fill="x", padx=16, pady=4)
        self.sw_de_independent = ctk.CTkSwitch(row_de_opts, text="Attack if Dark Elixir Meets Target (DE Raid Priority)", font=ctk.CTkFont(size=12))
        self.sw_de_independent.pack(side="left", padx=8)
        if mm_cfg.get("allow_de_independent", True):
            self.sw_de_independent.select()
        else:
            self.sw_de_independent.deselect()

        # Max Search Skips
        row_skips = ctk.CTkFrame(c1, fg_color="transparent")
        row_skips.pack(fill="x", padx=16, pady=(4, 12))
        ctk.CTkLabel(row_skips, text="Max 'Next' Base Skips:", width=180, anchor="w", font=ctk.CTkFont(size=13)).pack(side="left")
        self.ent_max_skips = ctk.CTkEntry(row_skips, width=150)
        self.ent_max_skips.insert(0, str(mm_cfg.get("max_search_skips", 100)))
        self.ent_max_skips.pack(side="left", padx=8)

        # Card 2: Wall Dumping & Resource Sink
        c2 = ctk.CTkFrame(tab, fg_color=PANEL_DARK, corner_radius=12, border_width=1, border_color=CARD_BORDER)
        c2.pack(fill="x", pady=6)
        ctk.CTkLabel(c2, text="🧱 Builder Menu Wall Dump & Resource Sink", font=ctk.CTkFont(size=15, weight="bold"), text_color=ACCENT_GOLD).pack(anchor="w", padx=16, pady=(12, 8))

        self.sw_wall_enable = ctk.CTkSwitch(c2, text="Enable Automatic Wall Dumping", font=ctk.CTkFont(size=13))
        self.sw_wall_enable.pack(anchor="w", padx=16, pady=6)
        if w_cfg.get("enabled", True):
            self.sw_wall_enable.select()

        # Gold Reserve
        row_gr = ctk.CTkFrame(c2, fg_color="transparent")
        row_gr.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(row_gr, text="Keep Gold Reserve:", width=180, anchor="w", font=ctk.CTkFont(size=13)).pack(side="left")
        self.ent_gold_reserve = ctk.CTkEntry(row_gr, width=150)
        self.ent_gold_reserve.insert(0, str(w_cfg.get("keep_gold_reserve", 0)))
        self.ent_gold_reserve.pack(side="left", padx=8)

        # Elixir Reserve
        row_er = ctk.CTkFrame(c2, fg_color="transparent")
        row_er.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(row_er, text="Keep Elixir Reserve:", width=180, anchor="w", font=ctk.CTkFont(size=13)).pack(side="left")
        self.ent_elixir_reserve = ctk.CTkEntry(row_er, width=150)
        self.ent_elixir_reserve.insert(0, str(w_cfg.get("keep_elixir_reserve", 0)))
        self.ent_elixir_reserve.pack(side="left", padx=8)

        # Spending Priority
        row_prio = ctk.CTkFrame(c2, fg_color="transparent")
        row_prio.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(row_prio, text="Resource Priority:", width=180, anchor="w", font=ctk.CTkFont(size=13)).pack(side="left")
        self.seg_wall_prio = ctk.CTkSegmentedButton(row_prio, values=["BOTH", "GOLD", "ELIXIR"])
        self.seg_wall_prio.set(w_cfg.get("upgrade_resource_priority", "BOTH").upper())
        self.seg_wall_prio.pack(side="left", padx=8)

        # Wall Strategy
        row_strat = ctk.CTkFrame(c2, fg_color="transparent")
        row_strat.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(row_strat, text="Wall Priority Strategy:", width=180, anchor="w", font=ctk.CTkFont(size=13)).pack(side="left")
        self.opt_wall_strat = ctk.CTkOptionMenu(
            row_strat,
            values=["Cheapest First (25 lower walls first)", "Smart Hybrid", "Highest First"],
            width=250
        )
        saved_strat = self.cfg.get("village_profile", {}).get("wall_strategy", "CHEAPEST_FIRST")
        if "CHEAPEST" in saved_strat.upper():
            self.opt_wall_strat.set("Cheapest First (25 lower walls first)")
        elif "SMART" in saved_strat.upper():
            self.opt_wall_strat.set("Smart Hybrid")
        else:
            self.opt_wall_strat.set("Highest First")
        self.opt_wall_strat.pack(side="left", padx=8)

        # Storage Full Trigger (%)
        row_trig = ctk.CTkFrame(c2, fg_color="transparent")
        row_trig.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(row_trig, text="Storage Full Trigger (>= %):", width=180, anchor="w", font=ctk.CTkFont(size=13)).pack(side="left")
        self.ent_wall_trigger_pct = ctk.CTkEntry(row_trig, width=150)
        self.ent_wall_trigger_pct.insert(0, str(w_cfg.get("storage_full_percentage", 85)))
        self.ent_wall_trigger_pct.pack(side="left", padx=8)

        # Max Spend (% of excess)
        row_msp = ctk.CTkFrame(c2, fg_color="transparent")
        row_msp.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(row_msp, text="Max Dump Spend (% excess):", width=180, anchor="w", font=ctk.CTkFont(size=13)).pack(side="left")
        self.ent_max_spend_pct = ctk.CTkEntry(row_msp, width=150)
        self.ent_max_spend_pct.insert(0, str(w_cfg.get("max_dump_spend_percent", 100)))
        self.ent_max_spend_pct.pack(side="left", padx=8)

        # Max walls per cycle
        row_mw = ctk.CTkFrame(c2, fg_color="transparent")
        row_mw.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(row_mw, text="Max Walls Per Cycle:", width=180, anchor="w", font=ctk.CTkFont(size=13)).pack(side="left")
        self.ent_max_walls = ctk.CTkEntry(row_mw, width=150)
        self.ent_max_walls.insert(0, str(w_cfg.get("max_walls_per_cycle", 50)))
        self.ent_max_walls.pack(side="left", padx=8)

        # Wall Dump Trigger Mode
        row_dtm = ctk.CTkFrame(c2, fg_color="transparent")
        row_dtm.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(row_dtm, text="Dump Trigger Mode:", width=180, anchor="w", font=ctk.CTkFont(size=13)).pack(side="left")
        self.opt_dump_trigger_mode = ctk.CTkOptionMenu(
            row_dtm,
            values=["When Storages Full", "Every N Attacks", "Hybrid (Full or Every N Attacks)"],
            width=250
        )
        saved_dtm = w_cfg.get("dump_trigger_mode", "WHEN_FULL").upper()
        if "EVERY" in saved_dtm:
            self.opt_dump_trigger_mode.set("Every N Attacks")
        elif "HYBRID" in saved_dtm:
            self.opt_dump_trigger_mode.set("Hybrid (Full or Every N Attacks)")
        else:
            self.opt_dump_trigger_mode.set("When Storages Full")
        self.opt_dump_trigger_mode.pack(side="left", padx=8)

        # Dump Every N Attacks Count
        row_den = ctk.CTkFrame(c2, fg_color="transparent")
        row_den.pack(fill="x", padx=16, pady=(4, 12))
        ctk.CTkLabel(row_den, text="Dump Every N Attacks:", width=180, anchor="w", font=ctk.CTkFont(size=13)).pack(side="left")
        self.ent_dump_every_n = ctk.CTkEntry(row_den, width=150)
        self.ent_dump_every_n.insert(0, str(w_cfg.get("dump_every_n_attacks", 5)))
        self.ent_dump_every_n.pack(side="left", padx=8)

        # Card 2.5: Builders & Construction Management
        cb = ctk.CTkFrame(tab, fg_color=PANEL_DARK, corner_radius=12, border_width=1, border_color=CARD_BORDER)
        cb.pack(fill="x", pady=6)
        ctk.CTkLabel(cb, text="👷 Builders & Construction Management", font=ctk.CTkFont(size=15, weight="bold"), text_color=ACCENT_GOLD).pack(anchor="w", padx=16, pady=(12, 8))

        row_bld = ctk.CTkFrame(cb, fg_color="transparent")
        row_bld.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(row_bld, text="Total Unlocked Builders:", width=180, anchor="w", font=ctk.CTkFont(size=13)).pack(side="left")
        self.opt_total_builders = ctk.CTkOptionMenu(
            row_bld,
            values=["2 Builders", "3 Builders", "4 Builders", "5 Builders", "6 Builders"],
            command=self._on_builder_count_changed,
            width=180
        )
        cur_bld = self.cfg.get("village_profile", {}).get("total_builders", 3)
        self.opt_total_builders.set(f"{cur_bld} Builders")
        self.opt_total_builders.pack(side="left", padx=8)

        btn_reset_timers = ctk.CTkButton(
            row_bld,
            text="🔄 Clear Stale Timers (Mark All Free)",
            fg_color="#374151",
            hover_color="#4b5563",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._reset_builder_timers
        )
        btn_reset_timers.pack(side="left", padx=12)

        # Card 3: Intelligent Combat & Troop Deployment
        c3 = ctk.CTkFrame(tab, fg_color=PANEL_DARK, corner_radius=12, border_width=1, border_color=CARD_BORDER)
        c3.pack(fill="x", pady=6)
        ctk.CTkLabel(c3, text="⚔️ Intelligent Tactical Combat Engine", font=ctk.CTkFont(size=15, weight="bold"), text_color=ACCENT_GOLD).pack(anchor="w", padx=16, pady=(12, 8))

        row_pat = ctk.CTkFrame(c3, fg_color="transparent")
        row_pat.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(row_pat, text="Deployment Wave Style:", width=180, anchor="w", font=ctk.CTkFont(size=13)).pack(side="left")
        self.opt_deploy_pattern = ctk.CTkOptionMenu(
            row_pat,
            values=[
                "Adaptive Smart (AI Dynamic Variety)",
                "All 4 Sides (Surround)",
                "Two Sides (Pincer)",
                "Single Flank",
                "Surgical Perimeter",
                "Core Rush",
                "All 4 Corners"
            ],
            width=250
        )
        saved_pat = c_cfg.get("deployment_pattern", "ADAPTIVE_SMART")
        pat_map = {
            "ADAPTIVE_SMART": "Adaptive Smart (AI Dynamic Variety)",
            "ALL_4_SIDES": "All 4 Sides (Surround)",
            "TWO_SIDES": "Two Sides (Pincer)",
            "SINGLE_SIDE": "Single Flank",
            "SURGICAL_PERIMETER": "Surgical Perimeter",
            "CORE_RUSH": "Core Rush",
            "ALL_4_CORNERS": "All 4 Corners"
        }
        self.opt_deploy_pattern.set(pat_map.get(saved_pat, "Adaptive Smart (AI Dynamic Variety)"))
        self.opt_deploy_pattern.pack(side="left", padx=8)

        # Auto Zoom Out
        row_zoom = ctk.CTkFrame(c3, fg_color="transparent")
        row_zoom.pack(fill="x", padx=16, pady=4)
        self.sw_auto_zoom = ctk.CTkSwitch(row_zoom, text="Auto-Zoom Out Battlefield Camera (MEmu Native)", font=ctk.CTkFont(size=13))
        self.sw_auto_zoom.pack(side="left")
        if c_cfg.get("auto_zoom_out", True):
            self.sw_auto_zoom.select()

        # Heroes
        row_h = ctk.CTkFrame(c3, fg_color="transparent")
        row_h.pack(fill="x", padx=16, pady=4)
        self.sw_deploy_heroes = ctk.CTkSwitch(row_h, text="Auto-Deploy Heroes & Trigger Active Abilities", font=ctk.CTkFont(size=13))
        self.sw_deploy_heroes.pack(side="left")
        if c_cfg.get("deploy_heroes", True):
            self.sw_deploy_heroes.select()

        # Spells
        row_s = ctk.CTkFrame(c3, fg_color="transparent")
        row_s.pack(fill="x", padx=16, pady=4)
        self.sw_deploy_spells = ctk.CTkSwitch(row_s, text="Auto-Cast Spells into Base Core (Town Hall / Storages)", font=ctk.CTkFont(size=13))
        self.sw_deploy_spells.pack(side="left")
        if c_cfg.get("deploy_spells", True) or c_cfg.get("deploy_all_spells", True):
            self.sw_deploy_spells.select()

        # Battle duration
        row_dur = ctk.CTkFrame(c3, fg_color="transparent")
        row_dur.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(row_dur, text="Battle Looting Time (sec):", width=180, anchor="w", font=ctk.CTkFont(size=13)).pack(side="left")
        self.ent_battle_duration = ctk.CTkEntry(row_dur, width=150)
        self.ent_battle_duration.insert(0, str(c_cfg.get("battle_duration_seconds", 45)))
        self.ent_battle_duration.pack(side="left", padx=8)

        # Early Surrender Target (%)
        row_surr = ctk.CTkFrame(c3, fg_color="transparent")
        row_surr.pack(fill="x", padx=16, pady=(4, 12))
        ctk.CTkLabel(row_surr, text="Early Surrender Loot (%):", width=180, anchor="w", font=ctk.CTkFont(size=13)).pack(side="left")
        self.ent_surrender_pct = ctk.CTkEntry(row_surr, width=150)
        self.ent_surrender_pct.insert(0, str(c_cfg.get("early_surrender_loot_percent", 80)))
        self.ent_surrender_pct.pack(side="left", padx=8)

        # Card 4: Android Emulator Connection
        c4 = ctk.CTkFrame(tab, fg_color=PANEL_DARK, corner_radius=12, border_width=1, border_color=CARD_BORDER)
        c4.pack(fill="x", pady=6)
        ctk.CTkLabel(c4, text="⚙️ Emulator & ADB Connection", font=ctk.CTkFont(size=15, weight="bold"), text_color=ACCENT_GOLD).pack(anchor="w", padx=16, pady=(12, 8))

        row_emu = ctk.CTkFrame(c4, fg_color="transparent")
        row_emu.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(row_emu, text="Emulator Type:", width=180, anchor="w", font=ctk.CTkFont(size=13)).pack(side="left")
        self.opt_emu_type = ctk.CTkOptionMenu(row_emu, values=["MEmu", "LDPlayer", "BlueStacks", "Custom"])
        self.opt_emu_type.set(e_cfg.get("type", "MEmu"))
        self.opt_emu_type.pack(side="left", padx=8)

        row_port = ctk.CTkFrame(c4, fg_color="transparent")
        row_port.pack(fill="x", padx=16, pady=(4, 12))
        ctk.CTkLabel(row_port, text="ADB Port:", width=180, anchor="w", font=ctk.CTkFont(size=13)).pack(side="left")
        self.ent_adb_port = ctk.CTkEntry(row_port, width=150)
        self.ent_adb_port.insert(0, str(e_cfg.get("adb_port", 21503)))
        self.ent_adb_port.pack(side="left", padx=8)

        # Card 5: Scheduled Auto-Stop & Power Management
        c5 = ctk.CTkFrame(tab, fg_color=PANEL_DARK, corner_radius=12, border_width=1, border_color=CARD_BORDER)
        c5.pack(fill="x", pady=6)
        ctk.CTkLabel(c5, text="⏱️ Scheduled Auto-Stop & Power Management", font=ctk.CTkFont(size=15, weight="bold"), text_color=ACCENT_GOLD).pack(anchor="w", padx=16, pady=(12, 8))

        stop_cfg = self.cfg.get("auto_stop", {})
        row_stop_sw = ctk.CTkFrame(c5, fg_color="transparent")
        row_stop_sw.pack(fill="x", padx=16, pady=4)
        self.sw_auto_stop = ctk.CTkSwitch(row_stop_sw, text="Enable Scheduled Session Auto-Stop", font=ctk.CTkFont(size=13))
        self.sw_auto_stop.pack(side="left")
        if stop_cfg.get("enabled", False):
            self.sw_auto_stop.select()

        row_dur = ctk.CTkFrame(c5, fg_color="transparent")
        row_dur.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(row_dur, text="Stop Bot After:", width=180, anchor="w", font=ctk.CTkFont(size=13)).pack(side="left")
        self.ent_stop_hours = ctk.CTkEntry(row_dur, width=65)
        self.ent_stop_hours.insert(0, str(stop_cfg.get("hours", 2)))
        self.ent_stop_hours.pack(side="left", padx=(8, 4))
        ctk.CTkLabel(row_dur, text="hours", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 12))

        self.ent_stop_mins = ctk.CTkEntry(row_dur, width=65)
        self.ent_stop_mins.insert(0, str(stop_cfg.get("minutes", 0)))
        self.ent_stop_mins.pack(side="left", padx=(0, 4))
        ctk.CTkLabel(row_dur, text="minutes", font=ctk.CTkFont(size=12)).pack(side="left")

        row_act = ctk.CTkFrame(c5, fg_color="transparent")
        row_act.pack(fill="x", padx=16, pady=(4, 12))
        ctk.CTkLabel(row_act, text="Post-Stop Action:", width=180, anchor="w", font=ctk.CTkFont(size=13)).pack(side="left")
        self.opt_stop_action = ctk.CTkOptionMenu(
            row_act,
            values=[
                "Just Stop Bot",
                "Close Bot & Emulator",
                "Shutdown PC (60s Warning)",
                "Sleep PC (Suspend)"
            ],
            width=250
        )
        act_saved = stop_cfg.get("action", "JUST_STOP").upper()
        act_map = {
            "JUST_STOP": "Just Stop Bot",
            "CLOSE_BOT_AND_EMULATOR": "Close Bot & Emulator",
            "SHUTDOWN_PC": "Shutdown PC (60s Warning)",
            "SLEEP_PC": "Sleep PC (Suspend)"
        }
        self.opt_stop_action.set(act_map.get(act_saved, "Just Stop Bot"))
        self.opt_stop_action.pack(side="left", padx=8)

    # ================= TAB 3: LOGS =================
    def _init_logs_tab(self):
        tab = ctk.CTkFrame(self.tab_container, fg_color="transparent")
        self.tab_views["logs"] = tab
        tab.grid_rowconfigure(1, weight=1)
        tab.grid_columnconfigure(0, weight=1)

        hdr = ctk.CTkFrame(tab, fg_color=PANEL_DARK, corner_radius=12, border_width=1, border_color=CARD_BORDER, height=48)
        hdr.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        ctk.CTkLabel(hdr, text="📜 Activity Console", font=ctk.CTkFont(size=14, weight="bold"), text_color=TEXT_MAIN).pack(side="left", padx=14, pady=8)
        ctk.CTkButton(hdr, text="Clear Console", width=100, height=28, font=ctk.CTkFont(size=11), command=self._clear_logs).pack(side="right", padx=10)
        ctk.CTkButton(hdr, text="Export to File", width=100, height=28, font=ctk.CTkFont(size=11), command=self._export_logs).pack(side="right", padx=4)

        self.log_textbox = ctk.CTkTextbox(tab, fg_color=PANEL_DARK, font=ctk.CTkFont(family="Consolas", size=12), text_color="#e2e8f0")
        self.log_textbox.grid(row=1, column=0, sticky="nsew")

    # ================= LOG PROCESSING =================
    def _process_log_queue(self):
        try:
            while not self.log_queue.empty():
                msg = self.log_queue.get_nowait()
                self.log_textbox.insert("end", msg)
                self.log_textbox.see("end")
                self.mini_log_box.insert("end", msg)
                self.mini_log_box.see("end")
        except queue.Empty:
            pass
        self.after(80, self._process_log_queue)

    def _clear_logs(self):
        self.log_textbox.delete("1.0", "end")
        self.mini_log_box.delete("1.0", "end")

    def _export_logs(self):
        path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text Files", "*.txt")])
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(self.log_textbox.get("1.0", "end"))
                messagebox.showinfo("Exported", f"Logs exported to {path}")
            except Exception as e:
                messagebox.showerror("Error", f"Could not export logs: {e}")

    # ================= VIEWFINDER & TELEMETRY =================
    def _tick_builder_countdown(self):
        """Live 1-second dynamic countdown for builder completion time."""
        total = self.cfg.get("village_profile", {}).get("total_builders", 3)
        if hasattr(village_profile, 'total_builders'):
            village_profile.total_builders = total

        rem = village_profile.get_next_builder_free_seconds() if hasattr(village_profile, 'get_next_builder_free_seconds') else 0
        busy = village_profile.get_busy_builder_count() if hasattr(village_profile, 'get_busy_builder_count') else 0
        free = village_profile.get_free_builder_count() if hasattr(village_profile, 'get_free_builder_count') else total
        self.builder_remaining_seconds = rem

        if hasattr(self, "lbl_bld"):
            act_busy = max(busy, total - free)
            if free >= total and act_busy == 0:
                self.lbl_bld.configure(text=f"👷 All Builders Free! ({total}/{total})", text_color=ACCENT_GREEN)
                self.stat_builders.set(f"{total}/{total} Free")
                self.stat_builders_sub.set("All Builders Idle")
            else:
                if rem > 0:
                    hrs = rem // 3600
                    mins = (rem % 3600) // 60
                    secs = rem % 60
                    c_str = f"{hrs:02d}h {mins:02d}m {secs:02d}s"
                    self.lbl_bld.configure(text=f"⏳ Next Builder Free In: {c_str}", text_color=ACCENT_GOLD)
                    self.stat_builders.set(f"{free}/{total} Free" if free > 0 else f"0/{total} Busy")
                    self.stat_builders_sub.set(f"{act_busy} Busy • Next: {hrs:02d}h {mins:02d}m")
                else:
                    self.lbl_bld.configure(text=f"👷 Builders: {free}/{total} Free ({act_busy} Busy)", text_color=ACCENT_GOLD if free > 0 else ACCENT_RED)
                    self.stat_builders.set(f"{free}/{total} Free" if free > 0 else f"0/{total} Busy")
                    self.stat_builders_sub.set(f"{act_busy} Busy")

        # Check Scheduled Session Auto-Stop
        if self.bot_thread and self.bot_thread.is_alive() and hasattr(self, "fsm") and self.fsm.is_running:
            stop_cfg = self.cfg.get("auto_stop", {})
            if stop_cfg.get("enabled", False):
                h = stop_cfg.get("hours", 0)
                m = stop_cfg.get("minutes", 0)
                target_total_sec = h * 3600 + m * 60
                elapsed = time.time() - getattr(self.fsm, "session_start_time", time.time())
                rem_stop = max(0, int(target_total_sec - elapsed))
                if rem_stop <= 0:
                    print("\n[PowerManager] ⏱️ SCHEDULED AUTO-STOP TIMER EXPIRED! Executing configured post-stop action...")
                    act = stop_cfg.get("action", "JUST_STOP").upper()
                    self._stop_bot_thread()
                    if act == "CLOSE_BOT_AND_EMULATOR":
                        PowerManager.kill_emulator_processes()
                        self.after(1000, self.destroy)
                    elif act == "SHUTDOWN_PC":
                        PowerManager.kill_emulator_processes()
                        PowerManager.shutdown_pc(warning_seconds=60)
                        self.after(1000, self.destroy)
                    elif act == "SLEEP_PC":
                        PowerManager.kill_emulator_processes()
                        PowerManager.sleep_pc()
                        self.after(1000, self.destroy)

        self.after(1000, self._tick_builder_countdown)

    def _periodic_viewfinder_update(self):
        if self.auto_refresh_view.get() and not getattr(self, "_vf_updating", False):
            if (time.time() - self.last_preview_time) >= 0.35:
                self._vf_updating = True
                threading.Thread(target=self._refresh_viewfinder_async, daemon=True).start()
        self.after(350, self._periodic_viewfinder_update)

    def _refresh_viewfinder(self):
        if not getattr(self, "_vf_updating", False):
            self._vf_updating = True
            threading.Thread(target=self._refresh_viewfinder_async, daemon=True).start()

    def _refresh_viewfinder_async(self):
        try:
            frame = self.capture.get_frame(target_size=(1280, 720))
            if frame is not None:
                # 1. Overlay visual tap & swipe markers if enabled
                display_frame = frame.copy()
                if getattr(self, "show_tap_markers", None) and self.show_tap_markers.get():
                    if hasattr(self, "adb") and hasattr(self.adb, "get_recent_touch_events"):
                        now = time.time()
                        touch_events = self.adb.get_recent_touch_events()
                        for ev in touch_events:
                            ev_type = ev.get("type", "tap")
                            age = max(0.0, now - ev.get("time", now))
                            if age > 3.5:
                                continue

                            if ev_type == "tap":
                                tx = ev["x"]
                                ty = ev["y"]
                                label = ev.get("label", f"({tx}, {ty})")

                                # Visual styling according to age:
                                if age < 0.8:
                                    ring_color = (255, 255, 0)      # Neon Cyan
                                    inner_color = (0, 255, 255)     # Bright Yellow
                                    pulse_r = int(22 + (age / 0.8) * 8)
                                    thickness = 3
                                elif age < 2.0:
                                    ring_color = (0, 215, 255)      # Gold
                                    inner_color = (0, 165, 255)     # Amber/Orange
                                    pulse_r = 22
                                    thickness = 2
                                else:
                                    ring_color = (0, 140, 255)      # Fading Amber
                                    inner_color = (80, 80, 200)
                                    pulse_r = 18
                                    thickness = 1

                                # Bullseye center dot
                                cv2.circle(display_frame, (tx, ty), 6, inner_color, -1, lineType=cv2.LINE_AA)
                                cv2.circle(display_frame, (tx, ty), 7, (0, 0, 0), 1, lineType=cv2.LINE_AA)

                                # Main target ring
                                cv2.circle(display_frame, (tx, ty), pulse_r, ring_color, thickness, lineType=cv2.LINE_AA)

                                # Shockwave ripple for newest taps (<0.45s)
                                if age < 0.45:
                                    shock_r = int(28 + (age / 0.45) * 16)
                                    cv2.circle(display_frame, (tx, ty), shock_r, (255, 255, 255), 1, lineType=cv2.LINE_AA)

                                # Crosshairs
                                cv2.line(display_frame, (tx - 32, ty), (tx - 10, ty), ring_color, 2, lineType=cv2.LINE_AA)
                                cv2.line(display_frame, (tx + 10, ty), (tx + 32, ty), ring_color, 2, lineType=cv2.LINE_AA)
                                cv2.line(display_frame, (tx, ty - 32), (tx, ty - 10), ring_color, 2, lineType=cv2.LINE_AA)
                                cv2.line(display_frame, (tx, ty + 10), (tx, ty + 32), ring_color, 2, lineType=cv2.LINE_AA)

                                # Badge with coordinates
                                badge_text = f"TAP: {label}"
                                font = cv2.FONT_HERSHEY_SIMPLEX
                                f_scale = 0.52
                                f_thick = 2
                                (tw, th), _ = cv2.getTextSize(badge_text, font, f_scale, f_thick)
                                bx1 = max(4, tx - tw // 2 - 6)
                                by1 = max(4, ty - pulse_r - th - 10)
                                bx2 = min(1276, bx1 + tw + 12)
                                by2 = by1 + th + 8
                                cv2.rectangle(display_frame, (bx1, by1), (bx2, by2), (20, 20, 24), -1)
                                cv2.rectangle(display_frame, (bx1, by1), (bx2, by2), ring_color, 1, lineType=cv2.LINE_AA)
                                cv2.putText(display_frame, badge_text, (bx1 + 6, by2 - 4), font, f_scale, (255, 255, 255), f_thick, lineType=cv2.LINE_AA)

                            elif ev_type == "swipe":
                                x1, y1 = ev["x1"], ev["y1"]
                                x2, y2 = ev["x2"], ev["y2"]
                                cv2.arrowedLine(display_frame, (x1, y1), (x2, y2), (0, 165, 255), 3, tipLength=0.15, lineType=cv2.LINE_AA)
                                cv2.circle(display_frame, (x1, y1), 8, (255, 200, 0), -1, lineType=cv2.LINE_AA)
                                cv2.circle(display_frame, (x2, y2), 8, (0, 255, 100), -1, lineType=cv2.LINE_AA)
                                cv2.putText(display_frame, "SWIPE", (int((x1+x2)/2), int((y1+y2)/2) - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2, lineType=cv2.LINE_AA)

                # 2. Responsive DPI-Aware 16:9 Viewfinder Scaling
                lbl_w = 460
                lbl_h = 258
                try:
                    if hasattr(self, "viewfinder_lbl") and self.viewfinder_lbl.winfo_exists():
                        lbl_w = self.viewfinder_lbl.winfo_width()
                        lbl_h = self.viewfinder_lbl.winfo_height()
                except Exception:
                    pass

                # CustomTkinter scaling conversion: winfo returns physical pixels,
                # but CTkImage expects logical points (DIP). Converting physical to logical
                # prevents 1.25x/1.5x zoom clipping!
                scaling = self.viewfinder_lbl._get_widget_scaling() if hasattr(self.viewfinder_lbl, "_get_widget_scaling") else 1.0
                logical_w = max(240.0, (lbl_w / scaling) - 16.0)
                logical_h = max(135.0, (lbl_h / scaling) - 16.0)

                scale = min(logical_w / 1280.0, logical_h / 720.0)
                target_w = max(240, int(round(1280.0 * scale)))
                target_h = max(135, int(round(720.0 * scale)))

                # Render with anti-aliasing
                small = cv2.resize(display_frame, (target_w, target_h), interpolation=cv2.INTER_AREA)
                rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(rgb)
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(target_w, target_h))
                self.after(0, lambda: self.viewfinder_lbl.configure(image=ctk_img, text=""))
                self.last_preview_time = time.time()

                # Process telemetry
                screen_type = self.ocr.detect_screen(frame)
                if screen_type == "HOME_VILLAGE" or self.detector.find_template(frame, "build_button", threshold=0.55) or self.detector.find_template(frame, "attack_button", threshold=0.50):
                    storages = self.ocr.read_village_storages(frame)
                    builder_info = self.detector.get_builders_info(frame)
                    self.after(0, lambda: self._apply_telemetry(storages, builder_info))
        except Exception:
            pass
        finally:
            self._vf_updating = False

    def _periodic_telemetry_loop(self):
        def _fetch():
            try:
                frame = self.capture.get_frame(target_size=(1280, 720))
                if frame is not None:
                    screen_type = self.ocr.detect_screen(frame)
                    if screen_type == "HOME_VILLAGE" or self.detector.find_template(frame, "build_button", threshold=0.55) or self.detector.find_template(frame, "attack_button", threshold=0.50):
                        storages = self.ocr.read_village_storages(frame)
                        builder_info = self.detector.get_builders_info(frame)
                        self.after(0, lambda: self._apply_telemetry(storages, builder_info))
            except Exception:
                pass

        combat_active = (
            self.bot_thread and self.bot_thread.is_alive()
            and not self.fsm.is_paused
            and (self.fsm.current_state in [BotState.MATCHMAKING, BotState.ATTACKING, BotState.VILLAGE_UNDER_ATTACK])
        )
        if not combat_active:
            threading.Thread(target=_fetch, daemon=True).start()

        self.after(2500, self._periodic_telemetry_loop)

    def _apply_telemetry(self, storages=None, builder_info=None):
        if storages:
            caps = village_profile.get_max_storage_capacities() if hasattr(village_profile, 'get_max_storage_capacities') else {}
            max_g = caps.get("gold", 5504500)
            max_e = caps.get("elixir", 5503000)
            max_de = caps.get("dark_elixir", 100000)

            g = storages.get("gold", 0)
            e = storages.get("elixir", 0)
            de = storages.get("dark_elixir", 0)

            if g > 0:
                self.stat_gold.set(f"{g:,}")
                pct_g = min(100, int((g / max_g) * 100)) if max_g > 0 else 0
                self.stat_gold_sub.set(f"Max: {max_g:,} • {pct_g}%")
            if e > 0:
                self.stat_elixir.set(f"{e:,}")
                pct_e = min(100, int((e / max_e) * 100)) if max_e > 0 else 0
                self.stat_elixir_sub.set(f"Max: {max_e:,} • {pct_e}%")
            if de > 0:
                self.stat_de.set(f"{de:,}")
                pct_de = min(100, int((de / max_de) * 100)) if max_de > 0 else 0
                self.stat_de_sub.set(f"Max: {max_de:,} • {pct_de}%")
            elif de == 0 and (g > 0 or e > 0):
                self.stat_de.set("0")
                self.stat_de_sub.set(f"Max: {max_de:,} • 0%")

        if builder_info is not None:
            if hasattr(village_profile, 'sync_with_live_detector'):
                village_profile.sync_with_live_detector(builder_info)
            total = getattr(village_profile, 'total_builders', 3)
            free_count = village_profile.get_free_builder_count() if hasattr(village_profile, 'get_free_builder_count') else 1
            if isinstance(builder_info, dict) and "free" in builder_info:
                free_count = builder_info["free"]
            self.stat_builders.set(f"0/{total} Busy" if free_count == 0 else f"{free_count}/{total} Free")

            busy_count = max(0, total - free_count)
            sec = village_profile.get_next_builder_free_seconds() if hasattr(village_profile, 'get_next_builder_free_seconds') else 0
            if busy_count > 0 and sec > 0:
                h = sec // 3600
                m = (sec % 3600) // 60
                self.stat_builders_sub.set(f"{busy_count} Busy • Next: {h:02d}h {m:02d}m")
            elif busy_count == 0:
                self.stat_builders_sub.set("All Builders Idle")
            else:
                self.stat_builders_sub.set(f"{busy_count} Busy")

    def _on_builder_count_changed(self, choice):
        try:
            num = int(choice.split()[0])
            self.cfg.setdefault("village_profile", {})["total_builders"] = num
            if hasattr(village_profile, 'total_builders'):
                village_profile.total_builders = num
            self._tick_builder_countdown()
            print(f"[VillageProfile] Total unlocked builders set to: {num}")
        except Exception as e:
            print(f"[VillageProfile] Error changing builder count: {e}")

    def _reset_builder_timers(self):
        try:
            if hasattr(village_profile, 'clear_builder_timers'):
                village_profile.clear_builder_timers()
            self._tick_builder_countdown()
            messagebox.showinfo("Timers Reset", "All builder timers cleared! All builders marked as Free.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not reset timers: {e}")

    def _initial_telemetry_fetch(self):
        def _fetch():
            try:
                frame = self.capture.get_frame(target_size=(1280, 720))
                if frame is not None:
                    storages = self.ocr.read_village_storages(frame)
                    builder_info = self.detector.get_builders_info(frame)
                    self.after(0, lambda: self._apply_telemetry(storages, builder_info))
            except Exception:
                pass
        threading.Thread(target=_fetch, daemon=True).start()

    def _test_adb_connection(self):
        print("[ADB] Testing device connection...")
        def _run():
            conn = self.adb.ensure_connected()
            if conn and self.adb.device:
                serial = self.adb.device.serial
                self.after(0, lambda: self.adb_status_dot.configure(text_color=ACCENT_GREEN))
                self.after(0, lambda: self.adb_status_lbl.configure(text=f"Online ({serial})"))
                print(f"[ADB] Device {serial} is connected and ready.")
                self._refresh_viewfinder()
            else:
                self.after(0, lambda: self.adb_status_dot.configure(text_color=ACCENT_RED))
                self.after(0, lambda: self.adb_status_lbl.configure(text="Offline"))
                print("[ADB] Warning: Could not connect to any active ADB device.")
        threading.Thread(target=_run, daemon=True).start()

    # ================= BOT CONTROLS =================
    def _start_bot_thread(self):
        if self.bot_thread and self.bot_thread.is_alive():
            return

        self._read_ui_into_config()
        self.fsm.cfg = self.cfg
        self.wall_upgrader.cfg = self.cfg.get("wall_dump", {})
        self.maintenance.cfg = self.cfg.get("maintenance", {})
        self.attack_engine.cfg = self.cfg

        if hasattr(self, "attack_engine") and self.attack_engine:
            self.attack_engine.abort_requested = False
        if hasattr(self, "wall_upgrader") and self.wall_upgrader:
            self.wall_upgrader.abort_requested = False
        if hasattr(self.fsm, "intervention_monitor") and self.fsm.intervention_monitor:
            interv_cfg = self.cfg.get("humanization", {})
            self.fsm.intervention_monitor.idle_resume_seconds = interv_cfg.get("user_idle_resume_seconds", 2.0)
            self.fsm.intervention_monitor.enabled = interv_cfg.get("enable_user_intervention", True)
            self.fsm.intervention_monitor.clear_intervention()

        self.btn_start.configure(state="disabled")
        self.btn_pause.configure(text="⏸  PAUSE", state="normal")
        self.btn_stop.configure(state="normal")
        self.status_pill_dot.configure(text_color=ACCENT_GREEN)
        self.stat_bot_state.set("RUNNING")

        print("[App] Launching ClashBot autonomous execution loop...")
        self.bot_thread = threading.Thread(target=self._run_fsm_loop, daemon=True)
        self.bot_thread.start()

    def _run_fsm_loop(self):
        try:
            self.fsm.start()
        except Exception as e:
            print(f"[App] FSM Thread Error: {e}")
        finally:
            self.after(0, self._on_bot_stopped_ui)

    def _toggle_pause_bot(self):
        if self.fsm:
            is_paused = self.fsm.pause()
            if is_paused:
                self.btn_pause.configure(text="▶  RESUME")
                self.status_pill_dot.configure(text_color=ACCENT_GOLD)
                self.stat_bot_state.set("PAUSED")
            else:
                self.btn_pause.configure(text="⏸  PAUSE")
                self.status_pill_dot.configure(text_color=ACCENT_GREEN)
                self.stat_bot_state.set("RUNNING")

    def _stop_bot_thread(self):
        print("[App] Stop button clicked. Halting bot immediately...")
        if hasattr(self, "attack_engine") and self.attack_engine:
            self.attack_engine.abort_requested = True
        if hasattr(self, "wall_upgrader") and self.wall_upgrader:
            self.wall_upgrader.abort_requested = True
        if self.fsm:
            self.fsm.stop()
        self._on_bot_stopped_ui()

    def _on_bot_stopped_ui(self):
        self.btn_start.configure(state="normal")
        self.btn_pause.configure(text="⏸  PAUSE", state="disabled")
        self.btn_stop.configure(state="disabled")
        self.status_pill_dot.configure(text_color=TEXT_MUTED)
        self.stat_bot_state.set("STOPPED")

    def _on_fsm_state_change(self, state_name):
        if state_name == "USER_INTERVENTION":
            display_name = "MANUAL PLAY"
        elif state_name == "VILLAGE_UNDER_ATTACK":
            display_name = "UNDER ATTACK ⚔️"
        else:
            display_name = state_name
        self.after(0, lambda: self.stat_bot_state.set(display_name))
        color_map = {
            "RUNNING": ACCENT_GREEN,
            "HOME_VILLAGE": "#38bdf8",
            "CHECK_WALL_DUMP": ACCENT_GOLD,
            "MATCHMAKING": ACCENT_DE,
            "ATTACKING": ACCENT_RED,
            "VILLAGE_UNDER_ATTACK": ACCENT_RED,
            "MAINTENANCE": "#a855f7",
            "SESSION_BREAK": "#fbbf24",
            "USER_INTERVENTION": "#f59e0b",
            "PAUSED": ACCENT_GOLD,
            "STOPPED": TEXT_MUTED
        }
        c = color_map.get(state_name, TEXT_MAIN)
        self.after(0, lambda: self.status_pill_dot.configure(text_color=c))

    def _on_fsm_stats_update(self, storages):
        def _update():
            caps = village_profile.get_max_storage_capacities() if hasattr(village_profile, 'get_max_storage_capacities') else {}
            max_g = caps.get("gold", 5504500)
            max_e = caps.get("elixir", 5503000)
            max_de = caps.get("dark_elixir", 100000)

            g = storages.get("gold", 0)
            e = storages.get("elixir", 0)
            de = storages.get("dark_elixir", 0)
            if g > 0:
                self.stat_gold.set(f"{g:,}")
                pct_g = min(100, int((g / max_g) * 100)) if max_g > 0 else 0
                self.stat_gold_sub.set(f"Max: {max_g:,} • {pct_g}%")
            if e > 0:
                self.stat_elixir.set(f"{e:,}")
                pct_e = min(100, int((e / max_e) * 100)) if max_e > 0 else 0
                self.stat_elixir_sub.set(f"Max: {max_e:,} • {pct_e}%")
            if de > 0:
                self.stat_de.set(f"{de:,}")
                pct_de = min(100, int((de / max_de) * 100)) if max_de > 0 else 0
                self.stat_de_sub.set(f"Max: {max_de:,} • {pct_de}%")
            self.stat_raids.set(str(self.fsm.total_attacks_completed))
        self.after(0, _update)

    def _on_mode_changed(self, mode):
        descriptions = {
            "BOTH": "(⚔️+🧱 Attacks bases & dumps excess loot into walls)",
            "ONLY_ATTACK": "(⚔️ Continuously raids bases; wall dump strictly disabled)",
            "ONLY_WALL_DUMP": "(🧱 Dumps Gold & Elixir into walls; attacks strictly disabled)"
        }
        if hasattr(self, "lbl_mode_desc"):
            self.lbl_mode_desc.configure(text=descriptions.get(mode, ""))
        if hasattr(self, "seg_settings_mode") and self.seg_settings_mode.get() != mode:
            self.seg_settings_mode.set(mode)
        if hasattr(self, "seg_bot_mode") and self.seg_bot_mode.get() != mode:
            self.seg_bot_mode.set(mode)
        self.cfg.setdefault("general", {})["bot_mode"] = mode
        if self.fsm:
            self.fsm.cfg = self.cfg
        print(f"[App] Operating mode switched to: {mode}")
        self._save_config()

    # ================= CONFIG SYNC =================
    def _read_ui_into_config(self):
        # General / Bot Mode
        try:
            self.cfg.setdefault("general", {})
            if hasattr(self, "mode_var"):
                self.cfg["general"]["bot_mode"] = self.mode_var.get()
        except Exception:
            pass

        # Matchmaking
        try:
            self.cfg.setdefault("matchmaking", {})
            self.cfg["matchmaking"]["min_gold"] = int(self.ent_min_gold.get().replace(",", ""))
            self.cfg["matchmaking"]["min_elixir"] = int(self.ent_min_elixir.get().replace(",", ""))
            self.cfg["matchmaking"]["min_dark_elixir"] = int(self.ent_min_de.get().replace(",", ""))
            if hasattr(self, "ent_min_total_loot"):
                self.cfg["matchmaking"]["min_total_loot"] = int(self.ent_min_total_loot.get().replace(",", ""))

            # Logic Mode
            if hasattr(self, "opt_match_logic"):
                txt_l = self.opt_match_logic.get()
                if "Total" in txt_l or "Sum" in txt_l:
                    self.cfg["matchmaking"]["match_logic"] = "TOTAL_SUM"
                elif "AND" in txt_l:
                    self.cfg["matchmaking"]["match_logic"] = "AND"
                elif "Dark" in txt_l:
                    self.cfg["matchmaking"]["match_logic"] = "DE_ONLY"
                elif "Smart" in txt_l:
                    self.cfg["matchmaking"]["match_logic"] = "SMART_BALANCED"
                else:
                    self.cfg["matchmaking"]["match_logic"] = "OR"
            elif hasattr(self, "seg_match_logic"):
                self.cfg["matchmaking"]["match_logic"] = "AND" if "AND" in self.seg_match_logic.get() else "OR"

            # Resource Preference
            if hasattr(self, "opt_resource_pref"):
                txt_p = self.opt_resource_pref.get()
                if "Gold" in txt_p:
                    self.cfg["matchmaking"]["resource_preference"] = "PREFER_GOLD"
                elif "Dark" in txt_p:
                    self.cfg["matchmaking"]["resource_preference"] = "PREFER_DE"
                elif "Elixir" in txt_p:
                    self.cfg["matchmaking"]["resource_preference"] = "PREFER_ELIXIR"
                else:
                    self.cfg["matchmaking"]["resource_preference"] = "BALANCED"

            # DE Priority Switch
            if hasattr(self, "sw_de_independent"):
                self.cfg["matchmaking"]["allow_de_independent"] = (self.sw_de_independent.get() == 1)

            self.cfg["matchmaking"]["max_search_skips"] = int(self.ent_max_skips.get())
        except Exception:
            pass

        # Wall dump
        try:
            self.cfg.setdefault("wall_dump", {})
            self.cfg["wall_dump"]["enabled"] = (self.sw_wall_enable.get() == 1) if hasattr(self, 'sw_wall_enable') else True
            self.cfg["wall_dump"]["keep_gold_reserve"] = int(self.ent_gold_reserve.get().replace(",", ""))
            self.cfg["wall_dump"]["keep_elixir_reserve"] = int(self.ent_elixir_reserve.get().replace(",", ""))
            self.cfg["wall_dump"]["upgrade_resource_priority"] = self.seg_wall_prio.get()
            self.cfg["wall_dump"]["max_walls_per_cycle"] = int(self.ent_max_walls.get())
            if hasattr(self, "ent_wall_trigger_pct"):
                self.cfg["wall_dump"]["storage_full_percentage"] = int(self.ent_wall_trigger_pct.get().replace("%", ""))
            if hasattr(self, "ent_max_spend_pct"):
                self.cfg["wall_dump"]["max_dump_spend_percent"] = int(self.ent_max_spend_pct.get().replace("%", ""))

            if hasattr(self, "opt_dump_trigger_mode"):
                dtm_txt = self.opt_dump_trigger_mode.get()
                if "Every" in dtm_txt:
                    self.cfg["wall_dump"]["dump_trigger_mode"] = "EVERY_N_ATTACKS"
                elif "Hybrid" in dtm_txt:
                    self.cfg["wall_dump"]["dump_trigger_mode"] = "HYBRID"
                else:
                    self.cfg["wall_dump"]["dump_trigger_mode"] = "WHEN_FULL"
            if hasattr(self, "ent_dump_every_n"):
                self.cfg["wall_dump"]["dump_every_n_attacks"] = int(self.ent_dump_every_n.get())

            strat_txt = self.opt_wall_strat.get() if hasattr(self, 'opt_wall_strat') else "Cheapest First"
            self.cfg.setdefault("village_profile", {})
            if "Cheapest" in strat_txt:
                self.cfg["village_profile"]["wall_strategy"] = "CHEAPEST_FIRST"
                self.cfg["wall_dump"]["wall_strategy"] = "CHEAPEST_FIRST"
            elif "Smart" in strat_txt:
                self.cfg["village_profile"]["wall_strategy"] = "SMART_HYBRID"
                self.cfg["wall_dump"]["wall_strategy"] = "SMART_HYBRID"
            else:
                self.cfg["village_profile"]["wall_strategy"] = "HIGHEST_FIRST"
                self.cfg["wall_dump"]["wall_strategy"] = "HIGHEST_FIRST"

            if hasattr(self, "opt_total_builders"):
                try:
                    b_num = int(self.opt_total_builders.get().split()[0])
                except Exception:
                    b_num = 3
                self.cfg["village_profile"]["total_builders"] = b_num
                if hasattr(village_profile, 'total_builders'):
                    village_profile.total_builders = b_num
        except Exception:
            pass

        # Combat
        try:
            self.cfg.setdefault("combat", {})
            patt_val = self.opt_deploy_pattern.get() if hasattr(self, 'opt_deploy_pattern') else "Adaptive Smart"
            if "Adaptive" in patt_val or "Smart" in patt_val or "Variety" in patt_val:
                self.cfg["combat"]["deployment_pattern"] = "ADAPTIVE_SMART"
            elif "Single" in patt_val:
                self.cfg["combat"]["deployment_pattern"] = "SINGLE_SIDE"
            elif "Two Sides" in patt_val or "Pincer" in patt_val:
                self.cfg["combat"]["deployment_pattern"] = "TWO_SIDES"
            elif "Surgical" in patt_val:
                self.cfg["combat"]["deployment_pattern"] = "SURGICAL_PERIMETER"
            elif "Core" in patt_val:
                self.cfg["combat"]["deployment_pattern"] = "CORE_RUSH"
            elif "Corners" in patt_val:
                self.cfg["combat"]["deployment_pattern"] = "ALL_4_CORNERS"
            else:
                self.cfg["combat"]["deployment_pattern"] = "ALL_4_SIDES"

            self.cfg["combat"]["auto_zoom_out"] = (self.sw_auto_zoom.get() == 1) if hasattr(self, 'sw_auto_zoom') else True
            self.cfg["combat"]["deploy_heroes"] = self.sw_deploy_heroes.get() == 1
            self.cfg["combat"]["deploy_spells"] = self.sw_deploy_spells.get() == 1
            self.cfg["combat"]["deploy_all_spells"] = self.sw_deploy_spells.get() == 1
            self.cfg["combat"]["battle_duration_seconds"] = int(self.ent_battle_duration.get())
            if hasattr(self, "ent_surrender_pct"):
                self.cfg["combat"]["early_surrender_loot_percent"] = int(self.ent_surrender_pct.get().replace("%", ""))
            self.attack_engine.update_config(self.cfg)
        except Exception:
            pass

        # Emulator
        try:
            self.cfg.setdefault("emulator", {})
            self.cfg["emulator"]["type"] = self.opt_emu_type.get()
            self.cfg["emulator"]["adb_port"] = int(self.ent_adb_port.get())
        except Exception:
            pass

        # Scheduled Auto Stop & Power Management
        try:
            self.cfg.setdefault("auto_stop", {})
            self.cfg["auto_stop"]["enabled"] = (self.sw_auto_stop.get() == 1) if hasattr(self, "sw_auto_stop") else False
            self.cfg["auto_stop"]["hours"] = int(self.ent_stop_hours.get()) if hasattr(self, "ent_stop_hours") else 2
            self.cfg["auto_stop"]["minutes"] = int(self.ent_stop_mins.get()) if hasattr(self, "ent_stop_mins") else 0
            act_text = self.opt_stop_action.get() if hasattr(self, "opt_stop_action") else "Just Stop Bot"
            if "Close" in act_text:
                self.cfg["auto_stop"]["action"] = "CLOSE_BOT_AND_EMULATOR"
            elif "Shutdown" in act_text:
                self.cfg["auto_stop"]["action"] = "SHUTDOWN_PC"
            elif "Sleep" in act_text:
                self.cfg["auto_stop"]["action"] = "SLEEP_PC"
            else:
                self.cfg["auto_stop"]["action"] = "JUST_STOP"
        except Exception:
            pass

        # Persist to settings.yaml
        try:
            cfg_path = os.path.join(get_base_dir(), "config", "settings.yaml")
            with open(cfg_path, "w", encoding="utf-8") as f:
                yaml.dump(self.cfg, f, default_flow_style=False, sort_keys=False)
        except Exception as e:
            print(f"[Config Save Error] Could not save settings.yaml: {e}")


def main():
    app = ClashBotApp()
    app.mainloop()


if __name__ == "__main__":
    main()
