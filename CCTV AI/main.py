import cv2
import json
import os
import time
import threading
import logging
from datetime import datetime
from ultralytics import YOLO
from database import init_db, log_visitor
from notifier import send_alert

# ── Config ──────────────────────────────────────────────────────────────────
SNAPSHOT_DIR = "snapshots"
COOLDOWN_SECONDS = 15          # min seconds between alerts per camera
MODEL_PATH = "yolo26n.pt"      # upgrade from yolov8n - faster + NMS-free
PERSON_CLASS_ID = 0

os.makedirs(SNAPSHOT_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(threadName)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)

# ── Shared resources ─────────────────────────────────────────────────────────
# One model instance shared across all camera threads (YOLO inference is GIL-safe)
model = YOLO(MODEL_PATH)
db_lock = threading.Lock()          # protect SQLite writes
last_alert: dict[int, float] = {}   # {camera_id: last_alert_timestamp}
alert_lock = threading.Lock()


# ── Helpers ──────────────────────────────────────────────────────────────────
def save_snapshot(frame, camera_id: int) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"cam{camera_id}_{ts}.jpg"
    path = os.path.join(SNAPSHOT_DIR, filename)
    cv2.imwrite(path, frame)
    return path


def is_on_cooldown(camera_id: int) -> bool:
    with alert_lock:
        last = last_alert.get(camera_id, 0)
        return (time.time() - last) < COOLDOWN_SECONDS


def update_cooldown(camera_id: int):
    with alert_lock:
        last_alert[camera_id] = time.time()


# ── Per-camera detection loop ────────────────────────────────────────────────
def run_camera(cam: dict):
    cam_id = cam["id"]
    cam_name = cam["name"]
    url = cam["url"]
    conf_threshold = cam.get("conf", 0.45)

    log.info(f"Starting camera [{cam_name}] at {url} (conf={conf_threshold})")

    cap: cv2.VideoCapture | None = None

    def connect():
        nonlocal cap
        while True:
            log.info(f"[{cam_name}] Connecting...")
            cap = cv2.VideoCapture(url)
            if cap.isOpened():
                log.info(f"[{cam_name}] Connected ✓")
                return
            log.warning(f"[{cam_name}] Failed to connect, retrying in 5s...")
            time.sleep(5)

    connect()

    while True:
        if cap is None:
            connect()
            continue

        ret, frame = cap.read()

        if not ret:
            log.warning(f"[{cam_name}] Lost connection, reconnecting...")
            cap.release()
            time.sleep(3)
            connect()
            continue

        # Run detection
        results = model(frame, conf=conf_threshold, verbose=False)[0]
        persons = [b for b in results.boxes if int(b.cls[0]) == PERSON_CLASS_ID]

        if persons and not is_on_cooldown(cam_id):
            snapshot_path = save_snapshot(frame, cam_id)

            with db_lock:
                log_visitor(cam_id, cam_name, snapshot_path)

            update_cooldown(cam_id)
            log.info(f"[{cam_name}] Person detected → {snapshot_path}")

            # Send Telegram alert in background so it doesn't block detection
            threading.Thread(
                target=send_alert,
                args=(snapshot_path, cam_name),
                daemon=True
            ).start()


# ── Entry point ──────────────────────────────────────────────────────────────
def main():
    init_db()

    with open("cameras.json") as f:
        cameras = json.load(f)

    if not cameras:
        log.error("No cameras defined in cameras.json. Exiting.")
        return

    log.info(f"Loaded {len(cameras)} camera(s): {[c['name'] for c in cameras]}")

    threads = []
    for cam in cameras:
        t = threading.Thread(
            target=run_camera,
            args=(cam,),
            name=cam["name"],
            daemon=True
        )
        t.start()
        threads.append(t)

    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Shutting down...")


if __name__ == "__main__":
    main()