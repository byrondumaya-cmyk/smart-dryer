# state_store.py — Persistent JSON state
#
# Saves and loads system state to/from data/state.json.
# All modules share this for persistence across reboots.

import json
import os
import logging
import threading

from config import (
    STATE_FILE, TOTAL_SLOTS, DEFAULT_SCAN_INTERVAL_SECONDS,
    DEFAULT_MOTOR_SEGMENTS, DEFAULT_DWELL_TIME_SECONDS,
    DEFAULT_SENSOR_WEIGHT, DEFAULT_IMAGE_WEIGHT,
    DEFAULT_WET_THRESHOLD, DEFAULT_DRY_THRESHOLD,
    DEFAULT_UV_AUTO_MODE, DEFAULT_SMS_EVERY_CYCLE
)

logger = logging.getLogger(__name__)
_lock = threading.Lock()

DEFAULT_STATE = {
    "scan_interval":  DEFAULT_SCAN_INTERVAL_SECONDS,
    "motor_segments": dict(DEFAULT_MOTOR_SEGMENTS),
    "dwell_time":     DEFAULT_DWELL_TIME_SECONDS,
    "weights": {
        "sensor":     DEFAULT_SENSOR_WEIGHT,
        "image":      DEFAULT_IMAGE_WEIGHT
    },
    "thresholds": {
        "wet":        DEFAULT_WET_THRESHOLD,
        "dry":        DEFAULT_DRY_THRESHOLD
    },
    "toggles": {
        "uv_auto":    DEFAULT_UV_AUTO_MODE,
        "sms_cycle":  DEFAULT_SMS_EVERY_CYCLE
    },
    "sms_recipient":  "",
    "sms_api_key":    "",
    "slots": {
        str(i): {"label": None, "confidence": None, "last_scanned": None}
        for i in range(1, TOTAL_SLOTS + 1)
    },
    "system_status":  "idle",   # idle | scanning | error
    "last_cycle_at":  None,
    "all_dry_notified": False,
}


def load() -> dict:
    """Load state from disk, falling back to defaults."""
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    if not os.path.exists(STATE_FILE):
        save(DEFAULT_STATE)
        return dict(DEFAULT_STATE)
    try:
        with open(STATE_FILE, "r") as f:
            stored = json.load(f)
        # Merge with defaults so new keys are always present
        merged = dict(DEFAULT_STATE)
        merged.update(stored)
        return merged
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
