"""
Multi-Sport Video Analysis Agent using Google ADK (google-genai)

Supports: Basketball, Ultimate Frisbee
"""
import os
import re
import subprocess
import tempfile
import base64
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from google import genai
from google.genai import types
from google.cloud import storage
import logging

# Image processing imports (for tiled vision)
try:
    from PIL import Image
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False
    logging.warning("Pillow not available - High Fidelity mode will not work")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# Helper Functions
# ============================================================================

def format_timestamp(seconds: int) -> str:
    """Convert seconds to MM:SS format for human-readable timestamps"""
    minutes = int(seconds) // 60
    secs = int(seconds) % 60
    return f"{minutes}:{secs:02d}"


def check_ffmpeg_available() -> bool:
    """Check if ffmpeg is available on the system"""
    try:
        subprocess.run(
            ['ffmpeg', '-version'],
            capture_output=True,
            check=True,
            timeout=5
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False


def calculate_tile_geometry(
    frame_width: int,
    num_tiles: int = 3,
    overlap_ratio: float = 0.20
) -> List[Tuple[int, int]]:
    """
    Calculate tile positions for vertical strips with overlap

    Args:
        frame_width: Total width of the frame in pixels
        num_tiles: Number of vertical tiles (default: 3)
        overlap_ratio: Overlap ratio between adjacent tiles (default: 0.20 = 20%)

    Returns:
        List of (x_start, tile_width) tuples for each tile

    Example for 3840px width:
        Returns: [(0, 1477), (1182, 1477), (2363, 1477)]
        This provides 20% overlap between adjacent tiles
    """
    # Calculate strip width: W_strip = W_total / (N - r×(N-1))
    strip_width = int(frame_width / (num_tiles - overlap_ratio * (num_tiles - 1)))

    # Calculate overlap in pixels
    overlap_pixels = int(strip_width * overlap_ratio)

    # Calculate starting positions for each tile
    tiles = []
    for i in range(num_tiles):
        if i == 0:
            # First tile starts at 0
            x_start = 0
        else:
            # Subsequent tiles start at previous_start + strip_width - overlap
            x_start = tiles[-1][0] + strip_width - overlap_pixels

        # Last tile: adjust width to reach exactly to frame_width
        if i == num_tiles - 1:
            actual_width = frame_width - x_start
        else:
            actual_width = strip_width

        tiles.append((x_start, actual_width))

    logger.info(f"Tile geometry for {frame_width}px: {tiles}")
    return tiles


def extract_and_tile_frames(
    video_path: str,
    start_sec: float,
    end_sec: float,
    fps: int = 3,
    num_tiles: int = 3,
    overlap_ratio: float = 0.20,
    output_dir: Optional[str] = None
) -> List[List[str]]:
    """
    Extract frames from video and tile them into vertical strips

    Args:
        video_path: Path to video file (local or signed URL)
        start_sec: Start time in seconds
        end_sec: End time in seconds
        fps: Frames per second to extract (default: 3)
        num_tiles: Number of vertical tiles per frame (default: 3)
        overlap_ratio: Overlap ratio between tiles (default: 0.20)
        output_dir: Directory to save tiled frames (if None, uses temp dir)

    Returns:
        List of lists - outer list is frames, inner list is tile paths for each frame
        Example: [['frame0_tile0.jpg', 'frame0_tile1.jpg', 'frame0_tile2.jpg'],
                  ['frame1_tile0.jpg', 'frame1_tile1.jpg', 'frame1_tile2.jpg'], ...]
    """
    if not PILLOW_AVAILABLE:
        raise RuntimeError("Pillow is required for tiled vision but not available")

    if not check_ffmpeg_available():
        raise RuntimeError("ffmpeg is required for tiled vision but not available")

    # Create output directory
    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="tiled_frames_")
    else:
        os.makedirs(output_dir, exist_ok=True)

    output_dir_path = Path(output_dir)

    logger.info(f"Extracting frames from {start_sec}s to {end_sec}s at {fps} FPS")

    # Step 1: Extract frames using ffmpeg
    # Output pattern: frame_%04d.png
    frame_pattern = str(output_dir_path / "frame_%04d.png")

    duration = end_sec - start_sec

    ffmpeg_cmd = [
        'ffmpeg',
        '-ss', str(start_sec),  # Start time
        '-i', video_path,  # Input file
        '-t', str(duration),  # Duration
        '-vf', f'fps={fps}',  # Frame rate
        '-q:v', '2',  # High quality (1-31, lower is better)
        '-y',  # Overwrite output files
        frame_pattern
    ]

    try:
        result = subprocess.run(
            ffmpeg_cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
            check=True
        )
        logger.info(f"ffmpeg extraction completed")
    except subprocess.CalledProcessError as e:
        logger.error(f"ffmpeg extraction failed: {e.stderr}")
        raise RuntimeError(f"Frame extraction failed: {e.stderr}")
    except subprocess.TimeoutExpired:
        logger.error("ffmpeg extraction timed out after 5 minutes")
        raise RuntimeError("Frame extraction timed out")

    # Step 2: Find all extracted frames
    extracted_frames = sorted(output_dir_path.glob("frame_*.png"))

    if not extracted_frames:
        raise RuntimeError(f"No frames extracted from {video_path}")

    logger.info(f"Extracted {len(extracted_frames)} frames")

    # Step 3: Tile each frame
    all_tiled_frames = []

    for frame_idx, frame_path in enumerate(extracted_frames):
        try:
            # Load frame
            img = Image.open(frame_path)
            frame_width, frame_height = img.size

            # Calculate tile geometry (only need to do this once)
            if frame_idx == 0:
                tile_geometry = calculate_tile_geometry(
                    frame_width, num_tiles, overlap_ratio
                )

            # Crop tiles
            frame_tiles = []
            for tile_idx, (x_start, tile_width) in enumerate(tile_geometry):
                # Crop: (left, top, right, bottom)
                tile = img.crop((x_start, 0, x_start + tile_width, frame_height))

                # Save tile
                tile_path = output_dir_path / f"frame_{frame_idx:04d}_tile_{tile_idx}.jpg"
                tile.save(tile_path, quality=95)
                frame_tiles.append(str(tile_path))

            all_tiled_frames.append(frame_tiles)

            # Clean up original frame to save space
            frame_path.unlink()

        except Exception as e:
            logger.error(f"Error tiling frame {frame_path}: {e}")
            raise

    logger.info(f"Created {len(all_tiled_frames)} frames with {num_tiles} tiles each")
    return all_tiled_frames


