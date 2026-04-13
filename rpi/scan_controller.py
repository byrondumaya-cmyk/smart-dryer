# scan_controller.py — Core Scanning Brain (Local-First)

import time
import threading
import logging
import datetime
import os
import cv2

from config import TOTAL_SLOTS
from ai.classifier        import classify
from modules.motor        import motor
from modules.buzzer       import buzzer
from modules.relay        import relay
from modules.sms          import sms
from modules.sensor       import sensor
import state_store

logger = logging.getLogger(__name__)

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
        
    def _safe_float(self, val, default=0.0):
        try:
            return float(val)
        except (TypeError, ValueError):
            return default

    # ── Single slot scan ──────────────────────────────────────────────────────
    def _scan_slot(self, slot: int, global_camera) -> dict | None:
        self._log_event(f"Scanning slot {slot}...", "INFO")
        self._current_slot = slot
        self._state["system_status"] = "scanning"
        buzzer.play("moving_to_slot")

        if not motor.move_to_slot(slot):
            self._log_event(f"Motor failed to reach slot {slot}", "ERROR")
            buzzer.play("generic_error")
            return None

        buzzer.play("slot_reached")
        dwell_time = self._state.get("dwell_time", 5)
        buzzer.play("slot_scan_started")
        time.sleep(dwell_time)  # Wait for DHT and frame to stabilize

        # 1. Capture Image -> Convert to Continuous Score
        frame = global_camera.read_latest() if global_camera else None
        snapshot_url = None
        result = {"label": "UNKNOWN", "confidence": 0.0}
        
        if frame is not None:
            # multiple frame captures could be added here if needed, but 1 latest frame is usually safe
            path = os.path.join(SNAP_DIR, f"slot_{slot}.jpg")
            cv2.imwrite(path, frame)
            snapshot_url = f"/snapshots/slot_{slot}.jpg"
            result = classify(frame)
            
        label_img = result['label']
        conf_img = self._safe_float(result['confidence'])

        # Explicit Image Score Conversion
        image_dry_score = 0.5
        if label_img == "DRY":
            image_dry_score = conf_img
        elif label_img == "WET":
            image_dry_score = 1.0 - conf_img
        elif label_img == "EMPTY":
            image_dry_score = None # Neutral state, do not leak float scores

        # 2. Read Sensor -> Convert to Continuous Score w/ Hysteresis
        sensor_data = sensor.read_slot(slot)
        hum = sensor_data.get('humidity') if sensor_data else None
        temp = sensor_data.get('temperature') if sensor_data else None

        calib = self._state.get("calibration", {}).get(str(slot), {})
        if hum is not None: 
            hum = round(hum + calib.get("h_offset", 0.0), 1)
            sensor_data['humidity'] = hum
        if temp is not None: 
            temp = round(temp + calib.get("t_offset", 0.0), 1)
            sensor_data['temperature'] = temp
        
        wet_thresh = self._safe_float(self._state.get("thresholds", {}).get("wet", 80.0))
        dry_thresh = self._safe_float(self._state.get("thresholds", {}).get("dry", 75.0))
        stable_state = self._state["slots"][str(slot)].get("stable_state", "UNKNOWN")
        
        sensor_dry_score = 0.5
        if hum is None:
            label_sensor = "UNKNOWN"
        else:
            hum = self._safe_float(hum)
            if hum >= wet_thresh:
                stable_state = "WET"
                sensor_dry_score = 0.0
            elif hum <= dry_thresh:
                stable_state = "DRY"
                sensor_dry_score = 1.0
            else:
                # Interpolate if in between thresholds
                calc = (wet_thresh - hum) / max((wet_thresh - dry_thresh), 0.001)
                sensor_dry_score = max(0.0, min(1.0, calc))
            label_sensor = stable_state

        self._state["slots"][str(slot)]["stable_state"] = stable_state

        # 3. Final Fusion Math (Weighted Average)
        w_sens = self._safe_float(self._state.get("weights", {}).get("sensor", 0.6))
        w_img  = self._safe_float(self._state.get("weights", {}).get("image", 0.4))
        
        # Isolate missing metrics for true degradation without score dilution
        if label_img == "UNKNOWN":
            w_img = 0.0
            w_sens = 1.0
        
        if hum is None:
            w_sens = 0.0
            w_img = 1.0

        # Normalization
        tot_w = w_sens + w_img
        if tot_w <= 0:
            w_sens, w_img = 0.5, 0.5
        else:
            w_sens /= tot_w
            w_img /= tot_w

        final_label = "UNKNOWN"
        final_score = 0.5
        
        if label_img == "EMPTY":
            final_label = "EMPTY"
            final_score = None
        elif hum is None and label_img == "UNKNOWN":
            final_label = "UNKNOWN"
            final_score = None
        else:
            # Safely fallback to 0.5 if image_dry_score is somehow None but we shouldn't have hit this
            ids = image_dry_score if image_dry_score is not None else 0.5
            final_score = (sensor_dry_score * w_sens) + (ids * w_img)
            final_label = "DRY" if final_score >= 0.50 else "WET"

        msg_f = f"{final_score:.2f}" if final_score is not None else "N/A"
        msg_i = f"{image_dry_score:.2f}" if image_dry_score is not None else "N/A"
        msg = f"Slot {slot}: {final_label} ({msg_f}) | Sens({label_sensor}):{sensor_dry_score:.2f} Img({label_img}):{msg_i}"
        self._log_event(msg, "INFO")
        buzzer.play("slot_scan_complete")

        return {
            "label": final_label,
            "final_score": final_score,
            "sensor_score": sensor_dry_score,
            "image_score": image_dry_score,
            "snapshot_url": snapshot_url,
            "sensor_hum": hum,
            "sensor_temp": temp,
            "breakdown": {"image_label": label_img, "sensor_label": label_sensor}
        }

    # ── Full scan cycle ───────────────────────────────────────────────────────
    def _run_cycle(self, global_camera):
        self._log_event("Starting explicit scan cycle...", 'INFO')
        buzzer.play("cycle_started")
        self._state["system_status"] = "scanning"
        sms.reset_sent_flag()
        state_store.save(self._state)

        self._log_event("Homing carriage before cycle...", "INFO")
        if not motor.home():
            self._log_event("Homing failed! Aborting cycle.", "ERROR")
            return

        cycle_results = {}

        for slot in range(1, TOTAL_SLOTS + 1):
            if self._stop_event.is_set():
                self._log_event("Scan aborted by user.", "WARN")
                break

            result = self._scan_slot(slot, global_camera)
            ts = datetime.datetime.now().isoformat()

            if result:
                slot_data = {
                    "label":        result["label"],
                    "confidence":   round(result.get("final_score"), 4) if result.get("final_score") is not None else None,
                    "sensor_score": round(result.get("sensor_score"), 4) if result.get("sensor_score") is not None else None,
                    "image_score":  round(result.get("image_score"), 4) if result.get("image_score") is not None else None,
                    "last_scanned": ts,
                    "snapshot_url": result.get("snapshot_url"),
                    "sensor_hum":   result.get("sensor_hum"),
                    "sensor_temp":  result.get("sensor_temp"),
                    "stable_state": self._state["slots"][str(slot)].get("stable_state"),
                    "breakdown":    result.get("breakdown")
                }
                self._state["slots"][str(slot)] = slot_data
                cycle_results[slot] = result["label"]
            else:
                self._state["slots"][str(slot)]["last_scanned"] = ts
                cycle_results[slot] = self._state["slots"][str(slot)].get("label", "UNKNOWN")

            state_store.save(self._state)

        # MANDATORY END OF CYCLE HOMING
        self._log_event("Cycle complete. Returning home...", "INFO")
        motor.home()
        self._current_slot = None
        buzzer.play("cycle_complete")

        # ── Post-cycle evaluations ────────────────────────────────────────
        # A cycle is only ALL DRY if every slot is either DRY or EMPTY (and >= 1 valid slot exists)
        # UNKNOWN defaults to holding back the cycle. WET immediately holds it back.
        wet_count     = sum(1 for v in cycle_results.values() if v == "WET")
        unknown_count = sum(1 for v in cycle_results.values() if v == "UNKNOWN")
        dry_count     = sum(1 for v in cycle_results.values() if v == "DRY")
        empty_count   = sum(1 for v in cycle_results.values() if v == "EMPTY")
        
        all_dry = (wet_count == 0 and unknown_count == 0) and (dry_count + empty_count > 0)
        self._state["last_cycle_at"] = datetime.datetime.now().isoformat()

        # Terminal count logic
        self._log_event(f"Cycle result -> DRY:{dry_count} WET:{wet_count} EMPTY:{empty_count} UNKNOWN:{unknown_count}", "INFO")

        if all_dry:
            buzzer.play("all_dry")
        else:
            buzzer.play("not_all_dry")

        # SMS
        sms_every = self._state.get("toggles", {}).get("sms_cycle", False)
        if (all_dry and not self._state.get("all_dry_notified")) or sms_every:
            self._log_event("Triggering Semaphore SMS out.", 'SUCCESS')
            sent = sms.send_drying_complete()
            if sent:
                buzzer.play("sms_sent")
                self._log_event(f"SMS Alert sent to {self._state.get('sms_recipient','')}", 'SUCCESS')
            else:
                buzzer.play("sms_failed")
                self._log_event("SMS Delivery Failed.", 'ERROR')
            self._state["all_dry_notified"] = sent if all_dry else self._state.get("all_dry_notified")
        elif not all_dry:
            self._state["all_dry_notified"] = False

        self._state["system_status"] = "idle"
        state_store.save(self._state)

        # UV Sterilization logic
        uv_auto = self._state.get("toggles", {}).get("uv_auto", False)
        if all_dry and uv_auto:
            self._log_event("Clothes DRY & UV Auto ON. Activating Relay.", "SUCCESS")
            relay.on()
            buzzer.play("uv_on")
            self._state["uv_on"] = True
            
            # UV Auto-off Thread Dispatcher
            timeout_mins = self._state.get("uv_auto_off_minutes", 15)
            def safe_off():
                time.sleep(timeout_mins * 60)
                if self._state["uv_on"] and not self._running:
                    relay.off()
                    self._state["uv_on"] = False
                    buzzer.play("uv_off")
                    self._log_event(f"UV Auto-OFF triggered after {timeout_mins}m.", "INFO")
                    state_store.save(self._state)
            threading.Thread(target=safe_off, daemon=True).start()
            
        else:
            relay.off()
            if self._state["uv_on"]:
                buzzer.play("uv_off")
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
                buzzer.play("generic_error")
                self._state["system_status"] = "error"
                state_store.save(self._state)

            if self._stop_event.is_set():
                break

            interval = self._state.get("scan_interval", 300)
            msg = f"Idle sleep. Scheduled next cycle in {interval}s."
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
        self._log_event("Scan loop stopped.", "WARN")

    # ── Public control ────────────────────────────────────────────────────────
    def start(self, global_camera=None) -> bool:
        if self._running:
            return False
        
        # Clear previous results so UI fallback to live DHT works
        for slot in range(1, TOTAL_SLOTS + 1):
            if str(slot) in self._state["slots"]:
                self._state["slots"][str(slot)].update({
                    "label": "UNKNOWN",
                    "confidence": None,
                    "sensor_score": None,
                    "image_score": None,
                    "snapshot_url": None,
                    "sensor_hum": None,
                    "sensor_temp": None
                })
        state_store.save(self._state)

        self._stop_event.clear()
        self._running = True
        self._state["running"] = True
        buzzer.play("system_started")
        self._thread  = threading.Thread(
            target=self._loop, args=(global_camera,), daemon=True, name="scan-loop"
        )
        self._thread.start()
        self._log_event("Scan controller initiated.", "INFO")
        return True

    def stop(self) -> bool:
        if not self._running:
            return False
        self._log_event("Aborting scan loop...", "WARN")
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
