# Orchestration Plan: Dashboard UI Upgrades (Snapshots & Logs)

## Task Breakdown
The user requested three specific UI/UX enhancements while they work on hardware wiring:
1. **Inline Screenshots**: Display the latest snapshot image directly on the dashboard whenever a slot is scanned.
2. **System Log Box**: Add a real-time scrolling terminal/log window to the dashboard to track events.
3. **UI Improvements**: General polish to make the dashboard feel more premium and industrial.

## Domains & Agents
- **Frontend/UI**: `frontend-specialist`
- **Backend/API** (Firebase Syncing): `backend-specialist`
- **Testing/Verification**: `test-engineer`

---

## Proposed Implementation

### 1. Backend (`backend-specialist`)
The backend currently pushes system status and slot data to Firestore.
- **Log System**: Modify `rpi/modules/firestore_sync.py` and `rpi/scan_controller.py` to push lightweight log string messages to a `logs` document or array in Firestore whenever major events happen (e.g., "Scanning Slot 1...", "Slot 1: DRY").
- **Limit Logs**: Keep the log bounded to the last 20 events to prevent Firebase bloat.

### 2. Frontend (`frontend-specialist`)
Modify `smart-dryer-web/index.html`:
- **Snapshots**: Remove the hidden `View Snapshot` modal button. Instead, embed a physical `<img class="slot-image">` inside the Slot Card so the clothing is always visible inside the grid.
- **Log Console**: Create a dedicated new panel styled like a terminal window that listens to the Firestore `logs` and auto-scrolls bottom-up.
- **UI Polish**: Add glassmorphism borders, tighten neon glows, implement smooth transition animations for states, and reorganize controls.

### 3. Verification (`test-engineer`)
- Validate the new UI logic.
- Verify `pylint` on backend modifications.

---

## Open Questions for User
1. Do you want the **Snapshot Images** to replace the modal completely and just show on the slot cards?
2. Are you okay with the **Log Box** sitting right below the slots?
