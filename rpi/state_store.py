# state_store.py — Persistent JSON state
#
# Saves and loads system state to/from data/state.json.
# All modules share this for persistence across reboots.

import json
import os
import logging
import threading

from config import (
    STATE_FILE,
    TOTAL_SLOTS,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DEFAULT_MOTOR_SEGMENTS,
    DEFAULT_DWELL_TIME,
    DEFAULT_SENSOR_WEIGHT,
    DEFAULT_IMAGE_WEIGHT,
    DEFAULT_WET_THRESHOLD,
    DEFAULT_DRY_THRESHOLD,
    DEFAULT_UV_AUTO_MODE,
    DEFAULT_SMS_EVERY_CYCLE,
    DEFAULT_MOTOR_HOME_TIMEOUT,
)

logger = logging.getLogger(__name__)
_lock = threading.Lock()

# Default structure for a fresh installation
DEFAULT_STATE = {
    "system_status": "idle",
    "running": False,
    "current_slot": None,
    "last_cycle_at": None,
    "scan_interval": DEFAULT_SCAN_INTERVAL_SECONDS,
    "dwell_time": DEFAULT_DWELL_TIME,
    "motor_segments": dict(DEFAULT_MOTOR_SEGMENTS),
    "motor_home_timeout": DEFAULT_MOTOR_HOME_TIMEOUT,
    "weights": {
        "sensor": DEFAULT_SENSOR_WEIGHT,
        "image": DEFAULT_IMAGE_WEIGHT
    },
    "thresholds": {
        "wet": DEFAULT_WET_THRESHOLD,
        "dry": DEFAULT_DRY_THRESHOLD
    },
    "toggles": {
        "uv_auto": DEFAULT_UV_AUTO_MODE,
        "sms_cycle": DEFAULT_SMS_EVERY_CYCLE
    },
    "sms_recipient": "",
    "all_dry_notified": False,
    "uv_on": False,
    "slots": {
        str(i): {
            "label": "WAITING",
            "confidence": 0.0,
            "last_scanned": None,
            "sensor_hum": None,
            "sensor_temp": None,
            # For robust hysteresis, we track the last resolved stable state locally inside the slot
            "stable_state": "UNKNOWN",
            "breakdown": {}
        }
        for i in range(1, TOTAL_SLOTS + 1)
    }
}


def load() -> dict:
    """Load state from disk, falling back to defaults."""
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    if not os.path.exists(STATE_FILE):
        save(DEFAULT_STATE)
        return dict(DEFAULT_STATE)
    try:
        with open(STATE_FILE, "r") as f:
            state = json.load(f)
        
        # Migration checks to ensure missing nested dicts are added dynamically
        # without overwriting existing settings
        for key, val in DEFAULT_STATE.items():
            if key not in state:
                state[key] = val
                
        if "toggles" not in state:
            state["toggles"] = DEFAULT_STATE["toggles"]
        if "weights" not in state:
            state["weights"] = DEFAULT_STATE["weights"]
        if "thresholds" not in state:
            state["thresholds"] = DEFAULT_STATE["thresholds"]
        if "dwell_time" not in state:
            state["dwell_time"] = DEFAULT_STATE["dwell_time"]
            
        return state
    except Exception as e:
        logger.error(f"State load failed: {e} — using defaults.")
        return dict(DEFAULT_STATE)


def save(state: dict):
    """Persist state to disk (thread-safe)."""
    with _lock:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        try:
            with open(STATE_FILE, "w") as f:
                json.dump(state, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"State save failed: {e}")
