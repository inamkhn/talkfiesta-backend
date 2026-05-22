from pydantic import BaseModel, ConfigDict
from typing import List, Optional, Any
from datetime import datetime

class SpeakingExerciseResponse(BaseModel):
    id: str
    cycle: int
    day: int
    title: str
    instruction: str
    prompt_text: str
    duration_seconds: int
    difficulty: Optional[str] = None
    tips: List[str] = []
    
    model_config = ConfigDict(from_attributes=True)

class SpeakingJobResponse(BaseModel):
    id: str
    status: str
    error_message: Optional[str] = None
    result_summary: Optional[Any] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    # Full submission result — populated only when status == 'done'
    result: Optional["SpeakingSubmissionResponse"] = None

    model_config = ConfigDict(from_attributes=True)

class SpeakingSubmissionResponse(BaseModel):
    id: str
    exercise_id: str
    status: str
    audio_file_path: str
    transcript: Optional[str] = None
    overall_score: Optional[int] = None
    fluency_score: Optional[int] = None
    pronunciation_score: Optional[int] = None
    pace_score: Optional[int] = None
    words_mispronounced: List[str] = []
    pronunciation_issues: List[Any] = []
    feedback: Optional[str] = None
    improvement_tips: List[str] = []
    encouragement: Optional[str] = None
    passed: bool = False
    xp_earned: int = 0
    created_at: datetime
    analysed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class PresignedUrlResponse(BaseModel):
    url: str
    fields: dict
    s3_key: str

class SpeakingSubmissionCreate(BaseModel):
    exercise_id: str
    s3_file_key: str
    content_type: str = "audio/webm"
    size_bytes: int = 0

# Resolve forward reference
SpeakingJobResponse.model_rebuild()
