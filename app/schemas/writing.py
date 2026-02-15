from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum

class PromptType(str, Enum):
    ESSAY = "ESSAY"
    EMAIL = "EMAIL"
    STORY = "STORY"
    OPINION = "OPINION"
    DESCRIPTION = "DESCRIPTION"

# Request Schemas
class WritingSubmissionCreate(BaseModel):
    """Create writing submission"""
    prompt_id: str
    daily_activity_id: str
    content: str = Field(..., min_length=10)
    time_spent_seconds: int

class WritingSubmissionUpdate(BaseModel):
    """Update writing submission (revision)"""
    content: str = Field(..., min_length=10)
    time_spent_seconds: int

class WritingAnalyzeRequest(BaseModel):
    """Quick writing analysis request"""
    content: str = Field(..., min_length=10)

# Response Schemas
class WritingPromptResponse(BaseModel):
    """Writing prompt response"""
    id: str
    day_number: int
    cycle_number: int
    difficulty_level: str
    prompt_title: str
    prompt_text: str
    prompt_type: PromptType
    target_word_count: int
    time_limit_minutes: Optional[int] = None
    focus_areas: list[str]
    writing_tips: list[str]
    sample_outline: Optional[str] = None
    learning_resources: list[dict]

    class Config:
        from_attributes = True

class GrammarError(BaseModel):
    """Grammar error schema"""
    type: str
    position: int
    suggestion: str

class VocabularySuggestion(BaseModel):
    """Vocabulary suggestion schema"""
    word: str
    alternatives: list[str]

class WritingAIFeedback(BaseModel):
    """Writing AI feedback schema"""
    strengths: list[str]
    improvements: list[str]
    tips: list[str]

class WritingSubmissionResponse(BaseModel):
    """Writing submission response"""
    id: str
    content: str
    word_count: int
    time_spent_seconds: int
    grammar_score: float
    structure_score: float
    vocabulary_score: float
    coherence_score: float
    overall_score: float
    grammar_errors: list[GrammarError]
    vocabulary_suggestions: list[VocabularySuggestion]
    structure_feedback: str
    ai_feedback: WritingAIFeedback
    revision_count: int
    submitted_at: datetime
    last_edited_at: datetime

    class Config:
        from_attributes = True

class WritingAnalysisResponse(BaseModel):
    """Quick writing analysis response"""
    grammar_errors: list[GrammarError]
    vocabulary_suggestions: list[VocabularySuggestion]
    readability_score: float
    suggestions: list[str]
