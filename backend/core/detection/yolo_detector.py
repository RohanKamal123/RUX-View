"""
yolo_detector.py — YOLO nano detection gate (ONNX Runtime).

Runs YOLOv8 nano inference via ONNX Runtime on JPEG frames.
No ultralytics dependency at runtime — uses exported .onnx model.

Export the model once with:
    python -m connect.scripts.export_yolo_onnx

Model path: connect/models/yolov8n.onnx
Input:  float32 [1, 3, 640, 640] — normalized RGB
Output: float32 [1, 84, 8400] — cx, cy, w, h, 80 class scores
"""

import io
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

RELEVANT_CLASSES = {0, 1, 2, 3, 5, 7, 15, 16}
CLASS_NAMES = {
    0: "person", 1: "bicycle", 2: "car", 3: "motorcycle",
    5: "bus", 7: "truck", 15: "cat", 16: "dog"
}
CONFIDENCE_THRESHOLD = 0.35
NMS_IOU_THRESHOLD = 0.45
INPUT_SIZE = 640

MODEL_PATH = Path(__file__).parent.parent.parent.parent / \
             "connect" / "models" / "yolov8n.onnx"
# Fallback: also check relative to this file
_ALT_MODEL_PATH = Path(__file__).resolve().parents[3] / \
                  "connect" / "models" / "yolov8n.onnx"

_session = None  # ONNX Runtime InferenceSession singleton


@dataclass
class Detection:
    class_id: int
    class_name: str
    confidence: float
    bbox: list  # [x1, y1, x2, y2] normalized 0-1


@dataclass
class DetectionResult:
    has_relevant_objects: bool
    detections: list = field(default_factory=list)
    annotated_jpeg: Optional[bytes] = None
    object_summary: str = ""
    inference_ms: int = 0


def _get_session():
    """Lazy-load ONNX Runtime session singleton."""
    global _session
    if _session is not None:
        return _session

    try:
        import onnxruntime as ort

        # Find model file
        model_file = None
        for candidate in [MODEL_PATH, _ALT_MODEL_PATH]:
            if candidate.exists():
                model_file = candidate
                break

        if model_file is None:
            logger.error(
                "ONNX model not found. Run: "
                "python -m connect.scripts.export_yolo_onnx"
            )
            return None

        # CPU provider only — connect client runs on edge hardware
        opts = ort.SessionOptions()
        opts.inter_op_num_threads = 2
        opts.intra_op_num_threads = 2
        opts.graph_optimization_level = (
            ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        )

        _session = ort.InferenceSession(
            str(model_file),
            sess_options=opts,
            providers=["CPUExecutionProvider"],
        )
        logger.info(
            "ONNX Runtime session loaded: %s (%.1f MB)",
            model_file.name,
            model_file.stat().st_size / 1024 / 1024,
        )
        return _session

    except ImportError:
        logger.error(
            "onnxruntime not installed. Run: pip install onnxruntime"
        )
        return None
    except Exception as e:
        logger.error("Failed to load ONNX session: %s", e)
        return None


def _preprocess(image: Image.Image) -> tuple:
    """Resize and normalize image for YOLOv8 nano input.

    Returns:
        (input_tensor float32 [1,3,640,640], scale_x, scale_y)
    """
    orig_w, orig_h = image.size

    # Letterbox resize — maintain aspect ratio
    scale = min(INPUT_SIZE / orig_w, INPUT_SIZE / orig_h)
    new_w = int(orig_w * scale)
    new_h = int(orig_h * scale)
    resized = image.resize((new_w, new_h), Image.BILINEAR)

    # Pad to 640x640 with grey (114)
    canvas = Image.new("RGB", (INPUT_SIZE, INPUT_SIZE), (114, 114, 114))
    pad_x = (INPUT_SIZE - new_w) // 2
    pad_y = (INPUT_SIZE - new_h) // 2
    canvas.paste(resized, (pad_x, pad_y))

    # HWC → CHW, normalize 0-1
    arr = np.array(canvas, dtype=np.float32) / 255.0
    arr = arr.transpose(2, 0, 1)[np.newaxis]  # [1, 3, 640, 640]

    # Scale factors for bbox denormalization
    scale_x = orig_w / new_w
    scale_y = orig_h / new_h

    return arr, scale_x, scale_y, pad_x, pad_y, scale


