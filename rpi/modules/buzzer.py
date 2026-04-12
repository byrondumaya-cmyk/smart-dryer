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
                    # Ascending boot sequence
                    self._beep(0.2, 1200)
                    time.sleep(0.05)
                    self._beep(0.2, 1500)
                    time.sleep(0.05)
                    self._beep(0.4, 2000)
                elif state == "homing_started":
                    # Low prolonged drone
                    self._beep(0.4, 600)
                elif state == "homing_success":
                    # Happy double high ping
                    self._beep(0.1, 1800)
                    time.sleep(0.05)
                    self._beep(0.1, 2200)
                elif state == "homing_timeout_or_error":
                    # 4 flat droning wails
                    for _ in range(4):
                        self._beep(0.4, 300)
                        time.sleep(0.1)
                elif state == "moving_to_slot":
                    # Very short click/tick
                    self._beep(0.03, 1500)
                elif state == "slot_reached":
                    # Double tick
                    self._beep(0.05, 1500)
                    time.sleep(0.05)
                    self._beep(0.05, 1500)
                elif state == "slot_scan_started":
                    # Rising chirp
                    self._beep(0.1, 1000)
                    time.sleep(0.05)
                    self._beep(0.1, 1200)
                elif state == "slot_scan_complete":
                    # Descending chirp
                    self._beep(0.1, 1200)
                    time.sleep(0.05)
                    self._beep(0.1, 1000)
                elif state == "cycle_started":
                    # 3 ascending
                    for freq in (1000, 1500, 2000):
                        self._beep(0.15, freq)
                        time.sleep(0.05)
                elif state == "cycle_complete":
                    # 3 descending
                    for freq in (2000, 1500, 1000):
                        self._beep(0.2, freq)
                        time.sleep(0.05)
                elif state == "all_dry":
                    # Merry arpeggio (C6, E6, G6, C7)
                    for freq in (1046, 1318, 1568, 2093):
                        self._beep(0.15, freq)
                        time.sleep(0.05)
                elif state == "not_all_dry":
                    # Sad descending
                    self._beep(0.3, 1000)
                    time.sleep(0.05)
                    self._beep(0.3, 800)
                    time.sleep(0.05)
                    self._beep(0.5, 600)
                elif state == "sms_sent":
                    # High pitched staccato dual beep
                    self._beep(0.05, 2500)
                    time.sleep(0.05)
                    self._beep(0.05, 2500)
                elif state == "sms_failed":
                    # Low staccato dual beep
                    self._beep(0.3, 400)
                    time.sleep(0.1)
                    self._beep(0.3, 400)
                elif state == "uv_on":
                    # Long descending wail
                    self._beep(0.2, 1500)
                    self._beep(0.4, 1000)
                elif state == "uv_off":
                    # Rising
                    self._beep(0.2, 1000)
                    self._beep(0.4, 1500)
                elif state == "generic_error":
                    # Harsh rapid staccato
                    for _ in range(5):
                        self._beep(0.1, 500)
                        time.sleep(0.05)
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
