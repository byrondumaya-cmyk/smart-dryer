



























K#!/bin/bash

cd ~/Desktop/wet_dry_yolo
source yenv/bin/activate
pip install requests numpy opencv-python Pillow pyserial -q

cat << 'PYEOF' > firebase_detect.py
#!/usr/bin/env python3
"""
Wet/Dry Detector - Optimized
- Images loaded ONCE at startup only
- Sensor metadata reloaded every 60s (lightweight)
- No memory overload
"""

import cv2
import numpy as np
import requests
import time
import threading
import serial
import urllib.request
import gc

# ── Config ─────────────────────────────────────────────────
FIREBASE_PROJECT  = "ehubtest-51d0a"
FIRESTORE_URL     = f"https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT}/databases/(default)/documents/training_images"

CAMERA_INDEX      = 0
FRAME_WIDTH       = 1280
FRAME_HEIGHT      = 720
ROTATE_MODE       = cv2.ROTATE_90_COUNTERCLOCKWISE
WINDOW_NAME       = "Wet/Dry Detector"
ANALYSIS_INTERVAL = 3
SENSOR_RELOAD     = 30   # reload sensor ranges only (lightweight)

SERIAL_PORT       = "/dev/tty.usbserial-143340"
SERIAL_BAUD       = 9600

# Weights — sensor is more reliable
W_SENSOR = 0.6
W_KNN    = 0.4

# ── Global sensor state ────────────────────────────────────
sensor_temp = None
sensor_hum  = None
sensor_lock = threading.Lock()
serial_ok   = False

# ── Serial reader thread ───────────────────────────────────
def serial_reader():
    global sensor_temp, sensor_hum, serial_ok
    print(f"[SERIAL] Connecting to {SERIAL_PORT}...")
    try:
        ser = serial.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=2)
        serial_ok = True
        print(f"[SERIAL] ✅ Arduino connected!")
        while True:
            try:
                raw = ser.readline().decode("utf-8", errors="ignore").strip()
                if not raw:
                    continue
                if raw.startswith("DHT22:"):
                    parts = raw.replace("DHT22:","").replace("C,","|").replace("%","").split("|")
                    if len(parts) == 2:
                        with sensor_lock:
                            sensor_temp = float(parts[0])
                            sensor_hum  = float(parts[1])
            except Exception:
                time.sleep(1)
    except serial.SerialException as e:
        serial_ok = False
        print(f"[SERIAL] ❌ {e}")
        print("[SERIAL] Running without sensor")

# ── Fetch ONLY metadata from Firebase (no images) ─────────
def fetch_metadata():
    try:
        all_docs = []
        url = FIRESTORE_URL + "?pageSize=300"
        while url:
            res  = requests.get(url, timeout=10)
            data = res.json()
            all_docs.extend(data.get("documents", []))
            token = data.get("nextPageToken")
            url   = (FIRESTORE_URL + "?pageSize=300&pageToken=" + token) if token else None

        samples = []
        for doc in all_docs:
            f     = doc.get("fields", {})
            label = f.get("label", {}).get("stringValue", "")
            furl  = f.get("url",   {}).get("stringValue", "")
            sensor = None
            sm = f.get("sensor", {}).get("mapValue", {}).get("fields", {})
            if sm:
                t = sm.get("temp", {}).get("doubleValue") or sm.get("temp", {}).get("integerValue")
                h = sm.get("hum",  {}).get("doubleValue") or sm.get("hum",  {}).get("integerValue")
                if t and h:
                    sensor = {"temp": float(t), "hum": float(h)}
            if label and furl:
                samples.append({"label": label, "url": furl, "sensor": sensor})
        return samples
    except Exception as e:
        print(f"[FIREBASE] Error: {e}")
        return []

# ── Compute sensor ranges from metadata ───────────────────
def compute_ranges(samples):
    wet_s = [s for s in samples if s["label"]=="WET" and s["sensor"]]
    dry_s = [s for s in samples if s["label"]=="DRY" and s["sensor"]]
    ranges = {}
    if wet_s:
        wh = [s["sensor"]["hum"] for s in wet_s]
        ranges["wet"] = {
            "hum_avg": sum(wh)/len(wh),
            "hum_min": min(wh),
            "hum_max": max(wh),
            "count":   len(wet_s)
        }
    if dry_s:
        dh = [s["sensor"]["hum"] for s in dry_s]
        ranges["dry"] = {
            "hum_avg": sum(dh)/len(dh),
            "hum_min": min(dh),
            "hum_max": max(dh),
            "count":   len(dry_s)
        }
    print("\n[LEARNED RANGES]")
    if "wet" in ranges:
        r = ranges["wet"]
        print(f"  WET hum: {r['hum_min']:.1f}–{r['hum_max']:.1f}%  avg={r['hum_avg']:.1f}%  n={r['count']}")
    if "dry" in ranges:
        r = ranges["dry"]
        print(f"  DRY hum: {r['hum_min']:.1f}–{r['hum_max']:.1f}%  avg={r['hum_avg']:.1f}%  n={r['count']}")
    return ranges

