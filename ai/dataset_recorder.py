"""
High-Performance Gameplay Dataset Recorder & Auto-Annotator.
Captures frames and ADB touch events during farming sessions and generates
YOLO-compliant datasets (images + normalized labels) for model training.
"""

import os
import time
import json
import cv2
from ai.constants import CLASS_TO_ID


class DatasetRecorder:
    def __init__(self, data_dir="ai_data", max_samples=5000, screen_capture=None):
        self.data_dir = data_dir
        self.max_samples = max_samples
        self.capture = screen_capture
        self.is_recording = False
        self.sample_count = 0
        self.last_capture_time = 0
        self.min_interval = 0.5  # Max 2 FPS
        self.record_thread = None

        self.img_dir = os.path.join(self.data_dir, "images")
        self.lbl_dir = os.path.join(self.data_dir, "labels")
        self.events_file = os.path.join(self.data_dir, "events.jsonl")

        self._ensure_dirs()
        self._sync_sample_count()

    def _ensure_dirs(self):
        os.makedirs(self.img_dir, exist_ok=True)
        os.makedirs(self.lbl_dir, exist_ok=True)

    def _sync_sample_count(self):
        if os.path.exists(self.img_dir):
            existing = [f for f in os.listdir(self.img_dir) if f.lower().endswith((".jpg", ".png"))]
            self.sample_count = len(existing)

    def start_recording(self, screen_capture=None):
        if screen_capture:
            self.capture = screen_capture
        self.is_recording = True
        self._ensure_dirs()
        self._sync_sample_count()
        print(f"[DatasetRecorder] Recording STARTED. Data directory: {self.data_dir} (Existing samples: {self.sample_count})")
        
        # Start background streaming capture if capture object is provided
        if self.capture and (self.record_thread is None or not self.record_thread.is_alive()):
            import threading
            self.record_thread = threading.Thread(target=self._stream_capture_loop, daemon=True)
            self.record_thread.start()

    def _stream_capture_loop(self):
        """Continuously captures frames at ~1 FPS when manual recording is active."""
        while self.is_recording:
            try:
                if self.capture:
                    frame = self.capture.get_frame(target_size=(1280, 720))
                    if frame is not None and frame.size > 0:
                        self.record_sample(frame, action_type="stream_frame", state_name="RECORDING", auto_annotate=True)
            except Exception:
                pass
            time.sleep(1.0)

    def stop_recording(self):
        self.is_recording = False
        self._sync_sample_count()
        print(f"[DatasetRecorder] Recording STOPPED. Total samples collected: {self.sample_count}")

    def seed_from_existing_frames(self, root_dir="."):
        """
        Scans root directory for existing Clash of Clans 1280x720 screenshots and
        auto-annotates them to bootstrap a ready-to-train dataset immediately.
        """
        import glob
        seeded = 0
        self._ensure_dirs()
        patterns = ["*.png", "assets/*.png"]
        for pat in patterns:
            for f in glob.glob(os.path.join(root_dir, pat)):
                try:
                    img = cv2.imread(f)
                    if img is not None and img.shape == (720, 1280, 3):
                        fname_base = f"seed_{os.path.splitext(os.path.basename(f))[0]}"
                        target_jpg = os.path.join(self.img_dir, f"{fname_base}.jpg")
                        target_lbl = os.path.join(self.lbl_dir, f"{fname_base}.txt")
                        if not os.path.exists(target_jpg):
                            cv2.imwrite(target_jpg, img, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
                            self._generate_yolo_labels(img, target_lbl, action_type="seed", coords=None)
                            seeded += 1
                except Exception:
                    pass
        self._sync_sample_count()
        print(f"[DatasetRecorder] Auto-seeded {seeded} screenshots from project. Total dataset size: {self.sample_count} images.")
        return self.sample_count

    def record_sample(self, frame, action_type=None, coords=None, state_name="UNKNOWN", auto_annotate=True):
        """
        Saves a frame and associated metadata.
        If auto_annotate is True, automatically generates a YOLO label file.
        """
        if not self.is_recording or frame is None or frame.size == 0:
            return

        now = time.time()
        if now - self.last_capture_time < self.min_interval:
            return

        if self.sample_count >= self.max_samples:
            self.stop_recording()
            return

        self.last_capture_time = now
        timestamp_ms = int(now * 1000)
        filename_base = f"coc_{timestamp_ms}_{self.sample_count:05d}"
        img_path = os.path.join(self.img_dir, f"{filename_base}.jpg")
        lbl_path = os.path.join(self.lbl_dir, f"{filename_base}.txt")

        # 1. Save compressed JPEG image
        cv2.imwrite(img_path, frame, [int(cv2.IMWRITE_JPEG_QUALITY), 92])

        # 2. Log Action Event to JSONL
        event_data = {
            "timestamp": now,
            "filename": f"{filename_base}.jpg",
            "state": state_name,
            "action": action_type,
            "coords": coords
        }
        with open(self.events_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event_data) + "\n")

        # 3. Automatic YOLO Annotation Generation
        if auto_annotate:
            self._generate_yolo_labels(frame, lbl_path, action_type, coords)

        self.sample_count += 1
        if self.sample_count % 25 == 0:
            print(f"[DatasetRecorder] Collected {self.sample_count} training samples...")

    def _generate_yolo_labels(self, frame, lbl_path, action_type, coords):
        """
        Auto-generates YOLO-format annotations (class_id, x_center, y_center, width, height)
        normalized between 0.0 and 1.0.
        """
        h, w = frame.shape[:2]
        annotations = []

        # 1. Detect red deployment boundary
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask1 = cv2.inRange(hsv, (0, 130, 120), (8, 255, 255))
        mask2 = cv2.inRange(hsv, (172, 130, 120), (180, 255, 255))
        red_mask = cv2.bitwise_or(mask1, mask2)
        red_mask[580:, :] = 0
        red_mask[:120, :] = 0

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        red_cleaned = cv2.morphologyEx(red_mask, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(red_cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for c in contours:
            if cv2.contourArea(c) > 180:
                bx, by, bw, bh = cv2.boundingRect(c)
                if 120 <= by <= 580 and 100 <= bx <= 1180:
                    cx = (bx + bw / 2) / w
                    cy = (by + bh / 2) / h
                    nw = bw / w
                    nh = bh / h
                    cid = CLASS_TO_ID.get("red_boundary", 14)
                    annotations.append(f"{cid} {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}")

        # 2. Add Town Hall core approximation if in battlefield
        core_box = [580, 290, 700, 410]
        th_cx = (core_box[0] + 60) / w
        th_cy = (core_box[1] + 60) / h
        th_w = 120 / w
        th_h = 120 / h
        cid_th = CLASS_TO_ID.get("town_hall", 0)
        annotations.append(f"{cid_th} {th_cx:.6f} {th_cy:.6f} {th_w:.6f} {th_h:.6f}")

        # Write labels to file
        with open(lbl_path, "w", encoding="utf-8") as f:
            f.write("\n".join(annotations))
