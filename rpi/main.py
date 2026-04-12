import threading
import time
import logging
from modules.sensor import sensor
from modules import buzzer
import server

# Override standard logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)-5s %(module)-12s — %(message)s'
)
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

def main():
    logger.info("=" * 60)
    logger.info("Smart Dryer System starting (Vanilla Dashboard Mode)...")
    logger.info("=" * 60)

    # 1. Start sensors
    sensor.start()

    # 2. Start firestore sync
    from scan_controller import scanner
    from modules.firestore_sync import start_command_listener, push_config
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
