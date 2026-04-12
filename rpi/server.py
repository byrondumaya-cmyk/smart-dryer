# server.py — Flask REST API + Server-Sent Events
#
# Endpoints:
#   POST /scan/start
#   POST /scan/stop
#   POST /scan/interval        { "seconds": int }
#   POST /motor/calibration    { "slot": int, "steps": int }
#   POST /sms/number           { "number": str }
#   POST /sms/test             { "number": str }
#   GET  /sensor               → per-slot {temperature, humidity, ...}
#   GET  /sensor/<slot>        → single slot reading
#   GET  /status               → full system status
#   GET  /slots                → per-slot dryness states
#   GET  /relay                → UV relay state
#   POST /relay/on | /relay/off
#   GET  /stream               → SSE (status + slots + sensors every 2s)
#   GET  /                     → dashboard (index.html in project root)

import json
import time
import logging
import os

from flask import Flask, request, jsonify, Response, send_from_directory
from flask_cors import CORS

from scan_controller  import scanner
from modules.sensor   import sensor
from modules.buzzer   import buzzer
from modules.relay    import relay
from config           import API_HOST, API_PORT, DEBUG

logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder=None)
CORS(app)

# Dashboard lives in the project root alongside server.py
DASHBOARD_DIR = os.path.dirname(os.path.abspath(__file__))


# ── Dashboard ─────────────────────────────────────────────────────────────────
@app.route("/")
def dashboard():
    return send_from_directory(DASHBOARD_DIR, "index.html")


# ── Scan control ──────────────────────────────────────────────────────────────
@app.route("/scan/start", methods=["POST"])
def scan_start():
    ok = scanner.start()
    return jsonify({"success": ok, "message": "Started" if ok else "Already running"})


@app.route("/scan/stop", methods=["POST"])
def scan_stop():
    ok = scanner.stop()
    return jsonify({"success": ok, "message": "Stopped" if ok else "Not running"})


@app.route("/scan/interval", methods=["POST"])
def scan_interval():
    data    = request.get_json(silent=True) or {}
    seconds = data.get("seconds")
    if seconds is None:
        return jsonify({"success": False, "error": "Missing 'seconds'"}), 400
    ok = scanner.set_interval(int(seconds))
    return jsonify({"success": ok})


# ── Motor calibration ─────────────────────────────────────────────────────────
@app.route("/motor/calibration", methods=["POST"])
def motor_calibration():
    data  = request.get_json(silent=True) or {}
    slot  = data.get("slot")
    steps = data.get("steps")
    if slot is None or steps is None:
        return jsonify({"success": False, "error": "Missing 'slot' or 'steps'"}), 400
    ok = scanner.set_motor_calibration(int(slot), int(steps))
    return jsonify({"success": ok})


# ── SMS ───────────────────────────────────────────────────────────────────────
@app.route("/sms/number", methods=["POST"])
def sms_number():
    data   = request.get_json(silent=True) or {}
    number = data.get("number", "").strip()
    if not number:
        return jsonify({"success": False, "error": "Missing 'number'"}), 400
    scanner.set_sms_number(number)
    return jsonify({"success": True})


@app.route("/sms/test", methods=["POST"])
def sms_test():
    from modules.sms import sms
    data   = request.get_json(silent=True) or {}
    number = data.get("number", "").strip()
    if not number:
        return jsonify({"success": False, "error": "Missing 'number'"}), 400
    ok = sms.send_custom(number, "Smart Dryer test message — system online ✅")
    return jsonify({"success": ok})


# ── Sensor ────────────────────────────────────────────────────────────────────
@app.route("/sensor")
def sensor_all():
    """Return readings for all 5 slots."""
    return jsonify(sensor.read_all())


@app.route("/sensor/<int:slot_id>")
def sensor_slot(slot_id: int):
    """Return reading for a single slot."""
    data = sensor.read_slot(slot_id)
    if not data:
        return jsonify({"error": f"Slot {slot_id} not found"}), 404
    return jsonify(data)


# ── UV Relay ──────────────────────────────────────────────────────────────────
@app.route("/relay")
def relay_status():
    return jsonify({"uv_on": relay.is_on})


@app.route("/relay/on", methods=["POST"])
def relay_on():
    relay.on()
    return jsonify({"success": True, "uv_on": True})


@app.route("/relay/off", methods=["POST"])
def relay_off():
    relay.off()
    return jsonify({"success": True, "uv_on": False})


# ── Status ────────────────────────────────────────────────────────────────────
@app.route("/status")
def status():
    s = scanner.get_status()
    s["uv_on"] = relay.is_on
    return jsonify(s)


@app.route("/slots")
def slots():
    return jsonify(scanner.get_slots())


# ── SSE real-time stream ──────────────────────────────────────────────────────
@app.route("/stream")
def stream():
    """
    Server-Sent Events — pushes JSON every 2s:
      { status, slots, sensors, uv_on }
    JavaScript: const es = new EventSource('/stream');
    """
    def event_generator():
        while True:
            payload = {
                "status":  scanner.get_status(),
                "slots":   scanner.get_slots(),
                "sensors": sensor.read_all(),
                "uv_on":   relay.is_on,
            }
            yield f"data: {json.dumps(payload, default=str)}\n\n"
            time.sleep(2)

    return Response(
        event_generator(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control":               "no-cache",
            "X-Accel-Buffering":           "no",
            "Access-Control-Allow-Origin": "*",
        },
    )


# ── Buzzer test ───────────────────────────────────────────────────────────────
@app.route("/buzzer/test", methods=["POST"])
def buzzer_test():
    buzzer.alert()
    return jsonify({"success": True})


def run():
    sensor.start()

    # Start Firestore command listener — routes dashboard commands to scanner
    from scan_controller import scanner
    from modules.firestore_sync import start_command_listener, push_config
    start_command_listener(scanner.handle_command)

    # Push initial config so dashboard shows current state on first load
    from config import DEFAULT_SLOT_STEPS, DEFAULT_SCAN_INTERVAL_SECONDS
    import state_store
    state = state_store.load()
    push_config({
        'scan_interval': state.get('scan_interval', DEFAULT_SCAN_INTERVAL_SECONDS),
        'sms_recipient': state.get('sms_recipient', ''),
        'slot_steps':    state.get('slot_steps', {str(k): v for k, v in DEFAULT_SLOT_STEPS.items()}),
    })

    logger.info(f"API server starting on http://{API_HOST}:{API_PORT}")
    app.run(
        host=API_HOST, port=API_PORT,
        debug=DEBUG, threaded=True, use_reloader=False
    )
