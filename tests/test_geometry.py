"""
Tests for GeometryEngine class

Tests the Cross Ratio formula for single-view height estimation
based on Criminisi's single-view metrology.

The Cross Ratio is a projective invariant:
CR(A,B,C,D) = [(A-C)(B-D)] / [(A-D)(B-C)]

For height estimation with vertical vanishing point v:
H_target = H_ref × (t_top - t_bottom)/(r_top - r_bottom)
         × (v - r_top)/(v - t_top)
         × (v - t_bottom)/(v - r_bottom)

Key property: When v → ∞, the formula reduces to simple pixel ratio.
"""
import pytest
import math


class TestCrossRatioCalculation:
    """Tests for the fundamental cross-ratio calculation"""

    def test_cross_ratio_basic_calculation(self):
        """Test basic cross-ratio CR(A,B,C,D) = [(A-C)(B-D)] / [(A-D)(B-C)]"""
        from geometry_engine import GeometryEngine

        engine = GeometryEngine()

        # CR(0, 1, 2, 3) = [(0-2)(1-3)] / [(0-3)(1-2)]
        #                = [(-2)(-2)] / [(-3)(-1)]
        #                = 4 / 3
        result = engine.cross_ratio(0, 1, 2, 3)
        assert abs(result - 4/3) < 1e-10

    def test_cross_ratio_with_negative_values(self):
        """Test cross-ratio with negative coordinates"""
        from geometry_engine import GeometryEngine

        engine = GeometryEngine()

        # CR(-2, -1, 0, 1) = [(-2-0)(-1-1)] / [(-2-1)(-1-0)]
        #                 = [(-2)(-2)] / [(-3)(-1)]
        #                 = 4 / 3
        result = engine.cross_ratio(-2, -1, 0, 1)
        assert abs(result - 4/3) < 1e-10

    def test_cross_ratio_invariant_under_translation(self):
        """Cross-ratio should be invariant under translation"""
        from geometry_engine import GeometryEngine

        engine = GeometryEngine()

        cr1 = engine.cross_ratio(0, 1, 2, 3)
        cr2 = engine.cross_ratio(100, 101, 102, 103)  # Translated by 100
        cr3 = engine.cross_ratio(-50, -49, -48, -47)  # Translated by -50

        assert abs(cr1 - cr2) < 1e-10
        assert abs(cr1 - cr3) < 1e-10

    def test_cross_ratio_division_by_zero_raises_error(self):
        """Test that degenerate cases raise appropriate errors"""
        from geometry_engine import GeometryEngine

        engine = GeometryEngine()

        # When A=D or B=C, denominator is zero
        with pytest.raises(ValueError, match="(?i)degenerate"):
            engine.cross_ratio(0, 1, 2, 0)  # A=D

        with pytest.raises(ValueError, match="(?i)degenerate"):
            engine.cross_ratio(0, 2, 2, 3)  # B=C


