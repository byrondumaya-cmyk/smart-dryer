#!/usr/bin/env python3
"""
Full Firebase Backup — Firestore + Storage
Handles 1400+ images with pagination + parallel downloads
"""

import requests
import json
import os
import datetime
import urllib.request
import urllib.parse
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# ── Config ─────────────────────────────────────────────────
PROJECT    = "ehubtest-51d0a"
BUCKET     = "ehubtest-51d0a.firebasestorage.app"
TS         = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
BACKUP_DIR = f"backup_{TS}"
IMG_DIR    = os.path.join(BACKUP_DIR, "images")
MAX_WORKERS = 8       # parallel downloads — increase if fast internet
RETRY       = 3       # retries per image on fail

os.makedirs(IMG_DIR, exist_ok=True)

print("=" * 60)
print("  FULL FIREBASE BACKUP")
print(f"  Output folder: {BACKUP_DIR}/")
print(f"  Parallel workers: {MAX_WORKERS}")
print("=" * 60)

# ══════════════════════════════════════════════════════════
# 1. FIRESTORE BACKUP
# ══════════════════════════════════════════════════════════
print("\n[1/2] FIRESTORE — fetching training labels...")

FIRESTORE_URL = (
    f"https://firestore.googleapis.com/v1/projects/{PROJECT}"
    f"/databases/(default)/documents/training_images?pageSize=300"
)

all_docs = []
next_url = FIRESTORE_URL
page     = 1

while next_url:
    try:
        res  = requests.get(next_url, timeout=15)
        data = res.json()
        docs = data.get("documents", [])
        all_docs.extend(docs)
        token = data.get("nextPageToken")
        next_url = FIRESTORE_URL + "&pageToken=" + token if token else None
        print(f"  Page {page}: +{len(docs)} docs (total {len(all_docs)})")
        page += 1
    except Exception as e:
        print(f"  ⚠️  Page {page} error: {e} — retrying...")
        time.sleep(2)

records = []
for doc in all_docs:
    f  = doc.get("fields", {})
    sm = f.get("sensor", {}).get("mapValue", {}).get("fields", {})
    sensor = None
    if sm:
        t = sm.get("temp", {}).get("doubleValue") or sm.get("temp", {}).get("integerValue")
        h = sm.get("hum",  {}).get("doubleValue") or sm.get("hum",  {}).get("integerValue")
        if t and h:
            sensor = {"temp": float(t), "hum": float(h)}
    records.append({
        "id":          doc["name"].split("/")[-1],
        "label":       f.get("label",      {}).get("stringValue",  ""),
        "url":         f.get("url",        {}).get("stringValue",  ""),
        "filename":    f.get("filename",   {}).get("stringValue",  ""),
        "timestamp":   f.get("timestamp",  {}).get("stringValue",  ""),
        "groundTruth": f.get("groundTruth",{}).get("booleanValue", False),
        "decidedBy":   f.get("decidedBy",  {}).get("stringValue",  ""),
        "sensor":      sensor
    })

wet = sum(1 for r in records if r["label"] == "WET")
dry = sum(1 for r in records if r["label"] == "DRY")

db_file = os.path.join(BACKUP_DIR, f"firestore_{TS}.json")
with open(db_file, "w") as out:
    json.dump({
        "project":     PROJECT,
        "total":       len(records),
        "wet":         wet,
        "dry":         dry,
        "exported_at": datetime.datetime.now().isoformat(),
        "records":     records
    }, out, indent=2)

print(f"\n  ✅ Firestore done: {len(records)} records ({wet} WET / {dry} DRY)")
print(f"  📄 Saved to: {db_file}")

# ══════════════════════════════════════════════════════════
# 2. STORAGE BACKUP — paginated listing + parallel download
# ══════════════════════════════════════════════════════════
print("\n[2/2] STORAGE — listing all images...")

