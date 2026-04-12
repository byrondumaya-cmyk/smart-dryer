# ai/classifier.py — Firebase-hosted YOLOv8 Classifier
#
# Flow:
#   1. On first call: download best.pt from Firebase Storage → ai/model_cache/
#   2. Load model with ultralytics YOLO (runs locally on Pi)
#   3. classify(frame) → {"label": "DRY"|"WET", "confidence": float}
#
# The model file lives in Firebase Storage at: models/best.pt
# Authentication requires serviceAccountKey.json in the project root.
#
# To update the model remotely:
#   1. Upload new best.pt to Firebase Storage → models/best.pt
#   2. Delete ai/model_cache/best.pt on the Pi
#   3. Restart the service — it re-downloads automatically

import os
import logging

from config import FIREBASE_STORAGE_BUCKET, FIREBASE_MODEL_PATH, MODEL_CACHE_PATH

logger = logging.getLogger(__name__)

_model       = None
_initialized = False   # Attempt init once per process


def _init_model() -> bool:
    global _model, _initialized
    if _initialized:
        return _model is not None
    _initialized = True

    # ── Ensure cache directory exists ─────────────────────────────────────────
    os.makedirs(os.path.dirname(MODEL_CACHE_PATH), exist_ok=True)

    # ── Download from Firebase Storage if not cached ──────────────────────────
    if not os.path.exists(MODEL_CACHE_PATH):
        logger.info(
            f"Model not cached. Downloading from Firebase Storage: "
            f"{FIREBASE_STORAGE_BUCKET}/{FIREBASE_MODEL_PATH}"
        )
        if not _download_model():
            logger.error("Model download failed — classifier unavailable.")
            return False
    else:
        logger.info(f"Using cached model: {MODEL_CACHE_PATH}")

    # ── Load YOLO ─────────────────────────────────────────────────────────────
    try:
        from ultralytics import YOLO
        _model = YOLO(MODEL_CACHE_PATH)
        logger.info("YOLOv8 model loaded successfully.")
        return True
    except Exception as e:
        logger.error(f"YOLO load failed: {e}")
        return False


def _download_model() -> bool:
    """Download best.pt from Firebase Storage via Admin SDK."""
    # Service account key must be at project root
    key_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), '..', 'serviceAccountKey.json'
    )
    key_path = os.path.normpath(key_path)

    if not os.path.exists(key_path):
        logger.error(
            f"serviceAccountKey.json not found at {key_path}. "
            "Download from Firebase Console → Project Settings → "
            "Service Accounts → Generate new private key."
        )
        return False

    try:
        import firebase_admin
        from firebase_admin import credentials, storage

        if not firebase_admin._apps:
            cred = credentials.Certificate(key_path)
            firebase_admin.initialize_app(
                cred, {'storageBucket': FIREBASE_STORAGE_BUCKET}
            )

        bucket = storage.bucket()
        blob   = bucket.blob(FIREBASE_MODEL_PATH)
        blob.download_to_filename(MODEL_CACHE_PATH)
        size_mb = os.path.getsize(MODEL_CACHE_PATH) / (1024 * 1024)
        logger.info(f"Model downloaded: {MODEL_CACHE_PATH} ({size_mb:.1f} MB)")
        return True

    except Exception as e:
        logger.error(f"Firebase download error: {e}")
        # Clean up partial download
        if os.path.exists(MODEL_CACHE_PATH):
            os.remove(MODEL_CACHE_PATH)
        return False


def classify(frame) -> dict:
    """
    Classify a camera frame as DRY or WET.

    Args:
        frame: numpy array (BGR) — OpenCV frame.

    Returns:
        {"label": "DRY"|"WET", "confidence": float, "simulated": bool}
    """
    if not _init_model() or _model is None:
        logger.warning("Classifier unavailable — returning fallback result.")
        return {"label": "DRY", "confidence": 0.0, "simulated": True}

    try:
        results    = _model(frame, verbose=False)
        top_idx    = int(results[0].probs.top1)
        confidence = float(results[0].probs.top1conf)
        label      = results[0].names[top_idx].upper()
        return {"label": label, "confidence": confidence, "simulated": False}
    except Exception as e:
        logger.error(f"Inference error: {e}")
        return {"label": "DRY", "confidence": 0.0, "simulated": True}
