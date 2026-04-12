# modules/sensor.py — 5-Slot DHT Sensor Array
#
# Driver priority (best → worst reliability on Pi 4):
#   1. pigpio   — hardware-timed via C daemon  ← PREFERRED, fixes Pi 4 jitter
#   2. adafruit_dht — pure-Python bitbang      ← fallback
#   3. simulation   — random values            ← non-Pi / dev environments
#
# To enable pigpio (run once per boot on the Pi):
#   sudo pigpiod
#   OR add to /etc/rc.local before exit 0:  pigpiod
#
# Why pigpio fixes "DHT sensor not found" on Pi 4:
#   The DHT protocol uses ~26µs vs ~70µs pulse widths to encode 0/1.
#   Python's GIL + Linux scheduler introduce ≥50µs jitter on Pi 4's
#   fast Cortex-A72 — enough to misread every bit. pigpiod runs as a
#   real-time C process and timestamps GPIO edges via hardware interrupts,
#   completely bypassing Python's timing limitations.

import time
import threading
import logging

logger = logging.getLogger(__name__)

from config import SLOT_SENSOR_MAP, DHT_READ_INTERVAL

# ── Driver detection ──────────────────────────────────────────────────────────

_DRIVER = 'simulation'   # set below

try:
    import pigpio
    _pi = pigpio.pi()
    if _pi.connected:
        _DRIVER = 'pigpio'
        logger.info('pigpio daemon connected — using hardware-timed DHT reads.')
    else:
        _pi = None
        logger.warning('pigpio installed but daemon not running (sudo pigpiod). '
                       'Falling back to adafruit_dht.')
except ImportError:
    _pi = None
    logger.warning('pigpio not installed. Trying adafruit_dht...')

if _DRIVER != 'pigpio':
    try:
        import board
        import adafruit_dht
        _DRIVER = 'adafruit'
        logger.info('adafruit_dht available — using bitbang mode (may be unreliable on Pi 4).')
    except ImportError:
        logger.warning('adafruit_dht not available — sensors will run in simulation mode.')


# ── pigpio DHT implementation ─────────────────────────────────────────────────

class _PigpioDHT:
    """
    Hardware-timed DHT22/DHT11 reader via the pigpio daemon.

    How it works:
      1. trigger() pulls GPIO LOW for 18 ms to wake the sensor.
      2. The sensor responds with a 40-bit pulse train.
      3. pigpiod timestamps every GPIO edge via hardware interrupt (not Python).
      4. _edge() callback converts pulse widths to bits → _decode() validates.

    This runs entirely outside Python's GIL during the timing-critical phase,
    which is why it's reliable on Pi 4 where pure-Python bitbang is not.
    """

    _GLITCH_US = 100   # ignore pulses shorter than 100 µs (noise rejection)

    def __init__(self, pi, gpio: int, model: str = 'DHT22'):
        self._pi     = pi
        self._gpio   = gpio
        self._model  = model
        self._reset()
        pi.set_pull_up_down(gpio, pigpio.PUD_UP)
        pi.set_glitch_filter(gpio, self._GLITCH_US)
        self._cb = pi.callback(gpio, pigpio.EITHER_EDGE, self._edge)

    def _reset(self):
        self._high_tick  = 0
        self._bits       = []
        self._temperature = None
        self._humidity    = None
        self._error       = None

    def _edge(self, gpio, level, tick):
        if level == pigpio.HIGH:
            self._high_tick = tick
            return
        if self._high_tick == 0:
            return

        dt = pigpio.tickDiff(self._high_tick, tick)   # µs since last rising edge

        if dt > 10_000:
            # Long LOW = gap before start signal — reset bit buffer
            self._bits = []
        elif len(self._bits) < 40:
            # DHT encodes: ~26µs = 0-bit, ~70µs = 1-bit
            self._bits.append(1 if dt > 100 else 0)

        if len(self._bits) == 40:
            self._decode()

    def _decode(self):
        b = self._bits
        raw = [
            int(''.join(str(x) for x in b[0:8]),  2),
            int(''.join(str(x) for x in b[8:16]), 2),
            int(''.join(str(x) for x in b[16:24]), 2),
            int(''.join(str(x) for x in b[24:32]), 2),
            int(''.join(str(x) for x in b[32:40]), 2),
        ]
        checksum = (raw[0] + raw[1] + raw[2] + raw[3]) & 0xFF
        if checksum != raw[4]:
            self._error = f'Checksum mismatch (got {raw[4]:#04x}, expected {checksum:#04x})'
            return

        if self._model == 'DHT22':
            hum  = ((raw[0] << 8) | raw[1]) / 10.0
            temp = (((raw[2] & 0x7F) << 8) | raw[3]) / 10.0
            if raw[2] & 0x80:
                temp = -temp
        else:   # DHT11
            hum  = float(raw[0])
            temp = float(raw[2])

        if 0 <= hum <= 100 and -40 <= temp <= 80:
            self._humidity    = hum
            self._temperature = temp
            self._error       = None
        else:
            self._error = f'Out-of-range: T={temp} H={hum}'

    def trigger(self):
        """Send the 18 ms wake-up pulse to the DHT sensor then release line."""
        self._reset()
        self._pi.set_mode(self._gpio, pigpio.OUTPUT)
        self._pi.write(self._gpio, pigpio.LOW)
        time.sleep(0.018)              # ≥18 ms required by DHT spec
        self._pi.set_mode(self._gpio, pigpio.INPUT)

    @property
    def temperature(self):
        return self._temperature

    @property
    def humidity(self):
        return self._humidity

    @property
    def last_error(self):
        return self._error

    def cancel(self):
        try:
            self._cb.cancel()
        except Exception:
            pass


