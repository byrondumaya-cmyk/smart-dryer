# modules/motor.py — L298N DC Motor Control
#
# Hardware: L298N dual H-bridge driver
#   IN1 / IN2 → direction
#   ENA (PWM)  → speed via GPIO.PWM on GPIO 18
#   limit_home → active-LOW limit switch for homing (GPIO 25, pull-up)
#
# Positioning is time-based (ms from home).
# Calibrate slot timing via the dashboard.

import time
import threading
import logging

try:
    import RPi.GPIO as GPIO
    _GPIO_AVAILABLE = True
except ImportError:
    _GPIO_AVAILABLE = False
    logging.warning("RPi.GPIO not available — motor running in simulation mode.")

from config import (
    GPIO_PINS,
    DEFAULT_MOTOR_SEGMENTS,
    MOTOR_PWM_FREQ,
    MOTOR_PWM_SPEED,
    MOTOR_HOME_TIMEOUT,
)

logger = logging.getLogger(__name__)
_lock = threading.Lock()


class MotorController:
    def __init__(self):
        self.segments = dict(DEFAULT_MOTOR_SEGMENTS)   # ms segments between slots
        self.current_position_ms = 0                   # track time-based position
        self._pwm = None
        self._setup_gpio()

    # ── GPIO Setup ────────────────────────────────────────────────────────────
    def _setup_gpio(self):
        if not _GPIO_AVAILABLE:
            return
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(GPIO_PINS['motor_in1'],  GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(GPIO_PINS['motor_in2'],  GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(GPIO_PINS['motor_en'],   GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(GPIO_PINS['limit_home'], GPIO.IN,
                   pull_up_down=GPIO.PUD_UP)   # active LOW on press
        self._pwm = GPIO.PWM(GPIO_PINS['motor_en'], MOTOR_PWM_FREQ)
        self._pwm.start(0)
        logger.info("Motor GPIO initialised (L298N).")

    # ── Direction helpers ─────────────────────────────────────────────────────
    def _forward(self):
        if not _GPIO_AVAILABLE:
            return
        GPIO.output(GPIO_PINS['motor_in1'], GPIO.HIGH)
        GPIO.output(GPIO_PINS['motor_in2'], GPIO.LOW)
        self._pwm.ChangeDutyCycle(MOTOR_PWM_SPEED)

    def _backward(self):
        if not _GPIO_AVAILABLE:
            return
        GPIO.output(GPIO_PINS['motor_in1'], GPIO.LOW)
        GPIO.output(GPIO_PINS['motor_in2'], GPIO.HIGH)
        self._pwm.ChangeDutyCycle(MOTOR_PWM_SPEED)

    def _stop(self):
        if not _GPIO_AVAILABLE:
            return
        GPIO.output(GPIO_PINS['motor_in1'], GPIO.LOW)
        GPIO.output(GPIO_PINS['motor_in2'], GPIO.LOW)
        self._pwm.ChangeDutyCycle(0)

    def _limit_hit(self) -> bool:
        """Returns True when limit switch is pressed (active LOW)."""
        if not _GPIO_AVAILABLE:
            return True   # Simulate immediate home in dev
        return GPIO.input(GPIO_PINS['limit_home']) == GPIO.LOW

    # ── Public: Home ──────────────────────────────────────────────────────────
    def home(self) -> bool:
        """
        Drive backward until limit switch triggers.
        Returns True on success, False on timeout.
        """
        with _lock:
            logger.info("Homing motor...")
            try:
                if not _GPIO_AVAILABLE:
                    logger.info("[SIM] Motor homed.")
                    self.current_position_ms = 0
                    return True

                self._backward()
                deadline = time.time() + MOTOR_HOME_TIMEOUT
                while time.time() < deadline:
                    if self._limit_hit():
                        self._stop()
                        self.current_position_ms = 0
                        logger.info("Motor homed — limit switch triggered.")
                        return True
                    time.sleep(0.01)

                self._stop()
                logger.error("Homing timeout — limit switch not reached.")
                return False
            except Exception as e:
                self._stop()
                logger.error(f"Homing error: {e}")
                return False

    def _get_slot_ms(self, slot: int) -> int:
        pos = 0
        if slot >= 1: pos += self.segments.get('home_to_s1', 800)
        if slot >= 2: pos += self.segments.get('s1_to_s2', 800)
        if slot >= 3: pos += self.segments.get('s2_to_s3', 800)
        if slot >= 4: pos += self.segments.get('s3_to_s4', 800)
        if slot >= 5: pos += self.segments.get('s4_to_s5', 800)
        return pos

    # ── Public: Move to slot ──────────────────────────────────────────────────
    def move_to_slot(self, slot: int) -> bool:
        """
        Move to `slot` position using time-based drive from current position.
        Position is calculated by summing segments.
        """
        if slot not in range(1, 6):
            logger.error(f"Invalid slot: {slot}")
            return False

        target_ms = self._get_slot_ms(slot)
        delta_ms  = target_ms - self.current_position_ms

        with _lock:
            logger.info(
                f"Moving to slot {slot} "
                f"(target={target_ms}ms, delta={delta_ms:+}ms)"
            )
            try:
                if not _GPIO_AVAILABLE:
                    logger.info(f"[SIM] Moved to slot {slot}.")
                    self.current_position_ms = target_ms
                    time.sleep(abs(delta_ms) / 1000.0)
                    return True

                if delta_ms > 0:
                    self._forward()
                    time.sleep(delta_ms / 1000.0)
                    self._stop()
                elif delta_ms < 0:
                    self._backward()
                    time.sleep(abs(delta_ms) / 1000.0)
                    self._stop()
                # delta_ms == 0: already there

                self.current_position_ms = target_ms
                logger.info(f"Arrived at slot {slot}.")
                return True
            except Exception as e:
                self._stop()
                logger.error(f"Motor move failed: {e}")
                return False

    # ── Public: Wiggle ────────────────────────────────────────────────────────
    def wiggle(self, direction: int, duration_ms: int = 150) -> bool:
        """
        Jog motor for manual alignment.
        direction: 1 (forward), -1 (backward)
        """
        with _lock:
            try:
                if not _GPIO_AVAILABLE:
                    logger.info(f"[SIM] Wiggled {direction} for {duration_ms}ms.")
                    return True
                
                if direction > 0:
                    self._forward()
                else:
                    self._backward()
                
                time.sleep(duration_ms / 1000.0)
                self._stop()
                
                # Note: this alters actual position, but since it's just a manual
                # wiggle we don't strictly update current_position_ms because a 
                # calibration cycle will likely home immediately after anyway.
                logger.info(f"Motor wiggled direction: {direction}")
                return True
            except Exception as e:
                self._stop()
                logger.error(f"Wiggle failed: {e}")
                return False

    # ── Calibration ───────────────────────────────────────────────────────────
    def set_segment(self, segment: str, ms: int):
        if segment in self.segments:
            self.segments[segment] = max(0, int(ms))
            logger.info(f"Calibration: segment {segment} → {self.segments[segment]}ms")

    def get_segments(self) -> dict:
        return dict(self.segments)

    # ── Cleanup ───────────────────────────────────────────────────────────────
    def cleanup(self):
        self._stop()
        if self._pwm:
            try:
                self._pwm.stop()
            except Exception:
                pass
        logger.info("Motor controller cleaned up.")


# Singleton
motor = MotorController()