def _postprocess(
    output: np.ndarray,
    orig_w: int,
    orig_h: int,
    scale: float,
    pad_x: int,
    pad_y: int,
) -> list:
    """Parse YOLOv8 output tensor to Detection list.

    YOLOv8 output shape: [1, 84, 8400]
    84 = 4 (cx,cy,w,h) + 80 class scores
    8400 = number of anchor predictions
    """
    preds = output[0]  # [84, 8400]
    preds = preds.T    # [8400, 84]

    boxes = preds[:, :4]      # cx, cy, w, h (in 640x640 space)
    scores = preds[:, 4:]     # 80 class scores

    class_ids = np.argmax(scores, axis=1)
    confidences = scores[np.arange(len(scores)), class_ids]

    # Filter by confidence and relevant classes
    mask = (confidences >= CONFIDENCE_THRESHOLD) & \
           np.isin(class_ids, list(RELEVANT_CLASSES))

    boxes = boxes[mask]
    confidences = confidences[mask]
    class_ids = class_ids[mask]

    if len(boxes) == 0:
        return []

    # cx,cy,w,h → x1,y1,x2,y2 (in letterboxed 640x640 space)
    x1 = boxes[:, 0] - boxes[:, 2] / 2
    y1 = boxes[:, 1] - boxes[:, 3] / 2
    x2 = boxes[:, 0] + boxes[:, 2] / 2
    y2 = boxes[:, 1] + boxes[:, 3] / 2

    # Remove letterbox padding and rescale to original image size
    x1 = np.clip((x1 - pad_x) / scale, 0, orig_w) / orig_w
    y1 = np.clip((y1 - pad_y) / scale, 0, orig_h) / orig_h
    x2 = np.clip((x2 - pad_x) / scale, 0, orig_w) / orig_w
    y2 = np.clip((y2 - pad_y) / scale, 0, orig_h) / orig_h

    # NMS per class
    detections = []
    for cls_id in np.unique(class_ids):
        cls_mask = class_ids == cls_id
        cls_boxes = np.stack([x1[cls_mask], y1[cls_mask],
                               x2[cls_mask], y2[cls_mask]], axis=1)
        cls_confs = confidences[cls_mask]

        # OpenCV NMS (expects pixel coords — scale up temporarily)
        boxes_px = (cls_boxes * [orig_w, orig_h, orig_w, orig_h]).tolist()
        scores_list = cls_confs.tolist()
        indices = cv2.dnn.NMSBoxes(
            boxes_px,
            scores_list,
            CONFIDENCE_THRESHOLD,
            NMS_IOU_THRESHOLD,
        )
        if len(indices) == 0:
            continue
        for i in indices.flatten():
            detections.append(Detection(
                class_id=int(cls_id),
                class_name=CLASS_NAMES.get(int(cls_id), "object"),
                confidence=round(float(cls_confs[i]), 3),
                bbox=[
                    round(float(cls_boxes[i][0]), 3),
                    round(float(cls_boxes[i][1]), 3),
                    round(float(cls_boxes[i][2]), 3),
                    round(float(cls_boxes[i][3]), 3),
                ],
            ))

    return detections


def detect(jpeg_bytes: bytes, annotate: bool = True,
           config: Optional[dict] = None) -> DetectionResult:
    """Run YOLO nano ONNX inference on a JPEG frame.

    Args:
        jpeg_bytes: Raw JPEG image bytes from camera.
        annotate: If True, draw bounding boxes for Gemini context.
        config: Optional runtime config dict (e.g. from config_store).
                If provided, ``yolo_confidence_threshold``,
                ``nms_iou_threshold``, and ``yolo_jpeg_quality``
                are read from it.

    Returns:
        DetectionResult. has_relevant_objects=False skips Gemini.
    """
    global CONFIDENCE_THRESHOLD, NMS_IOU_THRESHOLD
    jpeg_quality = 85
    if config is not None:
        CONFIDENCE_THRESHOLD = config.get("yolo_confidence_threshold", 0.35)
        NMS_IOU_THRESHOLD = config.get("nms_iou_threshold", 0.45)
        jpeg_quality = config.get("yolo_jpeg_quality", 85)

    session = _get_session()
    if session is None:
        # Fail open — let frame through to Gemini
        return DetectionResult(has_relevant_objects=True)

    try:
        image = Image.open(io.BytesIO(jpeg_bytes)).convert("RGB")
        orig_w, orig_h = image.size

        # Preprocess
        t0 = time.monotonic()
        tensor, scale_x, scale_y, pad_x, pad_y, scale = _preprocess(image)

        # Inference
        input_name = session.get_inputs()[0].name
        outputs = session.run(None, {input_name: tensor})
        inference_ms = int((time.monotonic() - t0) * 1000)

        # Postprocess
        detections = _postprocess(
            outputs[0], orig_w, orig_h, scale, pad_x, pad_y
        )

        if not detections:
            return DetectionResult(
                has_relevant_objects=False,
                inference_ms=inference_ms,
            )

        # Object summary
        counts: dict = {}
        for d in detections:
            counts[d.class_name] = counts.get(d.class_name, 0) + 1
        summary = ", ".join(
            f"{v} {k}{'s' if v > 1 else ''}"
            for k, v in counts.items()
        )

        logger.debug(
            "ONNX inference: %dms — %s", inference_ms, summary
        )

        # Annotate frame
        annotated_bytes = None
        if annotate:
            annotated_bytes = _annotate_frame(image, detections, jpeg_quality=jpeg_quality)

        return DetectionResult(
            has_relevant_objects=True,
            detections=detections,
            annotated_jpeg=annotated_bytes or jpeg_bytes,
            object_summary=summary,
            inference_ms=inference_ms,
        )

    except Exception as e:
        logger.error("ONNX detection failed: %s", e, exc_info=True)
        return DetectionResult(has_relevant_objects=True)


def _annotate_frame(image: Image.Image, detections: list,
                    jpeg_quality: int = 85) -> bytes:
    """Draw bounding boxes and labels on frame.

    Args:
        image: PIL Image to annotate.
        detections: List of Detection objects.
        jpeg_quality: JPEG compression quality (1-100, from config).

    Returns:
        JPEG bytes of annotated frame.
    """
    try:
        from PIL import ImageDraw
        draw = ImageDraw.Draw(image)
        img_w, img_h = image.size
        for det in detections:
            x1 = int(det.bbox[0] * img_w)
            y1 = int(det.bbox[1] * img_h)
            x2 = int(det.bbox[2] * img_w)
            y2 = int(det.bbox[3] * img_h)
            label = f"{det.class_name} {det.confidence:.0%}"
            draw.rectangle([x1, y1, x2, y2], outline="lime", width=2)
            draw.rectangle(
                [x1, y1 - 16, x1 + len(label) * 7, y1], fill="lime"
            )
            draw.text((x1 + 2, y1 - 14), label, fill="black")
        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=jpeg_quality)
        return buf.getvalue()
    except Exception:
        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=jpeg_quality)
        return buf.getvalue()