class TestHeightEstimationCrossRatio:
    """Tests for height estimation using cross-ratio formula"""

    def test_vanishing_point_at_infinity_gives_pixel_ratio(self):
        """
        KEY TEST: When vanishing point is at infinity, the cross-ratio
        correction factors approach 1, and height reduces to simple pixel ratio.

        This simulates orthographic projection (parallel rays, no perspective).

        Setup:
        - Target: 100 pixels tall (y: 100 to 200)
        - Reference: 50 pixels tall (y: 150 to 200), known height = 10 feet
        - Vanishing point: y = 1e10 (effectively infinity)

        Expected: H_target = 10 × (100/50) = 20 feet
        """
        from geometry_engine import GeometryEngine

        engine = GeometryEngine()

        result = engine.estimate_height(
            target_top_y=100.0,
            target_bottom_y=200.0,
            ref_top_y=150.0,
            ref_bottom_y=200.0,
            vanishing_point_y=1e10,  # Very large = "at infinity"
            ref_height=10.0
        )

        expected = 20.0  # Simple pixel ratio: 10 × (100 pixels / 50 pixels)
        assert abs(result - expected) < 0.01, f"Expected {expected}, got {result}"

    def test_vanishing_point_at_negative_infinity(self):
        """Test that negative infinity also gives pixel ratio"""
        from geometry_engine import GeometryEngine

        engine = GeometryEngine()

        result = engine.estimate_height(
            target_top_y=100.0,
            target_bottom_y=200.0,
            ref_top_y=150.0,
            ref_bottom_y=200.0,
            vanishing_point_y=-1e10,  # Negative infinity
            ref_height=10.0
        )

        expected = 20.0
        assert abs(result - expected) < 0.01

    def test_same_size_objects_same_position_returns_ref_height(self):
        """If target has same pixel dimensions as reference, should return ref height"""
        from geometry_engine import GeometryEngine

        engine = GeometryEngine()

        # Both objects: 100 pixels tall, same base
        result = engine.estimate_height(
            target_top_y=100.0,
            target_bottom_y=200.0,
            ref_top_y=100.0,
            ref_bottom_y=200.0,
            vanishing_point_y=1e10,
            ref_height=6.0
        )

        assert abs(result - 6.0) < 0.001

    def test_perspective_correction_closer_object_appears_larger(self):
        """
        Test perspective correction when objects are at different depths.

        In image coordinates with y increasing downward:
        - Vanishing point at y=0 (horizon at top)
        - Objects closer to y=0 are further from camera
        - Objects closer to bottom of image are nearer

        If target base is closer to vanishing point than reference base,
        target is further from camera, so same pixel height = actually taller.
        """
        from geometry_engine import GeometryEngine

        engine = GeometryEngine()

        # Target: base at y=150 (further from camera)
        # Reference: base at y=200 (closer to camera)
        # Same pixel height (50 pixels each)
        # Vanishing point at y=0

        result = engine.estimate_height(
            target_top_y=100.0,
            target_bottom_y=150.0,  # 50 pixels, base at 150
            ref_top_y=150.0,
            ref_bottom_y=200.0,     # 50 pixels, base at 200
            vanishing_point_y=0.0,
            ref_height=6.0
        )

        # Target is further from camera (base closer to vanishing point)
        # So same pixel height means target is actually TALLER
        assert result > 6.0, f"Target should be taller than reference, got {result}"

    def test_perspective_correction_same_base_different_heights(self):
        """
        When two objects have same base y-coordinate (same depth),
        the perspective correction should be based only on their tops.
        """
        from geometry_engine import GeometryEngine

        engine = GeometryEngine()

        # Same base at y=200
        # Target is twice the pixel height of reference
        # With perspective correction, result depends on vanishing point

        result_with_perspective = engine.estimate_height(
            target_top_y=0.0,       # 200 pixels tall
            target_bottom_y=200.0,
            ref_top_y=100.0,        # 100 pixels tall
            ref_bottom_y=200.0,
            vanishing_point_y=-100.0,  # Above image (y < 0)
            ref_height=6.0
        )

        result_no_perspective = engine.estimate_height(
            target_top_y=0.0,
            target_bottom_y=200.0,
            ref_top_y=100.0,
            ref_bottom_y=200.0,
            vanishing_point_y=1e10,  # At infinity
            ref_height=6.0
        )

        # Without perspective: simple ratio = 6 × (200/100) = 12 feet
        assert abs(result_no_perspective - 12.0) < 0.01

        # With perspective: should be different (correction applied)
        assert result_with_perspective != result_no_perspective

    def test_basketball_hoop_reference_scenario(self):
        """
        Real-world test: Estimating player height using basketball hoop as reference.

        Known: Basketball hoop is 10 feet (3.05m) from ground to rim.

        Scenario (image coordinates, y increases downward):
        - Using vanishing point at infinity for simple pixel ratio test
        - Hoop: 200 pixels tall (y=100 to y=300), 10 feet
        - Player: 120 pixels tall (y=180 to y=300), should be 6 feet
        """
        from geometry_engine import GeometryEngine

        engine = GeometryEngine()

        # With vanishing point at infinity, use simple pixel ratio
        result = engine.estimate_height(
            target_top_y=180.0,      # Player head
            target_bottom_y=300.0,   # Player feet (same base as hoop)
            ref_top_y=100.0,         # Hoop rim
            ref_bottom_y=300.0,      # Hoop base (ground level)
            vanishing_point_y=1e10,  # At infinity for simple ratio
            ref_height=10.0          # Hoop height = 10 feet
        )

        # Player is 120/200 = 0.6 of hoop height = 6 feet
        expected = 6.0
        assert abs(result - expected) < 0.1, f"Expected ~{expected}, got {result}"

    def test_symmetric_cross_ratio_property(self):
        """
        Test mathematical property: CR(A,B,C,D) × CR(A,B,D,C) = 1

        This ensures our cross-ratio implementation is mathematically correct.
        """
        from geometry_engine import GeometryEngine

        engine = GeometryEngine()

        cr1 = engine.cross_ratio(0, 10, 20, 30)
        cr2 = engine.cross_ratio(0, 10, 30, 20)  # C and D swapped

        # Product should equal 1
        assert abs(cr1 * cr2 - 1.0) < 1e-10