class VideoAnalysisTool:
    """Generic video segment analysis tool - used by all sport agents"""

    def __init__(self, model_name: str = "gemini-2.5-flash-lite"):
        """
        Initialize the video analysis tool

        Args:
            model_name: The Gemini model to use for analysis
        """
        self.model_name = model_name
        self.client = genai.Client(
            vertexai=True,
            project=os.getenv("GCP_PROJECT_ID"),
            location=os.getenv("GCP_LOCATION", "us-central1")
        )

    def _is_output_incomplete(self, text: str) -> bool:
        """
        Check if the output appears to be truncated or incomplete

        Args:
            text: The analysis text to check

        Returns:
            True if output appears incomplete
        """
        # Check for common signs of truncation
        truncation_indicators = [
            text.endswith('#'),  # Cut off mid-number reference
            text.endswith('*'),  # Cut off mid-markdown
            text.count('*') % 2 != 0,  # Odd number of asterisks (unclosed markdown)
            len(text) < 50,  # Suspiciously short
            text.strip().endswith(':'),  # Ends with colon (incomplete list)
            '**' in text and text.rfind('**') > len(text) - 20,  # Unclosed bold near end
        ]

        return any(truncation_indicators)

    def analyze_video_segment(
        self,
        video_uri: str,
        start_sec: float,
        end_sec: float,
        prompt: str,
        previous_context: Optional[str] = None
    ) -> tuple[str, dict]:
        """
        Analyze a specific segment of video using provided sport-specific prompt

        Args:
            video_uri: GCS URI of the video (gs://bucket/path/to/video.mp4)
            start_sec: Start time in seconds
            end_sec: End time in seconds
            prompt: Sport-specific analysis prompt
            previous_context: Context from previous segment for continuity

        Returns:
            Tuple of (analysis_text, token_usage_dict)
        """
        try:
            # Create video part with time range
            # Note: VideoMetadata offsets are strings with 's' suffix (e.g., "60s")
            video_part = types.Part.from_uri(
                file_uri=video_uri,
                mime_type="video/mp4"
            )

            # Add time range metadata
            video_part.video_metadata = types.VideoMetadata(
                start_offset=f"{int(start_sec)}s",
                end_offset=f"{int(end_sec)}s"
            )

            # Generate content with LOW temperature for factual accuracy
            logger.info(f"Analyzing segment {start_sec}-{end_sec}s with model: {self.model_name}")

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[prompt, video_part],
                config=types.GenerateContentConfig(
                    temperature=0.2,  # Low creativity - factual play-by-play
                    max_output_tokens=4096,  # Increased from 2048 for complete coverage
                )
            )

            result = response.text

            # Extract token usage metadata
            token_usage = {}
            if hasattr(response, 'usage_metadata'):
                usage = response.usage_metadata
                token_usage = {
                    "prompt_tokens": getattr(usage, 'prompt_token_count', 0),
                    "output_tokens": getattr(usage, 'candidates_token_count', 0),
                    "total_tokens": getattr(usage, 'total_token_count', 0)
                }
                logger.info(f"Segment {start_sec}-{end_sec}s token usage:")
                logger.info(f"  - Prompt tokens: {token_usage['prompt_tokens']} (includes video)")
                logger.info(f"  - Output tokens: {token_usage['output_tokens']}")
                logger.info(f"  - Total tokens: {token_usage['total_tokens']}")
            else:
                logger.warning(f"No usage metadata available for segment {start_sec}-{end_sec}s")
                token_usage = {"prompt_tokens": 0, "output_tokens": 0, "total_tokens": 0}

            # Validate output quality
            if self._is_output_incomplete(result):
                logger.warning(f"Segment {start_sec}-{end_sec}s appears to have incomplete output")
                # Add warning to result
                result = f"{result}\n\n⚠️ [Note: This segment analysis may be incomplete. Consider using shorter chunk sizes.]"

            logger.info(f"Successfully analyzed segment {start_sec}-{end_sec}s")
            return result, token_usage

        except Exception as e:
            error_msg = f"Error analyzing segment {start_sec}-{end_sec}s: {str(e)}"
            logger.error(error_msg)
            logger.error(f"Model: {self.model_name}")
            logger.error(f"Video URI: {video_uri}")
            logger.error(f"Time range: {start_sec}s - {end_sec}s")
            logger.error(f"Prompt length: {len(prompt)} characters")

            # Check for specific error types
            error_str = str(e).lower()
            if "404" in error_str or "not found" in error_str:
                if "gemini-3" in self.model_name:
                    logger.error("⚠️ Gemini 3 model not available. Try:")
                    logger.error("  1. Use gemini-2.5-pro instead (fully available)")
                    logger.error("  2. Check if your project has Gemini 3 access")
                    logger.error("  3. Gemini 3 may require allowlist or newer API version")
                else:
                    logger.error(f"⚠️ Model {self.model_name} not found in your project")

            # Log the full exception for debugging
            import traceback
            logger.error(f"Full traceback:\n{traceback.format_exc()}")

            return error_msg, {"prompt_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    def analyze_tiled_sequence(
        self,
        video_uri: str,
        start_sec: float,
        end_sec: float,
        prompt: str,
        fps: int = 3,
        num_tiles: int = 3,
        overlap_ratio: float = 0.20
    ) -> tuple[str, dict]:
        """
        Analyze video segment using tiled high-resolution frames (Tiled Vision Pipeline)

        This method implements the "Tiled Vision" approach to overcome the Wide-Angle Paradox.
        Instead of sending the video URI directly to Gemini (which causes visual erasure due to
        token compression), we extract frames, tile them into vertical strips, and send them as
        a sequence of high-resolution images.

        Token allocation:
        - Native Video: ~258 tokens per 4K frame → Visual Erasure
        - Tiled Vision: ~1,120 tokens per tile × 3 tiles = ~3,360 tokens per timestamp → Biomechanical fidelity

        Args:
            video_uri: GCS URI of the video (gs://bucket/path/to/video.mp4)
            start_sec: Start time in seconds
            end_sec: End time in seconds
            prompt: Sport-specific analysis prompt
            fps: Frames per second to extract (default: 3)
            num_tiles: Number of vertical tiles per frame (default: 3)
            overlap_ratio: Horizontal overlap between tiles (default: 0.20)

        Returns:
            Tuple of (analysis_text, token_usage_dict)
        """
        try:
            # Check dependencies
            if not PILLOW_AVAILABLE:
                logger.warning("Pillow not available, falling back to Native Video mode")
                return self.analyze_video_segment(video_uri, start_sec, end_sec, prompt)

            if not check_ffmpeg_available():
                logger.warning("ffmpeg not available, falling back to Native Video mode")
                return self.analyze_video_segment(video_uri, start_sec, end_sec, prompt)

            logger.info(f"🎬 Starting Tiled Vision analysis: {start_sec}-{end_sec}s")
            logger.info(f"   FPS: {fps}, Tiles: {num_tiles}, Overlap: {overlap_ratio*100}%")

            # Step 1: Generate signed URL for video access
            logger.info("Generating signed URL for video access...")
            if not video_uri.startswith("gs://"):
                raise ValueError("Video URI must be a GCS URI (gs://...)")

            # Parse GCS URI
            uri_parts = video_uri[5:].split("/", 1)
            bucket_name = uri_parts[0]
            blob_path = uri_parts[1] if len(uri_parts) > 1 else ""

            # Create signed URL
            storage_client = storage.Client()
            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_path)

            signed_url = blob.generate_signed_url(
                version="v4",
                expiration=3600,  # 1 hour
                method="GET"
            )

            logger.info("✅ Signed URL generated")

            # Step 2: Extract and tile frames
            logger.info("Extracting and tiling frames...")
            tiled_frames = extract_and_tile_frames(
                video_path=signed_url,
                start_sec=start_sec,
                end_sec=end_sec,
                fps=fps,
                num_tiles=num_tiles,
                overlap_ratio=overlap_ratio
            )

            logger.info(f"✅ Extracted {len(tiled_frames)} frames with {num_tiles} tiles each")

            # Step 3: Create image parts for API
            # We'll send all tiles in sequence: [frame0_tile0, frame0_tile1, frame0_tile2, frame1_tile0, ...]
            image_parts = []

            for frame_idx, frame_tiles in enumerate(tiled_frames):
                for tile_idx, tile_path in enumerate(frame_tiles):
                    # Read and encode image
                    with open(tile_path, 'rb') as f:
                        image_data = f.read()

                    # Create image part
                    image_part = types.Part.from_bytes(
                        data=image_data,
                        mime_type="image/jpeg"
                    )
                    image_parts.append(image_part)

            logger.info(f"Created {len(image_parts)} image parts for API")

            # Step 4: Construct enhanced prompt for tiled analysis
            enhanced_prompt = f"""{prompt}

**TILED VISION MODE ACTIVE**

You are viewing this video segment as a sequence of high-resolution tiled images.
- Total frames: {len(tiled_frames)}
- Tiles per frame: {num_tiles} (vertical strips with {overlap_ratio*100}% overlap)
- Frame rate: {fps} FPS
- Time range: {start_sec}s to {end_sec}s

The images are ordered as:
Frame 1: [Left tile, Center tile, Right tile]
Frame 2: [Left tile, Center tile, Right tile]
... and so on.

Use the high resolution to detect:
- Small player movements (cuts, off-ball motion)
- Biomechanical details (shooting form, defensive stance)
- Fine-grained spatial relationships
- Precise ball location and trajectory

Provide your analysis with the same format and structure as requested above."""

            # Step 5: Call Gemini with image sequence
            logger.info(f"Calling Gemini {self.model_name} with {len(image_parts)} image tiles...")

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[enhanced_prompt] + image_parts,
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    max_output_tokens=4096,
                )
            )

            result = response.text

            # Extract token usage
            token_usage = {}
            if hasattr(response, 'usage_metadata'):
                usage = response.usage_metadata
                token_usage = {
                    "prompt_tokens": getattr(usage, 'prompt_token_count', 0),
                    "output_tokens": getattr(usage, 'candidates_token_count', 0),
                    "total_tokens": getattr(usage, 'total_token_count', 0)
                }
                logger.info(f"🎯 Tiled Vision token usage:")
                logger.info(f"   - Prompt tokens: {token_usage['prompt_tokens']:,} (includes {len(image_parts)} image tiles)")
                logger.info(f"   - Output tokens: {token_usage['output_tokens']:,}")
                logger.info(f"   - Total tokens: {token_usage['total_tokens']:,}")
                logger.info(f"   - Tokens per tile: ~{token_usage['prompt_tokens'] // len(image_parts):,}")
            else:
                logger.warning("No usage metadata available")
                token_usage = {"prompt_tokens": 0, "output_tokens": 0, "total_tokens": 0}

            # Step 6: Cleanup tiled frames
            logger.info("Cleaning up temporary files...")
            if tiled_frames:
                # Get the directory from first tile
                first_tile_dir = Path(tiled_frames[0][0]).parent
                try:
                    import shutil
                    shutil.rmtree(first_tile_dir)
                    logger.info("✅ Temporary files cleaned up")
                except Exception as e:
                    logger.warning(f"Could not clean up temp directory: {e}")

            logger.info(f"✅ Tiled Vision analysis complete for segment {start_sec}-{end_sec}s")
            return result, token_usage

        except Exception as e:
            error_msg = f"Error in Tiled Vision analysis {start_sec}-{end_sec}s: {str(e)}"
            logger.error(error_msg)
            logger.error(f"Falling back to Native Video mode")

            # Fallback to native video mode
            try:
                return self.analyze_video_segment(video_uri, start_sec, end_sec, prompt)
            except Exception as fallback_error:
                logger.error(f"Fallback also failed: {fallback_error}")
                return error_msg, {"prompt_tokens": 0, "output_tokens": 0, "total_tokens": 0}


