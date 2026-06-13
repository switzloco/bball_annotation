"""
SpatialPipeline - wires YOLO detection -> SAM2 tracking -> GeometryEngine.

This is the additive "spatial" layer that complements the existing Gemini
"semantic" layer in agent.py. It is intentionally standalone: nothing in
agent.py or app.py imports it, so it can be developed and tested in isolation
and later surfaced behind a feature flag.

Flow:
    1. YOLODetector finds players (and ball) on a seed frame.
    2. Those bounding boxes prompt SAM2Tracker, which propagates masks/positions
       across the clip with temporal memory.
    3. GeometryEngine converts pixel head/foot positions into real-world height
       using a known court reference (the 10ft rim by default).

The output is a structured list of per-object tracks that can be summarised by
the existing Gemini layer, or used directly for analytics.

Usage:
    from detector_yolo import YOLODetector
    from tracker_sam2 import SAM2Tracker
    from geometry_engine import GeometryEngine
    from tracking_pipeline import SpatialPipeline

    pipeline = SpatialPipeline(
        detector=YOLODetector(),
        tracker=SAM2Tracker.create_default(),
        geometry=GeometryEngine(),
    )
    tracks = pipeline.run("/path/to/clip.mp4", seed_frame_idx=0, max_frames=120)
"""
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from detector_yolo import Detection, YOLODetector
from geometry_engine import GeometryEngine

logger = logging.getLogger(__name__)


@dataclass
class CourtReference:
    """A known-height vertical reference used for metrology.

    Defaults to the basketball rim (10 ft). Provide the pixel y-coordinates of
    the reference's top and bottom in the seed frame, plus the vertical
    vanishing point. With vanishing_point_y = inf the math reduces to a simple
    pixel ratio (orthographic), which is a reasonable first approximation.
    """
    ref_height_ft: float = 10.0
    ref_top_y: Optional[float] = None
    ref_bottom_y: Optional[float] = None
    vanishing_point_y: float = float("inf")

    def is_complete(self) -> bool:
        return self.ref_top_y is not None and self.ref_bottom_y is not None


@dataclass
class ObjectTrack:
    """Accumulated tracking result for one object across the clip."""
    obj_id: int
    class_name: str
    seed_bbox: np.ndarray
    seed_frame: int
    estimated_height_ft: Optional[float] = None
    frames_tracked: int = 0
    foot_positions: List[Tuple[int, Tuple[float, float]]] = field(default_factory=list)


class SpatialPipeline:
    """Orchestrates detection, tracking, and geometry into structured tracks."""

    def __init__(
        self,
        detector: YOLODetector,
        tracker,  # SAM2Tracker (duck-typed to keep this importable without SAM2)
        geometry: Optional[GeometryEngine] = None,
    ):
        self.detector = detector
        self.tracker = tracker
        self.geometry = geometry or GeometryEngine()

    @staticmethod
    def _read_frame(video_path: str, frame_idx: int) -> np.ndarray:
        """Grab a single frame as a BGR ndarray using OpenCV."""
        try:
            import cv2
        except ImportError as exc:
            raise ImportError(
                "opencv-python(-headless) is required to read frames."
            ) from exc

        cap = cv2.VideoCapture(video_path)
        try:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ok, frame = cap.read()
            if not ok:
                raise RuntimeError(
                    f"Could not read frame {frame_idx} from {video_path}"
                )
            return frame
        finally:
            cap.release()

    def run(
        self,
        video_path: str,
        seed_frame_idx: int = 0,
        max_frames: Optional[int] = None,
        court_reference: Optional[CourtReference] = None,
        seed_classes=("person",),
    ) -> List[ObjectTrack]:
        """Run the full spatial pipeline over a clip.

        Args:
            video_path: Path to a local video file.
            seed_frame_idx: Frame on which to detect objects to track.
            max_frames: Max frames to propagate (None = whole clip).
            court_reference: Optional reference for height estimation. If
                provided and complete, each track gets estimated_height_ft.
            seed_classes: Classes to seed tracking with (players by default).

        Returns:
            List of ObjectTrack, one per seeded object.
        """
        seed_frame = self._read_frame(video_path, seed_frame_idx)
        detections: List[Detection] = self.detector.detect(
            seed_frame, classes=list(seed_classes)
        )
        logger.info(
            "Seeded %d detections on frame %d", len(detections), seed_frame_idx
        )

        self.tracker.initialize_video(video_path)

        tracks: Dict[int, ObjectTrack] = {}
        for obj_id, det in enumerate(detections):
            self.tracker.add_object(
                frame_idx=seed_frame_idx, obj_id=obj_id, bbox=det.bbox
            )
            tracks[obj_id] = ObjectTrack(
                obj_id=obj_id,
                class_name=det.class_name,
                seed_bbox=det.bbox.copy(),
                seed_frame=seed_frame_idx,
            )
            self._estimate_height(tracks[obj_id], det, court_reference)

        # Propagate masks across the clip and count frames per object.
        for frame_idx, obj_ids, _masks in self.tracker.propagate(
            start_frame=seed_frame_idx, max_frames=max_frames
        ):
            for oid in obj_ids:
                oid = int(oid)
                if oid in tracks:
                    tracks[oid].frames_tracked += 1

        return list(tracks.values())

    def _estimate_height(
        self,
        track: ObjectTrack,
        det: Detection,
        court_reference: Optional[CourtReference],
    ) -> None:
        """Fill in estimated_height_ft from the seed bbox + court reference."""
        if court_reference is None or not court_reference.is_complete():
            return
        x1, y1, x2, y2 = det.bbox  # head ~ y1 (top), feet ~ y2 (bottom)
        try:
            if np.isfinite(court_reference.vanishing_point_y):
                track.estimated_height_ft = self.geometry.estimate_height(
                    target_top_y=float(y1),
                    target_bottom_y=float(y2),
                    ref_top_y=court_reference.ref_top_y,
                    ref_bottom_y=court_reference.ref_bottom_y,
                    vanishing_point_y=court_reference.vanishing_point_y,
                    ref_height=court_reference.ref_height_ft,
                )
            else:
                # Orthographic limit (vanishing point at infinity): the
                # Criminisi perspective corrections -> 1, leaving a pixel ratio.
                # Computed directly because inf/inf is nan, not the limit.
                ref_px = self.geometry.pixel_height(
                    court_reference.ref_top_y, court_reference.ref_bottom_y
                )
                target_px = self.geometry.pixel_height(float(y1), float(y2))
                track.estimated_height_ft = (
                    court_reference.ref_height_ft * target_px / ref_px
                )
        except ValueError as exc:
            logger.warning("Height estimation skipped for obj %d: %s",
                           track.obj_id, exc)
