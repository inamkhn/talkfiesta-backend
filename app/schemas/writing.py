from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class WritingPromptResponse(BaseModel):
    id: str
    cycle: int
    day: int
    title: str
    prompt: str
    min_words: int
    max_words: int
    grammar_focus: Optional[str] = None
    difficulty: Optional[str] = None
    tips: List[str] = []
    model_config = ConfigDict(from_attributes=True)

class WritingSubmitRequest(BaseModel):
    prompt_id: str
    content: str

class WritingSubmissionResponse(BaseModel):
    id: str
    prompt_id: str
    content: str
    word_count: int
    overall_score: Optional[int] = None
    grammar_score: Optional[int] = None
    vocabulary_score: Optional[int] = None
    coherence_score: Optional[int] = None
    grammar_errors: List = []
    vocabulary_suggestions: List = []
    feedback: Optional[str] = None
    improvement_tips: List = []
    encouragement: Optional[str] = None
    passed: bool = False
    xp_earned: int = 0
    is_revised: bool = False
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