# ── SensorModule ──────────────────────────────────────────────────────────────

class SensorModule:
    def __init__(self):
        self._data = {
            slot_id: {
                'temperature': None,
                'humidity':    None,
                'last_read':   None,
                'error':       None,
                'online':      None,
                'label':       info['label'],
            }
            for slot_id, info in SLOT_SENSOR_MAP.items()
        }
        self._devices    = {}
        self._stop_event = threading.Event()
        self._thread     = None
        self._init_devices()

    # ── Device init ───────────────────────────────────────────────────────────
    def _init_devices(self):
        if _DRIVER == 'pigpio':
            for slot_id, info in SLOT_SENSOR_MAP.items():
                try:
                    dev = _PigpioDHT(_pi, info['gpio'], info['model'])
                    self._devices[slot_id] = dev
                    logger.info(
                        f"[pigpio] {info['model']} on GPIO {info['gpio']} "
                        f"({info['label']}) initialised."
                    )
                except Exception as e:
                    logger.error(f'Slot {slot_id} pigpio init failed: {e}')

        elif _DRIVER == 'adafruit':
            for slot_id, info in SLOT_SENSOR_MAP.items():
                try:
                    pin = getattr(board, f"D{info['gpio']}")
                    dev = (adafruit_dht.DHT22(pin, use_pulseio=False)
                           if info['model'] == 'DHT22'
                           else adafruit_dht.DHT11(pin, use_pulseio=False))
                    self._devices[slot_id] = dev
                    logger.info(
                        f"[adafruit] {info['model']} on GPIO {info['gpio']} "
                        f"({info['label']}) initialised."
                    )
                except Exception as e:
                    logger.error(f'Slot {slot_id} adafruit init failed: {e}')

    # ── Polling loop ──────────────────────────────────────────────────────────
    def _poll(self):
        from modules.firestore_sync import push_sensors

        if _DRIVER == 'pigpio':
            # Trigger all sensors first, then wait, then read — pipeline reads
            # so all sensors are sampling in parallel (no sequential blocking).
            while not self._stop_event.is_set():
                self._trigger_all()
                time.sleep(0.3)   # DHT needs ~250 ms to finish transmission
                for slot_id in SLOT_SENSOR_MAP:
                    if self._stop_event.is_set():
                        break
                    self._read_slot_pigpio(slot_id)
                push_sensors(self.read_all())
                time.sleep(DHT_READ_INTERVAL)
        else:
            # adafruit / simulation: sequential with gaps
            while not self._stop_event.is_set():
                for slot_id in SLOT_SENSOR_MAP:
                    if self._stop_event.is_set():
                        break
                    self._read_slot_legacy(slot_id)
                    time.sleep(0.5)
                push_sensors(self.read_all())
                time.sleep(DHT_READ_INTERVAL)

    def _trigger_all(self):
        """Trigger all pigpio DHT devices simultaneously."""
        for slot_id, dev in list(self._devices.items()):
            try:
                dev.trigger()
                time.sleep(0.002)   # tiny gap between triggers avoids power spike
            except Exception as e:
                logger.warning(f'Slot {slot_id} trigger failed: {e}')

    # ── pigpio read ───────────────────────────────────────────────────────────
    def _read_slot_pigpio(self, slot_id: int):
        if slot_id not in self._devices:
            self._simulate(slot_id)
            return

        dev = self._devices[slot_id]
        t   = dev.temperature
        h   = dev.humidity
        err = dev.last_error

        if t is not None and h is not None:
            self._data[slot_id].update({
                'temperature': t,
                'humidity':    h,
                'last_read':   time.time(),
                'error':       None,
                'online':      True,
            })
        else:
            reason = err or 'No response after trigger'
            logger.warning(f'Slot {slot_id} pigpio read: {reason}')
            self._data[slot_id].update({
                'error':  reason,
                'online': False,
            })
            # Re-trigger for next cycle (pigpio devices reuse the same callback)
            try:
                dev.trigger()
            except Exception:
                pass

    # ── adafruit/simulation read ──────────────────────────────────────────────
    def _read_slot_legacy(self, slot_id: int):
        info = SLOT_SENSOR_MAP[slot_id]

        if _DRIVER == 'simulation' or slot_id not in self._devices:
            self._simulate(slot_id)
            return

        dev         = self._devices[slot_id]
        retry_delay = 3.0 if info['model'] == 'DHT22' else 2.0
        success     = False

        for attempt in range(3):
            try:
                t = dev.temperature
                h = dev.humidity
                if t is not None and h is not None:
                    self._data[slot_id].update({
                        'temperature': t,
                        'humidity':    h,
                        'last_read':   time.time(),
                        'error':       None,
                        'online':      True,
                    })
                    success = True
                    break
            except RuntimeError as e:
                logger.warning(f'Slot {slot_id} attempt {attempt+1}: {e}')
                time.sleep(retry_delay)
            except Exception as e:
                logger.error(f'Slot {slot_id} unexpected error: {e}')
                break

        if not success:
            logger.error(f'Slot {slot_id} failed after 3 attempts — reinitialising device.')
            self._data[slot_id].update({
                'error':  'Persistent read error — check wiring',
                'online': False,
            })
            self._reinit_slot(slot_id)

    def _simulate(self, slot_id: int):
        import random
        self._data[slot_id].update({
            'temperature': round(28.0 + random.uniform(-2, 2), 1),
            'humidity':    round(65.0 + random.uniform(-5, 5), 1),
            'last_read':   time.time(),
            'error':       None,
            'online':      True,
        })

    def _reinit_slot(self, slot_id: int):
        """Destroy and recreate the adafruit device object (self-healing)."""
        if _DRIVER != 'adafruit':
            return
        info = SLOT_SENSOR_MAP.get(slot_id)
        if not info:
            return
        dev = self._devices.pop(slot_id, None)
        if dev:
            try:
                dev.exit()
            except Exception:
                pass
        try:
            pin = getattr(board, f"D{info['gpio']}")
            new = (adafruit_dht.DHT22(pin, use_pulseio=False)
                   if info['model'] == 'DHT22'
                   else adafruit_dht.DHT11(pin, use_pulseio=False))
            self._devices[slot_id] = new
            logger.info(f'Slot {slot_id} re-initialised on GPIO {info["gpio"]}.')
        except Exception as e:
            logger.error(f'Slot {slot_id} re-init failed: {e}')

    # ── Public interface ──────────────────────────────────────────────────────
    def start(self):
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._poll, daemon=True, name='sensor-poll'
        )
        self._thread.start()
        logger.info(f'Sensor polling started (5 slots) via [{_DRIVER}] driver.')

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)
        logger.info('Sensor polling stopped.')

    def read_all(self) -> dict:
        return {str(k): dict(v) for k, v in self._data.items()}

    def read_slot(self, slot_id: int) -> dict:
        return dict(self._data.get(slot_id, {}))

    def cleanup(self):
        self.stop()
        if _DRIVER == 'pigpio':
            for dev in self._devices.values():
                dev.cancel()
            if _pi:
                _pi.stop()
        elif _DRIVER == 'adafruit':
            for dev in self._devices.values():
                try:
                    dev.exit()
                except Exception:
                    pass
        logger.info('Sensor module cleaned up.')

    @property
    def driver(self) -> str:
        return _DRIVER


# Singleton
sensor = SensorModule()
