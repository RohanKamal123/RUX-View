import pytest
from EMS_DATA_Ingestion.point_system import (
    mz_media_points,
    _calculate_short_video_points,
    _calculate_long_video_points,
)

# Test cases for mz_media_points
def test_mz_media_points_short_video():
    """Test mz_media_points with a typical short video."""
    # base = 11, total = 11 * 1 = 11
    assert mz_media_points("short", "medium", "medium", 0.5) == 11

def test_mz_media_points_long_video():
    """Test mz_media_points with a typical long video."""
    # base = 21, total = 21 * 1 = 21
    assert mz_media_points("long", "medium", "medium", 6) == 21

def test_mz_media_points_multiple_videos():
    """Test mz_media_points with multiple videos."""
    # base = 11, total = 11 * 3 = 33
    assert mz_media_points("short", "medium", "medium", 0.5, no_of_videos=3) == 33

def test_mz_media_points_invalid_video_type():
    """Test mz_media_points with an invalid video type."""
    with pytest.raises(ValueError, match="Invalid video_type: 'invalid'. Must be 'short' or 'long'."):
        mz_media_points("invalid", "low", "low", 0.5)

def test_mz_media_points_short_medium_low_duration_2_videos_2():
    """Test mz_media_points for a specific short video scenario."""
    assert mz_media_points("short", "medium", "low", 2.0, no_of_videos=2) == 22

# Test cases for _calculate_short_video_points
@pytest.mark.parametrize("editing_style, difficulty, duration, simple_batch, expected", [
    # Low editing style
    ("low", "low", 0.5, False, 8),      # Normal case
    ("low", "low", 0.2, False, 8),      # Short duration, clamped
    ("low", "low", 1.5, False, 9),      # Long duration
    ("low", "high", 0.5, False, 11),    # High difficulty
    ("low", "low", 0.5, True, 8),       # Simple batch, base 6 clamped to 8
    
    # Medium editing style
    ("medium", "medium", 0.5, False, 11), # Normal case
    ("medium", "medium", 0.2, False, 10), # Short duration
    ("medium", "medium", 1.5, False, 12), # Long duration (<= 2.5)
    ("medium", "medium", 3.0, False, 13), # Very long duration (> 2.5)
    ("medium", "low", 0.2, False, 9),     # Low difficulty, short duration
    ("medium", "high", 3.0, False, 14),   # High difficulty, very long duration, clamped
    
    # High editing style
    ("high", "high", 0.5, False, 20),   # Normal case
    ("high", "high", 0.2, False, 19),   # Short duration
    ("high", "high", 1.5, False, 21),   # Long duration
    ("high", "low", 0.2, False, 16),    # Low difficulty, short duration
    ("high", "medium", 1.5, False, 20), # Medium difficulty, long duration
])
def test_calculate_short_video_points(editing_style, difficulty, duration, simple_batch, expected):
    """Test _calculate_short_video_points with various parameters."""
    assert _calculate_short_video_points(editing_style, difficulty, duration, simple_batch) == expected

def test_calculate_short_video_points_invalid_style():
    """Test _calculate_short_video_points with an invalid editing style."""
    with pytest.raises(ValueError, match="Invalid editing_style: 'invalid'. Must be 'low', 'medium', or 'high'."):
        _calculate_short_video_points("invalid", "low", 0.5, False)

# Test cases for _calculate_long_video_points
@pytest.mark.parametrize("editing_style, difficulty, duration, expected", [
    # Low editing style
    ("low", "high", 4.0, 18),     # Course-style, < 5 min
    ("low", "high", 6.0, 20),     # Course-style, <= 7 min
    ("low", "high", 8.0, 22),     # Course-style, > 7 min
    ("low", "low", 5.0, 18),      # Non-course, < 6 min
    ("low", "low", 7.0, 19),      # Non-course, normal duration
    ("low", "low", 10.0, 20),     # Non-course, > 9 min
    
    # Medium editing style
    ("medium", "medium", 4.0, 20), # < 5 min
    ("medium", "medium", 6.0, 21), # Normal duration
    ("medium", "medium", 9.0, 22), # > 8 min
    ("medium", "low", 4.0, 19),    # Low difficulty, < 5 min
    ("medium", "high", 9.0, 23),   # High difficulty, > 8 min
    
    # High editing style
    ("high", "high", 3.0, 22),    # Special case < 3.5 min
    ("high", "high", 5.0, 25),    # Normal duration
    ("high", "high", 7.0, 26),    # > 6 min
    ("high", "low", 3.0, 22),     # Low difficulty, special case, clamped
    ("high", "medium", 7.0, 25),  # Medium difficulty, > 6 min
])
def test_calculate_long_video_points(editing_style, difficulty, duration, expected):
    """Test _calculate_long_video_points with various parameters."""
    assert _calculate_long_video_points(editing_style, difficulty, duration) == expected

def test_calculate_long_video_points_invalid_style():
    """Test _calculate_long_video_points with an invalid editing style."""
    with pytest.raises(ValueError, match="Invalid editing_style: 'invalid'. Must be 'low', 'medium', or 'high'."):
        _calculate_long_video_points("invalid", "low", 5.0)
