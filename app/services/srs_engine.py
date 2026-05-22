from datetime import date, timedelta
from typing import Tuple

MASTERY_THRESHOLD = 5

def calculate_next_review(
    ease_factor: float, 
    interval_days: int, 
    repetitions: int, 
    grade: int
) -> Tuple[float, int, int, date, bool]:
    """
    Computes the SuperMemo-2 attributes based on a user's 0-5 grade.
    
    Args:
        ease_factor: Current multiplier for gaps.
        interval_days: How many days the previous gap was.
        repetitions: Consecutive correct hits.
        grade: 0-5 user self-assessment.
        
    Returns:
        (updated_ease_factor, new_interval, new_repetitions, next_review_date, is_mastered)
    """
    if grade >= 3:
        # User remembered the word correctly
        if repetitions == 0:
            new_interval = 1
        elif repetitions == 1:
            new_interval = 6
        else:
            new_interval = round(interval_days * ease_factor)
        new_repetitions = repetitions + 1
    else:
        # User failed the word - reset sequence entirely
        new_repetitions = 0
        new_interval = 1
        
    # Update Ease Factor mathematically
    # EF = EF + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
    new_ease_factor = ease_factor + (0.1 - (5 - grade) * (0.08 + (5 - grade) * 0.02))
    
    # Floor to hard boundary of 1.3
    if new_ease_factor < 1.3:
        new_ease_factor = 1.3
        
    next_review_date = date.today() + timedelta(days=new_interval)
    is_mastered = new_repetitions >= MASTERY_THRESHOLD
    
    return new_ease_factor, new_interval, new_repetitions, next_review_date, is_mastered