class BaseSportAgent:
    """
    Base class for sport-specific video analysis agents

    Provides shared infrastructure for video processing, duration detection,
    streaming analysis, and retroactive classification. Sport-specific subclasses
    implement prompts, event parsing, and heuristics.
    """

    def __init__(self, model_name: str = "gemini-2.5-pro", sport_name: str = "Generic Sport"):
        """
        Initialize the base sport agent

        Args:
            model_name: The Gemini model to use (default: gemini-2.5-pro)
            sport_name: Display name for the sport
        """
        self.model_name = model_name
        self.sport_name = sport_name
        self.video_tool = VideoAnalysisTool(model_name=model_name)
        self.client = genai.Client(
            vertexai=True,
            project=os.getenv("GCP_PROJECT_ID"),
            location=os.getenv("GCP_LOCATION", "us-central1")
        )

    # Abstract methods - must be implemented by subclasses
    def get_system_instruction(self) -> str:
        """Return sport-specific system instruction for the agent"""
        raise NotImplementedError("Subclasses must implement get_system_instruction()")

    def get_analysis_prompt(self, start_sec: float, end_sec: float, previous_context: Optional[str] = None) -> str:
        """Return sport-specific analysis prompt for a segment"""
        raise NotImplementedError("Subclasses must implement get_analysis_prompt()")

    def parse_events(self, analysis_text: str) -> List[Dict[str, Any]]:
        """Parse sport-specific events from analysis text"""
        raise NotImplementedError("Subclasses must implement parse_events()")

    def apply_classification_heuristic(self, events: List[Dict], segment_duration_min: float, initial_classification: str) -> str:
        """Apply sport-specific heuristic to determine final classification"""
        raise NotImplementedError("Subclasses must implement apply_classification_heuristic()")

    def get_compilation_prompt(self, analyses: List[Dict]) -> str:
        """Return sport-specific prompt for final game summary"""
        raise NotImplementedError("Subclasses must implement get_compilation_prompt()")

    def parse_roster(self, analysis_text: str) -> List[Dict[str, Any]]:
        """
        Parse player roster from analysis text (optional - override in subclasses)

        Returns:
            List of player profile dictionaries
        """
        return []  # Default: no roster parsing

    # Shared infrastructure methods
    def get_video_duration(self, video_uri: str) -> Optional[int]:
        """
        Get video duration in seconds from GCS URI using ffprobe

        Args:
            video_uri: GCS URI (gs://bucket/path/to/video.mp4)

        Returns:
            Duration in seconds, or None if unable to determine
        """
        try:
            # Parse GCS URI
            if not video_uri.startswith("gs://"):
                logger.error(f"Invalid GCS URI: {video_uri}")
                return None

            # Extract bucket and blob path
            uri_parts = video_uri[5:].split("/", 1)
            bucket_name = uri_parts[0]
            blob_path = uri_parts[1] if len(uri_parts) > 1 else ""

            # Create signed URL for temporary access
            storage_client = storage.Client()
            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_path)

            # Generate signed URL (valid for 5 minutes)
            signed_url = blob.generate_signed_url(
                version="v4",
                expiration=300,  # 5 minutes
                method="GET"
            )

            # Use ffprobe to get duration (increased timeout for large videos)
            logger.info(f"Running ffprobe on video: {blob_path}")
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                signed_url
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            if result.returncode == 0:
                duration_str = result.stdout.strip()
                if duration_str:
                    duration = float(duration_str)
                    logger.info(f"✅ Detected video duration: {duration:.1f} seconds ({duration/60:.1f} minutes)")
                    return int(duration)
                else:
                    logger.error("ffprobe returned empty duration")
                    return None
            else:
                logger.error(f"❌ ffprobe failed with return code {result.returncode}")
                logger.error(f"ffprobe stderr: {result.stderr}")
                logger.error(f"ffprobe stdout: {result.stdout}")
                return None

        except subprocess.TimeoutExpired:
            logger.error(f"❌ ffprobe timed out after 60 seconds for video: {blob_path}")
            return None
        except Exception as e:
            logger.error(f"❌ Error getting video duration: {type(e).__name__}: {e}")
            import traceback
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            return None

    def analyze_full_video_stream(
        self,
        video_uri: str,
        duration_seconds: Optional[int] = None,
        chunk_size: int = 120,
        start_offset: int = 0,
        high_fidelity: bool = False,
        hf_threshold: float = 2.0,
        hf_fps: int = 3
    ):
        """
        Analyze a full video with streaming progress updates

        Args:
            video_uri: GCS URI of the video
            duration_seconds: Total video duration to analyze (if None, auto-detects from video)
            chunk_size: Size of each analysis chunk in seconds (default: 120 = 2 minutes)
            start_offset: Start time in seconds (skip this much from beginning)
            high_fidelity: Enable High Fidelity Mode (Tiled Vision Pipeline) (default: False)
            hf_threshold: Activity threshold for Pass 2 - events per minute (default: 2.0)
            hf_fps: Frame rate for tiled extraction in FPS (default: 3)

        High Fidelity Mode (Two-Pass Architecture):
            Pass 1: Temporal Filter using Native Video (fast, cheap)
            Pass 2: Tiled Vision on active segments (slow, high accuracy)

            When high_fidelity=True:
            - All segments analyzed with Pass 1 first
            - Segments with events_per_minute >= hf_threshold re-analyzed with Pass 2
            - Pass 2 extracts frames at hf_fps and tiles them for biomechanical fidelity

        Yields:
            Progress dictionaries with status updates and results
        """
        logger.info(f"Starting {self.sport_name} video analysis of {video_uri} from {start_offset}s")

        # Auto-detect duration if not specified
        if duration_seconds is None:
            yield {
                "status": "detecting_duration",
                "message": "Detecting video duration..."
            }
            duration_seconds = self.get_video_duration(video_uri)

            if duration_seconds is None:
                # Fallback to 10 minutes if detection fails
                logger.warning("Could not detect video duration, defaulting to 600 seconds")
                duration_seconds = 600
            else:
                logger.info(f"Auto-detected video duration: {duration_seconds}s")

        # Calculate number of chunks
        # If video is shorter than chunk_size, use video length as chunk size
        effective_chunk_size = min(chunk_size, duration_seconds)
        num_chunks = (duration_seconds + effective_chunk_size - 1) // effective_chunk_size

        yield {
            "status": "initialized",
            "message": f"Starting analysis of {num_chunks} segments",
            "num_chunks": num_chunks,
            "duration_seconds": duration_seconds
        }

        analyses = []
        highlights = []

        # Analyze each chunk
        for i in range(num_chunks):
            # Add start_offset to all times
            start_sec = start_offset + (i * effective_chunk_size)
            end_sec = start_offset + min((i + 1) * effective_chunk_size, duration_seconds)

            yield {
                "status": "processing",
                "message": f"Analyzing segment {i + 1}/{num_chunks} ({start_sec}-{end_sec}s)",
                "segment": i + 1,
                "total_segments": num_chunks,
                "progress": (i / num_chunks) * 100
            }

            # Get previous segment analysis for context (if exists)
            previous_context = analyses[-1]["analysis"] if analyses else None

            # Get sport-specific prompt
            prompt = self.get_analysis_prompt(start_sec, end_sec, previous_context)

            # Analyze segment
            chunk_analysis, token_usage = self.video_tool.analyze_video_segment(
                video_uri=video_uri,
                start_sec=start_sec,
                end_sec=end_sec,
                prompt=prompt,
                previous_context=previous_context
            )

            # Parse events from the analysis
            events = self.parse_events(chunk_analysis)

            # Parse roster profiles (warmup segments only, for sports that support it)
            roster_profiles = self.parse_roster(chunk_analysis)

            # Calculate events per minute
            segment_duration_min = (end_sec - start_sec) / 60.0
            events_per_minute = len(events) / segment_duration_min if segment_duration_min > 0 else 0

            # Extract initial classification from analysis
            initial_classification = "WARMUP"  # default
            if "[GAME]" in chunk_analysis.upper():
                initial_classification = "GAME"
            elif "[WARMUP]" in chunk_analysis.upper():
                initial_classification = "WARMUP"

            analyses.append({
                "segment": i + 1,
                "start_time": start_sec,
                "end_time": end_sec,
                "analysis": chunk_analysis,
                "events": events,
                "roster_profiles": roster_profiles,  # Player profiles from this segment
                "events_per_minute": round(events_per_minute, 1),
                "initial_classification": initial_classification,
                "final_classification": initial_classification,  # Will be updated later
                "token_usage": token_usage  # Token counts for this segment
            })

            # Extract highlights (sport-agnostic keywords + [game] tag)
            is_highlight = any(keyword in chunk_analysis.lower() for keyword in
                   ["highlight", "spectacular", "impressive", "[game]", "layout", "dunk", "half-court"])

            if is_highlight:
                highlights.append({
                    "time": f"{format_timestamp(start_sec)} - {format_timestamp(end_sec)}",
                    "description": chunk_analysis[:200] + "..."
                })

            yield {
                "status": "segment_complete",
                "message": f"Completed segment {i + 1}/{num_chunks}",
                "segment": i + 1,
                "total_segments": num_chunks,
                "progress": ((i + 1) / num_chunks) * 90,  # Save 10% for summary
                "segment_data": analyses[-1],
                "highlight_found": is_highlight
            }

        # HIGH FIDELITY MODE: Pass 2 - Tiled Vision on active segments
        if high_fidelity:
            logger.info("=" * 60)
            logger.info("🎨 HIGH FIDELITY MODE: Starting Pass 2 (Tiled Vision)")
            logger.info("=" * 60)

            # Identify segments that exceed the activity threshold
            active_segments = [
                seg for seg in analyses
                if seg["events_per_minute"] >= hf_threshold
            ]

            logger.info(f"Found {len(active_segments)}/{len(analyses)} active segments (≥{hf_threshold} events/min)")

            if active_segments:
                for idx, segment in enumerate(active_segments, 1):
                    seg_num = segment["segment"]
                    start_sec = segment["start_time"]
                    end_sec = segment["end_time"]
                    events_pm = segment["events_per_minute"]

                    yield {
                        "status": "tiling_frames",
                        "message": f"Pass 2: Tiling segment {idx}/{len(active_segments)} (Seg #{seg_num}, {events_pm} events/min)",
                        "segment": seg_num,
                        "pass2_current": idx,
                        "pass2_total": len(active_segments),
                        "progress": 90 + (idx / len(active_segments) * 5)  # 90-95%
                    }

                    logger.info(f"🎬 Pass 2: Re-analyzing segment {seg_num} ({start_sec}-{end_sec}s) with Tiled Vision")

                    try:
                        # Get sport-specific prompt
                        prompt = self.get_analysis_prompt(start_sec, end_sec, None)

                        # Analyze with Tiled Vision
                        tiled_analysis, tiled_tokens = self.video_tool.analyze_tiled_sequence(
                            video_uri=video_uri,
                            start_sec=start_sec,
                            end_sec=end_sec,
                            prompt=prompt,
                            fps=hf_fps,
                            num_tiles=3,
                            overlap_ratio=0.20
                        )

                        # Parse events from tiled analysis
                        tiled_events = self.parse_events(tiled_analysis)

                        # Update segment with Pass 2 results
                        segment["analysis"] = tiled_analysis
                        segment["events"] = tiled_events
                        segment["token_usage"] = tiled_tokens
                        segment["events_per_minute"] = len(tiled_events) / ((end_sec - start_sec) / 60.0)
                        segment["pass2_applied"] = True

                        logger.info(f"✅ Pass 2 complete: {len(tiled_events)} events detected (was {len(segment.get('pass1_events', []))})")

                        # Store Pass 1 events for comparison
                        if "pass1_events" not in segment:
                            segment["pass1_events"] = segment.get("events", [])

                    except Exception as e:
                        logger.error(f"❌ Pass 2 failed for segment {seg_num}: {e}")
                        logger.error("Keeping Pass 1 results for this segment")
                        segment["pass2_applied"] = False
                        segment["pass2_error"] = str(e)

                logger.info("✅ Pass 2 (Tiled Vision) complete")
            else:
                logger.info("No segments exceeded activity threshold - skipping Pass 2")

        # Apply retroactive classification based on sport-specific heuristics
        logger.info("Applying retroactive classification based on event frequency...")
        for analysis in analyses:
            events_pm = analysis["events_per_minute"]
            initial = analysis["initial_classification"]
            events = analysis["events"]
            segment_duration_min = (analysis["end_time"] - analysis["start_time"]) / 60.0

            # Apply sport-specific heuristic
            final_class = self.apply_classification_heuristic(events, segment_duration_min, initial)
            analysis["final_classification"] = final_class

            # Log override if classification changed
            if final_class != initial:
                logger.info(f"Segment {analysis['segment']}: Overriding {initial} → {final_class} (events/min={events_pm})")

            # Update the analysis text with classification override if changed
            if analysis["final_classification"] != analysis["initial_classification"]:
                override_note = f"\n\n**[RETROACTIVE CLASSIFICATION: {analysis['final_classification']} based on {events_pm} events/min]**"
                analysis["analysis"] = analysis["analysis"] + override_note

        # Compile final report using LLM
        yield {
            "status": "compiling",
            "message": "Generating comprehensive game summary...",
            "progress": 95
        }

        # Get sport-specific compilation prompt
        compilation_prompt = self.get_compilation_prompt(analyses)

        try:
            summary_response = self.client.models.generate_content(
                model=self.model_name,
                contents=compilation_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=self.get_system_instruction(),
                    temperature=0.8,  # High creativity - strategic insights
                    max_output_tokens=6144,
                )
            )
            game_summary = summary_response.text
        except Exception as e:
            game_summary = f"Error generating summary: {str(e)}"

        # Aggregate roster from all segments (deduplicate by jersey number)
        full_roster = {}
        for analysis in analyses:
            for profile in analysis.get("roster_profiles", []):
                jersey_num = profile.get("jersey_number", "Unknown")
                # Keep first sighting of each jersey number (warmup gives best view)
                if jersey_num not in full_roster:
                    full_roster[jersey_num] = profile

        roster_list = list(full_roster.values())
        logger.info(f"Built roster with {len(roster_list)} players identified")

        # Calculate total token usage across all segments
        total_prompt_tokens = sum(a.get("token_usage", {}).get("prompt_tokens", 0) for a in analyses)
        total_output_tokens = sum(a.get("token_usage", {}).get("output_tokens", 0) for a in analyses)
        total_tokens = sum(a.get("token_usage", {}).get("total_tokens", 0) for a in analyses)

        logger.info(f"Total token usage: {total_tokens:,} ({total_prompt_tokens:,} prompt + {total_output_tokens:,} output)")

        # Final result
        final_result = {
            "video_uri": video_uri,
            "duration_seconds": duration_seconds,
            "num_segments": num_chunks,
            "segment_analyses": analyses,
            "highlights": highlights,
            "game_summary": game_summary,
            "roster": roster_list,  # Aggregated player roster
            "total_token_usage": {
                "prompt_tokens": total_prompt_tokens,
                "output_tokens": total_output_tokens,
                "total_tokens": total_tokens
            }
        }

        yield {
            "status": "complete",
            "message": "Analysis complete!",
            "progress": 100,
            "result": final_result
        }

    def analyze_full_video(
        self,
        video_uri: str,
        duration_seconds: Optional[int] = None,
        chunk_size: int = 120,
        start_offset: int = 0,
        high_fidelity: bool = False,
        hf_threshold: float = 2.0,
        hf_fps: int = 3
    ) -> Dict[str, Any]:
        """
        Analyze a full video (non-streaming version)

        Args:
            video_uri: GCS URI of the video
            duration_seconds: Total video duration (if None, auto-detects)
            chunk_size: Size of each analysis chunk in seconds (default: 120 = 2 minutes)
            start_offset: Start time in seconds (skip this much from beginning)
            high_fidelity: Enable High Fidelity Mode (Tiled Vision Pipeline) (default: False)
            hf_threshold: Activity threshold for Pass 2 - events per minute (default: 2.0)
            hf_fps: Frame rate for tiled extraction in FPS (default: 3)

        Returns:
            Dictionary containing play-by-play analysis, highlights, and stats
        """
        # Use the streaming version and collect the final result
        result = None
        for update in self.analyze_full_video_stream(
            video_uri,
            duration_seconds,
            chunk_size,
            start_offset,
            high_fidelity,
            hf_threshold,
            hf_fps
        ):
            if update.get("status") == "complete":
                result = update.get("result")
        return result

    def get_quick_description_prompt(self) -> str:
        """
        Return sport-specific prompt for quick video description (for filename generation)
        Default implementation - can be overridden by subclasses
        """
        return f"""Analyze this {self.sport_name} video clip and provide a very concise description suitable for a filename.

Focus on:
1. The main action or event (e.g., "layup drill", "3v3 scrimmage", "warmup shots", "game highlights")
2. Key identifying features (player numbers, teams if visible, notable plays)
3. Keep it SHORT - 3-6 words maximum

Provide ONLY the description, nothing else. No punctuation except hyphens.
Examples: "red-team-layup-practice", "player-23-three-point-drill", "blue-vs-white-scrimmage"

Description:"""

    def describe_for_filename(
        self,
        video_uri: str,
        max_duration: int = 30
    ) -> tuple[str, str]:
        """
        Generate a brief description of video content suitable for filename

        Args:
            video_uri: GCS URI of the video
            max_duration: Maximum seconds to analyze (default: 30 - keeps it quick)

        Returns:
            Tuple of (description, suggested_filename)
        """
        try:
            # Auto-detect duration if needed
            duration = self.get_video_duration(video_uri)
            if duration is None:
                logger.warning("Could not detect duration, using 30s")
                duration = 30

            # Limit to max_duration
            analyze_duration = min(duration, max_duration)

            # Get sport-specific prompt
            prompt = self.get_quick_description_prompt()

            # Analyze the video (first N seconds only)
            description, _ = self.video_tool.analyze_video_segment(
                video_uri=video_uri,
                start_sec=0,
                end_sec=analyze_duration,
                prompt=prompt
            )

            # Clean up the description
            description = description.strip()

            # Remove any markdown or extra formatting
            description = re.sub(r'[*#`]', '', description)

            # Generate filename from description
            filename = self._generate_filename_from_description(description)

            return description, filename

        except Exception as e:
            logger.error(f"Error generating description: {e}")
            return "unknown-video", "unknown-video.mp4"

    def _generate_filename_from_description(self, description: str) -> str:
        """
        Convert a description into a safe filename

        Args:
            description: Text description

        Returns:
            Safe filename (without extension)
        """
        # Convert to lowercase
        filename = description.lower()

        # Remove special characters, keep only alphanumeric, hyphens, underscores
        filename = re.sub(r'[^a-z0-9\s\-_]', '', filename)

        # Replace spaces with hyphens
        filename = re.sub(r'\s+', '-', filename)

        # Remove multiple consecutive hyphens
        filename = re.sub(r'-+', '-', filename)

        # Trim hyphens from start/end
        filename = filename.strip('-')

        # Limit length (max 50 chars for filename)
        if len(filename) > 50:
            filename = filename[:50].rstrip('-')

        # Ensure it's not empty
        if not filename:
            filename = "video"

        return filename


