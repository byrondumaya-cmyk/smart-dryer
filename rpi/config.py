# config.py — Smart Dryer System Configuration
# All hardware and system settings in one place.

import os

# ── GPIO Pin Assignments (BCM numbering) ──────────────────────────────────────
# L298N DC Motor Driver
GPIO_PINS = {
    'motor_in1': 23,       # L298N IN1 — direction control
    'motor_in2': 24,       # L298N IN2 — direction control
    'motor_en':  18,       # L298N ENA — PWM speed (hardware PWM pin)
    'limit_home': 25,      # Limit switch — active LOW when pressed (pull-up)
    'relay_uv':  16,       # UV sterilization relay — active LOW module
    'buzzer':    12,       # Active/passive buzzer
}

# ── 5 Fixed Drying Slots → 1 DHT Sensor Per Slot ──────────────────────────────
SLOT_SENSOR_MAP = {
    1: {'gpio': 4,  'model': 'DHT22', 'label': 'Slot 1'},
    2: {'gpio': 17, 'model': 'DHT22', 'label': 'Slot 2'},
    3: {'gpio': 27, 'model': 'DHT11', 'label': 'Slot 3'},
    4: {'gpio': 22, 'model': 'DHT11', 'label': 'Slot 4'},
    5: {'gpio': 5,  'model': 'DHT22', 'label': 'Slot 5'},
}

# ── Motor (L298N DC) Calibration ──────────────────────────────────────────────
# Time (ms) from home position to reach each slot center.
# Adjust per your actual hardware via the dashboard calibration tool.
DEFAULT_SLOT_STEPS = {
    1: 0,       # home
    2: 800,
    3: 1600,
    4: 2400,
    5: 3200,
}

MOTOR_PWM_FREQ      = 1000    # Hz — PWM carrier frequency for ENA pin
MOTOR_PWM_SPEED     = 75      # Duty cycle 0–100 (75% = safe operating speed)
MOTOR_HOME_TIMEOUT  = 10.0    # Seconds before homing gives up

# ── Scan Settings ─────────────────────────────────────────────────────────────
TOTAL_SLOTS                  = 5
DEFAULT_SCAN_INTERVAL_SECONDS = 300   # 5 minutes
MIN_SCAN_INTERVAL_SECONDS     = 60
MAX_SCAN_INTERVAL_SECONDS     = 3600

# ── DHT Sensor ────────────────────────────────────────────────────────────────
DHT_READ_INTERVAL = 10   # Seconds between full 5-sensor poll cycles

# ── Firebase (project: ehubtest-51d0a) ────────────────────────────────────────
# Service account key must be placed at: <project_root>/serviceAccountKey.json
# Download from: Firebase Console → Project Settings → Service Accounts →
#                Generate new private key
FIREBASE_PROJECT_ID    = "ehubtest-51d0a"
FIREBASE_STORAGE_BUCKET = "ehubtest-51d0a.firebasestorage.app"
FIREBASE_MODEL_PATH    = "models/best.pt"        # Path inside Firebase Storage
MODEL_CACHE_PATH       = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "ai", "model_cache", "best.pt"
)

# Firestore collection / document names (matches dashboard expectations)
FIRESTORE_COL_SYSTEM   = "system"
FIRESTORE_COL_COMMANDS = "commands"
FIRESTORE_COL_HISTORY  = "scan_history"
FIRESTORE_STORAGE_SNAP = "snapshots"   # Firebase Storage prefix for snapshots

# ── SMS (Semaphore PH) ────────────────────────────────────────────────────────
SMS_API_URL = "https://api.semaphore.co/api/v4/messages"
SMS_API_KEY = "YOUR_API_KEY_HERE"   # Override via dashboard
SMS_SENDER  = "SmartDryer"

# ── Flask API ─────────────────────────────────────────────────────────────────
API_HOST = "0.0.0.0"
API_PORT = 5000
DEBUG    = False

# ── State Persistence ─────────────────────────────────────────────────────────
STATE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data", "state.json"
)
