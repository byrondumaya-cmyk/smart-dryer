import cv2
import time
import sys

def test_camera(index=0):
    print(f"--- Testing Camera Index {index} ---")
    cap = cv2.VideoCapture(index)
    
    if not cap.isOpened():
        print(f"Error: Could not open camera {index}.")
        return False

    # Try to set MJPG
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    
    print("Camera opened. Waiting for frame...")
    time.sleep(2)  # Warm up
    
    ret, frame = cap.read()
    if ret:
        print(f"Success! Captured frame of size {frame.shape[1]}x{frame.shape[0]}")
        cv2.imwrite(f"test_camera_{index}.jpg", frame)
    else:
        print("Failed to capture frame.")
    
    cap.release()
    return ret

if __name__ == "__main__":
    indices = [0, 1, 2]
    if len(sys.argv) > 1:
        indices = [int(sys.argv[1])]
        
    for i in indices:
        if test_camera(i):
            print(f"Camera {i} is WORKING.")
            break
        print("-" * 30)
