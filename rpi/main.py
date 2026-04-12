import threading
import time
import logging
from modules.sensor import sensor
import server

logger = logging.getLogger('main')

def start_web_server():
    # The desktop baseline used port 8080 and simpleHTTP
    # server.py from baseline handles this.
    try:
        import subprocess
        # Run server.py as a script so it serves the files from the root
        subprocess.run(["python", "server.py"])
    except Exception as e:
        logger.error(f"Web server failed: {e}")

def _check_environment():
    """
    Print a clear startup diagnostic so sensor/firebase failures are
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

    # 2. libgpiod2 system library (required by adafruit-circuitpython-dht ≥3.7)
    import subprocess
    result = subprocess.run(['dpkg', '-s', 'libgpiod2'],
                            capture_output=True, text=True)
    if result.returncode == 0:
        logger.info("  [OK]  libgpiod2 installed.")
    else:
        logger.warning("  [!!]  libgpiod2 NOT installed — adafruit_dht fallback will fail.")
        logger.warning("        Run:  sudo apt install libgpiod2")
        ok = False

    # 3. Firebase service account key
    import os
    key = os.path.join(os.path.dirname(__file__), 'serviceAccountKey.json')
    if os.path.exists(key):
        logger.info("  [OK]  serviceAccountKey.json found.")
    else:
        logger.warning("  [!!]  serviceAccountKey.json MISSING — Firestore/dashboard will be OFFLINE.")
        logger.warning(f"        Expected at: {key}")
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
    logger.info("Smart Dryer V2 starting...")
    logger.info("=" * 60)

    _check_environment()

    # 1. Start sensors
    sensor.start()

    # 2. Start firestore sync
    from scan_controller import scanner
    from modules.firestore_sync import start_command_listener, push_config, push_status, start_heartbeat
    from config import DEFAULT_SLOT_STEPS, DEFAULT_SCAN_INTERVAL_SECONDS
    import state_store

    start_command_listener(scanner.handle_command)

    # Push initial config
    state = state_store.load()
    push_config({
        'scan_interval': state.get('scan_interval', DEFAULT_SCAN_INTERVAL_SECONDS),
        'sms_recipient': state.get('sms_recipient', ''),
        'slot_steps':    state.get('slot_steps', {str(k): v for k, v in DEFAULT_SLOT_STEPS.items()}),
    })

    # Signal that system is online and ready — heartbeat keeps dashboard LIVE during idle
    push_status({'running': False, 'system_status': 'idle', 'current_slot': None})
    start_heartbeat()

    # Start the local file server (serves the dashboard.html locally)
    server_thread = threading.Thread(target=start_web_server, daemon=True)
    server_thread.start()

    # Wait for interrupts
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        sensor.stop()

if __name__ == "__main__":
    main()
