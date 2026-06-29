from pydantic import BaseModel, ConfigDict, field_validator
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

    @field_validator("grade")
    @classmethod
    def validate_grade(cls, v: int) -> int:
        if v < 0 or v > 5:
            raise ValueError("Grade must be between 0 and 5")
        return v

class VocabularySRSResponse(BaseModel):
    word: VocabularyWordResponse
    ease_factor: float
    interval_days: int
    repetitions: int
    mastery_level: int
    next_review_date: Optional[date]
    is_mastered: bool
    
    model_config = ConfigDict(from_attributes=True)

# --- Batch Review ---
class BatchReviewItem(BaseModel):
    word_id: str
    grade: int

    @field_validator("grade")
    @classmethod
    def validate_grade(cls, v: int) -> int:
        if v < 0 or v > 5:
            raise ValueError("Grade must be between 0 and 5")
        return v

class BatchReviewRequest(BaseModel):
    reviews: List[BatchReviewItem]

    @field_validator("reviews")
    @classmethod
    def validate_reviews_length(cls, v: list) -> list:
        if len(v) > 50:
            raise ValueError("Maximum 50 reviews per batch")
        if len(v) == 0:
            raise ValueError("At least one review is required")
        return v

class BatchReviewResult(BaseModel):
    word_id: str
    grade: int
    error: Optional[str] = None
    next_review_date: Optional[date] = None
    is_mastered: bool = False

class BatchReviewResponse(BaseModel):
    results: List[BatchReviewResult]
    stats_updated: dict

# --- Paginated Words ---
class PaginatedWordResponse(BaseModel):
    words: List[VocabularyWordResponse]
    next_cursor: Optional[str] = None
    has_more: bool = False
    total_count: int = 0

# --- Analytics / Progress ---
class VocabularyProgressStats(BaseModel):
    total_words_encountered: int
    words_mastered: int
    average_mastery_level: float
    words_due_today: int
