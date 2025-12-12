# REFACTOR_PLAN.md

## Video Processing Data Flow Refactoring Plan

**Date:** 2025-12-12
**Branch:** `claude/plan-refactor-data-flow-6zSs1`

---

## 1. Current Data Flow Map

### 1.1 Video Input Sources (app.py)

```
┌─────────────────────────────────────────────────────────────────────┐
│                      USER INPUT (app.py)                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   [GCS URI]              [YouTube URL]           [File Upload]      │
│       │                       │                       │             │
│       │                       ▼                       ▼             │
│       │              download_youtube_video()   upload_to_gcs()     │
│       │                       │                       │             │
│       │                       ▼                       ▼             │
│       └──────────────────────►│◄──────────────────────┘             │
│                               │                                     │
│                               ▼                                     │
│                     video_uri (gs://bucket/path.mp4)                │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    ANALYSIS ENGINE (agent.py)                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   create_coach_agent(model_name, sport)                             │
│       │                                                             │
│       ▼                                                             │
│   BasketballAgent / UltimateAgent                                   │
│       │                                                             │
│       ▼                                                             │
│   analyze_full_video_stream(video_uri, ...)                         │
│       │                                                             │
│       ├──► get_video_duration() ──► ffprobe via signed URL          │
│       │                                                             │
│       └──► FOR EACH SEGMENT:                                        │
│               │                                                     │
│               ├──► [PASS 1] VideoAnalysisTool.analyze_video_segment │
│               │        └── Uses GCS URI directly with Gemini API    │
│               │                                                     │
│               └──► [PASS 2 - if high_fidelity=True]                 │
│                       │                                             │
│                       ▼                                             │
│               VideoAnalysisTool.analyze_tiled_sequence()            │
│                       │                                             │
│                       ├── Generate signed URL                       │
│                       ├── extract_and_tile_frames()  ◄─── KEY AREA  │
│                       └── Send image sequence to Gemini             │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 Current Frame Extraction & Tiling (agent.py:103-222)

```
extract_and_tile_frames(video_path, start_sec, end_sec, fps, num_tiles, overlap_ratio)
    │
    ├── Step 1: FFmpeg Frame Extraction
    │       │
    │       └── ffmpeg -ss {start} -i {video_path} -t {duration} -vf fps={fps} frame_%04d.png
    │               │
    │               └── Outputs: frame_0001.png, frame_0002.png, ...
    │
    ├── Step 2: Calculate Tile Geometry (calculate_tile_geometry())
    │       │
    │       ├── strip_width = frame_width / (num_tiles - overlap_ratio × (num_tiles-1))
    │       ├── overlap_pixels = strip_width × overlap_ratio
    │       └── Returns: [(x_start, tile_width), ...] for each tile
    │
    └── Step 3: PIL Cropping (FOR EACH FRAME)
            │
            ├── Image.open(frame_path)
            ├── FOR EACH TILE:
            │       └── img.crop((x_start, 0, x_start + tile_width, frame_height))
            │               └── tile.save(tile_path, quality=95)
            └── Delete original frame
```

**Current Limitations:**
- Two-step process: FFmpeg extracts frames → PIL crops tiles
- I/O overhead: Each frame written to disk twice
- No geometry-aware cropping (purely pixel-based)
- No camera perspective correction

---

## 2. FFmpeg filter_complex Injection Point

### 2.1 Target Function

**File:** `agent.py`
**Function:** `extract_and_tile_frames()` (lines 103-222)

### 2.2 Current FFmpeg Command (line 151-159)

```python
ffmpeg_cmd = [
    'ffmpeg',
    '-ss', str(start_sec),      # Start time
    '-i', video_path,           # Input file
    '-t', str(duration),        # Duration
    '-vf', f'fps={fps}',        # Frame rate filter
    '-q:v', '2',                # Quality
    '-y',                       # Overwrite
    frame_pattern
]
```

### 2.3 Proposed filter_complex Replacement

Replace the current two-step process with a single FFmpeg command using `filter_complex`:

```python
def extract_and_tile_frames_v2(
    video_path: str,
    start_sec: float,
    end_sec: float,
    fps: int = 3,
    num_tiles: int = 3,
    overlap_ratio: float = 0.20,
    output_dir: Optional[str] = None
) -> List[List[str]]:
    """
    Extract frames AND tile them in a single FFmpeg pass using filter_complex
    """
    # Calculate tile geometry
    frame_width = get_video_width(video_path)  # New helper needed
    tiles = calculate_tile_geometry(frame_width, num_tiles, overlap_ratio)

    duration = end_sec - start_sec

    # Build filter_complex for vertical strip cropping
    # Example for 3 tiles from 3840px wide video:
    # crop=1477:2160:0:0      (tile 0: left)
    # crop=1477:2160:1182:0   (tile 1: center)
    # crop=1477:2160:2363:0   (tile 2: right)

    filter_parts = []
    output_mappings = []

    for i, (x_start, tile_width) in enumerate(tiles):
        filter_parts.append(
            f"[0:v]fps={fps},crop={tile_width}:ih:{x_start}:0[tile{i}]"
        )
        output_mappings.extend([
            '-map', f'[tile{i}]',
            f'{output_dir}/frame_%04d_tile_{i}.jpg'
        ])

    filter_complex = ";".join(filter_parts)

    ffmpeg_cmd = [
        'ffmpeg',
        '-ss', str(start_sec),
        '-i', video_path,
        '-t', str(duration),
        '-filter_complex', filter_complex,
        '-q:v', '2',
        '-y',
    ] + output_mappings

    # Execute and return tiled frame paths
    ...
