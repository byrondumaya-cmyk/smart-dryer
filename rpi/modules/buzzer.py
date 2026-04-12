# modules/buzzer.py — GPIO Buzzer Control (GPIO 12)
#
# Patterns:
#   alert()          — single short beep (startup / info)
#   error()          — 3 rapid low beeps (system error)
#   drying_complete() — ascending 3-tone chime (all slots dry)
#
# GPIO 12 supports hardware PWM → works with both active and passive buzzers.

import time
import threading
import logging

try:
    import RPi.GPIO as GPIO
    _GPIO_AVAILABLE = True
except ImportError:
    _GPIO_AVAILABLE = False
    logging.warning("RPi.GPIO not available — buzzer running in simulation mode.")

from config import GPIO_PINS

logger = logging.getLogger(__name__)
_lock  = threading.Lock()

BUZZER_PIN = GPIO_PINS['buzzer']   # GPIO 12


class BuzzerModule:
    def __init__(self):
        self._pwm = None
        self._setup_gpio()

    def _setup_gpio(self):
        if not _GPIO_AVAILABLE:
            return
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(BUZZER_PIN, GPIO.OUT, initial=GPIO.LOW)
        try:
            self._pwm = GPIO.PWM(BUZZER_PIN, 1000)   # 1kHz carrier
            self._pwm.start(0)
        except Exception as e:
            logger.warning(f"PWM init failed, falling back to digital: {e}")
            self._pwm = None
        logger.info(f"Buzzer initialised on GPIO {BUZZER_PIN}.")

    # ── Low-level helpers ─────────────────────────────────────────────────────
    def _on(self, freq: int = 1000):
        if not _GPIO_AVAILABLE:
            return
        if self._pwm:
            self._pwm.ChangeFrequency(freq)
            self._pwm.ChangeDutyCycle(50)
        else:
            GPIO.output(BUZZER_PIN, GPIO.HIGH)

    def _off(self):
        if not _GPIO_AVAILABLE:
            return
        if self._pwm:
            self._pwm.ChangeDutyCycle(0)
        else:
            GPIO.output(BUZZER_PIN, GPIO.LOW)

    def _beep(self, duration: float = 0.1, freq: int = 1000):
        self._on(freq)
        time.sleep(duration)
        self._off()

    # ── Public patterns ───────────────────────────────────────────────────────
    def _push_event(self, event_name: str):
        """Push buzzer event to Firestore status doc."""
        try:
            from modules.firestore_sync import push_status
            from google.cloud.firestore_v1 import SERVER_TIMESTAMP
            push_status({'buzzer_last': event_name, 'buzzer_last_at': SERVER_TIMESTAMP})
        except Exception as e:
            logger.debug(f'Buzzer Firestore push skipped: {e}')

    def alert(self):
        """Single short beep — startup / info."""
        def _run():
            with _lock:
                logger.info("[BUZZER] Alert")
                self._beep(0.15, 1000)
            self._push_event('alert')
        threading.Thread(target=_run, daemon=True).start()

    def error(self):
        """3 rapid low beeps — error condition."""
        def _run():
            with _lock:
                logger.info("[BUZZER] Error pattern")
                for _ in range(3):
                    self._beep(0.1, 800)
                    time.sleep(0.1)
            self._push_event('error')
        threading.Thread(target=_run, daemon=True).start()

    def drying_complete(self):
        """Ascending 3-tone chime — all slots dry."""
        def _run():
            with _lock:
                logger.info("[BUZZER] Drying complete chime")
                for freq in (800, 1000, 1200):
                    self._beep(0.2, freq)
                    time.sleep(0.05)
            self._push_event('drying_complete')
        threading.Thread(target=_run, daemon=True).start()

    def cleanup(self):
        self._off()
        if self._pwm:
            try:
                self._pwm.stop()
            except Exception:
                pass
        logger.info("Buzzer cleaned up.")


# Singleton
buzzer = BuzzerModule()
