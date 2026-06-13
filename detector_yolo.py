"""
YOLODetector - Ultralytics YOLO wrapper for per-frame player/ball detection.

This is the missing front-end of the spatial pipeline. It produces YOLO-style
bounding boxes ([x1, y1, x2, y2]) that feed directly into SAM2Tracker.add_object()
as box prompts, which in turn feed GeometryEngine for real-world measurement.

    YOLODetector  ->  SAM2Tracker  ->  GeometryEngine
    (this file)       (tracker_sam2)   (geometry_engine)

Design goals:
- ROCm/AMD first: device selection prefers the GPU exposed via the CUDA API,
  which is how PyTorch's ROCm builds present AMD GPUs (torch.version.hip set).
- Pretrained by default: ships nothing, downloads standard COCO weights on first
  use. "person" (class 0) and "sports ball" (class 32) cover basketball out of
  the box, so no training is required to get a working pipeline.
- Optional fine-tuned checkpoint: pass weights="path/to/best.pt" to use a model
  fine-tuned on your own footage (e.g. via the AMD hackathon run).
- Graceful degradation: if ultralytics/torch are not installed, construction
  raises a clear ImportError rather than failing deep in a call.

Usage:
    from detector_yolo import YOLODetector

    detector = YOLODetector()                      # pretrained, auto device
    detections = detector.detect(frame)            # frame: np.ndarray (H,W,3) BGR
    for det in detections:
        x1, y1, x2, y2 = det.bbox
        ...

    # Feed straight into SAM2:
    for i, det in enumerate(detector.detect(first_frame, classes=["person"])):
        tracker.add_object(frame_idx=0, obj_id=i, bbox=det.bbox)
"""
import logging
from dataclasses import dataclass
from typing import Any, List, Optional, Sequence, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# COCO class ids relevant to basketball footage.
COCO_PERSON = 0
COCO_SPORTS_BALL = 32

# Friendly name -> COCO id, for the `classes=` filter argument.
NAME_TO_COCO = {
    "person": COCO_PERSON,
    "player": COCO_PERSON,
    "ball": COCO_SPORTS_BALL,
    "sports ball": COCO_SPORTS_BALL,
}


@dataclass
class Detection:
    """A single detected object in one frame.

    Attributes:
        bbox: Bounding box as np.ndarray [x1, y1, x2, y2] in pixel coords.
              This is exactly the shape SAM2Tracker.add_object() expects.
        confidence: Detection confidence in [0, 1].
        class_id: Integer class id from the model (COCO ids for pretrained).
        class_name: Human-readable class name.
    """
    bbox: np.ndarray
    confidence: float
    class_id: int
    class_name: str

    @property
    def xyxy(self) -> Tuple[float, float, float, float]:
        """Bounding box as a plain (x1, y1, x2, y2) tuple."""
        return tuple(float(v) for v in self.bbox)

    @property
    def foot_point(self) -> Tuple[float, float]:
        """Bottom-center pixel (x, y) - the player's feet on the floor plane.

        This is the natural input to GeometryEngine for court-position and
        height estimation (bottom_y = feet, top_y = head = y1).
        """
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2.0, float(y2))


def select_device(prefer: str = "auto") -> str:
    """Choose an inference device, AMD/ROCm aware.

    PyTorch's ROCm builds expose AMD GPUs through the CUDA API, so
    torch.cuda.is_available() is True and the device string is still "cuda".
    We log whether the backend is HIP (ROCm) or genuine CUDA for clarity.

    Args:
        prefer: "auto" (default), "cuda", or "cpu". "auto" picks GPU if present.

    Returns:
        Device string suitable for Ultralytics / torch (e.g. "cuda" or "cpu").
    """
    if prefer == "cpu":
        return "cpu"

    try:
        import torch
    except ImportError:
        logger.warning("torch not installed; falling back to CPU.")
        return "cpu"

    if torch.cuda.is_available():
        backend = "ROCm/HIP" if getattr(torch.version, "hip", None) else "CUDA"
        try:
            name = torch.cuda.get_device_name(0)
        except Exception:  # pragma: no cover - defensive
            name = "unknown"
        logger.info("GPU available via %s backend: %s", backend, name)
        return "cuda"

    if prefer == "cuda":
        logger.warning("Requested cuda but no GPU available; using CPU.")
    return "cpu"


