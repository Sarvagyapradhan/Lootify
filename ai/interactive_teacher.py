"""
Clash of Clans AI Studio & Interactive Teacher.
Features:
1. 🏷️ Visual Building & Field Annotation (Auto-snap, custom definitions, YOLO label export).
2. 🎯 UI Button & Template Calibrator (Calibrate updated game buttons without polluting labels).
3. 🎮 Interactive Tap & Workflow Navigator (Tap emulator directly on canvas to navigate multi-step flows!).
4. ⏩ 1-Click Game Workflow Shortcuts (Open Attack Menu, Start Raid, Open Builder Menu, Return Home).
5. ⚙️ Advanced Model Training Studio with UTF-8 subprocess isolation (100% bug-free).
"""

import os
import sys
import glob
import subprocess
import threading
import time
import cv2
import numpy as np
from PIL import Image, ImageTk
import customtkinter as ctk
from tkinter import messagebox, filedialog

from ai.constants import CLASS_TO_ID, ID_TO_CLASS, CLASS_COLORS
from ai.knowledge_base import GameKnowledgeBase
from core.adb_client import ADBController

PANEL_DARK = "#111827"
CARD_BG = "#1f2937"
CARD_BORDER = "#374151"
TEXT_MAIN = "#f9fafb"
TEXT_MUTED = "#9ca3af"
ACCENT_GOLD = "#f59e0b"
ACCENT_GREEN = "#10b981"
ACCENT_RED = "#ef4444"
ACCENT_BLUE = "#3b82f6"

GAME_BUTTON_TEMPLATES = [
    ("attack_button", "⚔️ Attack! (Bottom Left)"),
    ("shop_button", "🛒 Shop (Bottom Right)"),
    ("find_match_button", "🔍 Find a Match (Attack Menu)"),
    ("army_attack_button", "⚔️ Army Attack! (Troop Menu)"),
    ("next_button", "⏩ Next (Matchmaking Search)"),
    ("end_battle_button", "🏳️ End Battle / Surrender"),
    ("return_home_button", "🏠 Return Home (Battle Results)"),
    ("builder_menu", "👷 Builder Banner (Top Center)"),
    ("builder_zero", "👷 0 Free Builders Badge"),
    ("wall_confirm_okay", "🧱 Wall Upgrade Okay / Confirm"),
    ("all_builders_busy", "🛑 All Builders Busy Modal"),
    ("modal_cancel_btn", "❌ Modal Cancel / Close Button"),
    ("reload_game", "🔄 Reload Game (Disconnect Dialog)")
]


