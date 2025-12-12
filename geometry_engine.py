"""
GeometryEngine - Single-view metrology using Cross Ratio formula

Implements height estimation from a single image using the Cross Ratio,
a projective invariant from Criminisi's single-view metrology work.

The Cross Ratio allows accurate height measurement even with perspective
distortion, given:
1. A reference object of known height
2. The vertical vanishing point (where vertical lines converge)

Reference:
    Criminisi, A., Reid, I., & Zisserman, A. (2000).
    "Single View Metrology." International Journal of Computer Vision.
"""
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)


class GeometryEngine:
    """
    Single-view geometry engine for height estimation using Cross Ratio.

    The Cross Ratio is a projective invariant that remains constant under
    perspective projection. For four collinear points A, B, C, D:

        CR(A, B, C, D) = [(A-C)(B-D)] / [(A-D)(B-C)]

    For height estimation with a vertical vanishing point v:

        H_target = H_ref × (pixel_ratio) × (perspective_correction)

    Where:
        pixel_ratio = (t_top - t_bottom) / (r_top - r_bottom)
        perspective_correction = [(v - r_top)/(v - t_top)] × [(v - t_bottom)/(v - r_bottom)]

    KEY PROPERTY:
        When vanishing_point → ±∞ (orthographic projection), the perspective
        correction approaches 1, and the formula reduces to simple pixel ratio.

    Example:
        >>> engine = GeometryEngine()
        >>> height = engine.estimate_height(
        ...     target_top_y=250,      # Player head y-coordinate
        ...     target_bottom_y=500,   # Player feet y-coordinate
        ...     ref_top_y=100,         # Hoop rim y-coordinate
        ...     ref_bottom_y=300,      # Hoop base y-coordinate
        ...     vanishing_point_y=-200,# Vertical vanishing point
        ...     ref_height=10.0        # Hoop is 10 feet tall
        ... )
    """

    def __init__(self):
        """Initialize the GeometryEngine."""
        pass

    def cross_ratio(
        self,
        a: float,
        b: float,
        c: float,
        d: float
    ) -> float:
        """
        Calculate the Cross Ratio of four collinear points.

        The Cross Ratio CR(A, B, C, D) is defined as:
            CR = [(A-C)(B-D)] / [(A-D)(B-C)]

        This is a projective invariant - it remains constant under
        perspective projection.

        Args:
            a: First point coordinate
            b: Second point coordinate
            c: Third point coordinate
            d: Fourth point coordinate

        Returns:
            The cross ratio value

        Raises:
            ValueError: If the configuration is degenerate (division by zero)

        Properties:
            - CR(A,B,C,D) × CR(A,B,D,C) = 1
            - Invariant under projective transformations
            - Invariant under translation (only ratios matter)
        """
        numerator = (a - c) * (b - d)
        denominator = (a - d) * (b - c)

        if abs(denominator) < 1e-12:
            raise ValueError(
                f"Degenerate cross-ratio configuration: denominator is zero. "
                f"Points: A={a}, B={b}, C={c}, D={d}"
            )

        return numerator / denominator

    def pixel_height(self, top_y: float, bottom_y: float) -> float:
        """
        Calculate pixel height from top and bottom y-coordinates.

        Args:
            top_y: Y-coordinate of top (e.g., head)
            bottom_y: Y-coordinate of bottom (e.g., feet)

        Returns:
            Absolute pixel height
        """
        return abs(bottom_y - top_y)

    def is_valid_for_estimation(
        self,
        target_top_y: float,
        target_bottom_y: float,
        ref_top_y: float,
        ref_bottom_y: float,
        vanishing_point_y: float,
        ref_height: float
    ) -> bool:
        """
        Check if the given parameters are valid for height estimation.

        Args:
            target_top_y: Y-coordinate of target top
            target_bottom_y: Y-coordinate of target bottom
            ref_top_y: Y-coordinate of reference top
            ref_bottom_y: Y-coordinate of reference bottom
            vanishing_point_y: Y-coordinate of vertical vanishing point
            ref_height: Known height of reference object

        Returns:
            True if parameters are valid, False otherwise
        """
        # Reference height must be positive
        if ref_height <= 0:
            return False

        # Reference must have non-zero pixel height
        if abs(ref_top_y - ref_bottom_y) < 1e-12:
            return False

        # Vanishing point cannot equal target_top (division by zero)
        if abs(vanishing_point_y - target_top_y) < 1e-12:
            return False

        # Vanishing point cannot equal ref_bottom (division by zero)
        if abs(vanishing_point_y - ref_bottom_y) < 1e-12:
            return False

        return True

    def estimate_height(
        self,
        target_top_y: float,
        target_bottom_y: float,
        ref_top_y: float,
        ref_bottom_y: float,
        vanishing_point_y: float,
        ref_height: float
    ) -> float:
        """
        Estimate real-world height using Cross Ratio formula.

        Implements the Criminisi single-view metrology formula:

            H_target = H_ref × (t_top - t_bottom)/(r_top - r_bottom)
                     × (v - r_top)/(v - t_top)
                     × (v - t_bottom)/(v - r_bottom)

        Where:
            - t_top, t_bottom: target top/bottom y-coordinates
            - r_top, r_bottom: reference top/bottom y-coordinates
            - v: vertical vanishing point y-coordinate
            - H_ref: known reference height

        KEY PROPERTY:
            When v → ±∞, the correction factors approach 1, and:
            H_target ≈ H_ref × (target_pixel_height / ref_pixel_height)

        Args:
            target_top_y: Y-coordinate of target object's top (e.g., head)
            target_bottom_y: Y-coordinate of target object's bottom (e.g., feet)
            ref_top_y: Y-coordinate of reference object's top
            ref_bottom_y: Y-coordinate of reference object's bottom
            vanishing_point_y: Y-coordinate of vertical vanishing point
            ref_height: Known real-world height of reference object

        Returns:
            Estimated real-world height of target object

        Raises:
            ValueError: If parameters are invalid (zero heights, bad vanishing point)

        Example:
            >>> engine = GeometryEngine()
            >>> # Player vs 10-foot basketball hoop
            >>> engine.estimate_height(
            ...     target_top_y=250, target_bottom_y=500,  # Player
            ...     ref_top_y=100, ref_bottom_y=300,        # Hoop
            ...     vanishing_point_y=-200,
            ...     ref_height=10.0
            ... )
            6.25  # Player is about 6.25 feet tall
        """
        # Validate reference height
        if ref_height <= 0:
            raise ValueError(
                f"Reference height must be positive, got {ref_height}"
            )

        # Validate reference pixel height
        ref_pixel_height = ref_top_y - ref_bottom_y
        if abs(ref_pixel_height) < 1e-12:
            raise ValueError(
                "Reference object must have non-zero pixel height "
                f"(ref_top_y={ref_top_y}, ref_bottom_y={ref_bottom_y})"
            )

        # Check for zero target height (valid case, returns 0)
        target_pixel_height = target_top_y - target_bottom_y
        if abs(target_pixel_height) < 1e-12:
            return 0.0

        # Validate vanishing point doesn't cause division by zero
        if abs(vanishing_point_y - target_top_y) < 1e-12:
            raise ValueError(
                f"Vanishing point y ({vanishing_point_y}) cannot equal "
                f"target top y ({target_top_y}) - causes division by zero"
            )

        if abs(vanishing_point_y - ref_bottom_y) < 1e-12:
            raise ValueError(
                f"Vanishing point y ({vanishing_point_y}) cannot equal "
                f"reference bottom y ({ref_bottom_y}) - causes division by zero"
            )

        # Calculate pixel ratio
        # Note: We use signed values to preserve direction
        pixel_ratio = target_pixel_height / ref_pixel_height

        # Calculate perspective correction factors
        # These approach 1.0 as vanishing_point_y → ±∞
        v = vanishing_point_y
        t_top = target_top_y
        t_bot = target_bottom_y
        r_top = ref_top_y
        r_bot = ref_bottom_y

        # Top correction: (v - r_top) / (v - t_top)
        top_correction = (v - r_top) / (v - t_top)

        # Bottom correction: (v - t_bottom) / (v - r_bottom)
        bottom_correction = (v - t_bot) / (v - r_bot)

        # Combined perspective correction
        perspective_correction = top_correction * bottom_correction

        # Final height estimate
        estimated_height = ref_height * pixel_ratio * perspective_correction

        logger.debug(
            f"Height estimation: pixel_ratio={pixel_ratio:.4f}, "
            f"top_correction={top_correction:.4f}, "
            f"bottom_correction={bottom_correction:.4f}, "
            f"result={estimated_height:.4f}"
        )

        return abs(estimated_height)  # Height is always positive

    def estimate_height_from_court(
        self,
        target_top_y: float,
        target_bottom_y: float,
        court_feature: str = "basketball_hoop",
        feature_top_y: Optional[float] = None,
        feature_bottom_y: Optional[float] = None,
        vanishing_point_y: float = float('inf')
    ) -> float:
        """
        Convenience method using known court features as reference.

        Args:
            target_top_y: Y-coordinate of target top
            target_bottom_y: Y-coordinate of target bottom
            court_feature: Name of court feature ("basketball_hoop", "three_point_line", etc.)
            feature_top_y: Y-coordinate of feature top (required)
            feature_bottom_y: Y-coordinate of feature bottom (required)
            vanishing_point_y: Vertical vanishing point (default: infinity)

        Returns:
            Estimated height in feet

        Raises:
            ValueError: If court feature is unknown or coordinates not provided
        """
        # Known heights of court features (in feet)
        feature_heights = {
            "basketball_hoop": 10.0,        # Rim height from floor
            "basketball_backboard": 3.5,    # Backboard height
            "free_throw_line_width": 12.0,  # Width of free throw lane
        }

        if court_feature not in feature_heights:
            raise ValueError(
                f"Unknown court feature: {court_feature}. "
                f"Known features: {list(feature_heights.keys())}"
            )

        if feature_top_y is None or feature_bottom_y is None:
            raise ValueError(
                "feature_top_y and feature_bottom_y must be provided"
            )

        return self.estimate_height(
            target_top_y=target_top_y,
            target_bottom_y=target_bottom_y,
            ref_top_y=feature_top_y,
            ref_bottom_y=feature_bottom_y,
            vanishing_point_y=vanishing_point_y,
            ref_height=feature_heights[court_feature]
        )
