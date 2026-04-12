import os
import cv2
import logging
from ultralytics import YOLO

logger = logging.getLogger(__name__)

# Try to use the trained model under runs/detect, fallback to basic YOLO
_trained_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "runs", "detect", "train2", "weights", "best.pt")
_fallback_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "yolo11n.pt")

if os.path.exists(_trained_path):
    MODEL_PATH = _trained_path
else:
    MODEL_PATH = _fallback_path

_model = None

def get_model():
    global _model
    if _model is None:
        logger.info(f"Loading YOLO model from {MODEL_PATH} ...")
        # Load the custom YOLO model silently
        _model = YOLO(MODEL_PATH)
    return _model

def classify(frame) -> dict:
    model = get_model()
    # Lower imgsz for faster CPU execution
    results = model(frame, imgsz=320, verbose=False)
    
    wet_detected = False
    highest_conf = 0.0

    for r in results:
        if r.boxes is not None and len(r.boxes) > 0:
            wet_detected = True
            for box in r.boxes:
                conf = box.conf[0].item()
                if conf > highest_conf:
                    highest_conf = conf

    # If no boxes detected, fallback to 60% confidence DRY assumed
    if highest_conf == 0.0:
        highest_conf = 0.6
        
    return {
        "label": "WET" if wet_detected else "DRY",
        "confidence": highest_conf,
        "simulated": False
    }
