"""
Tests for VideoEngine class

Tests the FFmpeg filter_complex generation for 2x2 grid tiling.
"""
import pytest
from unittest.mock import patch, MagicMock
import subprocess


def _ffmpeg_available() -> bool:
    """Check if FFmpeg is available on the system"""
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            check=True,
            timeout=5
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False


class TestVideoEngine:
    """Test suite for VideoEngine 2x2 grid generation"""

    # ─────────────────────────────────────────────────────────────────
    # Filter String Generation Tests
    # ─────────────────────────────────────────────────────────────────

    def test_build_filter_complex_2x2_standard_dimensions(self):
        """Test filter_complex string for standard 1920x1080 video"""
        from video_engine import VideoEngine

        engine = VideoEngine()
        filter_str = engine.build_2x2_filter_complex(
            input_width=1920,
            input_height=1080
        )

        # Each tile should be 960x540 (half dimensions, both even)
        assert "split=4" in filter_str
        assert "crop=960:540:0:0" in filter_str      # top-left
        assert "crop=960:540:960:0" in filter_str    # top-right
        assert "crop=960:540:0:540" in filter_str    # bottom-left
        assert "crop=960:540:960:540" in filter_str  # bottom-right
        assert "hstack=inputs=2" in filter_str
        assert "vstack=inputs=2" in filter_str

    def test_build_filter_complex_2x2_4k_video(self):
        """Test filter_complex string for 4K (3840x2160) video"""
        from video_engine import VideoEngine

        engine = VideoEngine()
        filter_str = engine.build_2x2_filter_complex(
            input_width=3840,
            input_height=2160
        )

        # Each tile should be 1920x1080
        assert "crop=1920:1080:0:0" in filter_str      # top-left
        assert "crop=1920:1080:1920:0" in filter_str   # top-right
        assert "crop=1920:1080:0:1080" in filter_str   # bottom-left
        assert "crop=1920:1080:1920:1080" in filter_str  # bottom-right

    def test_build_filter_complex_contains_correct_structure(self):
        """Test that filter_complex has correct FFmpeg structure"""
        from video_engine import VideoEngine

        engine = VideoEngine()
        filter_str = engine.build_2x2_filter_complex(
            input_width=1280,
            input_height=720
        )

        # Should have proper stream labels
        assert "[0:v]" in filter_str  # Input stream reference
        assert "[s0]" in filter_str   # Split outputs
        assert "[s1]" in filter_str
        assert "[s2]" in filter_str
        assert "[s3]" in filter_str
        assert "[tl]" in filter_str   # Tile labels (top-left, etc.)
        assert "[tr]" in filter_str
        assert "[bl]" in filter_str
        assert "[br]" in filter_str
        assert "[top]" in filter_str  # Intermediate stacks
        assert "[bottom]" in filter_str
        assert "[out]" in filter_str  # Final output

    # ─────────────────────────────────────────────────────────────────
    # Even Dimension Enforcement Tests
    # ─────────────────────────────────────────────────────────────────

    def test_odd_width_raises_value_error_in_strict_mode(self):
        """Test that odd tile width raises ValueError in strict mode"""
        from video_engine import VideoEngine

        engine = VideoEngine(strict_even=True)

        # 1920 / 2 = 960 (even) - OK
        # 1080 / 2 = 540 (even) - OK
        # But 1922 / 2 = 961 (odd) - should fail
        with pytest.raises(ValueError, match="even"):
            engine.build_2x2_filter_complex(
                input_width=1922,  # Results in 961 tile width (odd)
                input_height=1080
            )

    def test_odd_height_raises_value_error_in_strict_mode(self):
        """Test that odd tile height raises ValueError in strict mode"""
        from video_engine import VideoEngine

        engine = VideoEngine(strict_even=True)

        # 1082 / 2 = 541 (odd) - should fail
        with pytest.raises(ValueError, match="even"):
            engine.build_2x2_filter_complex(
                input_width=1920,
                input_height=1082  # Results in 541 tile height (odd)
            )

    def test_odd_dimensions_auto_adjusted_in_lenient_mode(self):
        """Test that odd dimensions are auto-adjusted when strict_even=False"""
        from video_engine import VideoEngine

        engine = VideoEngine(strict_even=False)

        # 1922 / 2 = 961 -> should be adjusted to 960
        filter_str = engine.build_2x2_filter_complex(
            input_width=1922,
            input_height=1082
        )

        # Should use 960 (not 961) for width and 540 (not 541) for height
        assert "crop=960:540" in filter_str

    def test_already_even_dimensions_unchanged(self):
        """Test that already even dimensions are not modified"""
        from video_engine import VideoEngine

        engine = VideoEngine(strict_even=False)
        filter_str = engine.build_2x2_filter_complex(
            input_width=1920,
            input_height=1080
        )

        # 960x540 should remain unchanged
        assert "crop=960:540:0:0" in filter_str

    # ─────────────────────────────────────────────────────────────────
    # FFmpeg Command Generation Tests
    # ─────────────────────────────────────────────────────────────────

    def test_build_ffmpeg_command_structure(self):
        """Test that FFmpeg command has correct structure"""
        from video_engine import VideoEngine

        engine = VideoEngine()
        cmd = engine.build_ffmpeg_command(
            input_path="/path/to/video.mp4",
            output_path="/path/to/output.mp4",
            input_width=1920,
            input_height=1080
        )

        assert cmd[0] == "ffmpeg"
        assert "-i" in cmd
        assert "/path/to/video.mp4" in cmd
        assert "-filter_complex" in cmd
        assert "/path/to/output.mp4" in cmd
        assert "-y" in cmd  # Overwrite output

    def test_build_ffmpeg_command_with_time_range(self):
        """Test FFmpeg command with start/duration parameters"""
        from video_engine import VideoEngine

        engine = VideoEngine()
        cmd = engine.build_ffmpeg_command(
            input_path="/path/to/video.mp4",
            output_path="/path/to/output.mp4",
            input_width=1920,
            input_height=1080,
            start_sec=30.0,
            duration_sec=60.0
        )

        assert "-ss" in cmd
        ss_idx = cmd.index("-ss")
        assert cmd[ss_idx + 1] == "30.0"

        assert "-t" in cmd
        t_idx = cmd.index("-t")
        assert cmd[t_idx + 1] == "60.0"

    def test_single_filter_complex_argument(self):
        """Test that only ONE -filter_complex argument is used (single process)"""
        from video_engine import VideoEngine

        engine = VideoEngine()
        cmd = engine.build_ffmpeg_command(
            input_path="/path/to/video.mp4",
            output_path="/path/to/output.mp4",
            input_width=1920,
            input_height=1080
        )

        # Count occurrences of -filter_complex
        filter_complex_count = cmd.count("-filter_complex")
        assert filter_complex_count == 1, "Must use single filter_complex (single FFmpeg process)"

    # ─────────────────────────────────────────────────────────────────
    # FFmpeg Execution Tests (Mocked)
    # ─────────────────────────────────────────────────────────────────

    @patch("video_engine.subprocess.run")
    def test_generate_2x2_grid_calls_ffmpeg_once(self, mock_run):
        """Test that generate_2x2_grid calls FFmpeg exactly once"""
        from video_engine import VideoEngine

        mock_run.return_value = MagicMock(returncode=0)

        engine = VideoEngine()
        engine.generate_2x2_grid(
            input_path="/path/to/video.mp4",
            output_path="/path/to/output.mp4",
            input_width=1920,
            input_height=1080
        )

        # FFmpeg should be called exactly once (single process requirement)
        assert mock_run.call_count == 1

    @patch("video_engine.subprocess.run")
    def test_generate_2x2_grid_passes_correct_filter_complex(self, mock_run):
        """Test that the correct filter_complex is passed to FFmpeg"""
        from video_engine import VideoEngine

        mock_run.return_value = MagicMock(returncode=0)

        engine = VideoEngine()
        engine.generate_2x2_grid(
            input_path="/path/to/video.mp4",
            output_path="/path/to/output.mp4",
            input_width=1920,
            input_height=1080
        )

        # Get the command that was passed to subprocess.run
        call_args = mock_run.call_args
        cmd = call_args[0][0]  # First positional arg is the command list

        # Find the filter_complex argument
        fc_idx = cmd.index("-filter_complex")
        filter_str = cmd[fc_idx + 1]

        # Verify key components
        assert "split=4" in filter_str
        assert "crop=960:540" in filter_str
        assert "hstack" in filter_str
        assert "vstack" in filter_str

    @patch("video_engine.subprocess.run")
    def test_generate_2x2_grid_raises_on_ffmpeg_failure(self, mock_run):
        """Test that FFmpeg failure raises RuntimeError"""
        from video_engine import VideoEngine

        mock_run.return_value = MagicMock(
            returncode=1,
            stderr="Error: Invalid input"
        )

        engine = VideoEngine()

        with pytest.raises(RuntimeError, match="FFmpeg"):
            engine.generate_2x2_grid(
                input_path="/path/to/video.mp4",
                output_path="/path/to/output.mp4",
                input_width=1920,
                input_height=1080
            )

    @patch("video_engine.subprocess.run")
    def test_generate_2x2_grid_with_fps_parameter(self, mock_run):
        """Test that FPS parameter is included in filter when specified"""
        from video_engine import VideoEngine

        mock_run.return_value = MagicMock(returncode=0)

        engine = VideoEngine()
        engine.generate_2x2_grid(
            input_path="/path/to/video.mp4",
            output_path="/path/to/output.mp4",
            input_width=1920,
            input_height=1080,
            fps=3
        )

        call_args = mock_run.call_args
        cmd = call_args[0][0]
        fc_idx = cmd.index("-filter_complex")
        filter_str = cmd[fc_idx + 1]

        # FPS filter should be applied before split
        assert "fps=3" in filter_str

    # ─────────────────────────────────────────────────────────────────
    # Edge Cases
    # ─────────────────────────────────────────────────────────────────

    def test_minimum_valid_dimensions(self):
        """Test with minimum valid dimensions (4x4 -> 2x2 tiles)"""
        from video_engine import VideoEngine

        engine = VideoEngine()
        filter_str = engine.build_2x2_filter_complex(
            input_width=4,
            input_height=4
        )

        assert "crop=2:2:0:0" in filter_str
        assert "crop=2:2:2:0" in filter_str
        assert "crop=2:2:0:2" in filter_str
        assert "crop=2:2:2:2" in filter_str

    def test_zero_dimensions_raises_error(self):
        """Test that zero dimensions raise ValueError"""
        from video_engine import VideoEngine

        engine = VideoEngine()

        with pytest.raises(ValueError):
            engine.build_2x2_filter_complex(input_width=0, input_height=1080)

        with pytest.raises(ValueError):
            engine.build_2x2_filter_complex(input_width=1920, input_height=0)

    def test_negative_dimensions_raises_error(self):
        """Test that negative dimensions raise ValueError"""
        from video_engine import VideoEngine

        engine = VideoEngine()

        with pytest.raises(ValueError):
            engine.build_2x2_filter_complex(input_width=-1920, input_height=1080)


class TestVideoEngineIntegration:
    """Integration tests for VideoEngine (require actual FFmpeg)"""

    @pytest.mark.skipif(
        not _ffmpeg_available(),
        reason="FFmpeg not available"
    )
    def test_actual_filter_complex_syntax_valid(self):
        """Test that generated filter_complex is valid FFmpeg syntax"""
        from video_engine import VideoEngine
        import subprocess

        engine = VideoEngine()
        filter_str = engine.build_2x2_filter_complex(
            input_width=1920,
            input_height=1080
        )

        # Use FFmpeg's filter graph parser to validate syntax
        # -filter_complex with -f lavfi creates a test source
        result = subprocess.run(
            [
                "ffmpeg", "-f", "lavfi",
                "-i", "testsrc=duration=1:size=1920x1080:rate=1",
                "-filter_complex", filter_str,
                "-map", "[out]",
                "-f", "null", "-"
            ],
            capture_output=True,
            text=True,
            timeout=10
        )

        assert result.returncode == 0, f"FFmpeg rejected filter: {result.stderr}"
