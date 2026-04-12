# scan_controller.py — Core Scanning Brain (Local-First)
#
# Full scan loop:
#   1. UV relay OFF  (safe to scan)
#   2. Iterate slots 1→5: move motor → wait dwell time → capture → read sensor → classify
#      → Save JPEG snapshot locally
#   3. Return motor home
#   4. Post-cycle: evaluate all-dry -> UV / SMS
#   5. Wait scan interval
#   6. Repeat

import time
import threading
import logging
import datetime
import os
import cv2

from config import TOTAL_SLOTS, MIN_SCAN_INTERVAL_SECONDS, MAX_SCAN_INTERVAL_SECONDS
from ai.classifier        import classify
from modules.motor        import motor
from modules.buzzer       import buzzer
from modules.relay        import relay
from modules.sms          import sms
from modules.sensor       import sensor
import state_store

logger = logging.getLogger(__name__)

# Directory for local snapshots
SNAP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "smart-dryer-web", "snapshots")
os.makedirs(SNAP_DIR, exist_ok=True)

class ScanController:
    def __init__(self):
        self._state        = state_store.load()
        self._running      = False
        self._stop_event   = threading.Event()
        self._thread       = None
        self._current_slot = None
        self.system_logs   = []

        # Restore persisted calibration
        saved_segments = self._state.get("motor_segments", {})
        for seg, ms in saved_segments.items():
            motor.set_segment(seg, int(ms))

        # Restore SMS recipient
        if self._state.get("sms_recipient"):
            sms.set_recipient(self._state["sms_recipient"])

    def _log_event(self, msg: str, level: str = 'INFO'):
        ts = datetime.datetime.now().isoformat()
        self.system_logs.insert(0, {'created_at': ts, 'message': msg, 'level': level})
        if len(self.system_logs) > 30:
            self.system_logs.pop()
        logger.info(f"[{level}] {msg}")

    # ── Single slot scan ──────────────────────────────────────────────────────
    def _scan_slot(self, slot: int, global_camera) -> dict | None:
        self._log_event(f"Scanning slot {slot}", "INFO")
        self._current_slot = slot
        self._state["system_status"] = "scanning"

        if not motor.move_to_slot(slot):
            self._log_event(f"Motor failed to reach slot {slot}", "ERROR")
            buzzer.error()
            return None

        dwell_time = self._state.get("dwell_time", 5)
        time.sleep(dwell_time)  # Stabilize before reading

        # Capture Image
        frame = global_camera.read_latest() if global_camera else None
        snapshot_url = None
        label_img = "UNKNOWN"
        conf_img = 0.0

        if frame is not None:
            # Save local snapshot
            path = os.path.join(SNAP_DIR, f"slot_{slot}.jpg")
            cv2.imwrite(path, frame)
            snapshot_url = f"/snapshots/slot_{slot}.jpg"
            
            result = classify(frame)
            label_img = result['label']
            conf_img = result['confidence']

        # Read Sensor
        sensor_data = sensor.read(slot)
        hum = sensor_data.get('humidity') if sensor_data else None
        
        # Hysteresis Logic
        prev_label = self._state["slots"][str(slot)].get("label", "UNKNOWN")
        wet_thresh = self._state.get("thresholds", {}).get("wet", 80)
        dry_thresh = self._state.get("thresholds", {}).get("dry", 75)
        
        label_sensor = "UNKNOWN"
        if hum is not None:
            if hum >= wet_thresh:
                label_sensor = "WET"
            elif hum <= dry_thresh:
                label_sensor = "DRY"
            else:
                label_sensor = "WET" if prev_label == "WET" else "DRY"

        # Fusion Logic
        w_sens = self._state.get("weights", {}).get("sensor", 0.6)
        w_img  = self._state.get("weights", {}).get("image", 0.4)

        score_sens = 1.0 if label_sensor == "WET" else 0.0
        score_img  = 1.0 if label_img == "WET" else 0.0

        final_score = (score_sens * w_sens) + (score_img * w_img)
        final_label = "WET" if final_score > 0.5 else "DRY"

        msg = f"Slot {slot}: Score {final_score:.2f} ({final_label}) | Img:{label_img} Sens:{label_sensor} Hum:{hum}%"
        self._log_event(msg, "INFO")

        return {
            "label": final_label,
            "confidence": max(final_score, 1 - final_score), # Pseudo-confidence
            "snapshot_url": snapshot_url,
            "sensor_hum": hum,
            "sensor_temp": sensor_data.get('temperature') if sensor_data else None,
            "breakdown": {"image_label": label_img, "sensor_label": label_sensor}
        }

    # ── Full scan cycle ───────────────────────────────────────────────────────
    def _run_cycle(self, global_camera):
        self._log_event("Starting scan cycle...", 'INFO')
        self._state["system_status"] = "scanning"
        sms.reset_sent_flag()
        state_store.save(self._state)

        cycle_results = {}

        for slot in range(1, TOTAL_SLOTS + 1):
            if self._stop_event.is_set():
                self._log_event("Scan aborted mid-cycle.", "WARN")
                break

            result = self._scan_slot(slot, global_camera)
            ts = datetime.datetime.now().isoformat()

            if result:
                slot_data = {
                    "label":        result["label"],
                    "confidence":   round(result["confidence"], 4),
                    "last_scanned": ts,
                    "snapshot_url": result.get("snapshot_url"),
                    "sensor_hum":   result.get("sensor_hum"),
                    "sensor_temp":  result.get("sensor_temp"),
                    "breakdown":    result.get("breakdown")
                }
                self._state["slots"][str(slot)] = slot_data
                cycle_results[slot] = result["label"]
            else:
                self._state["slots"][str(slot)]["last_scanned"] = ts
                cycle_results[slot] = self._state["slots"][str(slot)].get("label")

            state_store.save(self._state)

        # Implicit homing at end of cycle for repeatable accuracy
        motor.home()
        self._current_slot = None

        # ── Post-cycle checks ─────────────────────────────────────────────
        all_dry = all(v == "DRY" for v in cycle_results.values() if v)
        self._state["last_cycle_at"] = datetime.datetime.now().isoformat()

        # SMS Logic
        sms_every = self._state.get("toggles", {}).get("sms_cycle", False)
        if (all_dry and not self._state.get("all_dry_notified")) or sms_every:
            self._log_event("Triggering SMS notifications.", 'SUCCESS')
            if all_dry:
                buzzer.drying_complete()
            sent = sms.send_drying_complete()
            if sent:
                self._log_event(f"SMS Alert sent to {self._state.get('sms_recipient','')}", 'SUCCESS')
            self._state["all_dry_notified"] = sent if all_dry else self._state.get("all_dry_notified")
        elif not all_dry:
            self._state["all_dry_notified"] = False

        self._state["system_status"] = "idle"
        state_store.save(self._state)
        self._log_event("Scan cycle complete.", "INFO")

        # UV Logic
        uv_auto = self._state.get("toggles", {}).get("uv_auto", False)
        if all_dry and uv_auto:
            self._log_event("Clothes DRY and UV Auto enabled. Activating UV.", "SUCCESS")
            relay.on()
            self._state["uv_on"] = True
        else:
            relay.off()
            self._state["uv_on"] = False

    # ── Main loop ─────────────────────────────────────────────────────────────
    def _loop(self, global_camera):
        while not self._stop_event.is_set():
            relay.off()
            self._state["uv_on"] = False

            try:
                self._run_cycle(global_camera)
            except Exception as e:
                logger.exception(f"Scan cycle crashed: {e}")
                self._log_event(f"System error: {e}", 'ERROR')
                buzzer.error()
                self._state["system_status"] = "error"
                state_store.save(self._state)

            if self._stop_event.is_set():
                break

            interval = self._state.get("scan_interval", 300)
            msg = f"Idle wait. Next scan in {interval}s."
            self._log_event(msg, "INFO")

            waited = 0
            while waited < interval and not self._stop_event.is_set():
                time.sleep(1)
                waited += 1

        relay.off()
        self._state["uv_on"] = False
        self._state["running"] = False
        self._state["system_status"] = "idle"
        state_store.save(self._state)
        self._log_event("Scan loop stopped.", "INFO")

    # ── Public control ────────────────────────────────────────────────────────
    def start(self, global_camera=None) -> bool:
        if self._running:
            return False
        self._stop_event.clear()
        self._running = True
        self._state["running"] = True
        self._thread  = threading.Thread(
            target=self._loop, args=(global_camera,), daemon=True, name="scan-loop"
        )
        self._thread.start()
        self._log_event("Scan controller started.", "INFO")
        return True

    def stop(self) -> bool:
        if not self._running:
            return False
        self._log_event("Stopping scan controller...", "WARN")
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)
        self._running = False
        self._state["running"] = False
        relay.off()
        self._state["uv_on"] = False
        return True

    def get_status(self) -> dict:
        self._state = state_store.load()
        return {
            "running":          self._running,
            "system_status":    self._state.get("system_status", "idle"),
            "current_slot":     self._current_slot,
            "scan_interval":    self._state.get("scan_interval"),
            "last_cycle_at":    self._state.get("last_cycle_at"),
            "all_dry_notified": self._state.get("all_dry_notified"),
            "sms_recipient":    self._state.get("sms_recipient", ""),
            "calibration":      motor.get_segments(),
            "logs":             self.system_logs,
            "state_data":       self._state
        }

# Singleton
scanner = ScanController()
