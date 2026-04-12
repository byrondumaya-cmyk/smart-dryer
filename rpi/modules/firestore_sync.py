# modules/firestore_sync.py — Firestore + Firebase Storage sync for RPI
#
# Responsibilities:
#   1. Push system status, sensors, slots, config to Firestore
#   2. Upload JPEG snapshots to Firebase Storage during scans
#   3. Poll 'commands' collection and dispatch them to handlers
#
# Authentication: Uses serviceAccountKey.json in project root.
# The firebase-admin SDK is already in requirements.txt.

import os
import io
import json
import time
import logging
import threading
import datetime

logger = logging.getLogger(__name__)

_db      = None
_bucket  = None
_initted = False
_lock    = threading.Lock()

# ── Firestore collection/doc constants ────────────────────────────────────────
COL_SYSTEM  = 'system'
DOC_STATUS  = 'status'
DOC_CONFIG  = 'config'
DOC_SENSORS = 'sensors'
DOC_SLOTS   = 'slots'
COL_HISTORY = 'scan_history'
COL_COMMANDS = 'commands'

STORAGE_SNAPSHOT_PREFIX = 'snapshots'


def _init() -> bool:
    global _db, _bucket, _initted
    if _initted:
        return _db is not None

    _initted = True
    key_path = os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'serviceAccountKey.json')
    )

    if not os.path.exists(key_path):
        logger.error(
            f'serviceAccountKey.json not found at {key_path}. '
            'Firestore sync disabled.'
        )
        return False

    try:
        import firebase_admin
        from firebase_admin import credentials, firestore, storage
        from config import FIREBASE_STORAGE_BUCKET

        if not firebase_admin._apps:
            cred = credentials.Certificate(key_path)
            firebase_admin.initialize_app(cred, {'storageBucket': FIREBASE_STORAGE_BUCKET})

        _db     = firestore.client()
        _bucket = storage.bucket()
        logger.info('Firestore sync initialised.')
        return True
    except Exception as e:
        logger.error(f'Firestore init failed: {e}')
        return False


# ── Push helpers ──────────────────────────────────────────────────────────────

def _set(collection: str, document: str, data: dict, merge: bool = True):
    """Write data to Firestore (fire-and-forget, non-blocking via thread)."""
    if not _init():
        return

    def _write():
        try:
            from google.cloud.firestore_v1 import SERVER_TIMESTAMP
            data['updated_at'] = SERVER_TIMESTAMP
            _db.collection(collection).document(document).set(data, merge=merge)
        except Exception as e:
            logger.warning(f'Firestore write failed ({collection}/{document}): {e}')

    threading.Thread(target=_write, daemon=True).start()


def push_status(data: dict):
    _set(COL_SYSTEM, DOC_STATUS, data)


def push_sensors(data: dict):
    _set(COL_SYSTEM, DOC_SENSORS, data)


def push_slots(data: dict):
    _set(COL_SYSTEM, DOC_SLOTS, data)


def push_config(data: dict):
    _set(COL_SYSTEM, DOC_CONFIG, data)


def push_log(message: str, level: str = 'INFO'):
    """Push a system log message to Firestore for the frontend log console."""
    if not _init():
        return

    def _write():
        try:
            from google.cloud.firestore_v1 import SERVER_TIMESTAMP
            _db.collection('system_logs').add({
                'message': message,
                'level': level,
                'created_at': SERVER_TIMESTAMP
            })
        except Exception as e:
            logger.warning(f'Firestore log write failed: {e}')

    threading.Thread(target=_write, daemon=True).start()


def push_scan_history(slots_result: dict, all_dry: bool, sensor_snapshot: dict):
    """Add one document to scan_history collection."""
    if not _init():
        return

    def _write():
        try:
            from google.cloud.firestore_v1 import SERVER_TIMESTAMP
            _db.collection(COL_HISTORY).add({
                'timestamp':       SERVER_TIMESTAMP,
                'slots':           slots_result,
                'all_dry':         all_dry,
                'sensor_snapshot': sensor_snapshot,
            })
        except Exception as e:
            logger.warning(f'Firestore history write failed: {e}')

    threading.Thread(target=_write, daemon=True).start()


# ── Snapshot upload ───────────────────────────────────────────────────────────

def upload_snapshot(slot: int, frame) -> str | None:
    """
    Encode OpenCV frame as JPEG and upload to Firebase Storage.
    Returns the public download URL or None on failure.
    Path: snapshots/slot_{slot}/latest.jpg (overwritten each time)
    """
    if not _init():
        return None

    try:
        import cv2
        ret, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ret:
            logger.error(f'JPEG encode failed for slot {slot}')
            return None

        blob_path = f'{STORAGE_SNAPSHOT_PREFIX}/slot_{slot}/latest.jpg'
        blob      = _bucket.blob(blob_path)
        blob.upload_from_string(buf.tobytes(), content_type='image/jpeg')
        blob.make_public()
        url = blob.public_url
        logger.info(f'Snapshot uploaded for slot {slot}: {url}')
        return url
    except Exception as e:
        logger.error(f'Snapshot upload failed (slot {slot}): {e}')
        return None


# ── Command listener ──────────────────────────────────────────────────────────

_command_callback  = None
_listener_running  = False


def start_command_listener(callback):
    """
    Poll Firestore 'commands' collection for pending commands.
    callback(type, payload) is called for each.
    Runs in a background daemon thread.
    """
    global _command_callback, _listener_running
    _command_callback = callback
    if _listener_running:
        return
    _listener_running = True
    t = threading.Thread(target=_poll_commands, daemon=True, name='firestore-commands')
    t.start()
    logger.info('Firestore command listener started.')


def _poll_commands():
    if not _init():
        logger.error('Firestore unavailable — command listener disabled.')
        return

    from google.cloud.firestore_v1 import SERVER_TIMESTAMP

    while True:
        try:
            docs = (
                _db.collection(COL_COMMANDS)
                .where('status', '==', 'pending')
                .limit(5)
                .get()
            )
            for doc in docs:
                data = doc.to_dict()
                ref  = doc.reference

                # Mark processing immediately to prevent duplicate execution
                ref.update({'status': 'processing'})

                try:
                    if _command_callback:
                        _command_callback(data.get('type'), data.get('payload') or {})
                    ref.update({'status': 'done', 'processed_at': SERVER_TIMESTAMP})
                except Exception as e:
                    logger.error(f'Command execution failed ({data.get("type")}): {e}')
                    ref.update({'status': 'failed', 'error': str(e)})

        except Exception as e:
            logger.warning(f'Command poll error: {e}')

        time.sleep(3)   # Poll every 3 seconds
