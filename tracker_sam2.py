"""
SAM2Tracker - Segment Anything Model 2 wrapper for video object tracking

Provides a high-level interface for tracking objects (players) in video
using SAM2's video predictor with temporal memory. Accepts YOLO-style
bounding box prompts and returns segmentation masks.

The tracker maintains inference state and temporal memory across frames,
enabling consistent object tracking throughout a video sequence.

Usage:
    from tracker_sam2 import SAM2Tracker

    # With real SAM2 (requires segment-anything-2 installed)
    tracker = SAM2Tracker.create_default()

    # Or with custom predictor (for testing)
    tracker = SAM2Tracker(predictor=my_predictor)

    # Initialize for video
    tracker.initialize_video("/path/to/video.mp4")

    # Add object from YOLO detection
    bbox = np.array([x1, y1, x2, y2])
    tracker.add_object(frame_idx=0, obj_id=1, bbox=bbox)

    # Propagate through video
    for frame_idx, obj_ids, masks in tracker.propagate(max_frames=100):
        # Process masks...
        pass
"""
import logging
from typing import Dict, Any, Optional, List, Tuple, Generator, Union
import numpy as np

logger = logging.getLogger(__name__)


class SAM2Tracker:
    """
    SAM2 Video Tracker wrapper for object segmentation and tracking.

    Wraps the SAM2 video predictor to provide a simplified interface for:
    1. Initializing tracking state for a video
    2. Adding objects via bounding box prompts (from YOLO)
    3. Propagating tracking through frames with temporal memory
    4. Retrieving segmentation masks for tracked objects

    The tracker maintains:
    - inference_state: SAM2's internal state for video processing
    - temporal_memory: Frame-by-frame tracking results
    - tracked_objects: Registry of objects being tracked

    Args:
        predictor: SAM2 video predictor instance (or mock for testing)
        device: Device to run inference on ("cuda" or "cpu")
    """

    def __init__(
        self,
        predictor: Any,
        device: str = "cpu"
    ):
        """
        Initialize SAM2Tracker with a predictor.

        Args:
            predictor: SAM2 video predictor (real or mock)
            device: Inference device
        """
        self.predictor = predictor
        self.device = device

        # State management
        self.inference_state: Optional[Dict[str, Any]] = None
        self.tracked_objects: Dict[int, Dict[str, Any]] = {}
        self.current_frame_idx: int = 0
        self._initialized: bool = False

    @classmethod
    def create_default(
        cls,
        model_cfg: str = "sam2_hiera_l.yaml",
        checkpoint: Optional[str] = None,
        device: str = "cuda"
    ) -> "SAM2Tracker":
        """
        Create tracker with default SAM2 video predictor.

        Args:
            model_cfg: SAM2 model configuration file
            checkpoint: Path to model checkpoint (optional)
            device: Device for inference

        Returns:
            SAM2Tracker instance

        Raises:
            ImportError: If segment-anything-2 is not installed
        """
        try:
            from sam2.build_sam import build_sam2_video_predictor
        except ImportError:
            raise ImportError(
                "segment-anything-2 is required. Install with: "
                "pip install segment-anything-2"
            )

        predictor = build_sam2_video_predictor(
            model_cfg,
            checkpoint,
            device=device
        )

        return cls(predictor=predictor, device=device)

    def initialize_video(self, video_path: str) -> Dict[str, Any]:
        """
        Initialize inference state for a video.

        Must be called before adding objects or propagating.

        Args:
            video_path: Path to video file

        Returns:
            Inference state dictionary
        """
        logger.info(f"Initializing SAM2 tracker for video: {video_path}")

        self.inference_state = self.predictor.init_state(video_path)
        self.tracked_objects = {}
        self.current_frame_idx = 0
        self._initialized = True

        logger.info("SAM2 inference state initialized")
        return self.inference_state

    def reset(self) -> None:
        """
        Reset tracker state while keeping video initialized.

        Clears all tracked objects and temporal memory.
        """
        if not self._initialized:
            return

        self.predictor.reset_state(self.inference_state)
        self.tracked_objects = {}
        self.current_frame_idx = 0

        logger.info("SAM2 tracker state reset")

    def add_object(
        self,
        frame_idx: int,
        obj_id: int,
        bbox: np.ndarray,
        points: Optional[np.ndarray] = None,
        labels: Optional[np.ndarray] = None,
    ) -> Dict[str, Any]:
        """
        Add an object to track using a bounding box prompt.

        Accepts YOLO-style bounding box [x1, y1, x2, y2] and initializes
        tracking for the object at the specified frame.

        Args:
            frame_idx: Frame index where object appears
            obj_id: Unique identifier for this object
            bbox: Bounding box as [x1, y1, x2, y2] numpy array
            points: Optional point prompts (N, 2)
            labels: Optional point labels (N,) - 1 for foreground, 0 for background

        Returns:
            Dict with keys:
                - obj_id: Object ID
                - frame_idx: Frame where added
                - mask: Initial segmentation mask

        Raises:
            RuntimeError: If video not initialized
            ValueError: If bbox is invalid or frame_idx is negative
        """
        if not self._initialized:
            raise RuntimeError(
                "Video not initialized. Call initialize_video() first."
            )

        if frame_idx < 0:
            raise ValueError(f"frame_idx must be non-negative, got {frame_idx}")

        if bbox is None:
            raise ValueError("bbox cannot be None")

        bbox = np.asarray(bbox)
        if bbox.shape != (4,):
            raise ValueError(f"bbox must have shape (4,), got {bbox.shape}")

        logger.debug(f"Adding object {obj_id} at frame {frame_idx} with bbox {bbox}")

        # Call SAM2 predictor
        _, obj_ids, masks = self.predictor.add_new_points_or_box(
            inference_state=self.inference_state,
            frame_idx=frame_idx,
            obj_id=obj_id,
            box=bbox,
            points=points,
            labels=labels,
        )

        # Store tracking info
        self.tracked_objects[obj_id] = {
            "initial_frame": frame_idx,
            "initial_bbox": bbox.copy(),
            "last_mask": masks,
            "last_frame": frame_idx,
        }

        # Extract mask for this object
        mask = masks[0] if masks.ndim == 4 else masks

        logger.info(f"Object {obj_id} added successfully")

        return {
            "obj_id": obj_id,
            "frame_idx": frame_idx,
            "mask": mask,
        }

    def propagate(
        self,
        start_frame: int = 0,
        max_frames: Optional[int] = None,
        reverse: bool = False,
    ) -> Generator[Tuple[int, np.ndarray, np.ndarray], None, None]:
        """
        Propagate tracking through video frames.

        Yields segmentation masks for all tracked objects at each frame.
        Updates temporal memory as tracking progresses.

        Args:
            start_frame: Frame index to start propagation
            max_frames: Maximum number of frames to track (None = all)
            reverse: If True, propagate backwards

        Yields:
            Tuple of (frame_idx, obj_ids, masks)
                - frame_idx: Current frame index
                - obj_ids: Array of object IDs
                - masks: Array of masks (N_objects, 1, H, W)

        Raises:
            RuntimeError: If video not initialized
        """
        if not self._initialized:
            raise RuntimeError(
                "Video not initialized. Call initialize_video() first."
            )

        logger.info(
            f"Starting propagation from frame {start_frame}, "
            f"max_frames={max_frames}, reverse={reverse}"
        )

        for frame_idx, obj_ids, masks in self.predictor.propagate_in_video(
            inference_state=self.inference_state,
            start_frame_idx=start_frame,
            max_frame_num_to_track=max_frames,
            reverse=reverse,
        ):
            self.current_frame_idx = frame_idx

            # Update tracked objects with latest masks
            for i, oid in enumerate(obj_ids):
                if oid in self.tracked_objects:
                    self.tracked_objects[oid]["last_mask"] = masks[i:i+1]
                    self.tracked_objects[oid]["last_frame"] = frame_idx

            yield frame_idx, obj_ids, masks

    def process_frame(
        self,
        frame: np.ndarray,
        frame_idx: int,
    ) -> Dict[str, Any]:
        """
        Process a single frame and return tracking results.

        Used for online/streaming tracking where frames arrive one at a time.

        Args:
            frame: Video frame as numpy array (H, W, 3)
            frame_idx: Index of this frame

        Returns:
            Dict with tracking results for this frame
        """
        if not self._initialized:
            raise RuntimeError(
                "Video not initialized. Call initialize_video() first."
            )

        self.current_frame_idx = frame_idx

        # Get masks for all tracked objects at this frame
        results = {
            "frame_idx": frame_idx,
            "objects": {},
        }

        for obj_id, obj_info in self.tracked_objects.items():
            results["objects"][obj_id] = {
                "mask": obj_info.get("last_mask"),
                "tracked": True,
            }

        return results

    def get_object_mask(
        self,
        obj_id: int,
        frame_idx: Optional[int] = None,
    ) -> Optional[np.ndarray]:
        """
        Get the segmentation mask for a specific object.

        Args:
            obj_id: Object ID to retrieve mask for
            frame_idx: Optional frame index (uses last known if not specified)

        Returns:
            Segmentation mask as numpy array, or None if not found
        """
        if obj_id not in self.tracked_objects:
            return None

        obj_info = self.tracked_objects[obj_id]

        # If specific frame requested, check temporal memory
        if frame_idx is not None and self.inference_state:
            temporal_mem = self.inference_state.get("temporal_memory", {})
            if frame_idx in temporal_mem:
                frame_data = temporal_mem[frame_idx]
                obj_ids = frame_data.get("obj_ids", [])
                masks = frame_data.get("masks")

                if masks is not None:
                    for i, oid in enumerate(obj_ids):
                        if oid == obj_id:
                            return masks[i]

        # Return last known mask
        return obj_info.get("last_mask")

    def get_all_masks(
        self,
        frame_idx: Optional[int] = None,
    ) -> Dict[int, np.ndarray]:
        """
        Get masks for all tracked objects.

        Args:
            frame_idx: Optional frame index

        Returns:
            Dict mapping object ID to mask
        """
        masks = {}

        for obj_id in self.tracked_objects:
            mask = self.get_object_mask(obj_id, frame_idx)
            if mask is not None:
                masks[obj_id] = mask

        return masks

    @property
    def num_tracked_objects(self) -> int:
        """Number of currently tracked objects."""
        return len(self.tracked_objects)

    @property
    def object_ids(self) -> List[int]:
        """List of tracked object IDs."""
        return list(self.tracked_objects.keys())

    def remove_object(self, obj_id: int) -> bool:
        """
        Remove an object from tracking.

        Args:
            obj_id: Object ID to remove

        Returns:
            True if object was removed, False if not found
        """
        if obj_id in self.tracked_objects:
            del self.tracked_objects[obj_id]
            logger.info(f"Object {obj_id} removed from tracking")
            return True

        return False
