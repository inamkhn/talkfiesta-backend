import logging
import asyncio
import base64
from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect, Request
from sqlalchemy.orm import Session
from app.core.rate_limiter import limiter
from google import genai
# pyrefly: ignore [missing-import]
from google.genai import types

from app.config import settings
from app.db.session import get_db
from app.core.dependencies import get_current_user, get_current_user_websocket
from app.models.user import User
from app.models.conversation import ConversationSession, ConversationMessage
from app.schemas.conversation import (
    ConversationSessionCreate,
    ConversationSessionResponse,
    ConversationSyncPayload,
    ConversationMessageResponse,
    WebRTCTokenResponse
)

router = APIRouter(prefix="/speaking/conversation", tags=["Speaking Conversation (WebRTC)"])
logger = logging.getLogger(__name__)

# --- SCENARIOS ---
@router.get("/scenarios")
def get_scenarios():
    """Mock database or constant of scenarios to present in the App UI."""
    return [
        {
            "id": "airport_customs",
            "title": "Airport Customs",
            "difficulty": "B1",
            "description": "Navigate through border control answering standard security questions."
        },
        {
            "id": "coffee_shop",
            "title": "Ordering Coffee",
            "difficulty": "A2",
            "description": "Order a customized espresso drink at a busy cafe."
        },
        {
            "id": "free_talk",
            "title": "Free Talk",
            "difficulty": "All",
            "description": "An unstructured conversation about any topic."
        }
    ]

# --- SESSION INITIALIZATION ---
@router.post("/sessions", response_model=ConversationSessionResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
def create_session(
    request: Request,
    payload: ConversationSessionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    scenarios = {s["id"]: s for s in get_scenarios()}
    scenario = scenarios.get(payload.scenario_id, scenarios["free_talk"])

    session = ConversationSession(
        user_id=current_user.id,
        session_type=payload.session_type,
        scenario_key=scenario["id"],
        scenario_title=scenario["title"],
        user_level=current_user.english_level or "B1",
        system_prompt=f"You are in this scenario: {scenario['description']}",
        max_duration_seconds=payload.max_duration_seconds,
        status="active"
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session

@router.websocket("/sessions/{session_id}/ws")
async def conversation_websocket_proxy(
    websocket: WebSocket,
    session_id: str,
    token: str = None,
    db: Session = Depends(get_db)
):
    """
    Secure WebSocket proxy utilizing the Google GenAI SDK's native Live Client.
    Exposes a frontend connection while shielding the API key securely.
    """
    await websocket.accept()
    
    # 1. Authenticate WebSocket User
    try:
        current_user = get_current_user_websocket(token, db)
    except Exception as e:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized")
        return

    # 2. Retrieve & Validate Session Ownership
    session_record = db.query(ConversationSession).filter(
        ConversationSession.id == session_id,
        ConversationSession.user_id == current_user.id
    ).first()
    
    if not session_record:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Session not found")
        return

    if not settings.GOOGLE_AI_STUDIO_API_KEY:
        await websocket.close(code=1011, reason="AI Studio API Key missing on server")
        return

    # 3. Initialize Google GenAI Client with v1alpha protocol (required for Multimodal Live)
    client = genai.Client(
        api_key=settings.GOOGLE_AI_STUDIO_API_KEY,
        http_options={'api_version': 'v1alpha'}
    )
    
    scenario_instructions = session_record.system_prompt or "Engage in a natural dialogue."
    
    # Build Live Connect Config using SDK Types
    live_config = types.LiveConnectConfig(
        response_modalities=[types.LiveModality.AUDIO],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name="Puck"
                )
            )
        ),
        generation_config=types.GenerateContentConfig(
            model="gemini-3.1-flash-live-preview",
            temperature=0.7,
        ),
        system_instruction=types.Content(
            parts=[
                types.Part.from_text(
                    text=f"{scenario_instructions} "
                         f"Adopt a helpful persona suited for level {session_record.user_level or 'B1'}. "
                         f"Speak naturally, keep your responses concise, and encourage the user to reply."
                )
            ]
        )
    )

    message_count = 0

    try:
        async with client.aio.live.connect(
            model="gemini-3.1-flash-live-preview",
            config=live_config
        ) as live_session:

            async def relay_client_to_gemini():
                try:
                    async for message in websocket.iter_json():
                        if "realtime_input" in message:
                            chunks = message["realtime_input"].get("media_chunks", [])
                            for chunk in chunks:
                                if "data" in chunk and "mime_type" in chunk:
                                    # Decode base64 string from client into raw bytes for google-genai SDK
                                    raw_audio_bytes = base64.b64decode(chunk["data"])
                                    await live_session.send(
                                        input={
                                            "data": raw_audio_bytes,
                                            "mime_type": chunk["mime_type"]
                                        }
                                    )
                        elif "client_content" in message:
                            await live_session.send(
                                input=message["client_content"],
                                end_of_turn=True
                            )
                except Exception as e:
                    logger.debug(f"Client to Gemini relay stopped: {e}")

            async def relay_gemini_to_client():
                nonlocal message_count
                try:
                    current_turn_content = []
                    async for response in live_session.receive():
                        server_content = response.server_content
                        if server_content is not None:
                            model_turn = server_content.model_turn
                            if model_turn is not None:
                                for part in model_turn.parts:
                                    if part.inline_data:
                                        # Encode raw bytes from google-genai SDK into base64 string for WebSocket JSON
                                        base64_audio = base64.b64encode(part.inline_data.data).decode('utf-8')
                                        await websocket.send_json({
                                            "server_content": {
                                                "model_turn": {
                                                    "parts": [{
                                                        "inline_data": {
                                                            "data": base64_audio,
                                                            "mime_type": part.inline_data.mime_type
                                                        }
                                                    }]
                                                }
                                            }
                                        })
                                    elif part.text:
                                        current_turn_content.append(part.text)
                                        await websocket.send_json({
                                            "server_content": {
                                                "model_turn": {
                                                    "parts": [{"text": part.text}]
                                                }
                                            }
                                        })
                            
                            if server_content.turn_complete:
                                text_response = "".join(current_turn_content).strip()
                                if text_response:
                                    message_count += 1
                                    db_msg = ConversationMessage(
                                        session_id=session_id,
                                        role="ai",
                                        content=text_response,
                                        turn_number=message_count
                                    )
                                    db.add(db_msg)
                                    db.commit()
                                current_turn_content = []

                except Exception as e:
                    logger.debug(f"Gemini to Client relay stopped: {e}")

            await asyncio.gather(
                relay_client_to_gemini(),
                relay_gemini_to_client()
            )

    except WebSocketDisconnect:
        logger.info(f"WebSocket session {session_id} disconnected by client.")
    except Exception as e:
        logger.error(f"WebSocket connection error on session {session_id}: {e}")
    finally:
        try:
            db_session = db.query(ConversationSession).filter(ConversationSession.id == session_id).first()
            if db_session:
                db_session.status = "completed"
                db_session.completed_at = datetime.utcnow()
                db_session.turn_count = message_count
                db_session.xp_earned = 15
                db.add(db_session)
                db.commit()
                logger.info(f"Successfully finalized session {session_id} in PostgreSQL with {message_count} turns.")
        except Exception as e:
            logger.error(f"Failed to finalize session {session_id} in DB: {e}")

