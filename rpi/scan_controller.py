# scan_controller.py — Core Scanning Brain
#
# Full scan loop:
#   1. UV relay OFF  (safe to scan)
#   2. Iterate slots 1→5: move motor → capture → classify → store result
#      → Upload JPEG snapshot to Firebase Storage after each slot
#      → Push slot result to Firestore after each slot
#   3. Return motor home
#   4. Post-cycle: all-dry check → SMS + buzzer
#      → Push scan history to Firestore
#   5. UV relay ON  (sterilization during idle interval)
#   6. Wait scan interval
#   7. Repeat
#
# Dashboard commands (via Firestore) are handled in _handle_command().

import time
import threading
import logging
import datetime

import cv2

from config import TOTAL_SLOTS, MIN_SCAN_INTERVAL_SECONDS, MAX_SCAN_INTERVAL_SECONDS
from ai.classifier        import classify
from modules.motor        import motor
from modules.buzzer       import buzzer
from modules.relay        import relay
from modules.sms          import sms
from modules.firestore_sync import (
    push_status, push_slots, push_scan_history,
    upload_snapshot, start_command_listener, push_log
)
import state_store

logger = logging.getLogger(__name__)


class ScanController:
    def __init__(self):
        self._state        = state_store.load()
        self._running      = False
        self._stop_event   = threading.Event()
        self._thread       = None
        self._camera       = None
        self._current_slot = None

        # Restore persisted calibration
        saved_steps = self._state.get("slot_steps", {})
        for slot_str, steps in saved_steps.items():
            motor.set_slot_steps(int(slot_str), int(steps))

        # Restore SMS recipient
        if self._state.get("sms_recipient"):
            sms.set_recipient(self._state["sms_recipient"])

    # ── Camera ────────────────────────────────────────────────────────────────
    def _open_camera(self) -> bool:
        if self._camera and self._camera.isOpened():
            return True
        self._camera = cv2.VideoCapture(0)
        if not self._camera.isOpened():
            logger.error("Cannot open camera.")
            return False
        logger.info("Camera opened.")
        return True

    def _capture_frame(self):
        if not self._open_camera():
            return None
        for _ in range(3):   # Discard stale frames
            self._camera.read()
        ret, frame = self._camera.read()
        if not ret:
            logger.error("Frame capture failed.")
            return None
        return frame

    def _release_camera(self):
        if self._camera:
            self._camera.release()
            self._camera = None

    # ── Single slot scan ──────────────────────────────────────────────────────
    def _scan_slot(self, slot: int) -> dict | None:
        logger.info(f"── Scanning slot {slot} ──")
        self._current_slot = slot

        # Notify Firestore: currently scanning this slot
        push_status({'current_slot': slot, 'system_status': 'scanning', 'running': True})

        if not motor.move_to_slot(slot):
            logger.error(f"Motor failed to reach slot {slot}")
            buzzer.error()
            push_status({'buzzer_last': 'error'})
            return None

        time.sleep(0.5)   # Settle after motor stops

        frame = self._capture_frame()
        if frame is None:
            return None

        result = classify(frame)
        msg = f"Slot {slot}: {result['label']} ({result['confidence']:.1%})"
        if result.get("simulated"): msg += " [SIM]"
        logger.info(msg)
        push_log(msg)

        # Upload snapshot to Firebase Storage
        snapshot_url = upload_snapshot(slot, frame) if frame is not None else None

        result['snapshot_url'] = snapshot_url
        return result

    # ── Full scan cycle ───────────────────────────────────────────────────────
    def _run_cycle(self):
        logger.info("═══ Starting scan cycle ═══")
        push_log("Starting scan cycle...", 'INFO')
        self._state["system_status"] = "scanning"
        sms.reset_sent_flag()
        state_store.save(self._state)

        cycle_results = {}

        for slot in range(1, TOTAL_SLOTS + 1):
            if self._stop_event.is_set():
                logger.info("Scan aborted mid-cycle.")
                break

            result = self._scan_slot(slot)
            ts     = datetime.datetime.now().isoformat()

            if result:
                slot_data = {
                    "label":        result["label"],
                    "confidence":   round(result["confidence"], 4),
                    "simulated":    result.get("simulated", False),
                    "last_scanned": ts,
                    "snapshot_url": result.get("snapshot_url"),
                }
                self._state["slots"][str(slot)] = slot_data
                cycle_results[slot] = result["label"]
            else:
                # Keep last known state on read error
                self._state["slots"][str(slot)]["last_scanned"] = ts
                cycle_results[slot] = (
                    self._state["slots"][str(slot)].get("label")
                )

            state_store.save(self._state)
            # Push updated slot data to Firestore
            push_slots({str(k): v for k, v in self._state["slots"].items()})

        motor.home()
        self._release_camera()
        self._current_slot = None

        # ── Post-cycle checks ─────────────────────────────────────────────
        all_dry = all(v == "DRY" for v in cycle_results.values() if v)
        self._state["last_cycle_at"] = datetime.datetime.now().isoformat()

        if all_dry and not self._state.get("all_dry_notified"):
            logger.info("All slots DRY — notifying.")
            push_log("All slots are DRY. Firing notifications.", 'SUCCESS')
            buzzer.drying_complete()
            push_status({'buzzer_last': 'drying_complete'})
            sent = sms.send_drying_complete()
            if sent:
                push_log(f"SMS Alert sent to {self._state.get('sms_recipient','')}", 'SUCCESS')
            self._state["all_dry_notified"] = sent
        elif not all_dry:
            self._state["all_dry_notified"] = False

        self._state["system_status"] = "idle"
        state_store.save(self._state)

        # Push final status + scan history to Firestore
        push_status({
            'running': True,
            'system_status': 'idle',
            'current_slot': None,
            'last_cycle_at': self._state['last_cycle_at'],
            'all_dry_notified': self._state.get('all_dry_notified', False),
            'uv_on': False,
        })

        from modules.sensor import sensor
        sensor_snapshot = {
            str(k): {
                'temperature': v.get('temperature'),
                'humidity':    v.get('humidity'),
            }
            for k, v in sensor.read_all().items()
        }
        push_scan_history(
            slots_result={str(k): {'label': v} for k, v in cycle_results.items()},
            all_dry=all_dry,
            sensor_snapshot=sensor_snapshot,
        )
        logger.info("═══ Scan cycle complete ═══")

    # ── Main loop ─────────────────────────────────────────────────────────────
    def _loop(self):
        while not self._stop_event.is_set():
            # UV OFF during scan
            relay.off()

            try:
                self._run_cycle()
            except Exception as e:
                logger.exception(f"Scan cycle crashed: {e}")
                push_log(f"System error: {e}", 'ERROR')
                buzzer.error()
                self._state["system_status"] = "error"
                state_store.save(self._state)

            if self._stop_event.is_set():
                push_log("Scan manually stopped.", 'WARN')
                break

            relay.on()
            push_status({'uv_on': True})
            interval = self._state.get("scan_interval", 300)
            msg = f"UV Sterilization ON. Next scan in {interval}s."
            logger.info(msg)
            push_log(msg)

            waited = 0
            while waited < interval and not self._stop_event.is_set():
                time.sleep(1)
                waited += 1

        relay.off()
        push_status({'uv_on': False, 'running': False, 'system_status': 'idle'})
        self._release_camera()
        self._state["system_status"] = "idle"
        state_store.save(self._state)
        logger.info("Scan loop stopped.")

    # ── Command handler (called by Firestore listener) ────────────────────────
    def handle_command(self, cmd_type: str, payload: dict):
        logger.info(f'Firestore command received: {cmd_type} payload={payload}')

        if cmd_type == 'scan_start':
            self.start()

        elif cmd_type == 'scan_stop':
            self.stop()

        elif cmd_type == 'sms_test':
            number = payload.get('number', '').strip()
            if number:
                sms.send_custom(number, 'Smart Dryer test message — system online ✅')
            else:
                logger.warning('sms_test command missing number')

        elif cmd_type == 'update_sms_recipient':
            number = payload.get('number', '').strip()
            if number:
                self.set_sms_number(number)

        elif cmd_type == 'update_config':
            if 'scan_interval' in payload:
                self.set_interval(int(payload['scan_interval']))
            if 'slot_steps' in payload:
                for slot_str, ms in payload['slot_steps'].items():
                    self.set_motor_calibration(int(slot_str), int(ms))

        else:
            logger.warning(f'Unknown command type: {cmd_type}')

    # ── Public control ────────────────────────────────────────────────────────
    def start(self) -> bool:
        if self._running:
            logger.warning("Scan already running.")
            return False
        self._stop_event.clear()
        self._running = True
        self._thread  = threading.Thread(
            target=self._loop, daemon=True, name="scan-loop"
        )
        self._thread.start()
        push_status({'running': True, 'system_status': 'scanning'})
        logger.info("Scan controller started.")
        return True

    def stop(self) -> bool:
        if not self._running:
            return False
        logger.info("Stopping scan controller...")
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)
        self._running = False
        relay.off()
        push_status({'running': False, 'system_status': 'idle', 'uv_on': False})
        return True

    def set_interval(self, seconds: int) -> bool:
        seconds = max(
            MIN_SCAN_INTERVAL_SECONDS,
            min(MAX_SCAN_INTERVAL_SECONDS, int(seconds))
        )
        self._state["scan_interval"] = seconds
        state_store.save(self._state)
        logger.info(f"Scan interval set to {seconds}s")
        return True

    def set_motor_calibration(self, slot: int, steps: int) -> bool:
        if slot not in range(1, TOTAL_SLOTS + 1):
            return False
        motor.set_slot_steps(slot, steps)
        self._state["slot_steps"][str(slot)] = steps
        state_store.save(self._state)
        return True

    def set_sms_number(self, number: str):
        sms.set_recipient(number)
        self._state["sms_recipient"] = number
        state_store.save(self._state)

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
            "calibration":      motor.get_calibration(),
        }

    def get_slots(self) -> dict:
        self._state = state_store.load()
        return self._state.get("slots", {})


# Singleton
scanner = ScanController()