# ── Load image features ONCE ───────────────────────────────
def extract_features(img):
    img_r = cv2.resize(img, (64, 64))   # smaller = faster + less memory
    grey  = cv2.cvtColor(img_r, cv2.COLOR_BGR2GRAY)
    mb    = float(np.mean(grey)) / 255
    sb    = float(np.std(grey))  / 255
    dr    = float(np.sum(grey < 80) / grey.size)
    hsv   = cv2.cvtColor(img_r, cv2.COLOR_BGR2HSV)
    ms    = float(np.mean(hsv[:,:,1])) / 255
    mv    = float(np.mean(hsv[:,:,2])) / 255
    hist  = cv2.calcHist([grey],[0],None,[8],[0,256])
    hist  = cv2.normalize(hist, hist).flatten().tolist()
    return np.array([mb, sb, dr, ms, mv] + hist, dtype=np.float32)

def load_features_once(samples):
    print(f"\n[kNN] Loading {len(samples)} images ONCE...")
    training = []
    for i, s in enumerate(samples):
        try:
            req = urllib.request.Request(s["url"],
                  headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as r:
                arr = np.frombuffer(r.read(), dtype=np.uint8)
            img  = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is not None:
                feat = extract_features(img)
                training.append({"label": s["label"], "features": feat})
                print(f"  [{i+1}/{len(samples)}] {s['label']} ✓")
                del img, arr  # free memory immediately
        except Exception:
            print(f"  [{i+1}/{len(samples)}] {s['label']} ✗")
        gc.collect()   # force garbage collection each image

    wet = sum(1 for t in training if t["label"]=="WET")
    dry = sum(1 for t in training if t["label"]=="DRY")
    print(f"[kNN] ✅ Ready — {len(training)} features ({wet}W/{dry}D)")
    return training

# ── Votes ──────────────────────────────────────────────────
def sensor_vote(hum, ranges):
    if hum is None:
        return "NO SENSOR", 0.0
    if not ranges or ("wet" not in ranges and "dry" not in ranges):
        return ("WET", 0.6) if hum >= 70 else ("DRY", 0.6)

    # Use learned ranges
    if "wet" in ranges and "dry" in ranges:
        wet_avg = ranges["wet"]["hum_avg"]
        dry_avg = ranges["dry"]["hum_avg"]
        dry_max = ranges["dry"]["hum_max"]
        wet_min = ranges["wet"]["hum_min"]

        # Clearly above DRY zone = WET
        if hum > dry_max:
            conf = min(0.5 + (hum - dry_max) / 30, 1.0)
            return "WET", round(conf, 2)

        # Clearly below WET zone = DRY
        if hum < wet_min:
            conf = min(0.5 + (wet_min - hum) / 30, 1.0)
            return "DRY", round(conf, 2)

        # Between zones — nearest average wins
        dw = abs(hum - wet_avg)
        dd = abs(hum - dry_avg)
        lb = "WET" if dw < dd else "DRY"
        cf = min(0.5 + abs(dw - dd) / 50, 1.0)
        return lb, round(cf, 2)

    if "wet" in ranges:
        return ("WET", 0.7) if hum >= ranges["wet"]["hum_avg"] else ("DRY", 0.6)
    if "dry" in ranges:
        return ("DRY", 0.7) if hum <= ranges["dry"]["hum_avg"] else ("WET", 0.6)

    return ("WET", 0.6) if hum >= 70 else ("DRY", 0.6)

def knn_vote(frame, training):
    if not training:
        return "NO DATA", 0.0
    feat  = extract_features(frame)
    dists = sorted(
        [(float(np.linalg.norm(feat - t["features"])), t["label"]) for t in training],
        key=lambda x: x[0]
    )
    k   = min(5, len(dists))
    top = dists[:k]
    wv  = sum(1 for d,l in top if l=="WET")
    dv  = sum(1 for d,l in top if l=="DRY")
    lb  = "WET" if wv > dv else "DRY"
    cf  = max(wv, dv) / k
    return lb, round(cf, 2)

def weighted_vote(sl, sc, kl, kc):
    wet = dry = 0.0
    if sl == "WET":   wet += W_SENSOR * sc
    elif sl == "DRY": dry += W_SENSOR * sc
    if kl == "WET":   wet += W_KNN * kc
    elif kl == "DRY": dry += W_KNN * kc
    total = wet + dry
    if total == 0: return "UNCERTAIN", 0.0, wet, dry
    lb = "WET" if wet > dry else "DRY"
    cf = max(wet, dry) / total
    return lb, round(cf, 2), round(wet, 3), round(dry, 3)

def print_result(final, conf, ws, ds, sl, sc, kl, kc, temp, hum):
    bar   = "█" * int(conf * 20)
    empty = "░" * (20 - int(conf * 20))
    print(f"\n  ╔═══════════════════════════════════════════╗")
    print(f"  ║  FINAL : {final:<6} [{bar}{empty}] {conf:.0%}  ║")
    print(f"  ╠═══════════════════════════════════════════╣")
    print(f"  ║  SENSOR ({W_SENSOR*100:.0f}%wt): {sl:<4} conf={sc:.0%}{'':<15}║")
    print(f"  ║  kNN   ({W_KNN*100:.0f}%wt): {kl:<4} conf={kc:.0%}{'':<15}║")
    if temp:
        print(f"  ║  DHT22 : {temp:.1f}°C  {hum:.1f}% humidity{'':<10}║")
    print(f"  ║  SCORE : WET={ws}  DRY={ds}{'':<17}║")
    print(f"  ╚═══════════════════════════════════════════╝")

# ── MAIN ───────────────────────────────────────────────────
def main():
    print("=" * 55)
    print("  WET/DRY DETECTOR — Optimized (no memory overload)")
    print(f"  Sensor weight: {W_SENSOR*100:.0f}%  |  kNN weight: {W_KNN*100:.0f}%")
    print("=" * 55)

    # 1) Start serial thread
    t = threading.Thread(target=serial_reader, daemon=True)
    t.start()
    time.sleep(2)

    # 2) Fetch metadata + compute ranges
    samples       = fetch_metadata()
    sensor_ranges = compute_ranges(samples)

    if not samples:
        print("[ERROR] No training data found!")
        return

    # 3) Load image features ONCE — never reload images again
    training = load_features_once(samples)
    gc.collect()

    # 4) Open webcam
    cap = cv2.VideoCapture(CAMERA_INDEX)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, 30)

    if not cap.isOpened():
        print("[ERROR] Cannot open webcam!")
        return

    print(f"\n[INFO] Ready! {len(training)} images loaded")
    print(f"[INFO] Sensor: {'✅ Connected' if serial_ok else '❌ Not connected (sensor vote disabled)'}")
    print("=" * 55)
    print("  T = Analyze   R = Refresh sensor ranges   Q = Quit")
    print("=" * 55)

    last_result  = {"final": "WAITING", "conf": 0.0}
    last_analyze = 0
    last_sreload = time.time()
    frame_count  = 0
    prev_time    = time.time()

    while True:
        ok, frame = cap.read()
        if not ok:
            continue

        frame   = cv2.rotate(frame, ROTATE_MODE)
        display = frame.copy()
        now     = time.time()
        fps     = 1.0 / max(now - prev_time, 1e-6)
        prev_time = now
        h, w    = display.shape[:2]

        with sensor_lock:
            cur_temp = sensor_temp
            cur_hum  = sensor_hum

        # Reload ONLY sensor ranges every 30s (lightweight - no images)
        if now - last_sreload >= SENSOR_RELOAD:
            new_samples   = fetch_metadata()
            sensor_ranges = compute_ranges(new_samples)
            last_sreload  = now

        force = (now - last_analyze >= ANALYSIS_INTERVAL)

        final = last_result.get("final", "WAITING")
        conf  = last_result.get("conf", 0.0)
        color = (0,0,255) if final=="WET" else (0,200,0) if final=="DRY" else (200,200,0)

        cv2.putText(display, f"Status: {final}", (10,45),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.3, color, 3)
        if final in ("WET","DRY"):
            cv2.putText(display, f"Confidence: {conf:.0%}", (10,85),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

        s_str = f"{cur_temp:.1f}C  {cur_hum:.1f}%" if cur_temp else "No sensor"
        s_col = (150,220,255) if cur_temp else (80,80,80)
        cv2.putText(display, f"Sensor: {s_str}", (10,h-60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, s_col, 1)
        cv2.putText(display,
                    f"kNN:{len(training)} samples | FPS:{fps:.1f}",
                    (10,h-35), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (120,120,120), 1)
        cv2.putText(display,
                    "T=analyze  R=refresh ranges  Q=quit",
                    (10,h-15), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (80,80,80), 1)

        frame_count += 1
        if frame_count % 90 == 0:  # print every 3 seconds not every second
            print(f"  [{final}] {conf:.0%} | {s_str}")

        cv2.imshow(WINDOW_NAME, display)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        elif key == ord("t") or key == ord("T"):
            force = True
        elif key == ord("r") or key == ord("R"):
            print("[REFRESH] Updating sensor ranges from Firebase...")
            new_samples   = fetch_metadata()
            sensor_ranges = compute_ranges(new_samples)
            last_sreload  = now

        if force:
            with sensor_lock:
                cur_temp = sensor_temp
                cur_hum  = sensor_hum

            sl, sc         = sensor_vote(cur_hum, sensor_ranges)
            kl, kc         = knn_vote(frame, training)
            final, conf, ws, ds = weighted_vote(sl, sc, kl, kc)
            last_result    = {"final": final, "conf": conf}
            last_analyze   = now
            print_result(final, conf, ws, ds, sl, sc, kl, kc, cur_temp, cur_hum)

    cap.release()
    cv2.destroyAllWindows()
    gc.collect()
    print("[INFO] Done.")

if __name__ == "__main__":
    main()
PYEOF

echo ""
echo "================================================"
echo "  Wet/Dry Detector — Optimized"
echo "  Sensor: /dev/tty.usbserial-143340"
echo "  Sensor weight: 60%  |  kNN weight: 40%"
echo "================================================"
echo ""

python3 firebase_detect.py
