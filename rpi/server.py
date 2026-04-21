import threading
import time
import os
import cv2
import numpy as np
import json
import logging
from flask import Flask, Response, request, jsonify, send_from_directory
from flask_cors import CORS

from scan_controller import scanner
from modules.motor import motor
import state_store

logger = logging.getLogger(__name__)

# Global camera reading thread to support both classification and live feed
class GlobalCamera:
    RECONNECT_INTERVAL = 5     # seconds between camera open attempts
    FRAME_READ_BACKOFF = 0.5   # seconds to wait after a failed frame read

    def __init__(self):
        self._cam = None
        self._latest_frame = None
        self._lock = threading.Lock()
        self._running = False
        self._thread = None
        self._cam_healthy = False     # True only when camera is actively yielding frames

        # Pre-generate a 'No Signal' frame
        self._no_signal_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(self._no_signal_frame, "NO CAMERA SIGNAL", (120, 240),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)
        cv2.putText(self._no_signal_frame, "Check USB/Ribbon Connection", (120, 280),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1)

    # ── Camera open helper ────────────────────────────────────────────────────
    def _try_open_camera(self) -> bool:
        """Attempt to open and configure /dev/video0.  Returns True on success."""
        try:
            if self._cam is not None:
                try:
                    self._cam.release()
                except Exception:
                    pass
                self._cam = None

            cap = cv2.VideoCapture(0)
            time.sleep(1.5)   # USB camera warm-up — avoids isOpened() false-negative on Pi

            if not cap.isOpened():
                try:
                    cap.release()
                except Exception:
                    pass
                return False

            # Explicitly request MJPG codec to reduce USB bandwidth and lag
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            cap.set(cv2.CAP_PROP_FPS, 15)

            # Validate we can actually grab a frame (guards against phantom /dev/video nodes)
            ret, _ = cap.read()
            if not ret:
                try:
                    cap.release()
                except Exception:
                    pass
                return False

            self._cam = cap
            self._cam_healthy = True
            return True

        except Exception as e:
            logger.error(f"Camera open exception: {e}")
            return False

    # ── Public: start ─────────────────────────────────────────────────────────
    def start(self):
        """Always launches the _update thread — it handles retries internally."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._update, daemon=True, name="camera-feed")
        self._thread.start()
        logger.info("Camera feed thread launched (will auto-connect).")

    # ── Core loop with auto-reconnect ─────────────────────────────────────────
    def _update(self):
        consecutive_read_failures = 0
        MAX_READ_FAILURES = 10    # after this many consecutive bad reads, reconnect

        while self._running:
            # ── Phase A: Ensure camera is open ────────────────────────────────
            if self._cam is None or not self._cam.isOpened():
                self._cam_healthy = False
                if self._try_open_camera():
                    logger.info("Camera connected successfully (720p MJPG).")
                    consecutive_read_failures = 0
                else:
                    # Back off before retry — don't spam USB bus
                    logger.warning("Camera not available — retrying in %ds...", self.RECONNECT_INTERVAL)
                    self._wait(self.RECONNECT_INTERVAL)
                    continue

            # ── Phase B: Read frames ──────────────────────────────────────────
            try:
                ret, frame = self._cam.read()
            except Exception as e:
                logger.error(f"Camera read exception: {e}")
                ret = False
                frame = None

            if ret and frame is not None:
                with self._lock:
                    self._latest_frame = frame
                consecutive_read_failures = 0
                self._cam_healthy = True
            else:
                consecutive_read_failures += 1
                if consecutive_read_failures >= MAX_READ_FAILURES:
                    logger.warning(
                        "Camera lost after %d consecutive read failures — releasing and reconnecting.",
                        consecutive_read_failures
                    )
                    self._release_camera()
                    consecutive_read_failures = 0
                    continue
                time.sleep(self.FRAME_READ_BACKOFF)
                continue

            time.sleep(0.01)   # ~100 fps max poll rate

        # Thread exiting — release hardware
        self._release_camera()

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _release_camera(self):
        self._cam_healthy = False
        if self._cam is not None:
            try:
                self._cam.release()
            except Exception:
                pass
            self._cam = None

    def _wait(self, seconds: float):
        """Interruptible wait so stop() doesn't hang."""
        end = time.monotonic() + seconds
        while time.monotonic() < end and self._running:
            time.sleep(0.25)

    def read_latest(self):
        with self._lock:
            if self._latest_frame is not None:
                return self._latest_frame.copy()
            return self._no_signal_frame.copy()

    def get_jpeg(self):
        frame = self.read_latest()
        if frame is not None:
            ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
            if ret:
                return buffer.tobytes()
        return None

    @property
    def is_healthy(self) -> bool:
        """True when camera is actively producing frames."""
        return self._cam_healthy

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)
        self._release_camera()
        logger.info("Global USB camera stopped.")

camera_feed = GlobalCamera()

app = Flask(__name__)
CORS(app)

WEB_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "smart-dryer-web"))

@app.route("/")
@app.route("/index.html")
def index():
    return send_from_directory(WEB_DIR, "index.html")

@app.route("/<path:filename>")
def serve_static(filename):
    return send_from_directory(WEB_DIR, filename)