# --- SESSION COMPLETION (SYNC) ---
@router.post("/sessions/{session_id}/sync")
@limiter.limit("10/minute")
def sync_session_messages(
    request: Request,
    session_id: str,
    payload: ConversationSyncPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Called by React when the WebRTC call is hung up. We ingest the array of conversation 
    that the backend was blind to, and save it to PostgreSQL.
    """
    session = db.query(ConversationSession).filter(
        ConversationSession.id == session_id,
        ConversationSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    for i, msg in enumerate(payload.messages):
        db_message = ConversationMessage(
            session_id=session.id,
            role=msg.role,
            content=msg.content,
            audio_clip_url=msg.audio_clip_url,
            turn_number=i + 1
        )
        db.add(db_message)
        
    session.status = "completed"
    session.completed_at = payload.completed_at or datetime.utcnow()
    session.turn_count = len(payload.messages)
    session.xp_earned = 15  # Award XP
    
    db.commit()
    return {"message": f"Successfully synced {len(payload.messages)} messages.", "xp": session.xp_earned}

# --- HISTORY FETCHING ---
@router.get("/sessions", response_model=List[ConversationSessionResponse])
def get_user_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return db.query(ConversationSession).filter(
        ConversationSession.user_id == current_user.id
    ).order_by(ConversationSession.created_at.desc()).all()

@router.get("/sessions/{session_id}", response_model=ConversationSessionResponse)
def get_single_session_metadata(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    session = db.query(ConversationSession).filter(
        ConversationSession.id == session_id,
        ConversationSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@router.get("/sessions/{session_id}/messages", response_model=List[ConversationMessageResponse])
def get_session_messages(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    session = db.query(ConversationSession).filter(
        ConversationSession.id == session_id,
        ConversationSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    return db.query(ConversationMessage).filter(
        ConversationMessage.session_id == session_id
    ).order_by(ConversationMessage.created_at.asc()).all()
