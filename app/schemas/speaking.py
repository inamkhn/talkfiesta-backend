from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum

class DifficultyLevel(str, Enum):
    BEGINNER = "BEGINNER"
    INTERMEDIATE = "INTERMEDIATE"
    ADVANCED = "ADVANCED"

# Request Schemas
class SpeakingSubmissionCreate(BaseModel):
    """Create speaking submission schema"""
    exercise_id: str
    daily_activity_id: str
    # audio_file will be handled as multipart/form-data

# Response Schemas
class SpeakingExerciseResponse(BaseModel):
    """Speaking exercise response"""
    id: str
    day_number: int
    cycle_number: int
    difficulty_level: DifficultyLevel
    topic: str
    prompt_text: str
    target_duration_seconds: int
    instructions: str
    example_response: Optional[str] = None
    focus_areas: list[str]
    learning_resources: list[dict]

    class Config:
        from_attributes = True

class GrammarCorrection(BaseModel):
    """Grammar correction schema"""
    error: str
    correction: str
    explanation: str

class VocabularySuggestion(BaseModel):
    """Vocabulary suggestion schema"""
    word: str
    better_options: list[str]

class AIFeedback(BaseModel):
    """AI feedback schema"""
    strengths: list[str]
    improvements: list[str]
    tips: list[str]

class SpeakingSubmissionResponse(BaseModel):
    """Speaking submission response"""
    id: str
    audio_url: str
    transcription: str
    duration_seconds: int
    word_count: int
    words_per_minute: float
    fluency_score: float
    grammar_score: float
    vocabulary_score: float
    pronunciation_score: float
    overall_score: float
    pause_count: int
    filler_words_count: int
    filler_words_list: list[str]
    ai_feedback: AIFeedback
    grammar_corrections: list[GrammarCorrection]
    vocabulary_suggestions: list[VocabularySuggestion]
    submitted_at: datetime

    class Config:
        from_attributes = True

class TranscriptionResponse(BaseModel):
    """Quick transcription response"""
    transcription: str
    duration_seconds: int
    word_count: int