@app.route("/api/state")
def get_state():
    status = scanner.get_status()
    # Add sensor runtime polling
    from modules.sensor import sensor
    sensor_data = sensor.read_all()
    
    # Apply calibration offsets
    calib = status.get("calibration", {})
    for slot_id, val in sensor_data.items():
        try:
            h_off = float(calib.get(str(slot_id), {}).get("h_offset", 0.0))
            t_off = float(calib.get(str(slot_id), {}).get("t_offset", 0.0))
            if val.get("humidity") is not None:
                val["humidity"] = round(float(val["humidity"]) + h_off, 1)
            if val.get("temperature") is not None:
                val["temperature"] = round(float(val["temperature"]) + t_off, 1)
        except (ValueError, TypeError) as e:
            pass # fallback to original values if calibration cast fails

    status["sensor_live"] = sensor_data
    return jsonify(status)

@app.route("/api/command", methods=["POST"])
def post_command():
    data = request.json or {}
    cmd = data.get("command")
    
    if cmd == "scan_start":
        # Pass the global camera so scan runs faster
        scanner.start(global_camera=camera_feed)
        return jsonify({"status": "started"})
        
    elif cmd == "scan_stop":
        scanner.stop()
        return jsonify({"status": "stopped"})
        
    elif cmd == "wiggle":
        direction = data.get("direction", 1)
        duration = data.get("duration", 150)
        motor.wiggle(direction, duration)
        return jsonify({"status": "wiggled"})
        
    elif cmd == "motor_home":
        motor.home()
        scanner._current_slot = None
        return jsonify({"status": "homed"})
        
    elif cmd == "motor_slot":
        slot = data.get("slot")
        motor.move_to_slot(slot)
        return jsonify({"status": f"moved to {slot}"})
        
    elif cmd == "update_settings":
        state = state_store.load()
        
        # Cast values appropriately
        if "motor_segments" in data:
            for k, v in data["motor_segments"].items():
                data["motor_segments"][k] = int(v)
            state["motor_segments"].update(data["motor_segments"])
            for seg, ms in state["motor_segments"].items():
                motor.set_segment(seg, int(ms))
                
        if "dwell_time" in data:
            state["dwell_time"] = int(data["dwell_time"])
            
        if "weights" in data:
            for k, v in data["weights"].items():
                state["weights"][k] = float(v)
                
        if "thresholds" in data:
            for k, v in data["thresholds"].items():
                state["thresholds"][k] = float(v)
                
        if "toggles" in data:
            for k, v in data["toggles"].items():
                state["toggles"][k] = bool(v)
                
        if "scan_interval" in data:
            state["scan_interval"] = int(data["scan_interval"])
            
        if "sms_recipient" in data:
            state["sms_recipient"] = data["sms_recipient"]

        if "sms_recipients" in data:
            state["sms_recipients"] = data["sms_recipients"]

        if "sms_api_key" in data:
            state["sms_api_key"] = data["sms_api_key"]
            
        if "calibration" in data:
            state["calibration"].update(data["calibration"])
        state_store.save(state)
        return jsonify({"status": "updated"})

    elif cmd == "test_buzzer":
        state_snd = data.get("state", "system_started")
        from modules.buzzer import buzzer
        buzzer.play(state_snd)
        return jsonify({"status": "buzzer_tested", "state": state_snd})

    elif cmd == "test_relay":
        from modules.relay import relay
        from modules.buzzer import buzzer
        def _relay_th():
            buzzer.play("uv_on")
            relay.on()
            time.sleep(3)
            relay.off()
            buzzer.play("uv_off")
        threading.Thread(target=_relay_th, daemon=True).start()
        return jsonify({"status": "relay_test_started"})

    elif cmd == "test_sms":
        from modules.sms import sms
        state = state_store.load()
        recipients = state.get("sms_recipients", [])
        if not recipients:
            return jsonify({"error": "No SMS recipients configured"}), 400
        
        success = False
        message = "TEST: Smart Dryer SMS integration is functional."
        for number in recipients:
            if number.strip():
                if sms.send_custom(number.strip(), message):
                    success = True

        if success:
            return jsonify({"status": "sms_test_sent"})
        else:
            return jsonify({"error": "SMS failed to send"}), 500

    elif cmd == "scan_dht":
        from modules.sensor import sensor
        readings = sensor.read_all()
        logger.info(f"Manual DHT scan: {readings}")
        return jsonify({"status": "dht_scanned", "readings": readings})

    elif cmd == "reset_cycle":
        from config import TOTAL_SLOTS
        state = state_store.load()
        for i in range(1, TOTAL_SLOTS + 1):
            state["slots"][str(i)] = {
                "label": "WAITING",
                "confidence": None,
                "last_scanned": None,
                "sensor_hum": None,
                "sensor_temp": None,
                "sensor_score": None,
                "image_score": None,
                "snapshot_url": None,
                "stable_state": "UNKNOWN",
                "breakdown": {}
            }
        state["last_cycle_at"] = None
        state["all_dry_notified"] = False
        state_store.save(state)
        scanner._state = state
        logger.info("Cycle data reset by user.")
        return jsonify({"status": "cycle_reset"})

    return jsonify({"error": "unknown command"}), 400

def generate_mjpeg():
    """MJPEG multipart stream — always yields a frame, even when camera is offline.

    get_jpeg() already returns the no-signal frame when no live frame exists,
    so the generator always has valid JPEG data to send.
    """
    while True:
        jpg = camera_feed.get_jpeg()
        if jpg:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + jpg + b'\r\n')
        time.sleep(0.05)  # ~20 fps cap — avoids flooding the browser

@app.route("/video_feed")
def video_feed():
    return Response(generate_mjpeg(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route("/api/camera_status")
def camera_status():
    return jsonify({"healthy": camera_feed.is_healthy})