def list_all_files():
    """Paginate through ALL files in Firebase Storage training/ folder."""
    files    = []
    base_url = (
        f"https://firebasestorage.googleapis.com/v0/b/{BUCKET}/o"
        f"?prefix=training%2F&maxResults=1000"
    )
    next_url = base_url
    page     = 1
    while next_url:
        try:
            res  = requests.get(next_url, timeout=15)
            data = res.json()
            items = data.get("items", [])
            files.extend(items)
            token = data.get("nextPageToken")
            next_url = base_url + "&pageToken=" + token if token else None
            print(f"  Listed page {page}: +{len(items)} files (total {len(files)})")
            page += 1
        except Exception as e:
            print(f"  ⚠️  List error page {page}: {e} — retrying...")
            time.sleep(2)
    return files

all_files = list_all_files()
print(f"\n  Found {len(all_files)} total files in Storage")

# Filter out folders (items with no size)
image_files = [f for f in all_files if "/" in f.get("name","") and "." in f["name"].split("/")[-1]]
print(f"  Image files to download: {len(image_files)}")

# ── Parallel download ──────────────────────────────────────
ok_count   = 0
fail_count = 0
skip_count = 0
lock       = threading.Lock()
start_time = time.time()

def download_one(item):
    name     = item["name"]
    filename = name.split("/")[-1]
    out_path = os.path.join(IMG_DIR, filename)

    # Skip if already downloaded (resume support)
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        return "skip", filename

    dl_url = (
        f"https://firebasestorage.googleapis.com/v0/b/{BUCKET}/o/"
        f"{urllib.parse.quote(name, safe='')}?alt=media"
    )

    for attempt in range(1, RETRY + 1):
        try:
            urllib.request.urlretrieve(dl_url, out_path)
            if os.path.getsize(out_path) > 0:
                return "ok", filename
        except Exception as e:
            if attempt == RETRY:
                return "fail", f"{filename} ({e})"
            time.sleep(1)

    return "fail", filename

print(f"\n  Downloading with {MAX_WORKERS} parallel workers...")
print("  (Already downloaded files will be skipped — safe to re-run)\n")

done = 0
with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    futures = {executor.submit(download_one, item): item for item in image_files}
    for future in as_completed(futures):
        status, name = future.result()
        done += 1
        with lock:
            if status == "ok":
                ok_count += 1
            elif status == "skip":
                skip_count += 1
            else:
                fail_count += 1

        # Progress every 50 files
        if done % 50 == 0 or done == len(image_files):
            elapsed = time.time() - start_time
            rate    = done / elapsed if elapsed > 0 else 0
            eta     = (len(image_files) - done) / rate if rate > 0 else 0
            print(f"  [{done}/{len(image_files)}] "
                  f"✓{ok_count} skip{skip_count} ✗{fail_count} | "
                  f"{rate:.1f} files/s | ETA {eta:.0f}s")

elapsed = time.time() - start_time

# ── Summary ────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  BACKUP COMPLETE")
print("=" * 60)
print(f"  📄 Firestore : {len(records)} records ({wet} WET / {dry} DRY)")
print(f"  🖼️  Images    : {ok_count} downloaded, {skip_count} skipped, {fail_count} failed")
print(f"  ⏱️  Time      : {elapsed:.1f}s ({elapsed/60:.1f} min)")
print(f"  📁 Location  : {os.path.abspath(BACKUP_DIR)}/")
print(f"  📦 Folder size: ", end="")

# Calculate folder size
total_bytes = sum(
    os.path.getsize(os.path.join(root, f))
    for root, dirs, files in os.walk(BACKUP_DIR)
    for f in files
)
if total_bytes > 1_000_000_000:
    print(f"{total_bytes/1_000_000_000:.2f} GB")
elif total_bytes > 1_000_000:
    print(f"{total_bytes/1_000_000:.1f} MB")
else:
    print(f"{total_bytes/1000:.0f} KB")

if fail_count > 0:
    print(f"\n  ⚠️  {fail_count} files failed — re-run the script to retry")
    print("  (Script skips already downloaded files automatically)")

print("\n  ✅ Done! Back up this folder to Google Drive / USB / GitHub.")
