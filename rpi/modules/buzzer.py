# modules/buzzer.py — GPIO Buzzer Control & Mapped Signals
#
# Provides comprehensive audio feedback loops for the Drying Rack.
# GPIO 12 supports hardware PWM, enabling pitch variations.

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
            logger.warning(f"PWM init failed, digital fallback: {e}")
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

    # ── Pattern Dictionary Runner ─────────────────────────────────────────────
    def play(self, state: str):
        """Play a mapped buzzer pattern in a background thread."""
        def _run():
            with _lock:
                if state == "system_started":
                    self._beep(0.2, 1200)
                    time.sleep(0.1)
                    self._beep(0.4, 1500)
                elif state == "homing_started":
                    self._beep(0.1, 800)
                elif state == "homing_success":
                    self._beep(0.15, 1200)
                elif state == "homing_timeout_or_error":
                    for _ in range(4):
                        self._beep(0.1, 400)
                        time.sleep(0.1)
                elif state == "moving_to_slot":
                    self._beep(0.05, 900)
                elif state == "slot_reached":
                    self._beep(0.1, 1000)
                elif state == "slot_scan_started":
                    self._beep(0.1, 1500)
                elif state == "slot_scan_complete":
                    self._beep(0.1, 1800)
                elif state == "cycle_started":
                    self._beep(0.3, 1000)
                elif state == "cycle_complete":
                    self._beep(0.3, 1200)
                elif state == "all_dry":
                    for freq in (800, 1000, 1200, 1500):
                        self._beep(0.15, freq)
                        time.sleep(0.05)
                elif state == "not_all_dry":
                    self._beep(0.2, 800)
                    time.sleep(0.1)
                    self._beep(0.2, 600)
                elif state == "sms_sent":
                    self._beep(0.1, 2000)
                    time.sleep(0.1)
                    self._beep(0.1, 2000)
                elif state == "sms_failed":
                    self._beep(0.5, 400)
                elif state == "uv_on":
                    self._beep(0.5, 1800)
                elif state == "uv_off":
                    self._beep(0.5, 800)
                elif state == "generic_error":
                    for _ in range(3):
                        self._beep(0.1, 800)
                        time.sleep(0.1)
                else:
                    logger.debug(f"Unknown buzzer state requested: {state}")
        
        threading.Thread(target=_run, daemon=True).start()

    # Legacy mappings
    def alert(self):
        self.play("system_started")
        
    def error(self):
        self.play("generic_error")
        
    def drying_complete(self):
        self.play("all_dry")

    def cleanup(self):
        self._off()
        if self._pwm:
            try:
                self._pwm.stop()
            except Exception:
                pass

# Singleton
buzzer = BuzzerModule()
