"""
Tests for SAM2Tracker class

Uses MockSAM2 to test the tracker wrapper without loading the heavy
segment-anything model. Tests verify data flow, state management,
and interface contracts.

CRITICAL: Does NOT import segment_anything library - uses mocks only.
"""
import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from typing import Dict, Any, Tuple, Optional


# ─────────────────────────────────────────────────────────────────────────────
# Mock SAM2 Implementation
# ─────────────────────────────────────────────────────────────────────────────

class MockSAM2Predictor:
    """
    Mock SAM2 video predictor that mimics the real API.

    The real SAM2 API (sam2.sam2_video_predictor) has methods like:
    - init_state(video_path) -> inference_state
    - add_new_points_or_box(state, frame_idx, obj_id, box=...) -> masks
    - propagate_in_video(state) -> generator of (frame_idx, obj_ids, masks)

    This mock returns random binary masks for testing data flow.
    """

    def __init__(self, model_cfg: str = "sam2_hiera_l.yaml", device: str = "cpu"):
        self.model_cfg = model_cfg
        self.device = device
        self._initialized = False
        self._inference_state: Optional[Dict[str, Any]] = None
        self._tracked_objects: Dict[int, Dict[str, Any]] = {}
        self._frame_count = 0

    def init_state(self, video_path: str) -> Dict[str, Any]:
        """Initialize inference state for a video."""
        self._initialized = True
        self._inference_state = {
            "video_path": video_path,
            "frame_idx": 0,
            "temporal_memory": {},
            "object_ids": [],
        }
        return self._inference_state

    def reset_state(self, inference_state: Dict[str, Any]) -> None:
        """Reset the inference state."""
        inference_state["frame_idx"] = 0
        inference_state["temporal_memory"] = {}
        inference_state["object_ids"] = []
        self._tracked_objects = {}

    def add_new_points_or_box(
        self,
        inference_state: Dict[str, Any],
        frame_idx: int,
        obj_id: int,
        points: Optional[np.ndarray] = None,
        labels: Optional[np.ndarray] = None,
        box: Optional[np.ndarray] = None,
        clear_old_points: bool = True,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Add a new prompt (points or box) for an object.

        Args:
            inference_state: State dict from init_state
            frame_idx: Frame index to add prompt
            obj_id: Object ID to track
            points: Optional point prompts (N, 2)
            labels: Optional point labels (N,)
            box: Optional bounding box [x1, y1, x2, y2]
            clear_old_points: Whether to clear previous prompts

        Returns:
            Tuple of (frame_idx, obj_ids, masks)
            - masks: (N_objects, 1, H, W) binary masks
        """
        if not self._initialized:
            raise RuntimeError("Must call init_state first")

        # Store tracked object info
        self._tracked_objects[obj_id] = {
            "frame_idx": frame_idx,
            "box": box,
            "points": points,
            "labels": labels,
        }

        # Update state
        if obj_id not in inference_state["object_ids"]:
            inference_state["object_ids"].append(obj_id)

        # Generate mock mask (random binary mask)
        # Real SAM2 returns (1, 1, H, W) but we'll use a simple shape
        mask_h, mask_w = 256, 256  # Default size
        if box is not None:
            # Generate mask roughly matching box region
            mask = np.zeros((1, 1, mask_h, mask_w), dtype=np.float32)
            x1, y1, x2, y2 = box.astype(int)
            # Scale to mask size
            scale_x = mask_w / 640  # Assume 640px input
            scale_y = mask_h / 480
            x1_s = int(x1 * scale_x)
            y1_s = int(y1 * scale_y)
            x2_s = int(x2 * scale_x)
            y2_s = int(y2 * scale_y)
            mask[0, 0, y1_s:y2_s, x1_s:x2_s] = 1.0
        else:
            # Random mask
            mask = (np.random.rand(1, 1, mask_h, mask_w) > 0.5).astype(np.float32)

        obj_ids = np.array([obj_id])
        return frame_idx, obj_ids, mask

    def propagate_in_video(
        self,
        inference_state: Dict[str, Any],
        start_frame_idx: int = 0,
        max_frame_num_to_track: Optional[int] = None,
        reverse: bool = False,
    ):
        """
        Propagate tracking through video frames.

        Yields:
            Tuple of (frame_idx, obj_ids, masks) for each frame
        """
        if not self._initialized:
            raise RuntimeError("Must call init_state first")

        num_frames = max_frame_num_to_track or 10
        obj_ids = np.array(inference_state["object_ids"])

        for i in range(num_frames):
            frame_idx = start_frame_idx + ((-1 if reverse else 1) * i)

            # Generate mock masks for all tracked objects
            mask_h, mask_w = 256, 256
            masks = np.random.rand(len(obj_ids), 1, mask_h, mask_w) > 0.5
            masks = masks.astype(np.float32)

            # Update temporal memory (mock)
            inference_state["temporal_memory"][frame_idx] = {
                "obj_ids": obj_ids.copy(),
                "masks": masks.copy(),
            }

            yield frame_idx, obj_ids, masks


class MockSAM2ImagePredictor:
    """Mock SAM2 image predictor for single-frame segmentation."""

    def __init__(self, model_cfg: str = "sam2_hiera_l.yaml", device: str = "cpu"):
        self.model_cfg = model_cfg
        self.device = device
        self._image_set = False
        self._image_shape: Optional[Tuple[int, int, int]] = None

    def set_image(self, image: np.ndarray) -> None:
        """Set the image for segmentation."""
        self._image_set = True
        self._image_shape = image.shape

    def predict(
        self,
        point_coords: Optional[np.ndarray] = None,
        point_labels: Optional[np.ndarray] = None,
        box: Optional[np.ndarray] = None,
        multimask_output: bool = True,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Predict segmentation masks.

        Returns:
            Tuple of (masks, scores, logits)
            - masks: (N, H, W) binary masks
            - scores: (N,) confidence scores
            - logits: (N, H, W) raw logits
        """
        if not self._image_set:
            raise RuntimeError("Must call set_image first")

        h, w = self._image_shape[:2]
        num_masks = 3 if multimask_output else 1

        # Generate mock outputs
        masks = (np.random.rand(num_masks, h, w) > 0.5).astype(bool)
        scores = np.random.rand(num_masks)
        logits = np.random.randn(num_masks, h, w).astype(np.float32)

        return masks, scores, logits


# ─────────────────────────────────────────────────────────────────────────────
# Test Classes
# ─────────────────────────────────────────────────────────────────────────────

class TestSAM2TrackerInitialization:
    """Tests for SAM2Tracker initialization and setup."""

    def test_tracker_initializes_with_mock(self):
        """Verify tracker can be instantiated with a mock predictor."""
        from tracker_sam2 import SAM2Tracker

        mock_predictor = MockSAM2Predictor()
        tracker = SAM2Tracker(predictor=mock_predictor)

        assert tracker is not None
        assert tracker.predictor is mock_predictor

    def test_tracker_creates_inference_state(self):
        """Verify tracker initializes inference state for video."""
        from tracker_sam2 import SAM2Tracker

        mock_predictor = MockSAM2Predictor()
        tracker = SAM2Tracker(predictor=mock_predictor)

        state = tracker.initialize_video("/path/to/video.mp4")

        assert state is not None
        assert "video_path" in state
        assert state["video_path"] == "/path/to/video.mp4"
        assert "temporal_memory" in state
        assert "object_ids" in state

    def test_tracker_can_reset_state(self):
        """Verify tracker can reset its state."""
        from tracker_sam2 import SAM2Tracker

        mock_predictor = MockSAM2Predictor()
        tracker = SAM2Tracker(predictor=mock_predictor)

        tracker.initialize_video("/path/to/video.mp4")
        tracker.reset()

        assert tracker.inference_state["object_ids"] == []
        assert tracker.inference_state["temporal_memory"] == {}


class TestSAM2TrackerBoundingBoxPrompt:
    """Tests for bounding box prompt handling."""

    def test_tracker_accepts_bounding_box(self):
        """Verify tracker accepts YOLO-style bounding box prompt."""
        from tracker_sam2 import SAM2Tracker

        mock_predictor = MockSAM2Predictor()
        tracker = SAM2Tracker(predictor=mock_predictor)
        tracker.initialize_video("/path/to/video.mp4")

        # YOLO-style bbox: [x1, y1, x2, y2]
        bbox = np.array([100, 150, 200, 300])
        frame_idx = 0
        obj_id = 1

        result = tracker.add_object(
            frame_idx=frame_idx,
            obj_id=obj_id,
            bbox=bbox
        )

        assert result is not None
        assert "mask" in result
        assert result["obj_id"] == obj_id

    def test_bounding_box_returns_mask(self):
        """Verify bounding box prompt returns segmentation mask."""
        from tracker_sam2 import SAM2Tracker

        mock_predictor = MockSAM2Predictor()
        tracker = SAM2Tracker(predictor=mock_predictor)
        tracker.initialize_video("/path/to/video.mp4")

        bbox = np.array([100, 150, 200, 300])
        result = tracker.add_object(frame_idx=0, obj_id=1, bbox=bbox)

        mask = result["mask"]
        assert isinstance(mask, np.ndarray)
        assert mask.ndim >= 2  # At least 2D mask
        assert mask.dtype in [np.float32, np.float64, np.bool_, bool]

    def test_multiple_objects_tracked(self):
        """Verify tracker can handle multiple objects."""
        from tracker_sam2 import SAM2Tracker

        mock_predictor = MockSAM2Predictor()
        tracker = SAM2Tracker(predictor=mock_predictor)
        tracker.initialize_video("/path/to/video.mp4")

        # Add multiple players
        bbox1 = np.array([100, 150, 200, 300])
        bbox2 = np.array([300, 150, 400, 300])
        bbox3 = np.array([500, 150, 600, 300])

        tracker.add_object(frame_idx=0, obj_id=1, bbox=bbox1)
        tracker.add_object(frame_idx=0, obj_id=2, bbox=bbox2)
        tracker.add_object(frame_idx=0, obj_id=3, bbox=bbox3)

        assert len(tracker.tracked_objects) == 3
        assert 1 in tracker.tracked_objects
        assert 2 in tracker.tracked_objects
        assert 3 in tracker.tracked_objects


class TestSAM2TrackerTemporalMemory:
    """Tests for temporal memory and state updates."""

    def test_temporal_memory_updated_on_propagate(self):
        """Verify temporal memory is updated during propagation."""
        from tracker_sam2 import SAM2Tracker

        mock_predictor = MockSAM2Predictor()
        tracker = SAM2Tracker(predictor=mock_predictor)
        tracker.initialize_video("/path/to/video.mp4")

        bbox = np.array([100, 150, 200, 300])
        tracker.add_object(frame_idx=0, obj_id=1, bbox=bbox)

        # Propagate through frames
        results = list(tracker.propagate(max_frames=5))

        assert len(results) == 5
        assert len(tracker.inference_state["temporal_memory"]) > 0

    def test_propagate_yields_frame_results(self):
        """Verify propagate yields results for each frame."""
        from tracker_sam2 import SAM2Tracker

        mock_predictor = MockSAM2Predictor()
        tracker = SAM2Tracker(predictor=mock_predictor)
        tracker.initialize_video("/path/to/video.mp4")

        tracker.add_object(frame_idx=0, obj_id=1, bbox=np.array([100, 150, 200, 300]))

        for frame_idx, obj_ids, masks in tracker.propagate(max_frames=3):
            assert isinstance(frame_idx, (int, np.integer))
            assert isinstance(obj_ids, np.ndarray)
            assert isinstance(masks, np.ndarray)
            assert len(obj_ids) > 0

    def test_process_frame_updates_state(self):
        """Verify processing a new frame updates tracker state."""
        from tracker_sam2 import SAM2Tracker

        mock_predictor = MockSAM2Predictor()
        tracker = SAM2Tracker(predictor=mock_predictor)
        tracker.initialize_video("/path/to/video.mp4")

        # Add initial object
        bbox = np.array([100, 150, 200, 300])
        tracker.add_object(frame_idx=0, obj_id=1, bbox=bbox)

        # Process next frame
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        result = tracker.process_frame(frame, frame_idx=1)

        assert result is not None
        assert tracker.current_frame_idx == 1


class TestSAM2TrackerFrameInput:
    """Tests for frame input handling."""

    def test_accepts_numpy_frame(self):
        """Verify tracker accepts numpy array frame."""
        from tracker_sam2 import SAM2Tracker

        mock_predictor = MockSAM2Predictor()
        tracker = SAM2Tracker(predictor=mock_predictor)
        tracker.initialize_video("/path/to/video.mp4")

        # Typical video frame: (H, W, 3) uint8
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        bbox = np.array([100, 150, 200, 300])

        tracker.add_object(frame_idx=0, obj_id=1, bbox=bbox)
        result = tracker.process_frame(frame, frame_idx=0)

        assert result is not None

    def test_handles_different_frame_sizes(self):
        """Verify tracker handles various frame dimensions."""
        from tracker_sam2 import SAM2Tracker

        mock_predictor = MockSAM2Predictor()
        tracker = SAM2Tracker(predictor=mock_predictor)
        tracker.initialize_video("/path/to/video.mp4")

        bbox = np.array([100, 150, 200, 300])
        tracker.add_object(frame_idx=0, obj_id=1, bbox=bbox)

        # Test different sizes
        for h, w in [(480, 640), (720, 1280), (1080, 1920), (2160, 3840)]:
            frame = np.random.randint(0, 255, (h, w, 3), dtype=np.uint8)
            result = tracker.process_frame(frame, frame_idx=0)
            assert result is not None


class TestSAM2TrackerEdgeCases:
    """Tests for edge cases and error handling."""

    def test_error_without_initialization(self):
        """Verify error when using tracker without initialization."""
        from tracker_sam2 import SAM2Tracker

        mock_predictor = MockSAM2Predictor()
        tracker = SAM2Tracker(predictor=mock_predictor)

        with pytest.raises((RuntimeError, ValueError)):
            tracker.add_object(frame_idx=0, obj_id=1, bbox=np.array([0, 0, 10, 10]))

    def test_empty_bbox_raises_error(self):
        """Verify error for invalid bounding box."""
        from tracker_sam2 import SAM2Tracker

        mock_predictor = MockSAM2Predictor()
        tracker = SAM2Tracker(predictor=mock_predictor)
        tracker.initialize_video("/path/to/video.mp4")

        with pytest.raises((ValueError, TypeError)):
            tracker.add_object(frame_idx=0, obj_id=1, bbox=None)

    def test_negative_frame_idx_raises_error(self):
        """Verify error for negative frame index."""
        from tracker_sam2 import SAM2Tracker

        mock_predictor = MockSAM2Predictor()
        tracker = SAM2Tracker(predictor=mock_predictor)
        tracker.initialize_video("/path/to/video.mp4")

        with pytest.raises(ValueError):
            tracker.add_object(
                frame_idx=-1,
                obj_id=1,
                bbox=np.array([100, 150, 200, 300])
            )

    def test_get_mask_for_object(self):
        """Verify can retrieve mask for specific object."""
        from tracker_sam2 import SAM2Tracker

        mock_predictor = MockSAM2Predictor()
        tracker = SAM2Tracker(predictor=mock_predictor)
        tracker.initialize_video("/path/to/video.mp4")

        bbox = np.array([100, 150, 200, 300])
        tracker.add_object(frame_idx=0, obj_id=42, bbox=bbox)

        mask = tracker.get_object_mask(obj_id=42)
        assert mask is not None
        assert isinstance(mask, np.ndarray)


class TestSAM2TrackerIntegrationWithYOLO:
    """Tests simulating integration with YOLO detections."""

    def test_yolo_detection_to_tracker_flow(self):
        """Verify YOLO-style detections can be passed to tracker."""
        from tracker_sam2 import SAM2Tracker

        mock_predictor = MockSAM2Predictor()
        tracker = SAM2Tracker(predictor=mock_predictor)
        tracker.initialize_video("/path/to/video.mp4")

        # Simulate YOLO detections: list of [x1, y1, x2, y2, conf, class_id]
        yolo_detections = [
            [100, 150, 200, 350, 0.95, 0],  # Person 1
            [300, 140, 380, 340, 0.92, 0],  # Person 2
            [450, 200, 520, 380, 0.88, 0],  # Person 3
        ]

        for idx, det in enumerate(yolo_detections):
            x1, y1, x2, y2, conf, cls = det
            bbox = np.array([x1, y1, x2, y2])
            tracker.add_object(frame_idx=0, obj_id=idx + 1, bbox=bbox)

        assert len(tracker.tracked_objects) == 3

    def test_track_players_across_frames(self):
        """Simulate tracking players across multiple frames."""
        from tracker_sam2 import SAM2Tracker

        mock_predictor = MockSAM2Predictor()
        tracker = SAM2Tracker(predictor=mock_predictor)
        tracker.initialize_video("/path/to/video.mp4")

        # Initialize with first frame detections
        initial_bbox = np.array([100, 150, 200, 350])
        tracker.add_object(frame_idx=0, obj_id=1, bbox=initial_bbox)

        # Track through 5 frames
        frames_tracked = 0
        for frame_idx, obj_ids, masks in tracker.propagate(max_frames=5):
            frames_tracked += 1
            assert 1 in obj_ids

        assert frames_tracked == 5
