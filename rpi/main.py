import threading
import time
import logging
import os
from modules.sensor import sensor
import server

logger = logging.getLogger('main')

def start_web_server():
    # Start the Flask app
    try:
        server.app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
    except Exception as e:
        logger.error(f"Web server failed: {e}")

def _check_environment():
    """
    Print a clear startup diagnostic so sensor failures are
    immediately obvious rather than buried in retry warnings.
    """
    ok = True
    logger.info("── Environment Check ─────────────────────────────────────")

    # 1. pigpiod daemon (preferred DHT driver)
    try:
        import pigpio
        pi = pigpio.pi()
        if pi.connected:
            logger.info("  [OK]  pigpiod running — hardware-timed DHT reads active.")
            pi.stop()
        else:
            logger.warning("  [!!]  pigpio installed but pigpiod NOT running.")
            logger.warning("        Run:  sudo systemctl start pigpiod")
            logger.warning("        Permanent: sudo systemctl enable pigpiod")
            ok = False
    except ImportError:
        logger.warning("  [!!]  pigpio not installed — falling back to adafruit_dht.")
        logger.warning("        Run:  pip install pigpio --break-system-packages")
        ok = False

    # 2. libgpiod2 system library
    import subprocess
    result = subprocess.run(['dpkg', '-s', 'libgpiod2'],
                            capture_output=True, text=True)
    if result.returncode == 0:
        logger.info("  [OK]  libgpiod2 installed.")
    else:
        logger.warning("  [!!]  libgpiod2 NOT installed — adafruit_dht fallback will fail.")
        logger.warning("        Run:  sudo apt install libgpiod2")
        ok = False

    logger.info("──────────────────────────────────────────────────────────")
    if not ok:
        logger.warning("  One or more issues detected above. System will continue")
        logger.warning("  but some features may not work until they are resolved.")
    else:
        logger.info("  All checks passed.")

def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)-5s %(module)-12s — %(message)s'
    )
    logger.info("=" * 60)
    logger.info("Smart Dryer V2 starting (Local API Mode)...")
    logger.info("CODE VERSION: 2026-04-21-B (Flask-thread SMS dispatch)")
    logger.info("=" * 60)

    _check_environment()

    # 1. Start sensors
    sensor.start()

    # 2. Start global camera
    server.camera_feed.start()

    # 3. Start local file server & API
    server_thread = threading.Thread(target=start_web_server, daemon=True)
    server_thread.start()

    logger.info("Local API Server running at http://0.0.0.0:5000")
    
    # Wait for interrupts
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        sensor.stop()
        server.camera_feed.stop()

if __name__ == "__main__":
    main()

