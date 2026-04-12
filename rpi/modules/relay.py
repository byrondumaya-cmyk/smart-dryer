# modules/relay.py — UV Sterilization Relay (GPIO 16)
#
# Hardware: Active-LOW relay module
#   relay_uv = GPIO 16
#   LOW  signal → relay closes → UV lamp ON
#   HIGH signal → relay opens  → UV lamp OFF
#
# Usage by scan_controller:
#   relay.on()   — between scan cycles (sterilization)
#   relay.off()  — during active scanning

import logging

try:
    import RPi.GPIO as GPIO
    _GPIO_AVAILABLE = True
except ImportError:
    _GPIO_AVAILABLE = False
    logging.warning("RPi.GPIO not available — relay running in simulation mode.")

from config import GPIO_PINS

logger = logging.getLogger(__name__)

RELAY_PIN = GPIO_PINS['relay_uv']   # GPIO 16


class RelayModule:
    def __init__(self):
        self._active = False
        self._setup_gpio()

    def _setup_gpio(self):
        if not _GPIO_AVAILABLE:
            return
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        # Start HIGH = relay open = UV OFF (safe default)
        GPIO.setup(RELAY_PIN, GPIO.OUT, initial=GPIO.HIGH)
        logger.info(f"UV relay initialised on GPIO {RELAY_PIN} (OFF).")

    def on(self):
        """Activate UV lamp (relay closes — active LOW)."""
        if not self._active:
            self._active = True
            if _GPIO_AVAILABLE:
                GPIO.output(RELAY_PIN, GPIO.LOW)
            logger.info("[RELAY] UV ON — sterilization active.")

    def off(self):
        """Deactivate UV lamp (relay opens)."""
        if self._active:
            self._active = False
            if _GPIO_AVAILABLE:
                GPIO.output(RELAY_PIN, GPIO.HIGH)
            logger.info("[RELAY] UV OFF.")

    @property
    def is_on(self) -> bool:
        return self._active

    def cleanup(self):
        self.off()
        logger.info("Relay cleaned up.")


# Singleton
relay = RelayModule()