class BasketballAgent(BaseSportAgent):
    """Basketball-specific video analysis agent"""

    def __init__(self, model_name: str = "gemini-2.5-pro"):
        super().__init__(model_name=model_name, sport_name="Basketball")

    def get_system_instruction(self) -> str:
        return """You are CoachAI, an expert basketball analyst with deep knowledge of the game.

Your mission is to analyze basketball game videos systematically and provide comprehensive insights.

When analyzing a video:
1. Break down the video into manageable segments (typically 60 seconds for optimal quality)
2. Use the analyze_video_segment tool to examine each segment thoroughly
3. Create a detailed play-by-play log of key events
4. Identify highlight-worthy moments (dunks, three-pointers, blocks, steals, spectacular plays)
5. Provide strategic insights about team performance

IMPORTANT: Provide complete, thorough analysis for each segment. Don't cut off mid-sentence or leave analysis incomplete.

Always be thorough, systematic, and professional in your analysis.
Focus on actionable insights that coaches and players can use to improve."""

    def get_analysis_prompt(self, start_sec: float, end_sec: float, previous_context: Optional[str] = None) -> str:
        context_section = ""
        if previous_context:
            # Truncate to avoid token bloat
            context_summary = previous_context[:500] + "..." if len(previous_context) > 500 else previous_context
            context_section = f"""
**Previous Segment Context:**
{context_summary}

Use this context to maintain continuity (e.g., if previous was warmup and you see tip-off, note "Game begins").
---

"""

        return f"""{context_section}Analyze this basketball segment from {start_sec} to {end_sec} seconds.

**🚨 CRITICAL: FOCUS ON PRIMARY GAME ONLY**
- Ignore any background courts, distant games, or TV screens visible in the background
- Only analyze the main/foreground basketball action being filmed
- Background movement (other courts, warm-ups in distance, screens) should NOT be counted
- Focus on the closest/primary court that the camera is focused on

**PRIMARY TASK: Enumerate EVERY shot attempt you observe in the PRIMARY game.**

**SHOT FORMAT (use this exact format for EVERY shot):**
SHOT: [MM:SS] - [Player description] - [shot_type] - [MADE/MISSED]

Where:
- MM:SS: Timestamp in minutes:seconds format (e.g., 0:05, 1:23, 10:45)
- Player description: Brief visual (jersey color, number if visible, height, identifying features)
- shot_type: One of: layup, dunk, floater, mid-range, three-pointer, free-throw
- MADE/MISSED: Whether the shot went in

**Examples:**
SHOT: 0:05 - Tall player white jersey #23 - layup - MADE
SHOT: 0:12 - Short player red jersey - three-pointer - MISSED
SHOT: 1:23 - Player blue jersey dark skin - mid-range - MADE

**CRITICAL: List ALL shots, even in warmups/shootarounds!**

After listing all shots, provide:

**GAME CONTEXT:**
Indicate if this is [GAME] or [WARMUP] based on these indicators:

**ACTUAL GAME PLAY** - Check for ANY of these:
✅ Jump ball / tip-off happening
✅ Organized team play with active defense (any team size: 2v2, 3v3, 4v4, 5v5, etc.)
✅ Continuous competitive play, ball possession changing
✅ Referee signals and active officiating
✅ Fast break action
✅ Game clock running (visible clock counting down)

**WARMUP / SHOOTAROUND / DEAD BALL** - Check for ANY of these:
✅ Layup lines
✅ Multiple simultaneous shooters
✅ Solo shooting practice (no defenders)
✅ Drill patterns
✅ Casual movement between shots
✅ **Game clock stopped at 0:00 or not visible**
✅ **Clock visible but not running** (dead ball, timeout, halftime)

**IF [WARMUP]: BUILD PLAYER ROSTER**

When you identify warmup/shootaround, describe players to build a roster:

**PLAYER FORMAT (use this exact format):**
PLAYER: [Jersey #] - [Team/Jersey color] - [Height: tall/medium/short] - [Build: slim/athletic/stocky] - [Skin tone] - [Hair: style/color] - [Shoes: color/notable features] - [Other: accessories, tattoos, etc.]

**Examples:**
PLAYER: #23 - White jersey - tall - athletic - light skin - short dark hair - white/red sneakers - arm sleeve on right arm
PLAYER: #7 - Blue jersey - medium height - stocky - dark skin - bald - black shoes - headband
PLAYER: #15 - White jersey - short - slim - medium skin - long braided hair - orange sneakers - wristbands

**Note:** Outfits may change (halftime, different games), so focus on:
- Permanent features: height, build, skin tone, hair
- Current outfit: jersey color/number, shoes, accessories

**OTHER NOTABLE EVENTS:**
- Defensive plays: blocks, steals, rebounds
- Turnovers, fouls
- Spectacular plays (dunks, half-court shots)

**OUTPUT FORMAT:**
1. Classification tag: [GAME] or [WARMUP]
2. List ALL shots using SHOT: format above
3. IF [WARMUP]: List visible PLAYER profiles (focus on clear views)
4. Brief context/notable events
5. Be factual, timestamp everything"""

    def parse_events(self, analysis_text: str) -> List[Dict[str, Any]]:
        """Parse shots from basketball analysis"""
        shots = []

        # Pattern: SHOT: 0:05 - Tall player white jersey #23 - layup - MADE
        # Also supports old format: SHOT: 5s - ...
        pattern = r'SHOT:\s*(?:(\d+):(\d+)|(\d+)s)\s*-\s*([^-]+?)\s*-\s*([^-]+?)\s*-\s*(MADE|MISSED)'

        for match in re.finditer(pattern, analysis_text, re.IGNORECASE):
            # Parse timestamp (MM:SS format or legacy seconds format)
            if match.group(1) is not None:  # MM:SS format
                minutes = int(match.group(1))
                seconds = int(match.group(2))
                timestamp = minutes * 60 + seconds
                player_desc = match.group(4).strip()
                shot_type = match.group(5).strip().lower()
                result = match.group(6).strip().upper()
            else:  # Legacy seconds format
                timestamp = int(match.group(3))
                player_desc = match.group(4).strip()
                shot_type = match.group(5).strip().lower()
                result = match.group(6).strip().upper()

            shots.append({
                "timestamp": timestamp,
                "player": player_desc,
                "shot_type": shot_type,
                "made": result == "MADE"
            })

        return shots

    def parse_roster(self, analysis_text: str) -> List[Dict[str, Any]]:
        """Parse player roster profiles from warmup analysis"""
        roster = []

        # Pattern: PLAYER: #23 - White jersey - tall - athletic - light skin - short dark hair - white/red sneakers - arm sleeve
        pattern = r'PLAYER:\s*([^-]+?)\s*-\s*([^-]+?)\s*-\s*([^-]+?)\s*-\s*([^-]+?)\s*-\s*([^-]+?)\s*-\s*([^-]+?)\s*-\s*([^-]+?)(?:\s*-\s*(.+))?$'

        for match in re.finditer(pattern, analysis_text, re.IGNORECASE | re.MULTILINE):
            jersey_num = match.group(1).strip()
            team_color = match.group(2).strip()
            height = match.group(3).strip()
            build = match.group(4).strip()
            skin_tone = match.group(5).strip()
            hair = match.group(6).strip()
            shoes = match.group(7).strip()
            other = match.group(8).strip() if match.group(8) else ""

            roster.append({
                "jersey_number": jersey_num,
                "team_color": team_color,
                "height": height,
                "build": build,
                "skin_tone": skin_tone,
                "hair": hair,
                "shoes": shoes,
                "other": other
            })

        return roster

    def apply_classification_heuristic(self, events: List[Dict], segment_duration_min: float, initial_classification: str) -> str:
        """Apply shots-per-minute heuristic for basketball"""
        shots_per_minute = len(events) / segment_duration_min if segment_duration_min > 0 else 0

        # Basketball-specific thresholds
        if shots_per_minute >= 10:
            # Very high shot rate = definitely warmup
            return "WARMUP"
        elif shots_per_minute <= 2 and shots_per_minute > 0:
            # Very low shot rate = likely game (slow, defensive play)
            return "GAME"
        elif 2 < shots_per_minute < 6:
            # Moderate-low rate = likely game (normal game pace)
            return "GAME"
        elif 6 <= shots_per_minute < 10:
            # Moderate-high rate = could be either, trust model
            return initial_classification
        else:
            # Keep original classification
            return initial_classification

    def get_compilation_prompt(self, analyses: List[Dict]) -> str:
        return f"""Based on these play-by-play segment analyses, provide a comprehensive strategic game summary with creative insights:

{chr(10).join([f"Segment {a['segment']} ({a['start_time']}-{a['end_time']}s): {a['analysis']}" for a in analyses])}

Your task is to provide HIGH-LEVEL STRATEGIC ANALYSIS with creativity and insight:

1. **Overall Game Narrative**:
   - What was the story of this game?
   - How did momentum shift?
   - What defined each team's approach?

2. **Strategic Insights** (be creative and analytical):
   - Offensive patterns and effectiveness
   - Defensive strategies and adjustments
   - Key player performances
   - Tempo and pace analysis

3. **Key Turning Points**:
   - Identify 2-3 moments that changed the game
   - Explain WHY they mattered strategically

4. **Top 5 Highlights**:
   - Most impactful plays from a game perspective
   - Not just flashy, but game-changing

5. **Actionable Takeaways**:
   - What could coaches learn from this?
   - Areas for improvement
   - Successful strategies to replicate

Be insightful, creative, and provide depth beyond just describing what happened. Focus on the "why" and "how" of the game."""


