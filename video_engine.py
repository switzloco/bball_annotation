"""
VideoEngine - FFmpeg-based video processing for 2x2 grid tiling

Uses FFmpeg filter_complex with split, crop, hstack, and vstack to generate
2x2 grid tiles from input videos in a single FFmpeg process.

Critical: All crop dimensions are enforced to be even numbers to prevent
YUV 4:2:0 chroma subsampling artifacts.
"""
import subprocess
import logging
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


class VideoEngine:
    """
    Video processing engine using FFmpeg filter_complex for 2x2 grid generation.

    Generates 2x2 grids from input videos using a single FFmpeg process with
    filter_complex containing split, crop, hstack, and vstack filters.

    Args:
        strict_even: If True, raise ValueError for odd crop dimensions.
                     If False, auto-adjust to nearest even number (default: True).

    Example:
        >>> engine = VideoEngine()
        >>> engine.generate_2x2_grid(
        ...     input_path="input.mp4",
        ...     output_path="output.mp4",
        ...     input_width=1920,
        ...     input_height=1080
        ... )
    """

    def __init__(self, strict_even: bool = True):
        """
        Initialize VideoEngine.

        Args:
            strict_even: If True, raise ValueError when crop dimensions would be odd.
                         If False, automatically adjust to even dimensions.
        """
        self.strict_even = strict_even

    def _ensure_even(self, value: int, name: str) -> int:
        """
        Ensure a dimension value is even for YUV 4:2:0 compatibility.

        Args:
            value: The dimension value to check/adjust
            name: Name of the dimension (for error messages)

        Returns:
            Even dimension value

        Raises:
            ValueError: If strict_even=True and value is odd
        """
        if value % 2 == 0:
            return value

        if self.strict_even:
            raise ValueError(
                f"Crop {name} must be even for YUV 4:2:0 compatibility. "
                f"Got {value}. Use strict_even=False to auto-adjust."
            )

        # Auto-adjust: round down to nearest even number
        adjusted = value - 1
        logger.warning(
            f"Auto-adjusting {name} from {value} to {adjusted} for YUV 4:2:0 compatibility"
        )
        return adjusted

    def _validate_dimensions(self, width: int, height: int) -> None:
        """
        Validate input dimensions are positive.

        Args:
            width: Input video width
            height: Input video height

        Raises:
            ValueError: If dimensions are zero or negative
        """
        if width <= 0:
            raise ValueError(f"Width must be positive, got {width}")
        if height <= 0:
            raise ValueError(f"Height must be positive, got {height}")

    def calculate_tile_dimensions(
        self,
        input_width: int,
        input_height: int
    ) -> Tuple[int, int]:
        """
        Calculate tile dimensions for 2x2 grid with even dimension enforcement.

        Args:
            input_width: Input video width in pixels
            input_height: Input video height in pixels

        Returns:
            Tuple of (tile_width, tile_height) both guaranteed to be even

        Raises:
            ValueError: If dimensions are invalid or odd (in strict mode)
        """
        self._validate_dimensions(input_width, input_height)

        # Calculate half dimensions
        tile_width = input_width // 2
        tile_height = input_height // 2

        # Ensure even dimensions for YUV 4:2:0
        tile_width = self._ensure_even(tile_width, "tile width")
        tile_height = self._ensure_even(tile_height, "tile height")

        return tile_width, tile_height

    def build_2x2_filter_complex(
        self,
        input_width: int,
        input_height: int,
        fps: Optional[int] = None
    ) -> str:
        """
        Build FFmpeg filter_complex string for 2x2 grid generation.

        Uses split to create 4 copies of the input, crops each to a quadrant,
        then uses hstack and vstack to reassemble into a 2x2 grid output.

        Args:
            input_width: Input video width in pixels
            input_height: Input video height in pixels
            fps: Optional FPS to apply before splitting

        Returns:
            FFmpeg filter_complex string

        Raises:
            ValueError: If dimensions are invalid or result in odd crop sizes

        Example output for 1920x1080:
            [0:v]split=4[s0][s1][s2][s3];
            [s0]crop=960:540:0:0[tl];
            [s1]crop=960:540:960:0[tr];
            [s2]crop=960:540:0:540[bl];
            [s3]crop=960:540:960:540[br];
            [tl][tr]hstack=inputs=2[top];
            [bl][br]hstack=inputs=2[bottom];
            [top][bottom]vstack=inputs=2[out]
        """
        tile_width, tile_height = self.calculate_tile_dimensions(
            input_width, input_height
        )

        # Build the filter graph
        parts = []

        # Step 1: Optional FPS filter and split into 4 streams
        if fps is not None:
            parts.append(f"[0:v]fps={fps},split=4[s0][s1][s2][s3]")
        else:
            parts.append("[0:v]split=4[s0][s1][s2][s3]")

        # Step 2: Crop each stream to its quadrant
        # crop=width:height:x:y
        # Top-left: (0, 0)
        parts.append(f"[s0]crop={tile_width}:{tile_height}:0:0[tl]")

        # Top-right: (tile_width, 0)
        parts.append(f"[s1]crop={tile_width}:{tile_height}:{tile_width}:0[tr]")

        # Bottom-left: (0, tile_height)
        parts.append(f"[s2]crop={tile_width}:{tile_height}:0:{tile_height}[bl]")

        # Bottom-right: (tile_width, tile_height)
        parts.append(
            f"[s3]crop={tile_width}:{tile_height}:{tile_width}:{tile_height}[br]"
        )

        # Step 3: Stack horizontally to create top and bottom rows
        parts.append("[tl][tr]hstack=inputs=2[top]")
        parts.append("[bl][br]hstack=inputs=2[bottom]")

        # Step 4: Stack vertically to create final 2x2 grid
        parts.append("[top][bottom]vstack=inputs=2[out]")

        return ";".join(parts)

    def build_ffmpeg_command(
        self,
        input_path: str,
        output_path: str,
        input_width: int,
        input_height: int,
        start_sec: Optional[float] = None,
        duration_sec: Optional[float] = None,
        fps: Optional[int] = None
    ) -> List[str]:
        """
        Build complete FFmpeg command for 2x2 grid generation.

        Args:
            input_path: Path to input video file
            output_path: Path for output video file
            input_width: Input video width in pixels
            input_height: Input video height in pixels
            start_sec: Optional start time in seconds
            duration_sec: Optional duration in seconds
            fps: Optional FPS to apply

        Returns:
            List of command arguments for subprocess

        Raises:
            ValueError: If dimensions are invalid
        """
        filter_complex = self.build_2x2_filter_complex(
            input_width, input_height, fps
        )

        cmd = ["ffmpeg"]

        # Add seek position (before input for fast seeking)
        if start_sec is not None:
            cmd.extend(["-ss", str(start_sec)])

        # Input file
        cmd.extend(["-i", input_path])

        # Duration (after input)
        if duration_sec is not None:
            cmd.extend(["-t", str(duration_sec)])

        # Filter complex
        cmd.extend(["-filter_complex", filter_complex])

        # Map the output stream
        cmd.extend(["-map", "[out]"])

        # Output options
        cmd.extend([
            "-c:v", "libx264",      # Video codec
            "-preset", "fast",      # Encoding speed
            "-crf", "23",           # Quality (lower = better)
            "-y",                   # Overwrite output
            output_path
        ])

        return cmd

    def generate_2x2_grid(
        self,
        input_path: str,
        output_path: str,
        input_width: int,
        input_height: int,
        start_sec: Optional[float] = None,
        duration_sec: Optional[float] = None,
        fps: Optional[int] = None,
        timeout: int = 300
    ) -> None:
        """
        Generate 2x2 grid video from input using single FFmpeg process.

        Args:
            input_path: Path to input video file
            output_path: Path for output video file
            input_width: Input video width in pixels
            input_height: Input video height in pixels
            start_sec: Optional start time in seconds
            duration_sec: Optional duration in seconds
            fps: Optional FPS to apply to output
            timeout: Command timeout in seconds (default: 300)

        Raises:
            ValueError: If dimensions are invalid or result in odd crop sizes
            RuntimeError: If FFmpeg command fails
        """
        cmd = self.build_ffmpeg_command(
            input_path=input_path,
            output_path=output_path,
            input_width=input_width,
            input_height=input_height,
            start_sec=start_sec,
            duration_sec=duration_sec,
            fps=fps
        )

        logger.info(f"Executing FFmpeg command: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            if result.returncode != 0:
                logger.error(f"FFmpeg stderr: {result.stderr}")
                raise RuntimeError(
                    f"FFmpeg command failed with return code {result.returncode}: "
                    f"{result.stderr}"
                )

            logger.info(f"Successfully generated 2x2 grid: {output_path}")

        except subprocess.TimeoutExpired:
            raise RuntimeError(
                f"FFmpeg command timed out after {timeout} seconds"
            )

    def get_video_dimensions(
        self,
        video_path: str,
        timeout: int = 30
    ) -> Tuple[int, int]:
        """
        Get video dimensions using ffprobe.

        Args:
            video_path: Path to video file
            timeout: Command timeout in seconds

        Returns:
            Tuple of (width, height)

        Raises:
            RuntimeError: If ffprobe fails
        """
        cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=s=x:p=0",
            video_path
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            if result.returncode != 0:
                raise RuntimeError(f"ffprobe failed: {result.stderr}")

            output = result.stdout.strip()
            width, height = map(int, output.split("x"))
            return width, height

        except subprocess.TimeoutExpired:
            raise RuntimeError(f"ffprobe timed out after {timeout} seconds")
        except ValueError as e:
            raise RuntimeError(f"Failed to parse ffprobe output: {e}")
