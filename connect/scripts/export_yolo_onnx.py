"""
export_yolo_onnx.py — Export YOLOv8 nano to ONNX format.

Run once during development:
    python -m connect.scripts.export_yolo_onnx

Output: connect/models/yolov8n.onnx  (~6MB)

The exported model is committed to the repo and used by
yolo_detector.py at runtime via ONNX Runtime — no ultralytics
dependency needed on end-user machines.
"""

import sys
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent / "models"
OUTPUT_PATH = OUTPUT_DIR / "yolov8n.onnx"
MODEL_NAME = "yolov8n.pt"
INPUT_SIZE = 640  # YOLOv8 nano default


def export():
    print("Loading YOLOv8 nano...")
    try:
        from ultralytics import YOLO
    except ImportError:
        print("ERROR: ultralytics not installed.")
        print("Run: pip install ultralytics")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    model = YOLO(MODEL_NAME)
    print(f"Exporting to ONNX (input size {INPUT_SIZE})...")

    model.export(
        format="onnx",
        imgsz=INPUT_SIZE,
        opset=12,          # broad ONNX Runtime compatibility
        simplify=True,     # fold constants, remove dead nodes
        dynamic=False,     # fixed batch size = 1 for edge devices
        half=False,        # float32 — ONNX Runtime CPU doesn't support fp16
    )

    # ultralytics exports to cwd — move to models/
    exported = Path("yolov8n.onnx")
    if exported.exists():
        exported.rename(OUTPUT_PATH)
        print(f"✓ Exported to {OUTPUT_PATH}")
        print(f"  Size: {OUTPUT_PATH.stat().st_size / 1024 / 1024:.1f} MB")
    elif OUTPUT_PATH.exists():
        print(f"✓ Already at {OUTPUT_PATH}")
    else:
        print("ERROR: Export file not found. Check ultralytics output above.")
        sys.exit(1)

    # Quick sanity check
    print("Verifying ONNX model...")
    try:
        import onnx
        model_onnx = onnx.load(str(OUTPUT_PATH))
        onnx.checker.check_model(model_onnx)
        print("✓ ONNX model verified — no errors")
    except ImportError:
        print("(onnx package not installed — skipping verification)")
    except Exception as e:
        print(f"WARNING: ONNX verification failed: {e}")

    print("\nDone. Commit connect/models/yolov8n.onnx to the repo.")
    print("yolo_detector.py will use it automatically.")


if __name__ == "__main__":
    export()