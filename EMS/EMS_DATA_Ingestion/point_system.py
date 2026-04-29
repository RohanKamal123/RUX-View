def mz_media_points(
    video_type: str,
    editing_style: str,
    difficulty: str,
    duration: float,
    no_of_videos: int = 1,
    simple_batch: bool = False
) -> int:
    """
    Calculate media points based on video specifications.
    
    Args:
        video_type: "Short" or "Long"
        editing_style: "Low", "Medium", or "High"
        difficulty: "low", "medium", or "high"
        duration: Video duration in minutes (float)
        no_of_videos: Number of videos (default: 1)
        simple_batch: True for Before/After Dump style batches (default: False)
    
    Returns:
        Total points as integer
    """
    # Normalize inputs
    editing_style = editing_style.lower()
    difficulty = difficulty.lower()
    video_type = video_type.lower()
    
    # Calculate base points
    if video_type == "short":
        base = _calculate_short_video_points(editing_style, difficulty, duration, simple_batch)
    elif video_type == "long":
        base = _calculate_long_video_points(editing_style, difficulty, duration)
    else:
        raise ValueError(f"Invalid video_type: '{video_type}'. Must be 'short' or 'long'.")
    
    # Apply multiplier for multiple videos
    total_points = round(base) * no_of_videos
    
    return total_points


def _calculate_short_video_points(
    editing_style: str,
    difficulty: str,
    duration: float,
    simple_batch: bool
) -> int:
    """Calculate base points for short videos."""
    
    if editing_style == "low":
        if simple_batch:
            base = 6
        else:
            # Set base by difficulty
            base = {"low": 8, "medium": 9, "high": 11}[difficulty]
            
            # Adjust for duration
            if duration < 0.30:
                base -= 1
            elif duration > 1.0:
                base += 1
        
        # Clamp to range
        base = max(8, min(base, 12))
    
    elif editing_style == "medium":
        # Set base by difficulty
        base = {"low": 10, "medium": 11, "high": 13}[difficulty]
        
        # Adjust for duration
        if duration < 0.30:
            base -= 1
        elif 1.0 < duration <= 2.5:
            base += 1
        elif duration > 2.5:
            base += 2
        
        # Clamp to range
        base = max(9, min(base, 14))
    
    elif editing_style == "high":
        # Set base by difficulty
        base = {"low": 17, "medium": 19, "high": 20}[difficulty]
        
        # Adjust for duration
        if duration < 0.30:
            base -= 1
        elif duration > 1.0:
            base += 1
        
        # Clamp to range
        base = max(15, min(base, 22))
    
    else:
        raise ValueError(f"Invalid editing_style: '{editing_style}'. Must be 'low', 'medium', or 'high'.")
    
    return base


def _calculate_long_video_points(
    editing_style: str,
    difficulty: str,
    duration: float
) -> int:
    """Calculate base points for long videos."""
    
    if editing_style == "low":
        if difficulty == "high":  # Course-style
            if duration < 5:
                base = 18
            elif duration <= 7:
                base = 20
            else:
                base = 22
        else:
            base = 19
            if duration < 6:
                base -= 1
            if duration > 9:
                base += 1
        
        # Clamp to range
        base = max(18, min(base, 22))
    
    elif editing_style == "medium":
        # Set base by difficulty
        base = {"low": 20, "medium": 21, "high": 22}[difficulty]
        
        # Adjust for duration
        if duration < 5:
            base -= 1
        if duration > 8:
            base += 1
        
        # Clamp to range
        base = max(19, min(base, 23))
    
    elif editing_style == "high":
        # Set base by difficulty
        base = {"low": 23, "medium": 24, "high": 25}[difficulty]
        
        # Adjust for duration
        if duration < 3.5:
            base -= 3  # Special case (e.g., Matteo)
        elif duration > 6:
            base += 1
        
        # Clamp to range
        base = max(22, min(base, 30))
    
    else:
        raise ValueError(f"Invalid editing_style: '{editing_style}'. Must be 'low', 'medium', or 'high'.")
    
    return base