```

### 2.4 Benefits of filter_complex Approach

| Aspect | Current (FFmpeg + PIL) | Proposed (filter_complex) |
|--------|------------------------|---------------------------|
| I/O Operations | 2× per frame (extract + crop) | 1× per tile |
| Processing | Sequential Python loop | Parallel FFmpeg streams |
| Memory | Load full frame in PIL | Stream-based |
| Latency | ~2-3s per segment | ~0.5-1s per segment |
| Dependency | Requires Pillow | FFmpeg only |

### 2.5 Injection Strategy

1. **Add new function** `extract_and_tile_frames_v2()` alongside existing
2. **Add feature flag** to toggle between methods
3. **Add helper** `get_video_dimensions()` using ffprobe
4. **Deprecate** PIL cropping loop after validation

---

## 3. GeometryEngine Class Design

### 3.1 Purpose

The `GeometryEngine` implements the Criminisi algorithm for single-view metrology, enabling:
- Real-world coordinate estimation from pixel positions
- Camera perspective correction
- Player height/position estimation using court geometry
- Vanishing point detection from court lines

### 3.2 Class Architecture

```python
# New file: geometry_engine.py

from dataclasses import dataclass
from typing import Tuple, List, Optional
import numpy as np

@dataclass
class CameraCalibration:
    """Camera intrinsic and extrinsic parameters"""
    focal_length: float
    principal_point: Tuple[float, float]
    vanishing_points: List[Tuple[float, float]]  # Vx, Vy, Vz
    reference_height: float  # Known height (e.g., rim = 10ft)
    reference_pixels: Tuple[int, int]  # Pixel coords of reference

@dataclass
class CourtGeometry:
    """Known court dimensions for calibration"""
    court_width: float = 50.0  # feet (NBA)
    court_length: float = 94.0  # feet (NBA)
    three_point_distance: float = 23.75  # feet
    rim_height: float = 10.0  # feet

class GeometryEngine:
    """
    Criminisi-based single-view geometry engine for sports video analysis

    Estimates real-world positions from 2D pixel coordinates using:
    1. Court line detection for vanishing points
    2. Known reference heights (rim, player)
    3. Homography estimation from court markings
    """

    def __init__(self, court: CourtGeometry = None):
        self.court = court or CourtGeometry()
        self.calibration: Optional[CameraCalibration] = None
        self._homography: Optional[np.ndarray] = None

    # ─────────────────────────────────────────────────────────────────
    # Calibration Methods
    # ─────────────────────────────────────────────────────────────────

    def calibrate_from_court_lines(
        self,
        frame: np.ndarray,
        court_corners: List[Tuple[int, int]] = None
    ) -> CameraCalibration:
        """
        Auto-detect court lines and compute camera parameters

        Args:
            frame: BGR image of court
            court_corners: Optional manual corner annotations

        Returns:
            CameraCalibration with vanishing points and homography
        """
        # 1. Detect court lines using Hough transform or edge detection
        # 2. Find intersections to get vanishing points
        # 3. Compute homography from known court dimensions
        pass

    def calibrate_from_reference(
        self,
        pixel_coords: Tuple[int, int],
        real_height: float,
        camera_height: float
    ) -> None:
        """
        Calibrate using a known reference object (e.g., player of known height)
        """
        pass

    # ─────────────────────────────────────────────────────────────────
    # Coordinate Transformation
    # ─────────────────────────────────────────────────────────────────

    def pixel_to_court(
        self,
        pixel_x: int,
        pixel_y: int
    ) -> Tuple[float, float]:
        """
        Convert pixel coordinates to court coordinates (feet)

        Uses homography matrix computed during calibration
        """
        if self._homography is None:
            raise ValueError("Camera not calibrated")

        point = np.array([pixel_x, pixel_y, 1])
        court_point = self._homography @ point
        return (court_point[0] / court_point[2],
                court_point[1] / court_point[2])

    def estimate_height(
        self,
        foot_pixel: Tuple[int, int],
        head_pixel: Tuple[int, int]
    ) -> float:
        """
        Estimate real-world height of an object from foot/head pixels

        Uses Criminisi's height estimation formula:
        H_real = H_ref × (d(v, b) × d(t, r)) / (d(v, t) × d(b, r))

        Where:
        - v = vertical vanishing point (zenith)
        - b = base (foot) pixel
        - t = top (head) pixel
        - r = reference point
        """
        pass

    def estimate_distance_from_camera(
        self,
        player_foot_pixel: Tuple[int, int]
    ) -> float:
        """
        Estimate distance from camera to player using floor plane
        """
        pass

    # ─────────────────────────────────────────────────────────────────
    # Smart Tiling (Geometry-Aware)
    # ─────────────────────────────────────────────────────────────────

    def calculate_perspective_tiles(
        self,
        frame_width: int,
        frame_height: int,
        num_tiles: int = 3
    ) -> List[Tuple[int, int, int, int]]:
        """
        Calculate tile boundaries that account for perspective

        Near court (bottom of frame) gets more pixels per tile
        Far court (top of frame) can have wider tiles

        Returns:
            List of (x, y, width, height) crop rectangles
        """
        pass

    def get_player_tile_weights(
        self,
        player_positions: List[Tuple[int, int]]
    ) -> List[float]:
        """
        Weight tiles by number of players for selective high-fidelity
        """
        pass
