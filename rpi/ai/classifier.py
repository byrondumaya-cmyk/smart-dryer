import os
import cv2
import logging
from ultralytics import YOLO

logger = logging.getLogger(__name__)

# The new config path handling
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from config import MODEL_PATH
except ImportError:
    MODEL_PATH = "models/best.pt"

_model = None
_model_available = True

def get_model():
    global _model, _model_available
    if not _model_available:
        return None
        
    if _model is None:
        # Full absolute path resolution
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        abs_model_path = os.path.join(base_dir, "rpi", MODEL_PATH)
        
        if not os.path.exists(abs_model_path):
            logger.error(f"[AI] Local classification model NOT FOUND at {abs_model_path}")
            logger.warning("[AI] System will gracefully degrade to SENSOR-ONLY logic.")
            _model_available = False
            return None
            
        try:
            logger.info(f"[AI] Loading YOLO classification model from {abs_model_path} ...")
            _model = YOLO(abs_model_path)
        except Exception as e:
            logger.error(f"[AI] Failed to load YOLO model: {e}")
            _model_available = False
            return None
            
    return _model

def classify(frame) -> dict:
    """
    Returns dict: { "label": "WET" | "DRY" | "EMPTY" | "UNKNOWN", "confidence": float }
    """
    model = get_model()
    if model is None:
        # Fallback if model is missing
        return {"label": "UNKNOWN", "confidence": 0.0}

    try:
        # standard classification imgsz is often 224
        results = model(frame, imgsz=224, verbose=False)
        
        if not results or len(results) == 0:
            return {"label": "UNKNOWN", "confidence": 0.0}
            
        r = results[0]
        
        # Ensure model is a classification model outputting probabilities
        if not hasattr(r, 'probs') or r.probs is None:
            logger.error("[AI] Model did not return classification 'probs'. It heavily seems to be a detection model. Retrain/Export properly.")
            return {"label": "UNKNOWN", "confidence": 0.0}
            
        # Extract Top-1 class
        top1_idx = r.probs.top1
        top1_conf = r.probs.top1conf.item()
        
        label_map = r.names
        detected_name = label_map.get(top1_idx, "UNKNOWN").upper()
        
        # Coerce to our expected outputs based on substring matching
        if "WET" in detected_name:
            final_label = "WET"
        elif "DRY" in detected_name:
            final_label = "DRY"
        elif "EMPTY" in detected_name or "NO CLOTHES" in detected_name:
            final_label = "EMPTY"
        else:
            final_label = "UNKNOWN"
            
        return {
            "label": final_label,
            "confidence": top1_conf
        }
            
    except Exception as e:
        logger.error(f"[AI] Inference error: {e}")
        return {"label": "UNKNOWN", "confidence": 0.0}