class TestHeightEstimationEdgeCases:
    """Edge cases and error handling for height estimation"""

    def test_zero_reference_height_raises_error(self):
        """Cannot estimate height with zero reference"""
        from geometry_engine import GeometryEngine

        engine = GeometryEngine()

        with pytest.raises(ValueError, match="(?i)reference height"):
            engine.estimate_height(
                target_top_y=100.0,
                target_bottom_y=200.0,
                ref_top_y=150.0,
                ref_bottom_y=200.0,
                vanishing_point_y=0.0,
                ref_height=0.0
            )

    def test_negative_reference_height_raises_error(self):
        """Reference height must be positive"""
        from geometry_engine import GeometryEngine

        engine = GeometryEngine()

        with pytest.raises(ValueError, match="(?i)reference height"):
            engine.estimate_height(
                target_top_y=100.0,
                target_bottom_y=200.0,
                ref_top_y=150.0,
                ref_bottom_y=200.0,
                vanishing_point_y=0.0,
                ref_height=-10.0
            )

    def test_zero_pixel_height_reference_raises_error(self):
        """Reference object must have non-zero pixel height"""
        from geometry_engine import GeometryEngine

        engine = GeometryEngine()

        with pytest.raises(ValueError, match="pixel height"):
            engine.estimate_height(
                target_top_y=100.0,
                target_bottom_y=200.0,
                ref_top_y=200.0,   # Same as bottom = 0 height
                ref_bottom_y=200.0,
                vanishing_point_y=0.0,
                ref_height=10.0
            )

    def test_zero_pixel_height_target_returns_zero(self):
        """Target with zero pixel height should return 0"""
        from geometry_engine import GeometryEngine

        engine = GeometryEngine()

        result = engine.estimate_height(
            target_top_y=200.0,    # Same as bottom = 0 height
            target_bottom_y=200.0,
            ref_top_y=100.0,
            ref_bottom_y=200.0,
            vanishing_point_y=0.0,
            ref_height=10.0
        )

        assert result == 0.0

    def test_vanishing_point_at_target_top_raises_error(self):
        """Division by zero when vanishing point equals target top"""
        from geometry_engine import GeometryEngine

        engine = GeometryEngine()

        with pytest.raises(ValueError, match="(?i)vanishing point"):
            engine.estimate_height(
                target_top_y=100.0,
                target_bottom_y=200.0,
                ref_top_y=150.0,
                ref_bottom_y=200.0,
                vanishing_point_y=100.0,  # Equals target_top_y
                ref_height=10.0
            )

    def test_vanishing_point_at_ref_bottom_raises_error(self):
        """Division by zero when vanishing point equals ref bottom"""
        from geometry_engine import GeometryEngine

        engine = GeometryEngine()

        with pytest.raises(ValueError, match="(?i)vanishing point"):
            engine.estimate_height(
                target_top_y=100.0,
                target_bottom_y=200.0,
                ref_top_y=150.0,
                ref_bottom_y=200.0,
                vanishing_point_y=200.0,  # Equals ref_bottom_y
                ref_height=10.0
            )


class TestGeometryEngineHelpers:
    """Tests for helper methods"""

    def test_pixel_height_calculation(self):
        """Test pixel height helper method"""
        from geometry_engine import GeometryEngine

        engine = GeometryEngine()

        # y increases downward, so bottom > top
        assert engine.pixel_height(top_y=100, bottom_y=200) == 100
        assert engine.pixel_height(top_y=0, bottom_y=500) == 500

    def test_pixel_height_with_inverted_coords(self):
        """Handle case where top_y > bottom_y (y increases upward)"""
        from geometry_engine import GeometryEngine

        engine = GeometryEngine()

        # Should return absolute value
        assert engine.pixel_height(top_y=200, bottom_y=100) == 100

    def test_is_valid_for_estimation(self):
        """Test validation helper"""
        from geometry_engine import GeometryEngine

        engine = GeometryEngine()

        # Valid case
        assert engine.is_valid_for_estimation(
            target_top_y=100, target_bottom_y=200,
            ref_top_y=150, ref_bottom_y=200,
            vanishing_point_y=0, ref_height=10
        ) is True

        # Invalid: vanishing point at target top
        assert engine.is_valid_for_estimation(
            target_top_y=100, target_bottom_y=200,
            ref_top_y=150, ref_bottom_y=200,
            vanishing_point_y=100, ref_height=10
        ) is False
