from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import datetime

# --- Requests ---

class ConversationSessionCreate(BaseModel):
    """Payload sent by React to start a conversation record"""
    scenario_id: Optional[str] = "free_talk"
    session_type: str = "voice"  # 'voice' or 'text'
    max_duration_seconds: Optional[int] = 600

class SyncMessageItem(BaseModel):
    """Individual subtitle text block streamed from WebRTC"""
    role: str  # 'user' or 'ai'
    content: str
    audio_clip_url: Optional[str] = None

class ConversationSyncPayload(BaseModel):
    """Payload blasted by React to dump the entire call history"""
    messages: List[SyncMessageItem]
    completed_at: Optional[datetime] = None

# --- Responses ---

class ConversationSessionResponse(BaseModel):
    id: str
    user_id: str
    session_type: str
    scenario_key: str
    scenario_title: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    max_duration_seconds: Optional[int] = None
    turn_count: int
    xp_earned: int
    status: str
    session_audio_url: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)

class ConversationMessageResponse(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    audio_clip_url: Optional[str] = None
    turn_number: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class WebRTCTokenResponse(BaseModel):
    """Returns the secure Ephemeral Connection string to React"""
    token: str
    provider: str = "google_genai"
    expires_in_seconds: int = 3600