class YOLODetector:
    """Per-frame object detector producing SAM2-compatible bounding boxes.

    Args:
        weights: Model weights. A bare name like "yolov8n.pt" / "yolo11n.pt"
            downloads pretrained COCO weights; a filesystem path loads a
            fine-tuned checkpoint.
        device: "auto" (default), "cuda", or "cpu".
        conf: Minimum confidence threshold for returned detections.
        iou: NMS IoU threshold.
        model: Pre-built Ultralytics model instance. Injecting one bypasses
            loading (useful for testing with a mock).
    """

    def __init__(
        self,
        weights: str = "yolov8n.pt",
        device: str = "auto",
        conf: float = 0.25,
        iou: float = 0.45,
        model: Optional[Any] = None,
    ):
        self.weights = weights
        self.device = select_device(device)
        self.conf = conf
        self.iou = iou

        if model is not None:
            self.model = model
        else:
            try:
                from ultralytics import YOLO
            except ImportError as exc:
                raise ImportError(
                    "ultralytics is required for YOLODetector. Install with: "
                    "pip install ultralytics"
                ) from exc
            logger.info("Loading YOLO weights '%s' on %s", weights, self.device)
            self.model = YOLO(weights)

    def _resolve_classes(
        self, classes: Optional[Sequence]
    ) -> Optional[List[int]]:
        """Translate a mix of names/ids into integer class ids, or None for all."""
        if classes is None:
            return None
        resolved: List[int] = []
        for c in classes:
            if isinstance(c, int):
                resolved.append(c)
            elif isinstance(c, str):
                if c not in NAME_TO_COCO:
                    raise ValueError(
                        f"Unknown class name '{c}'. Known: {list(NAME_TO_COCO)}"
                    )
                resolved.append(NAME_TO_COCO[c])
            else:
                raise TypeError(f"class must be int or str, got {type(c)}")
        # De-dupe while preserving order.
        return list(dict.fromkeys(resolved))

    def detect(
        self,
        frame: np.ndarray,
        classes: Optional[Sequence] = ("person", "ball"),
    ) -> List[Detection]:
        """Detect objects in a single frame.

        Args:
            frame: Image as np.ndarray (H, W, 3). BGR (OpenCV) or RGB both work;
                Ultralytics handles ndarray input directly.
            classes: Iterable of class names ("person", "ball") or COCO ids to
                keep. None keeps all classes. Defaults to players + ball.

        Returns:
            List of Detection objects sorted by descending confidence.
        """
        class_ids = self._resolve_classes(classes)

        results = self.model.predict(
            frame,
            conf=self.conf,
            iou=self.iou,
            classes=class_ids,
            device=self.device,
            verbose=False,
        )

        detections: List[Detection] = []
        names = getattr(self.model, "names", {})
        for result in results:
            boxes = getattr(result, "boxes", None)
            if boxes is None:
                continue
            for box in boxes:
                xyxy = box.xyxy[0].cpu().numpy().astype(float)
                cls_id = int(box.cls[0].item())
                detections.append(
                    Detection(
                        bbox=xyxy,
                        confidence=float(box.conf[0].item()),
                        class_id=cls_id,
                        class_name=names.get(cls_id, str(cls_id)),
                    )
                )

        detections.sort(key=lambda d: d.confidence, reverse=True)
        return detections

    def detect_players(self, frame: np.ndarray) -> List[Detection]:
        """Convenience: detect only players (COCO person)."""
        return self.detect(frame, classes=["person"])

    def detect_ball(self, frame: np.ndarray) -> Optional[Detection]:
        """Convenience: return the single most confident ball detection, if any."""
        balls = self.detect(frame, classes=["ball"])
        return balls[0] if balls else None