class UltimateAgent(BaseSportAgent):
    """Ultimate Frisbee-specific video analysis agent"""

    def __init__(self, model_name: str = "gemini-2.5-pro"):
        super().__init__(model_name=model_name, sport_name="Ultimate Frisbee")

    def get_system_instruction(self) -> str:
        return """You are UltimateAI, an expert ultimate frisbee analyst with deep knowledge of the sport.

Your mission is to analyze ultimate frisbee game videos systematically and provide comprehensive insights.

When analyzing a video:
1. Break down the video into manageable segments (typically 60 seconds for optimal quality)
2. Identify all key events: goals, turnovers, layouts, hucks, and defensive plays
3. Distinguish between actual game play and warmup/drills
4. Create a detailed play-by-play log of key events
5. Identify highlight-worthy moments (layouts, callahan goals, big blocks, hucks)
6. Provide strategic insights about team performance

IMPORTANT: Provide complete, thorough analysis for each segment. Don't cut off mid-sentence or leave analysis incomplete.

Always be thorough, systematic, and professional in your analysis.
Focus on actionable insights that coaches and players can use to improve."""

    def get_analysis_prompt(self, start_sec: float, end_sec: float, previous_context: Optional[str] = None) -> str:
        context_section = ""
        if previous_context:
            context_summary = previous_context[:500] + "..." if len(previous_context) > 500 else previous_context
            context_section = f"""
**Previous Segment Context:**
{context_summary}

Use this context to maintain continuity (e.g., if previous was warmup and you see pull, note "Game begins").
---

"""

        return f"""{context_section}Analyze this ultimate frisbee segment from {start_sec} to {end_sec} seconds.

**🚨 CRITICAL: FOCUS ON PRIMARY GAME ONLY**
- Ignore any background fields, distant games, or screens visible in the background
- Only analyze the main/foreground ultimate frisbee action being filmed
- Background activity (other fields, warm-ups in distance, spectators) should NOT be counted
- Focus on the closest/primary field that the camera is focused on

**PRIMARY TASK: Enumerate EVERY significant event you observe in the PRIMARY game.**

**EVENT FORMATS (use these exact formats):**

GOAL: [MM:SS] - [Player/team description] - SCORED
CATCH: [MM:SS] - [Player description] - [type: jump/one-handed/diving/contested] - [SUCCESS/FAILED]
LAYOUT: [MM:SS] - [Player description] - [catch/block] - [SUCCESS/FAILED]
DEFLECTION: [MM:SS] - [Player description] - [type: hand-block/knock-down/tipped]
BLOCK: [MM:SS] - [Player description] - [type: layout/poach/mark/clean]
TURNOVER: [MM:SS] - [type: drop/throwaway/block/stall] - [team description]
HUCK: [MM:SS] - [Player description] - [completed/incomplete] - [distance: short/medium/deep]

**Examples:**
GOAL: 0:15 - Red jersey #7 - SCORED
CATCH: 0:23 - White #12 - jump catch - SUCCESS
CATCH: 0:45 - Tall dark jersey - one-handed - SUCCESS
LAYOUT: 1:07 - Red team player - catch - SUCCESS
DEFLECTION: 1:29 - White #5 - hand-block - caused turnover
BLOCK: 1:52 - Short player red team - layout
TURNOVER: 2:14 - drop - White team
HUCK: 6:30 - Player white #23 - completed - deep

**CRITICAL: Track ALL highlight-worthy plays!**
- EVERY jump catch, diving catch, or difficult reception
- EVERY defensive deflection, hand block, or tipped disc
- ALL goals, layouts, blocks, turnovers
- This is for HIGHLIGHT DETECTION, not just strategy

After listing all events, provide:

**GAME CONTEXT:**
Indicate if this is [GAME] or [WARMUP] based on these indicators:

**ACTUAL GAME PLAY** - Check for ANY of these:
✅ Pull (kickoff) to start point
✅ Organized team play with active marking/defense (any team size: 4v4, 5v5, 6v6, 7v7, etc. - non-regulation sizes are common!)
✅ Continuous competitive play, disc possession changing
✅ Stall counts audible
✅ Turnovers occurring during play
✅ Fast break / transition offense

**NOTE:** Pickup ultimate games often have fewer than regulation 7v7 players. This is totally normal! Focus on whether there's organized competitive play, not the exact player count.

**WARMUP / DRILLS** - Check for ANY of these:
✅ Casual throwing back and forth
✅ Multiple discs visible on field
✅ Uncontested throwing drills
✅ No defensive pressure/marking
✅ Players standing around between throws
✅ Organized drill patterns (handler drills, cutting drills)

**OTHER NOTABLE EVENTS:**
- Callahan goals (defensive interception in endzone)
- Bookends (same player assists and scores)
- Long points or defensive holds
- Weather/field conditions affecting play

**OUTPUT FORMAT:**
1. Classification tag: [GAME] or [WARMUP]
2. List ALL events using formats above
3. Brief context/notable moments
4. Be factual, timestamp everything"""

    def parse_events(self, analysis_text: str) -> List[Dict[str, Any]]:
        """Parse events from ultimate frisbee analysis"""
        events = []

        # Helper function to parse timestamp (MM:SS or legacy seconds format)
        def parse_timestamp(time_str: str) -> int:
            """Convert MM:SS or seconds format to total seconds"""
            if ':' in time_str:
                parts = time_str.split(':')
                return int(parts[0]) * 60 + int(parts[1])
            else:
                return int(time_str.rstrip('s'))

        # Patterns for different event types (support both MM:SS and legacy Xs formats)
        patterns = {
            "goal": r'GOAL:\s*(\d+(?::\d+|s))\s*-\s*([^-]+?)\s*-\s*SCORED',
            "catch": r'CATCH:\s*(\d+(?::\d+|s))\s*-\s*([^-]+?)\s*-\s*([^-]+?)\s*-\s*(SUCCESS|FAILED)',
            "layout": r'LAYOUT:\s*(\d+(?::\d+|s))\s*-\s*([^-]+?)\s*-\s*([^-]+?)\s*-\s*(SUCCESS|FAILED)',
            "deflection": r'DEFLECTION:\s*(\d+(?::\d+|s))\s*-\s*([^-]+?)\s*-\s*(.+)',
            "block": r'BLOCK:\s*(\d+(?::\d+|s))\s*-\s*([^-]+?)\s*-\s*(.+)',
            "turnover": r'TURNOVER:\s*(\d+(?::\d+|s))\s*-\s*([^-]+?)\s*-\s*(.+)',
            "huck": r'HUCK:\s*(\d+(?::\d+|s))\s*-\s*([^-]+?)\s*-\s*([^-]+?)\s*-\s*(.+)',
        }

        for event_type, pattern in patterns.items():
            for match in re.finditer(pattern, analysis_text, re.IGNORECASE):
                timestamp = parse_timestamp(match.group(1))

                event = {
                    "timestamp": timestamp,
                    "type": event_type,
                }

                if event_type == "goal":
                    event["player"] = match.group(2).strip()
                elif event_type == "catch":
                    event["player"] = match.group(2).strip()
                    event["catch_type"] = match.group(3).strip()
                    event["success"] = match.group(4).strip().upper() == "SUCCESS"
                elif event_type == "layout":
                    event["player"] = match.group(2).strip()
                    event["action"] = match.group(3).strip()
                    event["success"] = match.group(4).strip().upper() == "SUCCESS"
                elif event_type == "deflection":
                    event["player"] = match.group(2).strip()
                    event["deflection_type"] = match.group(3).strip()
                elif event_type == "block":
                    event["player"] = match.group(2).strip()
                    event["block_type"] = match.group(3).strip()
                elif event_type == "turnover":
                    event["turnover_type"] = match.group(2).strip()
                    event["team"] = match.group(3).strip()
                elif event_type == "huck":
                    event["player"] = match.group(2).strip()
                    event["result"] = match.group(3).strip()
                    event["distance"] = match.group(4).strip()

                events.append(event)

        return events

    def apply_classification_heuristic(self, events: List[Dict], segment_duration_min: float, initial_classification: str) -> str:
        """Apply events-per-minute heuristic for ultimate frisbee"""
        events_per_minute = len(events) / segment_duration_min if segment_duration_min > 0 else 0

        # Count specific event types
        turnovers = sum(1 for e in events if e.get("type") == "turnover")
        goals = sum(1 for e in events if e.get("type") == "goal")
        layouts = sum(1 for e in events if e.get("type") == "layout")

        # Ultimate-specific thresholds
        # Game: 8-15 events/min (goals, turnovers, layouts, hucks, blocks)
        # Warmup: 0-4 events/min (mostly casual throws, few structured events)

        if events_per_minute >= 12:
            # High event rate with turnovers/goals = likely game
            if turnovers > 0 or goals > 0:
                return "GAME"
            else:
                # High events but no competitive indicators = warmup drills
                return "WARMUP"
        elif events_per_minute >= 6:
            # Moderate event rate = likely game if turnovers present
            if turnovers > 0 or layouts > 0:
                return "GAME"
            else:
                return initial_classification
        elif events_per_minute < 3:
            # Very low event rate = likely warmup
            return "WARMUP"
        else:
            # Ambiguous, trust model
            return initial_classification

    def get_compilation_prompt(self, analyses: List[Dict]) -> str:
        return f"""Based on these play-by-play segment analyses, provide a comprehensive strategic game summary with creative insights:

{chr(10).join([f"Segment {a['segment']} ({a['start_time']}-{a['end_time']}s): {a['analysis']}" for a in analyses])}

Your task is to provide HIGH-LEVEL STRATEGIC ANALYSIS with creativity and insight:

1. **Overall Game Narrative**:
   - What was the story of this ultimate frisbee game?
   - How did momentum shift?
   - What defined each team's approach?

2. **Strategic Insights** (be creative and analytical):
   - Offensive strategies (handler movement, cutting patterns, hucks)
   - Defensive strategies (person defense, zone, poaching)
   - Key player performances
   - Turnover patterns and causes
   - Flow and tempo of the game

3. **Key Turning Points**:
   - Identify 2-3 moments that changed the game
   - Explain WHY they mattered strategically
   - Big defensive holds or break opportunities

4. **Top 5 Highlights**:
   - Most impactful plays from a game perspective
   - Spectacular layouts, blocks, or goals
   - Game-changing turnovers or defensive stands

5. **Actionable Takeaways**:
   - What could coaches learn from this?
   - Areas for improvement (handler movement, cutting, marking)
   - Successful strategies to replicate
   - Turnover reduction opportunities

Be insightful, creative, and provide depth beyond just describing what happened. Focus on the "why" and "how" of the game from an ultimate frisbee perspective."""


def create_coach_agent(model_name: str = "gemini-2.5-flash-lite", sport: str = "basketball") -> BaseSportAgent:
    """
    Factory function to create a sport-specific analysis agent

    Args:
        model_name: The Gemini model to use
        sport: Sport type ("basketball" or "ultimate")

    Returns:
        Initialized sport-specific agent
    """
    sport = sport.lower()

    if sport == "basketball":
        return BasketballAgent(model_name=model_name)
    elif sport in ["ultimate", "ultimate frisbee", "frisbee"]:
        return UltimateAgent(model_name=model_name)
    else:
        raise ValueError(f"Unsupported sport: {sport}. Supported sports: basketball, ultimate")