class InteractiveTeacherStudio(ctk.CTkToplevel):
    def __init__(self, parent=None, screen_capture=None, ai_detector=None):
        super().__init__(parent)
        self.title("🎓 Clash of Clans AI Studio & Advanced Model Trainer")
        self.geometry("1360x900")
        self.minsize(1180, 800)
        self.configure(fg_color="#0b0f19")

        self.screen_capture = screen_capture
        self.ai_detector = ai_detector
        self.adb = getattr(screen_capture, "adb", None) if screen_capture else None
        if not self.adb:
            self.adb = ADBController(port=21503)
        self.kb = GameKnowledgeBase()

        # Carousel & image state
        self.image_list = []
        self.image_index = 0
        self.current_frame = None  # Full 1280x720 BGR image
        self.current_image_path = None

        # Mode: "BUILDINGS", "BUTTON_CALIBRATOR", "NAVIGATE_EMULATOR"
        self.active_canvas_mode = "BUILDINGS"

        # Screen environment mode: HOME_VILLAGE or ATTACK_BATTLEFIELD
        self.screen_mode = "HOME_VILLAGE"

        # Labeled boxes on current image (YOLO buildings)
        self.candidates = []  # list of {"box": [x1, y1, x2, y2], "class": str, "notes": str}
        self.active_idx = -1

        # Template calibration crop box (separate from building labels!)
        self.calib_box = None

        # Draggable / Movable Box State
        self.is_moving_box = False
        self.moving_box_start_coords = None
        self.moving_start_point = (0, 0)

        # Canvas drag & scaling
        self.drag_start = None
        self.drag_rect_id = None
        self.canvas_w = 760
        self.canvas_h = 428
        self.canvas_scale_x = 1.0
        self.canvas_scale_y = 1.0

        # Background training state
        self.is_training = False
        self.training_process = None

        self._refresh_image_list()
        self._build_ui()
        self._load_current_image_from_list()

    def _refresh_image_list(self):
        """Finds all captured gameplay screenshots."""
        patterns = ["ai_data/images/*.jpg", "ai_data/images/*.png"]
        found = []
        for p in patterns:
            found.extend(glob.glob(p))
        seen = set()
        self.image_list = []
        for f in found:
            norm = os.path.normpath(f)
            if norm not in seen:
                seen.add(norm)
                self.image_list.append(norm)

    def _build_ui(self):
        # 1. Top Header & Primary Actions
        top_bar = ctk.CTkFrame(self, fg_color=PANEL_DARK, corner_radius=10, height=54)
        top_bar.pack(fill="x", padx=12, pady=(10, 6))

        ctk.CTkLabel(top_bar, text="🎓 AI Studio & Model Trainer", font=ctk.CTkFont(size=16, weight="bold"), text_color=ACCENT_GOLD).pack(side="left", padx=14)

        # Mode Segmented Button
        self.seg_canvas_mode = ctk.CTkSegmentedButton(
            top_bar, values=["🏷️ Mark Buildings", "🎯 Button Calibrator", "🎮 Tap Emulator & Navigate"],
            command=self._on_canvas_mode_toggled, font=ctk.CTkFont(size=12, weight="bold")
        )
        self.seg_canvas_mode.set("🏷️ Mark Buildings")
        self.seg_canvas_mode.pack(side="left", padx=10)

        ctk.CTkButton(top_bar, text="📸 Capture Live Screen", width=150, height=32, fg_color=ACCENT_GREEN, hover_color="#059669", font=ctk.CTkFont(size=12, weight="bold"), command=self._capture_live_screen).pack(side="right", padx=6)
        ctk.CTkButton(top_bar, text="📂 Open Image", width=110, height=32, fg_color="#374151", hover_color="#4b5563", font=ctk.CTkFont(size=12), command=self._browse_image).pack(side="right", padx=6)
        ctk.CTkButton(top_bar, text="🗑️ Reset Dataset", width=115, height=32, fg_color=ACCENT_RED, hover_color="#dc2626", font=ctk.CTkFont(size=12), command=self._reset_entire_dataset).pack(side="right", padx=6)

        # 2. Carousel & Workflow Navigation Bar
        car_bar = ctk.CTkFrame(self, fg_color=CARD_BG, corner_radius=8, height=42)
        car_bar.pack(fill="x", padx=12, pady=(0, 6))

        # Carousel navigation
        ctk.CTkButton(car_bar, text="◀ Prev Image", width=105, height=28, fg_color="#374151", command=self._prev_image).pack(side="left", padx=6, pady=6)
        self.lbl_carousel_info = ctk.CTkLabel(car_bar, text="Image: 0 / 0", font=ctk.CTkFont(size=12, weight="bold"), text_color=TEXT_MAIN)
        self.lbl_carousel_info.pack(side="left", padx=10)
        ctk.CTkButton(car_bar, text="Next Image ▶", width=105, height=28, fg_color="#374151", command=self._next_image).pack(side="left", padx=6)

        # 1-Click Game Workflow Shortcuts (Answers: "How should I mark buttons that appear after clicking another button?")
        wf_box = ctk.CTkFrame(car_bar, fg_color="transparent")
        wf_box.pack(side="right", padx=6)

        ctk.CTkLabel(wf_box, text="Navigate Game:", font=ctk.CTkFont(size=11, weight="bold"), text_color=TEXT_MUTED).pack(side="left", padx=4)
        ctk.CTkButton(wf_box, text="⚔️ Open Attack Menu", width=135, height=26, fg_color="#0284c7", hover_color="#0369a1", font=ctk.CTkFont(size=11), command=lambda: self._quick_tap_and_refresh(60, 650, delay=1.2)).pack(side="left", padx=2)
        ctk.CTkButton(wf_box, text="🔍 Start Raid Search", width=135, height=26, fg_color="#0284c7", hover_color="#0369a1", font=ctk.CTkFont(size=11), command=lambda: self._quick_tap_and_refresh(930, 540, delay=2.5)).pack(side="left", padx=2)
        ctk.CTkButton(wf_box, text="👷 Open Builder Menu", width=135, height=26, fg_color="#0284c7", hover_color="#0369a1", font=ctk.CTkFont(size=11), command=lambda: self._quick_tap_and_refresh(620, 35, delay=1.0)).pack(side="left", padx=2)
        ctk.CTkButton(wf_box, text="🏠 Return Home", width=110, height=26, fg_color="#374151", font=ctk.CTkFont(size=11), command=lambda: self._quick_tap_and_refresh(640, 630, delay=1.5)).pack(side="left", padx=2)

        # 3. Main Body: Left (Canvas), Right (Tabbed Studio)
        main_body = ctk.CTkFrame(self, fg_color="transparent")
        main_body.pack(fill="both", expand=True, padx=12, pady=4)
        main_body.grid_columnconfigure(0, weight=3)
        main_body.grid_columnconfigure(1, weight=2)
        main_body.grid_rowconfigure(0, weight=1)

        # Left Column: Canvas Card
        canvas_card = ctk.CTkFrame(main_body, fg_color=PANEL_DARK, corner_radius=10, border_width=1, border_color=CARD_BORDER)
        canvas_card.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        canv_hdr = ctk.CTkFrame(canvas_card, fg_color="transparent")
        canv_hdr.pack(fill="x", padx=12, pady=6)
        self.lbl_canvas_title = ctk.CTkLabel(canv_hdr, text="Gameplay Canvas", font=ctk.CTkFont(size=12, weight="bold"), text_color=TEXT_MAIN)
        self.lbl_canvas_title.pack(side="left")

        self.lbl_mode_indicator = ctk.CTkLabel(canv_hdr, text="[Mode: Mark Buildings]", font=ctk.CTkFont(size=12, weight="bold"), text_color=ACCENT_GOLD)
        self.lbl_mode_indicator.pack(side="right")

        # Native Tkinter Canvas
        self.canvas = ctk.CTkCanvas(canvas_card, width=self.canvas_w, height=self.canvas_h, bg="#000000", highlightthickness=0)
        self.canvas.pack(padx=12, pady=(0, 4))
        self.canvas.bind("<ButtonPress-1>", self._on_canvas_press)
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
        # Keyboard Arrow Nudge Shortcuts
        self.canvas.bind("<Left>", lambda e: self._move_active_box(-5, 0))
        self.canvas.bind("<Right>", lambda e: self._move_active_box(5, 0))
        self.canvas.bind("<Up>", lambda e: self._move_active_box(0, -5))
        self.canvas.bind("<Down>", lambda e: self._move_active_box(0, 5))
        self.canvas.bind("<Shift-Left>", lambda e: self._move_active_box(-20, 0))
        self.canvas.bind("<Shift-Right>", lambda e: self._move_active_box(20, 0))
        self.canvas.bind("<Shift-Up>", lambda e: self._move_active_box(0, -20))
        self.canvas.bind("<Shift-Down>", lambda e: self._move_active_box(0, 20))

        # Movable Box Nudge & Resize Controls
        move_bar = ctk.CTkFrame(canvas_card, fg_color="#182234", corner_radius=6, height=30)
        move_bar.pack(fill="x", padx=12, pady=(0, 4))

        ctk.CTkLabel(move_bar, text="📦 Move Box:", font=ctk.CTkFont(size=11, weight="bold"), text_color=ACCENT_GOLD).pack(side="left", padx=6)
        ctk.CTkButton(move_bar, text="⬅️ Left", width=55, height=22, font=ctk.CTkFont(size=10), fg_color="#374151", command=lambda: self._move_active_box(-10, 0)).pack(side="left", padx=2)
        ctk.CTkButton(move_bar, text="➡️ Right", width=55, height=22, font=ctk.CTkFont(size=10), fg_color="#374151", command=lambda: self._move_active_box(10, 0)).pack(side="left", padx=2)
        ctk.CTkButton(move_bar, text="⬆️ Up", width=50, height=22, font=ctk.CTkFont(size=10), fg_color="#374151", command=lambda: self._move_active_box(0, -10)).pack(side="left", padx=2)
        ctk.CTkButton(move_bar, text="⬇️ Down", width=50, height=22, font=ctk.CTkFont(size=10), fg_color="#374151", command=lambda: self._move_active_box(0, 10)).pack(side="left", padx=2)
        ctk.CTkButton(move_bar, text="➖ Smaller", width=65, height=22, font=ctk.CTkFont(size=10), fg_color="#374151", command=lambda: self._resize_active_box(-10, -10)).pack(side="left", padx=4)
        ctk.CTkButton(move_bar, text="➕ Bigger", width=65, height=22, font=ctk.CTkFont(size=10), fg_color="#374151", command=lambda: self._resize_active_box(10, 10)).pack(side="left", padx=2)
        ctk.CTkLabel(move_bar, text="(or drag box directly on canvas)", font=ctk.CTkFont(size=10), text_color=TEXT_MUTED).pack(side="right", padx=6)

        # Box controls under Canvas
        box_nav = ctk.CTkFrame(canvas_card, fg_color="transparent")
        box_nav.pack(fill="x", padx=12, pady=(0, 6))

        ctk.CTkButton(box_nav, text="◀ Prev Box", width=95, height=26, fg_color="#374151", command=self._prev_box).pack(side="left", padx=2)
        self.lbl_box_pos = ctk.CTkLabel(box_nav, text="Box: 0 / 0", font=ctk.CTkFont(size=12, weight="bold"), text_color=TEXT_MAIN)
        self.lbl_box_pos.pack(side="left", padx=10)
        ctk.CTkButton(box_nav, text="Next Box ▶", width=95, height=26, fg_color="#374151", command=self._next_box).pack(side="left", padx=2)

        ctk.CTkButton(box_nav, text="🗑️ Delete Box", width=105, height=26, fg_color=ACCENT_RED, hover_color="#dc2626", command=self._delete_active_box).pack(side="right", padx=4)
        ctk.CTkButton(box_nav, text="Clear All", width=80, height=26, fg_color="#4b5563", command=self._clear_all_boxes).pack(side="right", padx=2)

        # Active Box Thumbnail Bar
        thumb_bar = ctk.CTkFrame(canvas_card, fg_color=CARD_BG, corner_radius=8, height=80)
        thumb_bar.pack(fill="x", padx=12, pady=(0, 8))

        self.lbl_thumb = ctk.CTkLabel(thumb_bar, text="[No Selection]", width=70, height=70, fg_color="#000000", corner_radius=6)
        self.lbl_thumb.pack(side="left", padx=8, pady=5)

        thumb_info = ctk.CTkFrame(thumb_bar, fg_color="transparent")
        thumb_info.pack(side="left", fill="both", expand=True, padx=8, pady=5)
        self.lbl_active_name = ctk.CTkLabel(thumb_info, text="Click a building to label it", font=ctk.CTkFont(size=13, weight="bold"), text_color=TEXT_MAIN)
        self.lbl_active_name.pack(anchor="w")
        self.lbl_active_pos = ctk.CTkLabel(thumb_info, text="Center: (0, 0) | Size: 0x0 px", font=ctk.CTkFont(size=11), text_color=TEXT_MUTED)
        self.lbl_active_pos.pack(anchor="w")

        # Right Column: Tabbed Control Center
        self.tabs = ctk.CTkTabview(main_body, fg_color=PANEL_DARK, corner_radius=10, border_width=1, border_color=CARD_BORDER, command=self._on_tab_changed)
        self.tabs.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        tab_mark = self.tabs.add("🏷️ Mark Buildings")
        tab_buttons = self.tabs.add("🎯 Button Calibrator")
        tab_train = self.tabs.add("⚙️ Advanced Training")

        self._build_mark_tab(tab_mark)
        self._build_button_calibrator_tab(tab_buttons)
        self._build_training_tab(tab_train)

    def _on_tab_changed(self):
        cur = self.tabs.get()
        if "Button" in cur:
            self.active_canvas_mode = "BUTTON_CALIBRATOR"
            self.seg_canvas_mode.set("🎯 Button Calibrator")
            self.lbl_mode_indicator.configure(text="[Mode: Calibrate Button]", text_color=ACCENT_BLUE)
        elif "Train" in cur:
            self.active_canvas_mode = "TRAIN"
            self.lbl_mode_indicator.configure(text="[Mode: Model Training]", text_color="#a855f7")
        else:
            self.active_canvas_mode = "BUILDINGS"
            self.seg_canvas_mode.se    # ---------------- TAB 1: MARK BUILDINGS ----------------
    def _build_mark_tab(self, tab):
        ctk.CTkLabel(tab, text="🏷️ Custom Building / Structure Labeler", font=ctk.CTkFont(size=14, weight="bold"), text_color=ACCENT_GOLD).pack(anchor="w", padx=6, pady=(4, 6))

        # Clean custom entry card
        def_card = ctk.CTkFrame(tab, fg_color=CARD_BG, corner_radius=8, border_width=1, border_color=CARD_BORDER)
        def_card.pack(fill="x", padx=6, pady=(0, 8))

        ctk.CTkLabel(def_card, text="Item Name / Tag:", font=ctk.CTkFont(size=11, weight="bold"), text_color=TEXT_MUTED).pack(anchor="w", padx=8, pady=(6, 2))
        self.ent_manual_class = ctk.CTkEntry(def_card, placeholder_text="e.g. elixir_collector, gold_storage, town_hall, wall", height=30)
        self.ent_manual_class.pack(fill="x", padx=8, pady=(0, 6))
        self.ent_manual_class.insert(0, "town_hall")

        ctk.CTkLabel(def_card, text="Description & Notes:", font=ctk.CTkFont(size=11, weight="bold"), text_color=TEXT_MUTED).pack(anchor="w", padx=8, pady=(2, 2))
        self.ent_notes = ctk.CTkEntry(def_card, placeholder_text="e.g. Town Hall 10 center, Level 11 Gold Storage", height=30)
        self.ent_notes.pack(fill="x", padx=8, pady=(0, 6))

        role_row = ctk.CTkFrame(def_card, fg_color="transparent")
        role_row.pack(fill="x", padx=8, pady=(0, 8))
        ctk.CTkLabel(role_row, text="Usage / Role:", font=ctk.CTkFont(size=11, weight="bold"), text_color=TEXT_MUTED).pack(side="left", padx=(0, 6))
        self.opt_manual_role = ctk.CTkOptionMenu(
            role_row, values=["LOOT_PRIORITY", "CORE_TARGET", "DEFENSE", "WALL_STRUCTURE", "OBSTACLE", "INFO_ONLY"],
            height=28, font=ctk.CTkFont(size=11)
        )
        self.opt_manual_role.set("LOOT_PRIORITY")
        self.opt_manual_role.pack(side="left", fill="x", expand=True)

        ctk.CTkButton(
            def_card, text="🏷️ Apply to Active Box & Save to Knowledge Base", height=32,
            fg_color=ACCENT_GREEN, hover_color="#059669", font=ctk.CTkFont(size=12, weight="bold"),
            command=self._apply_custom_class_to_active
        ).pack(fill="x", padx=8, pady=(0, 8))

        # Quick preset chips (Optional 1-click convenience)
        ctk.CTkLabel(tab, text="Quick Suggestions (Click to fill name):", font=ctk.CTkFont(size=11, weight="bold"), text_color=TEXT_MUTED).pack(anchor="w", padx=6, pady=(4, 2))
        chip_frame = ctk.CTkFrame(tab, fg_color="transparent")
        chip_frame.pack(fill="x", padx=4, pady=(0, 8))
        quick_chips = [
            ("Town Hall", "town_hall"),
            ("Elixir Collector", "elixir_collector"),
            ("Gold Mine", "gold_mine"),
            ("Elixir Storage", "elixir_storage"),
            ("Gold Storage", "gold_storage"),
            ("DE Storage", "dark_elixir_storage"),
            ("Air Defense", "air_defense"),
            ("Wall", "wall"),
            ("Red Line", "red_boundary")
        ]
        for i, (label, val) in enumerate(quick_chips):
            r, c = divmod(i, 3)
            btn = ctk.CTkButton(
                chip_frame, text=label, height=26, font=ctk.CTkFont(size=10),
                fg_color="#1f2937", hover_color="#374151", border_width=1, border_color="#374151",
                command=lambda v=val: self._fill_custom_class(v)
            )
            btn.grid(row=r, column=c, padx=2, pady=2, sticky="ew")
        chip_frame.grid_columnconfigure((0, 1, 2), weight=1)

    # ---------------- TAB 2: LIVE BUTTON & WORKFLOW CALIBRATOR ----------------
    def _build_button_calibrator_tab(self, tab):
        scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=2, pady=2)

        ctk.CTkLabel(scroll, text="🎯 UI Button & Template Calibrator", font=ctk.CTkFont(size=14, weight="bold"), text_color=ACCENT_GOLD).pack(anchor="w", padx=6, pady=(2, 4))

        # Clean Button Setup Card
        btn_card = ctk.CTkFrame(scroll, fg_color=CARD_BG, corner_radius=8, border_width=1, border_color=CARD_BORDER)
        btn_card.pack(fill="x", padx=6, pady=(0, 8))

        ctk.CTkLabel(btn_card, text="Button / Template Name (PNG):", font=ctk.CTkFont(size=11, weight="bold"), text_color=TEXT_MUTED).pack(anchor="w", padx=8, pady=(6, 2))
        self.ent_custom_btn_name = ctk.CTkEntry(btn_card, placeholder_text="e.g. wall_upgrade_more, attack_button, build_button, next_button", height=30)
        self.ent_custom_btn_name.pack(fill="x", padx=8, pady=(0, 6))
        self.ent_custom_btn_name.insert(0, "wall_upgrade_more")
        self.ent_custom_btn_name.bind("<KeyRelease>", self._on_custom_btn_typed)

        ctk.CTkLabel(btn_card, text="Description & Flow Usage:", font=ctk.CTkFont(size=11, weight="bold"), text_color=TEXT_MUTED).pack(anchor="w", padx=8, pady=(2, 2))
        self.ent_btn_usage = ctk.CTkEntry(btn_card, placeholder_text="e.g. Opens wall batch upgrade mode, Matchmaking next base", height=30)
        self.ent_btn_usage.pack(fill="x", padx=8, pady=(0, 8))

        # Quick Button Suggestions (Chips)
        ctk.CTkLabel(btn_card, text="Quick Button Tags (Click to fill):", font=ctk.CTkFont(size=10, weight="bold"), text_color=TEXT_MUTED).pack(anchor="w", padx=8, pady=(0, 2))
        chip_row = ctk.CTkFrame(btn_card, fg_color="transparent")
        chip_row.pack(fill="x", padx=6, pady=(0, 8))
        common_btns = [
            ("⚔️ Battle", "battle_button"),
            ("🔍 Find Match", "find_match_button"),
            ("⚔️ Army Attack", "army_attack_button"),
            ("⏩ Next", "next_button"),
            ("🏳️ End Battle", "end_battle_button"),
            ("🏠 Return Home", "return_home_button"),
            ("🔨 Build Button", "build_button"),
            ("🧱 Wall More", "wall_upgrade_more"),
            ("🧱 Select Row", "wall_select_row"),
            ("🧱 Add 10", "wall_add_10"),
            ("🧱 Add 1", "wall_add_1"),
            ("❌ Close X", "modal_close_x")
        ]
        for i, (blabel, bname) in enumerate(common_btns):
            r, c = divmod(i, 3)
            b = ctk.CTkButton(
                chip_row, text=blabel, height=24, font=ctk.CTkFont(size=10),
                fg_color="#111827", hover_color="#374151",
                command=lambda bn=bname: self._set_custom_btn_name(bn)
            )
            b.grid(row=r, column=c, padx=2, pady=2, sticky="ew")
        chip_row.grid_columnconfigure((0, 1, 2), weight=1)

        # Template preview cards (Saved vs New Crop)
        preview_frame = ctk.CTkFrame(scroll, fg_color=CARD_BG, corner_radius=8, border_width=1, border_color=CARD_BORDER)
        preview_frame.pack(fill="x", padx=6, pady=(0, 8))
        preview_frame.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(preview_frame, text="Saved Template:", font=ctk.CTkFont(size=11, weight="bold"), text_color=TEXT_MUTED).grid(row=0, column=0, padx=6, pady=(4, 2))
        self.lbl_prev_saved_tmpl = ctk.CTkLabel(preview_frame, text="[None]", width=80, height=45, fg_color="#000000", corner_radius=6)
        self.lbl_prev_saved_tmpl.grid(row=1, column=0, padx=6, pady=(0, 6))

        ctk.CTkLabel(preview_frame, text="New Canvas Crop:", font=ctk.CTkFont(size=11, weight="bold"), text_color=ACCENT_GOLD).grid(row=0, column=1, padx=6, pady=(4, 2))
        self.lbl_new_crop_preview = ctk.CTkLabel(preview_frame, text="[Click/Drag Canvas]", width=80, height=45, fg_color="#000000", corner_radius=6)
        self.lbl_new_crop_preview.grid(row=1, column=1, padx=6, pady=(0, 6))

        # Primary Actions
        action_row = ctk.CTkFrame(scroll, fg_color="transparent")
        action_row.pack(fill="x", padx=6, pady=(0, 6))

        self.btn_save_template = ctk.CTkButton(
            action_row, text="💾 Save Selected Box as Template", height=34,
            fg_color=ACCENT_GREEN, hover_color="#059669", font=ctk.CTkFont(size=12, weight="bold"),
            command=self._save_active_as_button_template
        )
        self.btn_save_template.pack(side="left", fill="x", expand=True, padx=(0, 4))

        ctk.CTkButton(
            action_row, text="🔍 Test Match", height=34, width=120,
            fg_color="#3b82f6", hover_color="#2563eb", font=ctk.CTkFont(size=12, weight="bold"),
            command=self._test_current_template_match
        ).pack(side="right")

        self.lbl_calib_result = ctk.CTkLabel(scroll, text="Status: Drag or move box over any button on canvas.", font=ctk.CTkFont(size=11), text_color=TEXT_MUTED)
        self.lbl_calib_result.pack(anchor="w", padx=6, pady=(0, 8))

        # Multi-Step Live Progression Tool
        self.btn_tap_selected_box = ctk.CTkButton(
            scroll, text="▶️ Tap Selected Box on Live Game & Reveal Next Screen", height=34,
            fg_color="#7c3aed", hover_color="#6d28d9", font=ctk.CTkFont(size=12, weight="bold"),
            command=self._tap_selected_box_and_refresh
        )
        self.btn_tap_selected_box.pack(fill="x", padx=6, pady=(0, 6))

        # Workflow Jumps Grid
        jumps_grid = ctk.CTkFrame(scroll, fg_color="transparent")
        jumps_grid.pack(fill="x", padx=6, pady=(0, 6))
        jumps = [
            ("⚔️ 1. Attack Menu", 66, 615, 1.2),
            ("🔍 2. Find Match", 218, 545, 2.5),
            ("⚔️ 3. Army Attack", 1131, 642, 2.0),
            ("⏩ 4. Next Base", 1166, 540, 2.5),
            ("🏳️ 5. End Battle", 91, 565, 1.2),
            ("🏠 6. Return Home", 640, 600, 1.5),
            ("🔨 7. Build Menu", 1210, 630, 1.0),
            ("🔄 8. Grab Live Screen", None, None, 0.0)
        ]
        for i, (jlabel, jx, jy, jdelay) in enumerate(jumps):
            r, c = divmod(i, 2)
            cmd = self._capture_live_screen if jx is None else (lambda x=jx, y=jy, d=jdelay: self._quick_tap_and_refresh(x, y, delay=d))
            btn = ctk.CTkButton(
                jumps_grid, text=jlabel, height=28, font=ctk.CTkFont(size=11),
                fg_color="#1f2937", hover_color="#374151", border_width=1, border_color="#374151",
                command=cmd
            )
            btn.grid(row=r, column=c, padx=3, pady=2, sticky="ew")
        jumps_grid.grid_columnconfigure((0, 1), weight=1)

        self._refresh_saved_template_preview()

    def _fill_custom_class(self, val):
        self.ent_manual_class.delete(0, "end")
        self.ent_manual_class.insert(0, val)

    def _set_custom_btn_name(self, name):
        self.ent_custom_btn_name.delete(0, "end")
        self.ent_custom_btn_name.insert(0, name)
        self._refresh_saved_template_preview()

    def _on_custom_btn_typed(self, event=None):
        self._refresh_saved_template_preview()

    def _apply_custom_class_to_active(self):
        cname = self.ent_manual_class.get().strip().lower().replace(" ", "_")
        if not cname:
            cname = "building"
        notes = self.ent_notes.get().strip()
        role = self.opt_manual_role.get().strip()

        if not (0 <= self.active_idx < len(self.candidates)):
            new_box = [590, 310, 690, 410]
            self.candidates.append({"box": new_box, "class": cname, "notes": notes})
            self.active_idx = len(self.candidates) - 1
        else:
            cand = self.candidates[self.active_idx]
            cand["class"] = cname
            cand["notes"] = notes

        self.kb.set_definition(
            class_key=cname,
            name=cname.replace("_", " ").title(),
            description=notes or f"Custom {cname} definition",
            role=role
        )

        self._save_yolo_labels()
        self._update_info_panel()
        self._redraw_canvas()
        messagebox.showinfo("Saved", f"✅ Set '{cname}' (Role: {role}) and saved to Knowledge Base!")

    def _nudge_box(self, dw=0, dh=0):
        if not self.calib_box:
            self.calib_box = [580, 335, 700, 385]
        x1, y1, x2, y2 = self.calib_box
        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2
        nw = max(16, (x2 - x1) + dw)
        nh = max(12, (y2 - y1) + dh)
        self.calib_box = [max(0, cx - nw // 2), max(0, cy - nh // 2), min(1280, cx + nw // 2), min(720, cy + nh // 2)]
        self._update_calib_crop_preview()
        self._redraw_canvas()

    def _reset_standard_button_box(self):
        if not self.calib_box:
            self.calib_box = [580, 335, 700, 385]
        x1, y1, x2, y2 = self.calib_box
        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2
        self.calib_box = [max(0, cx - 55), max(0, cy - 23), min(1280, cx + 55), min(720, cy + 23)]
        self._update_calib_crop_preview()
        self._redraw_canvas()

    def _tap_selected_box_and_refresh(self):
        if not self.calib_box:
            messagebox.showinfo("Notice", "Click or drag a box on the canvas first over the button you want to tap!")
            return
        x1, y1, x2, y2 = self.calib_box
        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2
        self.lbl_calib_result.configure(text=f"Tapping ({cx}, {cy}) on emulator...", text_color=ACCENT_GOLD)
        self._quick_tap_and_refresh(cx, cy, delay=1.5)

    def _get_active_template_name(self):
        if hasattr(self, "ent_custom_btn_name") and self.ent_custom_btn_name.get().strip():
            return self.ent_custom_btn_name.get().strip().lower().replace(" ", "_")
        if hasattr(self, "var_btn_template"):
            return self.var_btn_template.get().strip()
        return "custom_button"

    def _test_current_template_match(self):
        tmpl_name = self._get_active_template_name()
        p = os.path.join("assets", "templates", f"{tmpl_name}.png")
        if not os.path.exists(p):
            if self.calib_box and self.current_frame is not None:
                x1, y1, x2, y2 = self.calib_box
                tmpl = self.current_frame[y1:y2, x1:x2]
            else:
                messagebox.showinfo("Notice", f"Template '{tmpl_name}.png' not saved yet. Please drag a box and click Save Template first!")
                return
        else:
            tmpl = cv2.imread(p)

        if tmpl is None or self.current_frame is None or tmpl.size == 0:
            return

        res = cv2.matchTemplate(self.current_frame, tmpl, cv2.TM_CCOEFF_NORMED)
        min_v, max_v, min_l, max_l = cv2.minMaxLoc(res)
        th, tw = tmpl.shape[:2]
        found_box = [max_l[0], max_l[1], max_l[0] + tw, max_l[1] + th]
        self.calib_box = found_box
        self._update_calib_crop_preview()
        self._redraw_canvas()

        status = "✅ HIGH MATCH" if max_v >= 0.75 else "⚠️ LOW MATCH"
        msg = f"{status}: Score = {max_v:.3f} at ({max_l[0] + tw//2}, {max_l[1] + th//2})"
        self.lbl_calib_result.configure(text=msg, text_color=ACCENT_GREEN if max_v >= 0.75 else ACCENT_GOLD)

    def _update_calib_crop_preview(self):
        if self.calib_box and self.current_frame is not None:
            x1, y1, x2, y2 = self.calib_box
            c_crop = self.current_frame[y1:y2, x1:x2]
            if c_crop.size > 0:
                ch, cw = c_crop.shape[:2]
                rz = cv2.resize(c_crop, (max(1, min(80, int(cw * 45 / ch))), 45), interpolation=cv2.INTER_AREA)
                rgb = cv2.cvtColor(rz, cv2.COLOR_BGR2RGB)
                self.tk_new_crop_photo = ImageTk.PhotoImage(Image.fromarray(rgb))
                self.lbl_new_crop_preview.configure(image=self.tk_new_crop_photo, text="")

    def _refresh_saved_template_preview(self):
        tmpl_name = self._get_active_template_name()
        p = os.path.join("assets", "templates", f"{tmpl_name}.png")
        if os.path.exists(p):
            t_img = cv2.imread(p)
            if t_img is not None and t_img.size > 0:
                h, w = t_img.shape[:2]
                rz = cv2.resize(t_img, (max(1, min(80, int(w * 45 / h))), 45), interpolation=cv2.INTER_AREA)
                rgb = cv2.cvtColor(rz, cv2.COLOR_BGR2RGB)
                self.tk_saved_tmpl_photo = ImageTk.PhotoImage(Image.fromarray(rgb))
                self.lbl_prev_saved_tmpl.configure(image=self.tk_saved_tmpl_photo, text="")
                return
        self.lbl_prev_saved_tmpl.configure(image=None, text="[Missing]")

    def _save_active_as_button_template(self):
        """Crops calibrated box from current frame and saves to assets/templates/{name}.png."""
        if not self.calib_box or self.current_frame is None:
            messagebox.showinfo("Notice", "Please click or drag a box over the button on the canvas first!")
            return

        x1, y1, x2, y2 = self.calib_box
        crop = self.current_frame[y1:y2, x1:x2]
        if crop.size == 0 or (x2 - x1) < 8 or (y2 - y1) < 8:
            messagebox.showwarning("Notice", "Selected box is too small. Please select a clear box over the button.")
            return

        tmpl_name = self._get_active_template_name()
        target_path = os.path.join("assets", "templates", f"{tmpl_name}.png")
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        cv2.imwrite(target_path, crop)

        # Save description/usage to Knowledge Base
        usage = self.ent_btn_usage.get().strip() if hasattr(self, "ent_btn_usage") else ""
        if usage:
            self.kb.set_definition(
                class_key=tmpl_name,
                name=tmpl_name.replace("_", " ").title(),
                description=usage,
                role="UI_BUTTON"
            )

        # Immediate live match verification
        res = cv2.matchTemplate(self.current_frame, crop, cv2.TM_CCOEFF_NORMED)
        score = cv2.minMaxLoc(res)[1]

        msg = f"✅ Button '{tmpl_name}.png' successfully saved!\nMatch score on current screen: {score:.3f}"
        self.lbl_calib_result.configure(text=f"✅ Saved '{tmpl_name}.png' (Score: {score:.3f})", text_color=ACCENT_GREEN)
        self._refresh_saved_template_preview()
        messagebox.showinfo("Button Calibrated", msg)

    # ---------------- TAB 3: ADVANCED TRAINING ----------------
    def _build_training_tab(self, tab):
        ctk.CTkLabel(tab, text="⚙️ Advanced YOLO Model Training", font=ctk.CTkFont(size=14, weight="bold"), text_color=ACCENT_GOLD).pack(anchor="w", padx=6, pady=(4, 6))

        # Hyperparameters
        opt_grid = ctk.CTkFrame(tab, fg_color="transparent")
        opt_grid.pack(fill="x", padx=6, pady=(0, 10))

        ctk.CTkLabel(opt_grid, text="Epochs:", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=0, sticky="w", pady=4)
        self.seg_epochs = ctk.CTkSegmentedButton(opt_grid, values=["15", "25", "35", "50"])
        self.seg_epochs.set("25")
        self.seg_epochs.grid(row=0, column=1, sticky="ew", padx=6, pady=4)

        ctk.CTkLabel(opt_grid, text="Batch Size:", font=ctk.CTkFont(size=12, weight="bold")).grid(row=1, column=0, sticky="w", pady=4)
        self.seg_batch = ctk.CTkSegmentedButton(opt_grid, values=["Auto", "8", "16"])
        self.seg_batch.set("Auto")
        self.seg_batch.grid(row=1, column=1, sticky="ew", padx=6, pady=4)

        ctk.CTkLabel(opt_grid, text="Resolution:", font=ctk.CTkFont(size=12, weight="bold")).grid(row=2, column=0, sticky="w", pady=4)
        self.seg_res = ctk.CTkSegmentedButton(opt_grid, values=["640", "960"])
        self.seg_res.set("640")
        self.seg_res.grid(row=2, column=1, sticky="ew", padx=6, pady=4)

        ctk.CTkLabel(opt_grid, text="Optimizer:", font=ctk.CTkFont(size=12, weight="bold")).grid(row=3, column=0, sticky="w", pady=4)
        self.opt_optimizer = ctk.CTkOptionMenu(opt_grid, values=["AdamW (Recommended)", "auto"])
        self.opt_optimizer.set("AdamW (Recommended)")
        self.opt_optimizer.grid(row=3, column=1, sticky="ew", padx=6, pady=4)

        ctk.CTkLabel(opt_grid, text="Base Model:", font=ctk.CTkFont(size=12, weight="bold")).grid(row=4, column=0, sticky="w", pady=4)
        self.opt_model = ctk.CTkOptionMenu(opt_grid, values=["yolov8n.pt (Nano, Fastest)", "yolov8s.pt (Small, High-Acc)"])
        self.opt_model.set("yolov8n.pt (Nano, Fastest)")
        self.opt_model.grid(row=4, column=1, sticky="ew", padx=6, pady=4)

        ctk.CTkLabel(opt_grid, text="Hardware:", font=ctk.CTkFont(size=12, weight="bold")).grid(row=5, column=0, sticky="w", pady=4)
        self.opt_hw = ctk.CTkOptionMenu(opt_grid, values=["Auto (GPU / CPU)", "Force CPU"])
        self.opt_hw.set("Auto (GPU / CPU)")
        self.opt_hw.grid(row=5, column=1, sticky="ew", padx=6, pady=4)

        opt_grid.grid_columnconfigure(1, weight=1)

        self.sw_aug = ctk.CTkSwitch(tab, text="Data Augmentations (Rotation, HSV Jitter, Scale)", font=ctk.CTkFont(size=12))
        self.sw_aug.select()
        self.sw_aug.pack(anchor="w", padx=6, pady=(4, 6))

        train_act_row = ctk.CTkFrame(tab, fg_color="transparent")
        train_act_row.pack(fill="x", padx=6, pady=(2, 6))

        self.btn_train_adv = ctk.CTkButton(
            train_act_row, text="🚀 Launch Fresh YOLO Training Pipeline", height=38,
            fg_color=ACCENT_BLUE, hover_color="#1d4ed8", font=ctk.CTkFont(size=13, weight="bold"),
            command=self._launch_advanced_training
        )
        self.btn_train_adv.pack(side="left", fill="x", expand=True, padx=(0, 4))

        ctk.CTkButton(
            train_act_row, text="🔍 Test AI on Image", height=38, width=140,
            fg_color=ACCENT_GREEN, hover_color="#059669", font=ctk.CTkFont(size=12, weight="bold"),
            command=self._test_trained_ai_vision
        ).pack(side="right")

        ctk.CTkLabel(tab, text="Live Training Logs:", font=ctk.CTkFont(size=12, weight="bold"), text_color=TEXT_MUTED).pack(anchor="w", padx=6)
        self.txt_train_log = ctk.CTkTextbox(tab, height=130, font=ctk.CTkFont(size=11), fg_color="#000000", text_color="#10b981")
        self.txt_train_log.pack(fill="x", padx=6, pady=(2, 6))

    # ---------------- INTERACTION MODES & WORKFLOW TAP ----------------
    def _on_canvas_mode_toggled(self, val):
        if "Button" in val:
            self.active_canvas_mode = "BUTTON_CALIBRATOR"
            self.tabs.set("🎯 Button Calibrator")
            self.lbl_mode_indicator.configure(text="[Mode: Calibrate Button]", text_color=ACCENT_BLUE)
        elif "Tap" in val:
            self.active_canvas_mode = "NAVIGATE_EMULATOR"
            self.lbl_mode_indicator.configure(text="[Mode: Tap Emulator & Navigate]", text_color=ACCENT_GREEN)
        else:
            self.active_canvas_mode = "BUILDINGS"
            self.tabs.set("🏷️ Mark Buildings")
            self.lbl_mode_indicator.configure(text="[Mode: Mark Buildings]", text_color=ACCENT_GOLD)
        self._redraw_canvas()

    def _quick_tap_and_refresh(self, x, y, delay=1.2):
        """Sends tap to emulator and refreshes screen after delay."""
        if not self.adb or not self.adb.device:
            messagebox.showwarning("Notice", "ADB emulator not connected. Make sure MEmu is running.")
            return

        def _do():
            self.adb.tap(x, y)
            time.sleep(delay)
            self.after(0, self._capture_live_screen)

        threading.Thread(target=_do, daemon=True).start()

    def _move_active_box(self, dx, dy):
        """Moves either the active building candidate box or active calib template box."""
        if self.active_canvas_mode == "BUTTON_CALIBRATOR" and self.calib_box:
            b = self.calib_box
            w = b[2] - b[0]
            h = b[3] - b[1]
            nx1 = max(0, min(1280 - w, b[0] + dx))
            ny1 = max(0, min(720 - h, b[1] + dy))
            self.calib_box = [nx1, ny1, nx1 + w, ny1 + h]
            self._update_calib_crop_preview()
            self._redraw_canvas()
        elif 0 <= self.active_idx < len(self.candidates):
            b = self.candidates[self.active_idx]["box"]
            w = b[2] - b[0]
            h = b[3] - b[1]
            nx1 = max(0, min(1280 - w, b[0] + dx))
            ny1 = max(0, min(720 - h, b[1] + dy))
            self.candidates[self.active_idx]["box"] = [nx1, ny1, nx1 + w, ny1 + h]
            self._save_yolo_labels()
            self._update_info_panel()
            self._redraw_canvas()

    def _resize_active_box(self, dw, dh):
        """Resizes the active box while preserving center."""
        if self.active_canvas_mode == "BUTTON_CALIBRATOR" and self.calib_box:
            self._nudge_box(dw=dw, dh=dh)
        elif 0 <= self.active_idx < len(self.candidates):
            b = self.candidates[self.active_idx]["box"]
            cx = (b[0] + b[2]) // 2
            cy = (b[1] + b[3]) // 2
            nw = max(16, min(1280, (b[2] - b[0]) + dw))
            nh = max(16, min(720, (b[3] - b[1]) + dh))
            self.candidates[self.active_idx]["box"] = [
                max(0, cx - nw // 2), max(0, cy - nh // 2),
                min(1280, cx + nw // 2), min(720, cy + nh // 2)
            ]
            self._save_yolo_labels()
            self._update_info_panel()
            self._redraw_canvas()

    # ---------------- CANVAS MOUSE EVENTS ----------------
    def _on_canvas_press(self, event):
        self.canvas.focus_set()
        self.drag_start = (event.x, event.y)
        self.is_moving_box = False
        self.moving_box_start_coords = None
        self.moving_start_point = (event.x, event.y)

        rx = int(event.x / self.canvas_scale_x)
        ry = int(event.y / self.canvas_scale_y)

        # Check if user clicked inside an existing box to drag & move it!
        if self.active_canvas_mode == "BUTTON_CALIBRATOR" and self.calib_box:
            cb = self.calib_box
            if cb[0] <= rx <= cb[2] and cb[1] <= ry <= cb[3]:
                self.is_moving_box = True
                self.moving_box_start_coords = list(cb)
                return

        if self.active_canvas_mode == "BUILDINGS":
            if 0 <= self.active_idx < len(self.candidates):
                ab = self.candidates[self.active_idx]["box"]
                if ab[0] <= rx <= ab[2] and ab[1] <= ry <= ab[3]:
                    self.is_moving_box = True
                    self.moving_box_start_coords = list(ab)
                    return
            for i, cand in enumerate(self.candidates):
                b = cand["box"]
                if b[0] <= rx <= b[2] and b[1] <= ry <= b[3]:
                    self.active_idx = i
                    self.is_moving_box = True
                    self.moving_box_start_coords = list(b)
                    self._update_info_panel()
                    self._redraw_canvas()
                    return

        if self.drag_rect_id:
            self.canvas.delete(self.drag_rect_id)
            self.drag_rect_id = None

    def _on_canvas_drag(self, event):
        if self.is_moving_box and self.moving_box_start_coords:
            dx = int((event.x - self.moving_start_point[0]) / self.canvas_scale_x)
            dy = int((event.y - self.moving_start_point[1]) / self.canvas_scale_y)
            orig = self.moving_box_start_coords
            w = orig[2] - orig[0]
            h = orig[3] - orig[1]
            nx1 = max(0, min(1280 - w, orig[0] + dx))
            ny1 = max(0, min(720 - h, orig[1] + dy))
            new_box = [nx1, ny1, nx1 + w, ny1 + h]

            if self.active_canvas_mode == "BUTTON_CALIBRATOR":
                self.calib_box = new_box
                self._update_calib_crop_preview()
            elif 0 <= self.active_idx < len(self.candidates):
                self.candidates[self.active_idx]["box"] = new_box
                self._update_info_panel()

            self._redraw_canvas()
            return

        if not self.drag_start:
            return
        x0, y0 = self.drag_start
        x1, y1 = event.x, event.y
        color = "#3b82f6" if self.active_canvas_mode == "BUTTON_CALIBRATOR" else "#f59e0b"
        if self.drag_rect_id:
            self.canvas.coords(self.drag_rect_id, x0, y0, x1, y1)
        else:
            self.drag_rect_id = self.canvas.create_rectangle(x0, y0, x1, y1, outline=color, width=2, dash=(4, 2))

    def _on_canvas_release(self, event):
        if self.is_moving_box:
            self.is_moving_box = False
            self.moving_box_start_coords = None
            if self.active_canvas_mode == "BUILDINGS":
                self._save_yolo_labels()
            self._redraw_canvas()
            return

        if not self.drag_start:
            return
        x0, y0 = self.drag_start
        x1, y1 = event.x, event.y
        self.drag_start = None

        if self.drag_rect_id:
            self.canvas.delete(self.drag_rect_id)
            self.drag_rect_id = None

        rx0 = int(min(x0, x1) / self.canvas_scale_x)
        ry0 = int(min(y0, y1) / self.canvas_scale_y)
        rx1 = int(max(x0, x1) / self.canvas_scale_x)
        ry1 = int(max(y0, y1) / self.canvas_scale_y)

        # 1. EMULATOR TAP MODE: Clicking sends ADB touch!
        if self.active_canvas_mode == "NAVIGATE_EMULATOR":
            if (rx1 - rx0) < 14 and (ry1 - ry0) < 14:
                self._quick_tap_and_refresh(rx0, ry0, delay=1.2)
            return

        # 2. BUTTON CALIBRATOR MODE: Box is saved for template calibration
        if self.active_canvas_mode == "BUTTON_CALIBRATOR":
            if (rx1 - rx0) >= 8 and (ry1 - ry0) >= 8:
                self.calib_box = [max(0, rx0), max(0, ry0), min(1280, rx1), min(720, ry1)]
            else:
                cx, cy = rx0, ry0
                hw, hh = 55, 23
                self.calib_box = [max(0, cx - hw), max(0, cy - hh), min(1280, cx + hw), min(720, cy + hh)]
            self._update_calib_crop_preview()
            self._redraw_canvas()
            return

        # 3. BUILDINGS MODE: Mark building or snap 74x74
        cname = getattr(self, "ent_manual_class", None)
        c_val = cname.get().strip().lower().replace(" ", "_") if cname and cname.get().strip() else "town_hall"

        if (rx1 - rx0) < 14 and (ry1 - ry0) < 14:
            click_x, click_y = rx0, ry0
            for i, c in enumerate(self.candidates):
                b = c["box"]
                if b[0] <= click_x <= b[2] and b[1] <= click_y <= b[3]:
                    self.active_idx = i
                    self._update_info_panel()
                    self._redraw_canvas()
                    return

            half = 37
            new_box = [max(0, click_x - half), max(0, click_y - half), min(1280, click_x + half), min(720, click_y + half)]
            self.candidates.append({"box": new_box, "class": c_val, "notes": ""})
            self.active_idx = len(self.candidates) - 1
            self._save_yolo_labels()
            self._update_info_panel()
            self._redraw_canvas()
            return

        if (rx1 - rx0) >= 14 and (ry1 - ry0) >= 14:
            new_box = [max(0, rx0), max(0, ry0), min(1280, rx1), min(720, ry1)]
            self.candidates.append({"box": new_box, "class": c_val, "notes": ""})
            self.active_idx = len(self.candidates) - 1
            self._save_yolo_labels()
            self._update_info_panel()
            self._redraw_canvas()

    def _redraw_canvas(self):
        if self.current_frame is None:
            return

        display_img = self.current_frame.copy()

        # Draw building labeled boxes
        for i, c in enumerate(self.candidates):
            box = c["box"]
            cname = c["class"]
            is_active = (i == self.active_idx and self.active_canvas_mode == "BUILDINGS")
            color = (0, 255, 255) if is_active else CLASS_COLORS.get(cname, (0, 200, 0))
            thickness = 3 if is_active else 2

            cv2.rectangle(display_img, (box[0], box[1]), (box[2], box[3]), color, thickness)
            lbl = f"#{i+1} {cname}"
            cv2.putText(display_img, lbl, (box[0], max(16, box[1] - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2 if is_active else 1)

        # Draw active button calibrator box if in calibrator mode
        if self.active_canvas_mode == "BUTTON_CALIBRATOR" and self.calib_box:
            cb = self.calib_box
            cv2.rectangle(display_img, (cb[0], cb[1]), (cb[2], cb[3]), (255, 120, 0), 3)
            cv2.putText(display_img, f"CALIB: {self.var_btn_template.get()}", (cb[0], max(16, cb[1] - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 120, 0), 2)

        # Draw AI inspection test overlays if any
        if hasattr(self, "ai_test_boxes") and self.ai_test_boxes:
            for det in self.ai_test_boxes:
                b = det["box"]
                cname = det["class"]
                conf = det.get("conf", 0.0)
                col = (0, 255, 0)
                cv2.rectangle(display_img, (b[0], b[1]), (b[2], b[3]), col, 2)
                cv2.putText(display_img, f"{cname} {int(conf*100)}%", (b[0], max(16, b[1] - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, col, 2)

        disp_h, disp_w = display_img.shape[:2]
        self.canvas_scale_x = self.canvas_w / disp_w
        self.canvas_scale_y = self.canvas_h / disp_h

        resized = cv2.resize(display_img, (self.canvas_w, self.canvas_h), interpolation=cv2.INTER_AREA)
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        self.tk_canvas_img = ImageTk.PhotoImage(Image.fromarray(rgb))

        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_canvas_img)

        tot = len(self.candidates)
        cur = self.active_idx + 1 if tot > 0 else 0
        self.lbl_box_pos.configure(text=f"Box: {cur} / {tot}")

    def _update_info_panel(self):
        if 0 <= self.active_idx < len(self.candidates):
            cand = self.candidates[self.active_idx]
            cname = cand["class"]
            box = cand["box"]

            defn = self.kb.get_definition(cname)
            self.lbl_active_name.configure(text=f"#{self.active_idx + 1} {defn.get('name', cname)}")

            w = box[2] - box[0]
            h = box[3] - box[1]
            cx = box[0] + w // 2
            cy = box[1] + h // 2
            self.lbl_active_pos.configure(text=f"Center: ({cx}, {cy}) | Size: {w}x{h} px")

            self.ent_notes.delete(0, "end")
            self.ent_notes.insert(0, cand.get("notes") or defn.get("description", ""))

            if self.current_frame is not None:
                pad = 8
                y1 = max(0, box[1] - pad)
                y2 = min(720, box[3] + pad)
                x1 = max(0, box[0] - pad)
                x2 = min(1280, box[2] + pad)
                crop = self.current_frame[y1:y2, x1:x2]
                if crop.size > 0:
                    crop_sq = cv2.resize(crop, (70, 70), interpolation=cv2.INTER_AREA)
                    crop_rgb = cv2.cvtColor(crop_sq, cv2.COLOR_BGR2RGB)
                    self.tk_thumb_img = ImageTk.PhotoImage(Image.fromarray(crop_rgb))
                    self.lbl_thumb.configure(image=self.tk_thumb_img, text="")
        else:
            self.lbl_active_name.configure(text="Click a building to label it")
            self.lbl_active_pos.configure(text="Center: (0, 0) | Size: 0x0 px")
            self.lbl_thumb.configure(image=None, text="[No Selection]")

    def _apply_class_to_active(self, class_name):
        if not (0 <= self.active_idx < len(self.candidates)):
            new_box = [590, 310, 690, 410]
            self.candidates.append({"box": new_box, "class": class_name, "notes": ""})
            self.active_idx = len(self.candidates) - 1

        cand = self.candidates[self.active_idx]
        cand["class"] = class_name
        cand["notes"] = self.ent_notes.get().strip() or self.kb.get_definition(class_name).get("description", "")

        defn = self.kb.get_definition(class_name)
        self.kb.set_definition(
            class_key=class_name,
            name=defn.get("name", class_name.replace("_", " ").title()),
            description=cand["notes"],
            role=defn.get("role", "CORE_TARGET")
        )

        self._save_yolo_labels()
        self._update_info_panel()
        self._redraw_canvas()

    def _save_active_notes(self):
        if 0 <= self.active_idx < len(self.candidates):
            cand = self.candidates[self.active_idx]
            cand["notes"] = self.ent_notes.get().strip()
            self._save_yolo_labels()

    def _save_yolo_labels(self):
        if not self.current_image_path:
            return

        base = os.path.splitext(os.path.basename(self.current_image_path))[0]
        os.makedirs("ai_data/labels", exist_ok=True)
        lbl_path = os.path.join("ai_data", "labels", f"{base}.txt")

        target_img = os.path.join("ai_data", "images", f"{base}.jpg")
        if not os.path.exists(target_img) and self.current_frame is not None:
            os.makedirs("ai_data/images", exist_ok=True)
            cv2.imwrite(target_img, self.current_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 95])

        lines = []
        w, h = 1280.0, 720.0
        for c in self.candidates:
            b = c["box"]
            bw = b[2] - b[0]
            bh = b[3] - b[1]
            cx = (b[0] + bw / 2.0) / w
            cy = (b[1] + bh / 2.0) / h
            nw = bw / w
            nh = bh / h
            cid = CLASS_TO_ID.get(c["class"], 0)
            lines.append(f"{cid} {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}")

        with open(lbl_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def _next_box(self):
        if self.candidates:
            self.active_idx = (self.active_idx + 1) % len(self.candidates)
            self._update_info_panel()
            self._redraw_canvas()

    def _prev_box(self):
        if self.candidates:
            self.active_idx = (self.active_idx - 1) % len(self.candidates)
            self._update_info_panel()
            self._redraw_canvas()

    def _delete_active_box(self):
        if 0 <= self.active_idx < len(self.candidates):
            self.candidates.pop(self.active_idx)
            self.active_idx = min(self.active_idx, len(self.candidates) - 1) if self.candidates else -1
            self._save_yolo_labels()
            self._update_info_panel()
            self._redraw_canvas()

    def _clear_all_boxes(self):
        if messagebox.askyesno("Confirm", "Clear all bounding boxes on this screenshot?"):
            self.candidates = []
            self.active_idx = -1
            self._save_yolo_labels()
            self._update_info_panel()
            self._redraw_canvas()

    # ---------------- ADVANCED SUBPROCESS TRAINING (UTF-8 BUG-FREE) ----------------
    def _launch_advanced_training(self):
        if self.is_training:
            messagebox.showinfo("In Progress", "Training is already in progress!")
            return

        num_imgs = len(glob.glob("ai_data/images/*.jpg")) + len(glob.glob("ai_data/images/*.png"))
        if num_imgs == 0:
            messagebox.showwarning("Empty Dataset", "Please capture and mark at least one screen first before training!")
            return

        self.is_training = True
        self.btn_train_adv.configure(state="disabled", text="⏳ Training in Progress...")
        self.txt_train_log.delete("1.0", "end")
        self.txt_train_log.insert("end", "[App] Launching Advanced YOLO Training Pipeline...\n")

        epochs = self.seg_epochs.get()
        batch_val = self.seg_batch.get()
        if batch_val == "Auto":
            batch = str(min(16, max(1, num_imgs)))
        else:
            batch = batch_val

        imgsz = self.seg_res.get()
        opt_choice = "AdamW" if "AdamW" in self.opt_optimizer.get() else "auto"
        model_choice = "yolov8n.pt" if "Nano" in self.opt_model.get() else "yolov8s.pt"
        device = "cpu" if "Force CPU" in self.opt_hw.get() else "auto"

        cmd = [
            sys.executable, "-u", "-m", "ai.trainer",
            "--epochs", epochs,
            "--batch", batch,
            "--imgsz", imgsz,
            "--model", model_choice,
            "--device", device,
            "--optimizer", opt_choice,
            "--lr0", "0.005"
        ]
        if self.sw_aug.get() == 1:
            cmd.append("--augment")

        def _worker():
            try:
                # CRITICAL: Force UTF-8 environment and decode with errors='replace' to prevent charmap errors!
                env = os.environ.copy()
                env["PYTHONIOENCODING"] = "utf-8"
                env["PYTHONLEGACYWINDOWSSTDIO"] = "utf-8"

                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True,
                    encoding="utf-8",
                    errors="replace",
                    env=env
                )
                self.training_process = proc

                for line in proc.stdout:
                    line_text = line.strip()
                    if line_text:
                        print(f"[Trainer] {line_text}")
                        self.after(0, lambda msg=line_text: self._append_train_log(msg))

                proc.wait()
                rc = proc.returncode

                def _finish():
                    self.is_training = False
                    self.btn_train_adv.configure(state="normal", text="🚀 Launch Fresh YOLO Training Pipeline")
                    if rc == 0:
                        self._append_train_log("✅ Training succeeded! Model exported to assets/models/coc_detector.onnx")
                        if self.ai_detector:
                            self.ai_detector._init_model()
                        # Auto run visual test on current frame!
                        self._test_trained_ai_vision(auto_silent=True)
                        messagebox.showinfo("Success", "Model trained successfully on your fresh dataset!\nDeployed to assets/models/coc_detector.onnx\n\nVisual detection test has been overlaid on the canvas!")
                    else:
                        self._append_train_log(f"⚠️ Training exited with code {rc}")
                        messagebox.showwarning("Notice", f"Training exited with code {rc}. Check logs above.")

                self.after(0, _finish)
            except Exception as e:
                self.after(0, lambda err=e: [
                    setattr(self, 'is_training', False),
                    self.btn_train_adv.configure(state="normal", text="🚀 Launch Fresh YOLO Training Pipeline"),
                    messagebox.showerror("Error", str(err))
                ])

        threading.Thread(target=_worker, daemon=True).start()

    def _test_trained_ai_vision(self, auto_silent=False):
        """Runs object detection using the trained model on current canvas image."""
        if self.current_frame is None:
            if not auto_silent:
                messagebox.showinfo("Notice", "No image currently loaded on canvas.")
            return

        onnx_model = "assets/models/coc_detector.onnx"
        if not os.path.exists(onnx_model):
            if not auto_silent:
                messagebox.showwarning("Notice", "No trained model found at assets/models/coc_detector.onnx. Please launch training first!")
            return

        from ai.ai_detector import AIDetector
        det_engine = AIDetector(model_path=onnx_model, conf_threshold=0.20)
        detections = det_engine.detect(self.current_frame)
        self.ai_test_boxes = detections

        # If detections found, redraw canvas with overlays
        self._redraw_canvas()

        if detections:
            classes_found = [d["class"] for d in detections]
            counts = {}
            for c in classes_found:
                counts[c] = counts.get(c, 0) + 1
            summary_str = ", ".join([f"{k}: {v}" for k, v in counts.items()])
            msg = f"🎯 AI Vision Detection Results:\nTotal Objects Found: {len(detections)}\n\nBreakdown:\n{summary_str}\n\nGreen detection overlays are now visible on the canvas!"
            if not auto_silent:
                messagebox.showinfo("AI Test Results", msg)
        else:
            if not auto_silent:
                messagebox.showinfo("AI Test Results", "No objects detected with confidence >= 0.20 on this image.")

    def _append_train_log(self, msg):
        self.txt_train_log.insert("end", msg + "\n")
        self.txt_train_log.see("end")

    # ---------------- IMAGE BROWSING ----------------
    def _load_current_image_from_list(self):
        self._refresh_image_list()
        tot = len(self.image_list)

        if not self.image_list:
            blank = np.zeros((720, 1280, 3), dtype=np.uint8)
            cv2.putText(blank, "Clean Dataset: 0 Images. Click 'Capture Live Screen'", (180, 360), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            self._set_frame(blank, "[Clean Slate]")
            self.lbl_carousel_info.configure(text="Image: 0 / 0")
            return

        self.image_index = max(0, min(self.image_index, tot - 1))
        filepath = self.image_list[self.image_index]
        self._load_file(filepath)

    def _prev_image(self):
        if self.image_list:
            self.image_index = (self.image_index - 1) % len(self.image_list)
            self._load_current_image_from_list()

    def _next_image(self):
        if self.image_list:
            self.image_index = (self.image_index + 1) % len(self.image_list)
            self._load_current_image_from_list()

    def _capture_live_screen(self):
        if not self.screen_capture:
            messagebox.showwarning("Notice", "Screen capture engine not connected. Make sure emulator is running.")
            return

        frame = self.screen_capture.get_frame(target_size=(1280, 720))
        if frame is None or frame.size == 0:
            messagebox.showwarning("Capture Notice", "Could not grab frame from emulator. Check ADB connection.")
            return

        now_ms = int(cv2.getTickCount())
        save_path = os.path.normpath(f"ai_data/images/capture_{now_ms}.jpg")
        os.makedirs("ai_data/images", exist_ok=True)
        cv2.imwrite(save_path, frame, [int(cv2.IMWRITE_JPEG_QUALITY), 95])

        self._refresh_image_list()
        if save_path in self.image_list:
            self.image_index = self.image_list.index(save_path)
        self._load_current_image_from_list()

    def _browse_image(self):
        path = filedialog.askopenfilename(filetypes=[("Image files", "*.jpg;*.jpeg;*.png")])
        if path:
            norm = os.path.normpath(path)
            dest = os.path.normpath(os.path.join("ai_data", "images", os.path.basename(norm)))
            os.makedirs("ai_data/images", exist_ok=True)
            if not os.path.exists(dest):
                import shutil
                shutil.copy(norm, dest)
            self._refresh_image_list()
            self.image_index = self.image_list.index(dest) if dest in self.image_list else 0
            self._load_current_image_from_list()

    def _load_file(self, filepath):
        frame = cv2.imread(filepath)
        if frame is not None:
            if frame.shape[:2] != (720, 1280):
                frame = cv2.resize(frame, (1280, 720), interpolation=cv2.INTER_LINEAR)
            self._set_frame(frame, filepath)
            self._load_existing_labels_for_file(filepath)

    def _set_frame(self, frame, name):
        self.current_frame = frame.copy()
        self.current_image_path = name
        tot = len(self.image_list)
        cur = self.image_index + 1 if tot > 0 else 0
        fname = os.path.basename(name)
        self.lbl_carousel_info.configure(text=f"Image {cur} / {tot}: {fname}")
        self.lbl_canvas_title.configure(text=f"Gameplay: {fname} (1280x720)")
        self._redraw_canvas()

    def _load_existing_labels_for_file(self, filepath):
        base = os.path.splitext(os.path.basename(filepath))[0]
        lbl_file = os.path.join("ai_data", "labels", f"{base}.txt")
        self.candidates = []
        if os.path.exists(lbl_file):
            h, w = 720, 1280
            with open(lbl_file, "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        try:
                            cid = int(parts[0])
                            cx, cy, bw, bh = map(float, parts[1:5])
                            x1 = int((cx - bw / 2) * w)
                            y1 = int((cy - bh / 2) * h)
                            x2 = int((cx + bw / 2) * w)
                            y2 = int((cy + bh / 2) * h)
                            cname = ID_TO_CLASS.get(cid, "town_hall")
                            self.candidates.append({
                                "box": [max(0, x1), max(0, y1), min(w, x2), min(h, y2)],
                                "class": cname,
                                "notes": self.kb.get_definition(cname).get("description", "")
                            })
                        except Exception:
                            pass

        self.active_idx = 0 if self.candidates else -1
        self._update_info_panel()
        self._redraw_canvas()

    def _reset_entire_dataset(self):
        if messagebox.askyesno("Confirm Reset", "Are you sure you want to delete ALL images and labels in ai_data to start 100% fresh?"):
            for f in glob.glob("ai_data/images/*"):
                try:
                    os.remove(f)
                except Exception:
                    pass
            for f in glob.glob("ai_data/labels/*"):
                try:
                    os.remove(f)
                except Exception:
                    pass
            self.candidates = []
            self.active_idx = -1
            self._load_current_image_from_list()
            messagebox.showinfo("Reset Complete", "Dataset wiped clean. You can now capture fresh screens and mark them!")


if __name__ == "__main__":
    app = ctk.CTk()
    app.withdraw()
    studio = InteractiveTeacherStudio(parent=app)
    studio.protocol("WM_DELETE_WINDOW", lambda: sys.exit(0))
    app.mainloop()
