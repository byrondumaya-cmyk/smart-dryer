# Orchestration Plan: Local-First Smart Drying Rack (Revised)

## Goal
Enhance the existing Smart Dryer system into a robust, local-first architecture. This involves implementing explicit weighted sensor/image decision math, segment-based motor movement, comprehensive buzzer feedback, resilient camera sharing, UV/SMS automation toggles, and an MJPEG live feed—while seamlessly stripping out obsolete cloud dependencies.

## Domains & Agents
- **Planning**: `project-planner` (Current Phase)
- **Backend/API (Local-First Transition)**: `backend-specialist` (Phase 2)
- **Frontend/UI**: `frontend-specialist` (Phase 2)

---

## Proposed Implementation

### 1. Removing Cloud Dependencies & Local API Setup
- **Local API Engine**: Modify the existing Flask `server.py` to act as the primary REST/WebSocket bridge.
- **Cleanup List**: 
  - Delete `rpi/modules/firestore_sync.py`
  - Remove all Firebase dependencies/imports in `rpi/config.py`, `rpi/main.py`, and `smart-dryer-web/index.html`.

### 2. Local Model Handling (`best.pt`)
- **Config**: Set `MODEL_PATH = "models/best.pt"` locally.
- **Validation**: At startup (`main.py` environment check), verify the file exists. If missing, log a clear warning, set a flag, and gracefully bypass AI inference (always return `UNKNOWN` or fallback to sensor-only) rather than crashing. Update `.gitignore` to ignore the `models/` folder.

### 3. Explicit Scoring & Weighted Decision Logic
- **Image Score Conversion**: 
  - `image_dry_score` = `confidence` (if label is DRY)
  - `image_dry_score` = `1.0 - confidence` (if label is WET)
- **Sensor Score Conversion (Hysteresis)**:
  - If `humidity >= wet_threshold` (default 80): state = WET, `sensor_dry_score = 0.0`.
  - If `humidity <= dry_threshold` (default 75): state = DRY, `sensor_dry_score = 1.0`.
  - Otherwise: Keep previous state. If previous was WET, `0.0`. If DRY, `1.0`.
- **Final Decision Math**:
  - `final_dry_score = (sensor_weight * sensor_dry_score) + (image_weight * image_dry_score)`
  - Final Result: `DRY` if `final_dry_score >= 0.50`, else `WET`.

### 4. Motor Logic & Homing Safety
- **Segment Math**: Replace absolute ms arrays with segments (`home_to_s1`, `s1_to_s2`, etc.). Sum them dynamically.
- **Homing Safety (Active LOW)**: During homing, drive backward while checking `limit_home == LOW`. Implement a strict timeout (`MOTOR_HOME_TIMEOUT=15s`). If the limit is not hit in time, stop the motor, fire the `homing_timeout_or_error` buzzer pattern, and log critical failure.
- **End-of-Cycle Homing**: The scan loop will unconditionally invoke `motor.home()` at the end of every 5-slot iteration, making calibration highly repeatable.

### 5. Expanded Buzzer States & Tests
- **Backend Mapping**: Expand `buzzer.py` to support explicit states like: `system_started`, `homing_started`, `homing_success`, `homing_error`, `moving`, `cycle_started`, `cycle_complete`, `all_dry`, `sms_sent`, etc.
- **Frontend Testing**: Add a small `<select>` dropdown and "Test Buzzer" button to the dashboard for manual hardware verification.

### 6. UV / SMS Automation & Settings
- **SMS Logic**: Add format validation (09xxxxxxxxx). If `sms_every_cycle` is True, send a summary string every cycle. If False, only alert when ALL slots transition to DRY. Catch connection errors to prevent cycle crashes.
- **UV Logic**: If `uv_auto_mode` is True and ALL slots are DRY, activate UV. Implement an auto-off timer (e.g. 15 minutes) to ensure it doesn't burn indefinitely.

### 7. Resilient Camera Sharing
- **Thread-Safety**: Ensure `cv2.VideoCapture` is managed by a dedicated background thread that constantly reads frames.
- **Crash Recovery**: If the camera disconnects, the thread will attempt to re-open the node (`cv2.VideoCapture(0)`) continuously without throwing exceptions into the classification loop.

### 8. Dashboard Enhancements
- **Existing Elements**: Inject the `final_score`, `sensor_contribution`, and `image_contribution` visibly into the existing Slot Cards.
- **Simple Additions**: Add the "Live Feed" `<img src="/video_feed">` below the slots. Add Wiggle (L/R) buttons next to the Motor controls. Add the settings fields for weights, thresholds, dwell time, and phone numbers in a compact block.

---

## User Review Required

> [!IMPORTANT]
> The exact Math for deciding is now explicitly numeric and heavily values the DHT sensor when weights are 0.6 / 0.4. Do you approve of mapping `0.0` or `1.0` binary thresholds for the sensor score based on the hysteresis brackets?

## Open Questions
1. Do you approve this revised plan to proceed to Implementation Phase 2?
