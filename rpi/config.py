# config.py - Smart Dryer System Configuration
# All hardware and system settings in one place.

import os

# --- GPIO Pin Assignments (BCM numbering) ---
# L298N DC Motor Driver
GPIO_PINS = {
    'motor_in1': 23,       # L298N IN1 - direction control
    'motor_in2': 24,       # L298N IN2 - direction control
    'motor_en':  18,       # L298N ENA - PWM speed (hardware PWM pin)
    'limit_home': 25,      # Limit switch - active LOW when pressed (pull-up)
    'relay_uv':  16,       # UV sterilization relay - active LOW module
    'buzzer':    12,       # Active/passive buzzer
}

# --- 5 Fixed Drying Slots + 1 DHT Sensor Per Slot ---
SLOT_SENSOR_MAP = {
    1: {'gpio': 4,  'model': 'DHT22', 'label': 'Slot 1'},
    2: {'gpio': 17, 'model': 'DHT22', 'label': 'Slot 2'},
    3: {'gpio': 27, 'model': 'DHT22', 'label': 'Slot 3'},
    4: {'gpio': 22, 'model': 'DHT11', 'label': 'Slot 4'},
    5: {'gpio': 5,  'model': 'DHT11', 'label': 'Slot 5'},
}

# --- Motor (L298N DC) Calibration ---
# Time (ms) of travel for each segment.
# Absolute slot position is calculated by summing segments from home.
DEFAULT_MOTOR_SEGMENTS = {
    'home_to_s1': 800,
    's1_to_s2': 800,
    's2_to_s3': 800,
    's3_to_s4': 800,
    's4_to_s5': 800,
}
MOTOR_PWM_FREQ      = 1000    # Hz - PWM carrier frequency for ENA pin
MOTOR_PWM_SPEED     = 75      # Duty cycle 0-100 (75% = safe operating speed)

# --- Local Control Configurations (V2) ---
DEFAULT_MOTOR_HOME_TIMEOUT = 10.0       # Seconds before homing gives up
DEFAULT_DWELL_TIME = 5                  # seconds to wait at slot before reading
DEFAULT_SENSOR_WEIGHT = 0.60            # 60% importance
DEFAULT_IMAGE_WEIGHT = 0.40             # 40% importance
DEFAULT_WET_THRESHOLD = 80.0            # humidity >= 80 means stable WET
DEFAULT_DRY_THRESHOLD = 75.0            # humidity <= 75 means stable DRY

# Automation defaults
DEFAULT_UV_AUTO_MODE = False            # Auto-on UV when all clothes are dry?
DEFAULT_UV_AUTO_OFF_MINUTES = 15        # Turn off UV automatically after X minutes
DEFAULT_SMS_EVERY_CYCLE = False         # False = only send SMS when newly ALL DRY

# AI Model
MODEL_PATH = "models/best.pt"           # Local YOLOv8 path

# Buzzer States Enumeration
BUZZER_STATES = [
    "system_started", "homing_started", "homing_success", "homing_timeout_or_error",
    "moving_to_slot", "slot_reached", "slot_scan_started", "slot_scan_complete",
    "cycle_started", "cycle_complete", "all_dry", "not_all_dry",
    "sms_sent", "sms_failed", "uv_on", "uv_off", "generic_error"
]

# --- Scan & Decision Logic ---
TOTAL_SLOTS                   = 5
DEFAULT_SCAN_INTERVAL_SECONDS = 300   # 5 minutes
MIN_SCAN_INTERVAL_SECONDS     = 60
MAX_SCAN_INTERVAL_SECONDS     = 3600

# --- DHT Sensor ---
DHT_READ_INTERVAL = 10   # Seconds between full 5-sensor poll cycles


# --- SMS (Semaphore PH) ---
SMS_SENDER  = "Thesis"               # Approved Semaphore sender name
SMS_API_URL = "https://api.semaphore.co/api/v4/messages"

# --- Flask API ---
API_HOST = "0.0.0.0"
API_PORT = 5000
DEBUG    = False

# --- State Persistence ---
STATE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data", "state.json"
)
