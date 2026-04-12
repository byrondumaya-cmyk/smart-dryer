# modules/sensor.py — 5-Slot DHT Sensor Array
#
# Reads all 5 per-slot DHT sensors in a background polling loop.
# Each slot has its own GPIO pin and model (DHT22 or DHT11)
# defined in config.SLOT_SENSOR_MAP.
#
# Falls back to simulation values on non-Pi environments.

import time
import threading
import logging

try:
    import board
    import adafruit_dht
    _DHT_AVAILABLE = True
except ImportError:
    _DHT_AVAILABLE = False
    logging.warning("adafruit_dht not available — sensors in simulation mode.")

from config import SLOT_SENSOR_MAP, DHT_READ_INTERVAL

logger = logging.getLogger(__name__)


class SensorModule:
    def __init__(self):
        self._data = {
            slot_id: {
                'temperature': None,
                'humidity':    None,
                'last_read':   None,
                'error':       None,
                'label':       info['label'],
            }
            for slot_id, info in SLOT_SENSOR_MAP.items()
        }
        self._devices    = {}
        self._stop_event = threading.Event()
        self._thread     = None
        self._init_devices()

    # ── Device Init ───────────────────────────────────────────────────────────
    def _init_devices(self):
        if not _DHT_AVAILABLE:
            return
        for slot_id, info in SLOT_SENSOR_MAP.items():
            try:
                pin = getattr(board, f"D{info['gpio']}")
                if info['model'] == 'DHT22':
                    dev = adafruit_dht.DHT22(pin, use_pulseio=False)
                else:
                    dev = adafruit_dht.DHT11(pin, use_pulseio=False)
                self._devices[slot_id] = dev
                logger.info(
                    f"{info['model']} initialised on GPIO {info['gpio']} "
                    f"({info['label']})"
                )
            except Exception as e:
                logger.error(f"Slot {slot_id} DHT init failed: {e}")

    # ── Polling Loop ──────────────────────────────────────────────────────────
    def _poll(self):
        from modules.firestore_sync import push_sensors
        while not self._stop_event.is_set():
            for slot_id in SLOT_SENSOR_MAP:
                if self._stop_event.is_set():
                    break
                self._read_slot(slot_id)
                time.sleep(0.5)   # brief gap between sensors
            # Push all 5 sensor readings to Firestore
            push_sensors(self.read_all())
            time.sleep(DHT_READ_INTERVAL)

    def _read_slot(self, slot_id: int):
        if not _DHT_AVAILABLE or slot_id not in self._devices:
            # Simulation
            import random
            self._data[slot_id].update({
                'temperature': round(28.0 + random.uniform(-2, 2), 1),
                'humidity':    round(65.0 + random.uniform(-5, 5), 1),
                'last_read':   time.time(),
                'error':       None,
            })
            return

        dev = self._devices[slot_id]
        success = False
        
        # Pi 4 specific: DHT sensors are very timing sensitive. 
        # We try 3 times with a 2s gap between attempts.
        for attempt in range(3):
            try:
                # Note: adafruit_dht properties trigger a physical read
                t = dev.temperature
                h = dev.humidity
                
                if t is not None and h is not None:
                    self._data[slot_id].update({
                        'temperature': t,
                        'humidity':    h,
                        'last_read':   time.time(),
                        'error':       None,
                    })
                    success = True
                    break
            except RuntimeError as e:
                # Checksum errors or 'Timed out' are common. Retry.
                logger.warning(f"Slot {slot_id} read attempt {attempt+1} failed: {e}")
                time.sleep(2.0)
            except Exception as e:
                logger.error(f"Slot {slot_id} unexpected hardware error: {e}")
                break
        
        if not success:
            logger.error(f"Slot {slot_id} failed to read after 3 attempts.")
            self._data[slot_id]['error'] = "Persistent read error"

    # ── Public Interface ──────────────────────────────────────────────────────
    def start(self):
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._poll, daemon=True, name="sensor-poll"
        )
        self._thread.start()
        logger.info("Sensor polling started (5 slots).")

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Sensor polling stopped.")

    def read_all(self) -> dict:
        """Return latest readings for all 5 slots keyed by slot number."""
        return {str(k): dict(v) for k, v in self._data.items()}

    def read_slot(self, slot_id: int) -> dict:
        """Return latest reading for a single slot."""
        return dict(self._data.get(slot_id, {}))

    def cleanup(self):
        self.stop()
        for slot_id, dev in self._devices.items():
            try:
                dev.exit()
            except Exception:
                pass
        logger.info("Sensor module cleaned up.")


# Singleton
sensor = SensorModule()