```

### 3.3 Integration with Current Tiling

```
                    CURRENT FLOW
                    ────────────

extract_and_tile_frames()
    │
    ├── calculate_tile_geometry()  ◄── Pure pixel math
    │       └── Equal-width strips
    │
    └── PIL crop loop


                    PROPOSED FLOW (Side-by-Side)
                    ───────────────────────────────

extract_and_tile_frames()
    │
    ├── [Option A] calculate_tile_geometry()     ◄── Current (pixel-based)
    │       └── Equal-width strips
    │
    └── [Option B] GeometryEngine.calculate_perspective_tiles()  ◄── NEW
            │
            ├── Calibrate from first frame
            ├── Account for perspective
            └── Variable-width tiles (wider at horizon)
```

### 3.4 Testing Strategy

```python
# Side-by-side comparison
def analyze_segment_dual_mode(video_uri, start_sec, end_sec):
    """
    Analyze same segment with both pixel and geometry tiling
    Compare event detection rates
    """
    # Method A: Current pixel-based
    tiles_pixel = calculate_tile_geometry(frame_width)
    result_pixel = analyze_with_tiles(tiles_pixel)

    # Method B: Geometry-aware
    engine = GeometryEngine()
    engine.calibrate_from_court_lines(first_frame)
    tiles_geo = engine.calculate_perspective_tiles(frame_width, frame_height)
    result_geo = analyze_with_tiles(tiles_geo)

    return {
        "pixel_events": len(result_pixel.events),
        "geometry_events": len(result_geo.events),
        "improvement": (len(result_geo.events) - len(result_pixel.events))
                       / len(result_pixel.events) * 100
    }
```

---

## 4. Implementation Phases

### Phase 1: FFmpeg filter_complex (Low Risk)

**Scope:**
- New function `extract_and_tile_frames_v2()`
- New helper `get_video_dimensions()`
- Feature flag `use_filter_complex=False` (default off)
- A/B testing infrastructure

**Files Modified:**
- `agent.py` (add new functions)

### Phase 2: GeometryEngine Foundation (Medium Risk)

**Scope:**
- New file `geometry_engine.py`
- Basic court line detection using OpenCV
- Homography computation
- Integration point in `analyze_tiled_sequence()`

**Files Added:**
- `geometry_engine.py`

**Dependencies Added:**
- `opencv-python` (for court line detection)

### Phase 3: Perspective-Aware Tiling (Higher Risk)

**Scope:**
- Replace uniform tiles with perspective-corrected tiles
- Validate improvement in player detection
- Benchmark token usage vs accuracy

**Files Modified:**
- `agent.py` (integrate GeometryEngine)
- `app.py` (add UI toggle for geometry mode)

---

## 5. File Summary

| File | Current Role | Proposed Changes |
|------|--------------|------------------|
| `agent.py` | Frame extraction, tiling, analysis | Add `extract_and_tile_frames_v2()`, feature flags |
| `app.py` | Video input, UI | Add geometry mode toggle |
| `geometry_engine.py` | (NEW) | GeometryEngine class, Criminisi implementation |
| `TILED_VISION_ARCHITECTURE.md` | Documentation | Update with geometry mode docs |

---

## 6. Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| filter_complex complexity | Fallback to current PIL method |
| Court line detection failures | Manual calibration option |
| Performance regression | Feature flags for A/B testing |
| Dependency bloat (OpenCV) | Optional import with graceful degradation |

---

## 7. Success Metrics

1. **FFmpeg filter_complex:**
   - 50% reduction in frame extraction time
   - Identical output quality

2. **GeometryEngine:**
   - 20%+ improvement in player detection rate
   - Accurate height estimation (±5%)
   - Successful calibration on 80%+ of court footage

---

## 8. Note on Missing File

The task mentioned `your_video_script.py` - this file **does not exist** in the current codebase. The video processing logic is entirely contained in:
- `agent.py` (extraction, tiling, analysis)
- `app.py` (input handling, UI)

If `your_video_script.py` is intended to be a new file, it should be created as part of this refactoring effort.

---

**Status:** PLAN COMPLETE - Ready for Implementation
