# Smart Dryer — Raspberry Pi Control System

Raspberry Pi Python backend for the Smart Drying Rack system.

## Structure
```
rpi/
├── main.py               # Entry point (run this on the Pi)
├── server.py             # Flask REST API + SSE stream
├── scan_controller.py    # Core scan loop + Firestore command handler
├── state_store.py        # JSON persistence
├── config.py             # All GPIO pins + system settings
├── requirements.txt      # pip dependencies
├── smart-dryer.service   # systemd service file
├── ai/
│   └── classifier.py     # YOLOv8 via Firebase Storage (downloads best.pt on first boot)
└── modules/
    ├── motor.py           # L298N DC motor (time-based, GPIO 18/23/24/25)
    ├── sensor.py          # 5x DHT sensor array (GPIO 4/17/27/22/5)
    ├── buzzer.py          # Buzzer patterns (GPIO 12)
    ├── relay.py           # UV sterilization relay (GPIO 16, active-LOW)
    ├── sms.py             # Semaphore SMS (API key stored locally on Pi only)
    └── firestore_sync.py  # Firebase Firestore + Storage sync
```

## Setup on Raspberry Pi
```bash
cd rpi/
pip install -r requirements.txt --break-system-packages
# Place serviceAccountKey.json in this rpi/ directory
python main.py
```

## GPIO Pin Map
| Pin | Function |
|-----|----------|
| GPIO 18 | L298N ENA (PWM speed) |
| GPIO 23 | L298N IN1 (direction) |
| GPIO 24 | L298N IN2 (direction) |
| GPIO 25 | Limit switch (home, active LOW) |
| GPIO 16 | UV relay (active LOW) |
| GPIO 12 | Buzzer |
| GPIO 4  | DHT22 Slot 1 |
| GPIO 17 | DHT22 Slot 2 |
| GPIO 27 | DHT11 Slot 3 |
| GPIO 22 | DHT11 Slot 4 |
| GPIO 5  | DHT22 Slot 5 |
