# state_store.py — Persistent JSON state
#
# Saves and loads system state to/from data/state.json.
# All modules share this for persistence across reboots.

import json
import os
import logging
import threading

from config import STATE_FILE, DEFAULT_SLOT_STEPS, DEFAULT_SCAN_INTERVAL_SECONDS, TOTAL_SLOTS

logger = logging.getLogger(__name__)
_lock = threading.Lock()

DEFAULT_STATE = {
    "scan_interval":  DEFAULT_SCAN_INTERVAL_SECONDS,
    "slot_steps":     {str(k): v for k, v in DEFAULT_SLOT_STEPS.items()},
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
