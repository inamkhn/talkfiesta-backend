"""
Admin Module Endpoints
Handles admin operations for content management
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.session import get_db
from app.core.security import get_current_user
from app.services.admin_service import AdminService
from app.models.user import Role

router = APIRouter()

# ============================================
# ENDPOINT 1: GET ALL USERS (Admin Only)
# ============================================

@router.get("/users", response_model=List[dict])
async def get_all_users(
    role: Optional[str] = Query(None, description="Filter by role (USER, ADMIN)"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    limit: int = Query(20, ge=1, le=100, description="Maximum records to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all users (Admin only)
    
    **CRITICAL**: This endpoint requires admin role.
    
    **Query Parameters:**
    - **role** (optional): Filter by role (USER, ADMIN)
    - **is_active** (optional): Filter by active status
    - **limit** (optional): Max records (default 20, max 100)
    - **offset** (optional): Pagination offset (default 0)
    
    **Returns:**
    - Array of users
    
    **Example Response:**
    ```json
    [
      {
        "id": "uuid",
        "email": "user@example.com",
        "name": "John Doe",
        "role": "USER",
        "is_active": true,
        "is_email_verified": true,
        "created_at": "2024-01-01T00:00:00Z",
        "last_active_at": "2024-01-05T10:30:00Z"
      }
    ]
    ```
    
    **Use Cases:**
    1. Admin dashboard user management
    2. User search and filtering
    3. User statistics
    
    **Frontend Usage:**
    ```javascript
    // Get all users
    const response = await fetch('/api/v1/admin/users', {
      headers: {
        'Authorization': `Bearer ${adminToken}`
      }
    });
    const users = await response.json();
    
    // Filter by role
    const response = await fetch(
      '/api/v1/admin/users?role=ADMIN',
      {
        headers: {
          'Authorization': `Bearer ${adminToken}`
        }
      }
    );
    const admins = await response.json();
    ```
    
    **Error Handling:**
    - 401: Unauthorized (not admin)
    - 403: Forbidden (not admin role)
    """
    # Check if user is admin
    if current_user.role != Role.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    admin_service = AdminService(db)
    users = admin_service.get_all_users(
        role=role,
        is_active=is_active,
        limit=limit,
        offset=offset
    )
    
    return [
        {
            "id": u.id,
            "email": u.email,
            "name": u.name,
            "role": u.role,
            "is_active": u.is_active,
            "is_email_verified": u.is_email_verified,
            "created_at": u.created_at.strftime("%Y-%m-%d %H:%M:%S") if u.created_at else None,
            "last_active_at": u.last_active_at.strftime("%Y-%m-%d %H:%M:%S") if u.last_active_at else None
        }
        for u in users
    ]


# ============================================
# ENDPOINT 2: CREATE SPEAKING EXERCISE (Admin Only)
# ============================================

