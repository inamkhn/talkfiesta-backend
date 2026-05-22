from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import date

# --- Base Word Definition ---
class VocabularyWordResponse(BaseModel):
    id: str
    user_id: Optional[str] = None
    cycle: int
    day: int
    position_in_day: int
    word: str
    phonetic: Optional[str] = None
    part_of_speech: Optional[str] = None
    definition: str
    example_sentences: List[str]
    synonyms: List[str]
    antonyms: List[str]
    collocations: List[str]
    memory_tip: Optional[str] = None
    word_register: Optional[str] = None  # renamed from 'register' to avoid shadowing BaseModel
    difficulty: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

# --- Practice (New Learning) ---
class VocabularyPracticeSubmit(BaseModel):
    word_id: str

# --- SRS Review (Flashcard Memory) ---
class VocabularyReviewSubmit(BaseModel):
    word_id: str
    grade: int  # 0 to 5

class VocabularySRSResponse(BaseModel):
    word: VocabularyWordResponse
    ease_factor: float
    interval_days: int
    repetitions: int
    mastery_level: int
    next_review_date: Optional[date]
    is_mastered: bool
    
    model_config = ConfigDict(from_attributes=True)

# --- Analytics / Progress ---
class VocabularyProgressStats(BaseModel):
    total_words_encountered: int
    words_mastered: int
    average_mastery_level: float
    words_due_today: int
