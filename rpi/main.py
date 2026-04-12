#!/usr/bin/env python3
# main.py — Smart Dryer System Entry Point

import logging
import signal
import sys
import os

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("smart_dryer.log"),
    ],
)
logger = logging.getLogger("main")

# ── Project root on sys.path ──────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Import modules ────────────────────────────────────────────────────────────
from modules.motor  import motor
from modules.buzzer import buzzer
from modules.sensor import sensor
from modules.relay  import relay
from server         import run as run_server   # server.py is in project root


def shutdown(sig, frame):
    logger.info("Shutdown signal received — cleaning up...")
    try:
        from scan_controller import scanner
        scanner.stop()
    except Exception:
        pass
    relay.cleanup()
    sensor.cleanup()
    motor.cleanup()
    buzzer.cleanup()
    try:
        import RPi.GPIO as GPIO
        GPIO.cleanup()
    except Exception:
        pass
    logger.info("Goodbye.")
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT,  shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    logger.info("Smart Dryer System starting...")
    buzzer.alert()       # Startup beep

    # Flask server (blocks — sensor + scan threads started inside)
    run_server()
