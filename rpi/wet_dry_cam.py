import cv2
import time
from ultralytics import YOLO

# Path to your trained model
MODEL_PATH = "runs/detect/train2/weights/best.pt"
CAM_INDEX = 0
WIDTH = 640
HEIGHT = 480
TARGET_FPS = 30
IMG_SIZE = 320  # smaller = faster

def main():
    # 1) Load custom YOLO model
    model = YOLO(MODEL_PATH)

    # 2) Open webcam
    cap = cv2.VideoCapture(CAM_INDEX)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, TARGET_FPS)

    if not cap.isOpened():
        print("Camera not opened")
        return

    prev_time = time.time()

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        # 3) Run inference
        results = model(frame, imgsz=IMG_SIZE, verbose=False)

        # 4) Decide WET or DRY
        wet_detected = False
        for r in results:
            if r.boxes is not None and len(r.boxes) > 0:
                wet_detected = True
                # Draw boxes on frame
                for box in r.boxes:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    conf = box.conf[0].item()
                    cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 0, 255), 2)
                    cv2.putText(frame, f"WET {conf:.2f}", (int(x1), int(y1) - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

        status = "WET" if wet_detected else "DRY"
        print(status)

        # 5) Overlay status on frame
        color = (0, 0, 255) if wet_detected else (0, 255, 0)
        cv2.putText(frame, f"Status: {status}", (10, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, color, 3)

        # 6) Show FPS
        curr_time = time.time()
        fps = 1.0 / (curr_time - prev_time + 1e-9)
        prev_time = curr_time
        cv2.putText(frame, f"FPS: {fps:.1f}", (10, 80),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        cv2.imshow("Wet/Dry Detector", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
