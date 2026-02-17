from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum
import json

class PartOfSpeech(str, Enum):
    NOUN = "NOUN"
    VERB = "VERB"
    ADJECTIVE = "ADJECTIVE"
    ADVERB = "ADVERB"
    PRONOUN = "PRONOUN"
    PREPOSITION = "PREPOSITION"
    CONJUNCTION = "CONJUNCTION"
    INTERJECTION = "INTERJECTION"

class VocabularyStatus(str, Enum):
    NEW = "NEW"
    LEARNING = "LEARNING"
    REVIEWING = "REVIEWING"
    MASTERED = "MASTERED"

class ExerciseType(str, Enum):
    FILL_BLANK = "FILL_BLANK"
    MATCHING = "MATCHING"
    USAGE = "USAGE"
    PRONUNCIATION = "PRONUNCIATION"

# Request Schemas
class VocabularyPracticeSubmit(BaseModel):
    """Vocabulary practice submission"""
    user_vocabulary_id: str
    daily_activity_id: str
    exercise_type: ExerciseType
    user_answer: str
    correct_answer: str
    is_correct: bool
    time_taken_seconds: int

# Response Schemas
class ExampleSentence(BaseModel):
    """Example sentence schema"""
    sentence: str
    translation: str

class VocabularyWordResponse(BaseModel):
    """Vocabulary word response"""
    id: str
    word: str
    definition: str
    part_of_speech: PartOfSpeech
    difficulty_level: str
    cefr_level: str
    cycle_number: int
    pronunciation_ipa: str
    pronunciation_audio_url: Optional[str] = None
    example_sentences: list[ExampleSentence]
    synonyms: list[str]
    antonyms: list[str]
    usage_tips: Optional[str] = None
    category: str

    @classmethod
    def from_orm(cls, obj):
        """Handle JSON field parsing"""
        from app.services.vocabulary_service import VocabularyService
        from sqlalchemy.orm import Session
        from app.db.session import SessionLocal
        
        # Create a dict from the object
        data = {
            "id": str(obj.id),
            "word": obj.word,
            "definition": obj.definition,
            "part_of_speech": obj.part_of_speech,
            "difficulty_level": obj.difficulty_level,
            "cefr_level": obj.cefr_level,
            "cycle_number": obj.cycle_number,
            "pronunciation_ipa": obj.pronunciation_ipa,
            "pronunciation_audio_url": obj.pronunciation_audio_url,
            "example_sentences": obj.example_sentences if isinstance(obj.example_sentences, list) else json.loads(obj.example_sentences),
            "synonyms": obj.synonyms if isinstance(obj.synonyms, list) else json.loads(obj.synonyms),
            "antonyms": obj.antonyms if isinstance(obj.antonyms, list) else json.loads(obj.antonyms),
            "usage_tips": obj.usage_tips,
            "category": obj.category
        }
        return cls(**data)

    class Config:
        from_attributes = True

class UserVocabularyResponse(BaseModel):
    """User vocabulary progress response"""
    id: str
    word: VocabularyWordResponse
    day_number: int
    status: VocabularyStatus
    mastery_level: int
    times_reviewed: int
    times_practiced: int
    last_reviewed_at: Optional[datetime] = None
    next_review_at: Optional[datetime] = None
    learned_at: datetime
    mastered_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class VocabularyPracticeResponse(BaseModel):
    """Vocabulary practice response"""
    id: str
    is_correct: bool
    feedback: str
    updated_mastery_level: int
    next_review_at: Optional[datetime] = None

    class Config:
        from_attributes = True