@router.post("/speaking/exercises", response_model=dict)
async def create_speaking_exercise(
    day_number: int,
    cycle_number: int,
    difficulty_level: str,
    topic: str,
    prompt_text: str,
    target_duration_seconds: int,
    instructions: str,
    example_response: Optional[str] = None,
    focus_areas: Optional[List[str]] = None,
    learning_resources: Optional[List[dict]] = None,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new speaking exercise (Admin only)
    
    **CRITICAL**: This endpoint requires admin role.
    
    **Request Body:**
    ```json
    {
      "day_number": 1,
      "cycle_number": 1,
      "difficulty_level": "BEGINNER",
      "topic": "Self Introduction",
      "prompt_text": "Introduce yourself...",
      "target_duration_seconds": 60,
      "instructions": "Speak clearly...",
      "example_response": "Hello, my name is...",
      "focus_areas": ["grammar", "fluency"],
      "learning_resources": [...]
    }
    ```
    
    **Returns:**
    - Created exercise
    
    **Example Response:**
    ```json
    {
      "id": "uuid",
      "day_number": 1,
      "cycle_number": 1,
      "difficulty_level": "BEGINNER",
      "topic": "Self Introduction",
      "prompt_text": "Introduce yourself...",
      "target_duration_seconds": 60,
      "instructions": "Speak clearly...",
      "example_response": "Hello, my name is...",
      "focus_areas": ["grammar", "fluency"],
      "learning_resources": [...]
    }
    ```
    
    **Use Cases:**
    1. Admin creates new speaking exercises
    2. Bulk import exercises
    3. Update existing exercises
    
    **Frontend Usage:**
    ```javascript
    async function createExercise(exerciseData) {
      const response = await fetch('/api/v1/admin/speaking/exercises', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${adminToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(exerciseData)
      });
      
      const result = await response.json();
      
      // Add to list
      addExerciseToList(result);
    }
    ```
    
    **Error Handling:**
    - 400: Exercise already exists
    - 401: Unauthorized (not admin)
    - 403: Forbidden (not admin role)
    """
    # Check if user is admin
    if current_user.role != Role.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    admin_service = AdminService(db)
    exercise = admin_service.create_speaking_exercise(
        day_number=day_number,
        cycle_number=cycle_number,
        difficulty_level=difficulty_level,
        topic=topic,
        prompt_text=prompt_text,
        target_duration_seconds=target_duration_seconds,
        instructions=instructions,
        example_response=example_response,
        focus_areas=focus_areas,
        learning_resources=learning_resources
    )
    
    return {
        "id": exercise.id,
        "day_number": exercise.day_number,
        "cycle_number": exercise.cycle_number,
        "difficulty_level": exercise.difficulty_level,
        "topic": exercise.topic,
        "prompt_text": exercise.prompt_text,
        "target_duration_seconds": exercise.target_duration_seconds,
        "instructions": exercise.instructions,
        "example_response": exercise.example_response,
        "focus_areas": exercise.focus_areas,
        "learning_resources": exercise.learning_resources
    }


# ============================================
# ENDPOINT 3: CREATE VOCABULARY WORD (Admin Only)
# ============================================

@router.post("/vocabulary/words", response_model=dict)
async def create_vocabulary_word(
    word: str,
    definition: str,
    part_of_speech: str,
    difficulty_level: str,
    cefr_level: str,
    cycle_number: int,
    pronunciation_ipa: str,
    pronunciation_audio_url: Optional[str] = None,
    example_sentences: Optional[List[dict]] = None,
    synonyms: Optional[List[str]] = None,
    antonyms: Optional[List[str]] = None,
    usage_tips: Optional[str] = None,
    category: str = "daily",
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new vocabulary word (Admin only)
    
    **CRITICAL**: This endpoint requires admin role.
    
    **Request Body:**
    ```json
    {
      "word": "ambitious",
      "definition": "having a strong desire to succeed",
      "part_of_speech": "ADJECTIVE",
      "difficulty_level": "BEGINNER",
      "cefr_level": "B1",
      "cycle_number": 1,
      "pronunciation_ipa": "/æmˈbɪʃ.əs/",
      "pronunciation_audio_url": "https://...",
      "example_sentences": [{"sentence": "...", "translation": "..."}],
      "synonyms": ["driven", "determined"],
      "antonyms": ["complacent"],
      "usage_tips": "Often used for career goals",
      "category": "academic"
    }
    ```
    
    **Returns:**
    - Created vocabulary word
    
    **Use Cases:**
    1. Admin creates new vocabulary words
    2. Bulk import vocabulary
    3. Update existing words
    
    **Error Handling:**
    - 400: Word already exists
    - 401: Unauthorized (not admin)
    - 403: Forbidden (not admin role)
    """
    # Check if user is admin
    if current_user.role != Role.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    admin_service = AdminService(db)
    word_obj = admin_service.create_vocabulary_word(
        word=word,
        definition=definition,
        part_of_speech=part_of_speech,
        difficulty_level=difficulty_level,
        cefr_level=cefr_level,
        cycle_number=cycle_number,
        pronunciation_ipa=pronunciation_ipa,
        pronunciation_audio_url=pronunciation_audio_url,
        example_sentences=example_sentences,
        synonyms=synonyms,
        antonyms=antonyms,
        usage_tips=usage_tips,
        category=category
    )
    
    return {
        "id": word_obj.id,
        "word": word_obj.word,
        "definition": word_obj.definition,
        "part_of_speech": word_obj.part_of_speech,
        "difficulty_level": word_obj.difficulty_level,
        "cefr_level": word_obj.cefr_level,
        "cycle_number": word_obj.cycle_number,
        "pronunciation_ipa": word_obj.pronunciation_ipa,
        "pronunciation_audio_url": word_obj.pronunciation_audio_url,
        "example_sentences": word_obj.example_sentences,
        "synonyms": word_obj.synonyms,
        "antonyms": word_obj.antonyms,
        "usage_tips": word_obj.usage_tips,
        "category": word_obj.category
    }


# ============================================
# ENDPOINT 4: CREATE WRITING PROMPT (Admin Only)
# ============================================

@router.post("/writing/prompts", response_model=dict)
async def create_writing_prompt(
    day_number: int,
    cycle_number: int,
    difficulty_level: str,
    prompt_title: str,
    prompt_text: str,
    prompt_type: str,
    target_word_count: int,
    time_limit_minutes: Optional[int] = None,
    focus_areas: Optional[List[str]] = None,
    writing_tips: Optional[List[str]] = None,
    sample_outline: Optional[str] = None,
    learning_resources: Optional[List[dict]] = None,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new writing prompt (Admin only)
    
    **CRITICAL**: This endpoint requires admin role.
    
    **Request Body:**
    ```json
    {
      "day_number": 1,
      "cycle_number": 1,
      "difficulty_level": "BEGINNER",
      "prompt_title": "My Daily Routine",
      "prompt_text": "Write about your daily routine...",
      "prompt_type": "ESSAY",
      "target_word_count": 150,
      "time_limit_minutes": 15,
      "focus_areas": ["grammar", "structure"],
      "writing_tips": ["Use time transition words"],
      "sample_outline": "Introduction - Morning - Afternoon - Conclusion",
      "learning_resources": [...]
    }
    ```
    
    **Returns:**
    - Created writing prompt
    
    **Use Cases:**
    1. Admin creates new writing prompts
    2. Bulk import prompts
    3. Update existing prompts
    
    **Error Handling:**
    - 400: Prompt already exists
    - 401: Unauthorized (not admin)
    - 403: Forbidden (not admin role)
    """
    # Check if user is admin
    if current_user.role != Role.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    admin_service = AdminService(db)
    prompt = admin_service.create_writing_prompt(
        day_number=day_number,
        cycle_number=cycle_number,
        difficulty_level=difficulty_level,
        prompt_title=prompt_title,
        prompt_text=prompt_text,
        prompt_type=prompt_type,
        target_word_count=target_word_count,
        time_limit_minutes=time_limit_minutes,
        focus_areas=focus_areas,
        writing_tips=writing_tips,
        sample_outline=sample_outline,
        learning_resources=learning_resources
    )
    
    return {
        "id": prompt.id,
        "day_number": prompt.day_number,
        "cycle_number": prompt.cycle_number,
        "difficulty_level": prompt.difficulty_level,
        "prompt_title": prompt.prompt_title,
        "prompt_text": prompt.prompt_text,
        "prompt_type": prompt.prompt_type,
        "target_word_count": prompt.target_word_count,
        "time_limit_minutes": prompt.time_limit_minutes,
        "focus_areas": prompt.focus_areas,
        "writing_tips": prompt.writing_tips,
        "sample_outline": prompt.sample_outline,
        "learning_resources": prompt.learning_resources
    }
