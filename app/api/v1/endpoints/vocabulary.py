"""
Vocabulary Module Endpoints
Handles vocabulary learning and practice
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.session import get_db
from app.core.security import get_current_user
from app.services.vocabulary_service import VocabularyService
from app.schemas.vocabulary import (
    VocabularyWordResponse,
    UserVocabularyResponse,
    VocabularyPracticeResponse,
    ExerciseType
)

router = APIRouter()

# ============================================
# ENDPOINT 1: GET VOCABULARY WORDS
# ============================================

@router.get("/words", response_model=List[VocabularyWordResponse])
async def get_vocabulary_words(
    cycle_number: Optional[int] = Query(None, ge=1, le=5, description="Filter by cycle (1-5)"),
    difficulty_level: Optional[str] = Query(None, description="Filter by difficulty (BEGINNER, INTERMEDIATE, ADVANCED)"),
    category: Optional[str] = Query(None, description="Filter by category (business, academic, daily, etc.)"),
    limit: int = Query(20, ge=1, le=100, description="Maximum records to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get vocabulary words with optional filters
    
    Returns list of vocabulary words. Can be filtered by cycle, difficulty, or category.
    
    **Query Parameters:**
    - **cycle_number** (optional): Filter by cycle (1-5)
    - **difficulty_level** (optional): BEGINNER, INTERMEDIATE, or ADVANCED
    - **category** (optional): business, academic, daily, etc.
    - **limit** (optional): Max records (default 20, max 100)
    - **offset** (optional): Pagination offset (default 0)
    
    **Returns:**
    - Array of vocabulary words
    
    **Example Response:**
    ```json
    [
      {
        "id": "uuid",
        "word": "ambitious",
        "definition": "having a strong desire to succeed or achieve something",
        "part_of_speech": "ADJECTIVE",
        "difficulty_level": "INTERMEDIATE",
        "cefr_level": "B1",
        "cycle_number": 1,
        "pronunciation_ipa": "/æmˈbɪʃ.əs/",
        "pronunciation_audio_url": "https://...",
        "example_sentences": [
          {
            "sentence": "She is ambitious to become a CEO.",
            "translation": "Ella es ambiciosa de convertirse en CEO."
          }
        ],
        "synonyms": ["driven", "determined", "aspiring"],
        "antonyms": ["complacent", "satisfied"],
        "usage_tips": "Often used to describe career goals or personal ambitions",
        "category": "academic"
      }
    ]
    ```
    
    **Use Cases:**
    1. Get all vocabulary words for current cycle
    2. Filter by difficulty level
    3. Browse by category
    4. Paginate through large vocabulary lists
    
    **Frontend Usage:**
    ```javascript
    // Get vocabulary words for cycle 1
    const response = await fetch(
      '/api/v1/vocabulary/words?cycle_number=1&limit=20',
      {
        headers: {
          'Authorization': `Bearer ${accessToken}`
        }
      }
    );
    const words = await response.json();
    
    // Filter by difficulty
    const response = await fetch(
      '/api/v1/vocabulary/words?difficulty_level=BEGINNER',
      {
        headers: {
          'Authorization': `Bearer ${accessToken}`
        }
      }
    );
    ```
    """
    vocabulary_service = VocabularyService(db)
    words = vocabulary_service.get_vocabulary_words(
        cycle_number=cycle_number,
        difficulty_level=difficulty_level,
        category=category,
        limit=limit,
        offset=offset
    )
    
    return words


# ============================================
# ENDPOINT 2: GET VOCABULARY WORD BY ID
# ============================================

@router.get("/words/{word_id}", response_model=VocabularyWordResponse)
async def get_vocabulary_word(
    word_id: str,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get specific vocabulary word by ID
    
    Returns detailed information about a specific vocabulary word.
    
    **Path Parameters:**
    - **word_id**: Word UUID
    
    **Returns:**
    - Single vocabulary word object with all details
    
    **Example Response:**
    ```json
    {
      "id": "uuid",
      "word": "resilient",
      "definition": "able to withstand or recover quickly from difficult conditions",
      "part_of_speech": "ADJECTIVE",
      "difficulty_level": "INTERMEDIATE",
      "cefr_level": "B2",
      "cycle_number": 2,
      "pronunciation_ipa": "/rɪˈzɪl.jənt/",
      "pronunciation_audio_url": "https://...",
      "example_sentences": [
        {
          "sentence": "He was resilient in the face of adversity.",
          "translation": "Él fue resiliente frente a la adversidad."
        }
      ],
      "synonyms": ["tough", "strong", "sturdy"],
      "antonyms": ["fragile", "vulnerable"],
      "usage_tips": "Commonly used to describe people or systems",
      "category": "daily"
    }
    ```
    
    **Frontend Usage:**
    ```javascript
    // Load vocabulary word details
    async function loadWordDetails(wordId) {
      const response = await fetch(
        `/api/v1/vocabulary/words/${wordId}`,
        {
          headers: {
            'Authorization': `Bearer ${accessToken}`
          }
        }
      );
      const word = await response.json();
      
      return (
        <WordDetail>
          <WordHeader word={word.word} pos={word.part_of_speech} />
          <Definition definition={word.definition} />
          <Pronunciation ipa={word.pronunciation_ipa} audioUrl={word.pronunciation_audio_url} />
          <ExampleSentences sentences={word.example_sentences} />
          <WordRelations synonyms={word.synonyms} antonyms={word.antonyms} />
          <UsageTips tips={word.usage_tips} />
        </WordDetail>
      );
    }
    ```
    """
    vocabulary_service = VocabularyService(db)
    word = vocabulary_service.get_vocabulary_word_by_id(word_id)
    
    return word


# ============================================
# ENDPOINT 3: GET USER VOCABULARY PROGRESS
# ============================================

@router.get("/progress", response_model=List[UserVocabularyResponse])
async def get_user_vocabulary_progress(
    cycle_number: Optional[int] = Query(None, ge=1, le=5, description="Filter by cycle (1-5)"),
    status: Optional[str] = Query(None, description="Filter by status (NEW, LEARNING, REVIEWING, MASTERED)"),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get user's vocabulary learning progress
    
    Returns list of user's vocabulary words with their progress status.
    
    **Query Parameters:**
    - **cycle_number** (optional): Filter by cycle (1-5)
    - **status** (optional): NEW, LEARNING, REVIEWING, or MASTERED
    
    **Returns:**
    - Array of user vocabulary progress objects
    
    **Example Response:**
    ```json
    [
      {
        "id": "uuid",
        "word": {
          "id": "uuid",
          "word": "ambitious",
          "definition": "having a strong desire to succeed...",
          "part_of_speech": "ADJECTIVE",
          "difficulty_level": "INTERMEDIATE",
          "cefr_level": "B1",
          "cycle_number": 1,
          "pronunciation_ipa": "/æmˈbɪʃ.əs/",
          "example_sentences": [...],
          "synonyms": [...],
          "antonyms": [...]
        },
        "day_number": 1,
        "status": "LEARNING",
        "mastery_level": 2,
        "times_reviewed": 3,
        "times_practiced": 5,
        "last_reviewed_at": "2024-01-05T10:30:00Z",
        "next_review_at": "2024-01-06T10:30:00Z",
        "learned_at": "2024-01-01T00:00:00Z",
        "mastered_at": null
      }
    ]
    ```
    
    **Use Cases:**
    1. Show user's vocabulary progress dashboard
    2. Filter by status to see words to review
    3. Track mastery progression
    4. Identify words needing more practice
    
    **Frontend Usage:**
    ```javascript
    // Get all vocabulary progress
    const response = await fetch('/api/v1/vocabulary/progress', {
      headers: {
        'Authorization': `Bearer ${accessToken}`
      }
    });
    const progress = await response.json();
    
    // Filter by status to review
    const response = await fetch(
      '/api/v1/vocabulary/progress?status=LEARNING',
      {
        headers: {
          'Authorization': `Bearer ${accessToken}`
        }
      }
    );
    const toReview = await response.json();
    ```
    """
    vocabulary_service = VocabularyService(db)
    progress = vocabulary_service.get_user_vocabulary_progress(
        user_id=current_user.id,
        cycle_number=cycle_number,
        status_filter=status
    )
    
    return progress


# ============================================
# ENDPOINT 4: SUBMIT VOCABULARY PRACTICE
# ============================================

@router.post("/practice", response_model=VocabularyPracticeResponse)
async def submit_vocabulary_practice(
    user_vocabulary_id: str,
    daily_activity_id: str,
    exercise_type: ExerciseType,
    user_answer: str,
    correct_answer: str,
    is_correct: bool,
    time_taken_seconds: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submit vocabulary practice session
    
    **CRITICAL ENDPOINT**: This is where users submit their vocabulary practice.
    
    Handles:
    - Practice session recording
    - Mastery level updates
    - Status progression (NEW → LEARNING → REVIEWING → MASTERED)
    - Spaced repetition scheduling
    - Progress tracking
    
    **Request Body:**
    ```json
    {
      "user_vocabulary_id": "uuid",
      "daily_activity_id": "uuid",
      "exercise_type": "FILL_BLANK",
      "user_answer": "ambitious",
      "correct_answer": "ambitious",
      "is_correct": true,
      "time_taken_seconds": 15
    }
    ```
    
    **Exercise Types:**
    - **FILL_BLANK**: Fill in the blank exercise
    - **MATCHING**: Match words with definitions
    - **USAGE**: Choose correct usage
    - **PRONUNCIATION**: Pronunciation practice
    
    **Returns:**
    - Practice session with updated mastery level
    
    **Example Response:**
    ```json
    {
      "id": "uuid",
      "is_correct": true,
      "feedback": "Great job! You're mastering this word.",
      "updated_mastery_level": 3,
      "next_review_at": "2024-01-08T10:30:00Z"
    }
    ```
    
    **Mastery Progression:**
    - **Level 0 (NEW)**: Just started
    - **Level 1 (LEARNING)**: First correct answer
    - **Level 2 (LEARNING)**: Second correct answer
    - **Level 3 (REVIEWING)**: Third correct answer
    - **Level 4 (REVIEWING)**: Fourth correct answer
    - **Level 5 (MASTERED)**: Fifth correct answer
    
    **Spaced Repetition Schedule:**
    - Level 0: Review in 1 hour
    - Level 1: Review in 6 hours
    - Level 2: Review in 24 hours
    - Level 3: Review in 3 days
    - Level 4: Review in 7 days
    - Level 5: Review in 30 days
    
    **Frontend Usage:**
    ```javascript
    async function submitPractice(wordId, isCorrect, timeTaken) {
      const response = await fetch('/api/v1/vocabulary/practice', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          user_vocabulary_id: wordId,
          daily_activity_id: activityId,
          exercise_type: 'FILL_BLANK',
          user_answer: userAnswer,
          correct_answer: correctAnswer,
          is_correct: isCorrect,
          time_taken_seconds: timeTaken
        })
      });
      
      const result = await response.json();
      
      // Update UI with new mastery level
      updateMasteryLevel(result.updated_mastery_level);
      
      // Schedule next review
      scheduleReview(result.next_review_at);
    }
    ```
    """
    vocabulary_service = VocabularyService(db)
    practice = vocabulary_service.submit_vocabulary_practice(
        user_id=current_user.id,
        user_vocabulary_id=user_vocabulary_id,
        daily_activity_id=daily_activity_id,
        exercise_type=exercise_type,
        user_answer=user_answer,
        correct_answer=correct_answer,
        is_correct=is_correct,
        time_taken_seconds=time_taken_seconds
    )
    
    # Generate feedback based on correctness
    feedback = "Great job!" if practice.is_correct == "true" else "Keep practicing!"
    
    return VocabularyPracticeResponse(
        id=practice.id,
        is_correct=practice.is_correct == "true",
        feedback=feedback,
        updated_mastery_level=practice.user_vocabulary.mastery_level,
        next_review_at=practice.user_vocabulary.next_review_at
    )


# ============================================
# ENDPOINT 5: GET PRACTICE SESSIONS
# ============================================

@router.get("/practice", response_model=List[VocabularyPracticeResponse])
async def get_vocabulary_practice_sessions(
    word_id: Optional[str] = Query(None, description="Filter by word ID"),
    limit: int = Query(20, ge=1, le=100, description="Maximum records to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get user's vocabulary practice history
    
    Returns list of all vocabulary practice sessions with scores and feedback.
    Used for progress tracking and reviewing past attempts.
    
    **Query Parameters:**
    - **word_id** (optional): Filter by specific word
    - **limit** (optional): Max records (default 20, max 100)
    - **offset** (optional): Pagination offset (default 0)
    
    **Returns:**
    - Array of practice sessions (most recent first)
    
    **Example Response:**
    ```json
    [
      {
        "id": "uuid",
        "is_correct": true,
        "feedback": "Great job!",
        "updated_mastery_level": 3,
        "next_review_at": "2024-01-08T10:30:00Z"
      }
    ]
    ```
    
    **Frontend Usage:**
    ```javascript
    // Get all practice sessions
    const response = await fetch('/api/v1/vocabulary/practice', {
      headers: {
        'Authorization': `Bearer ${accessToken}`
      }
    });
    const sessions = await response.json();
    
    // Filter by word
    const response = await fetch(
      `/api/v1/vocabulary/practice?word_id=${wordId}`,
      {
        headers: {
          'Authorization': `Bearer ${accessToken}`
        }
      }
    );
    const wordSessions = await response.json();
    ```
    """
    vocabulary_service = VocabularyService(db)
    sessions = vocabulary_service.get_practice_sessions(
        user_id=current_user.id,
        word_id=word_id,
        limit=limit,
        offset=offset
    )
    
    # Map to response format
    return [
        VocabularyPracticeResponse(
            id=session.id,
            is_correct=session.is_correct == "true",
            feedback="Correct" if session.is_correct == "true" else "Incorrect",
            updated_mastery_level=session.user_vocabulary.mastery_level,
            next_review_at=session.user_vocabulary.next_review_at
        )
        for session in sessions
    ]


# ============================================
# ENDPOINT 6: GET VOCABULARY ANALYTICS
# ============================================

@router.get("/analytics", response_model=dict)
async def get_vocabulary_analytics(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get vocabulary analytics and statistics
    
    Returns comprehensive analytics about user's vocabulary learning
    including progress, mastery, and trends.
    
    **Returns:**
    - Total words count
    - Words by status (NEW, LEARNING, REVIEWING, MASTERED)
    - Average mastery level
    - Total practice sessions
    - Accuracy rate
    - Words mastered and to review
    - Mastery trend
    - Category breakdown
    
    **Example Response:**
    ```json
    {
      "total_words": 50,
      "words_by_status": {
        "NEW": 20,
        "LEARNING": 15,
        "REVIEWING": 10,
        "MASTERED": 5
      },
      "average_mastery_level": 2.5,
      "total_practice_sessions": 150,
      "accuracy_rate": 85.0,
      "words_mastered": 5,
      "words_to_review": 25,
      "mastery_trend": [
        {
          "word": "ambitious",
          "mastery_level": 3,
          "updated_at": "2024-01-05"
        }
      ],
      "category_breakdown": {
        "academic": {
          "total_words": 20,
          "mastered_words": 3,
          "average_mastery": 2.8
        },
        "business": {
          "total_words": 15,
          "mastered_words": 1,
          "average_mastery": 1.5
        },
        "daily": {
          "total_words": 15,
          "mastered_words": 1,
          "average_mastery": 2.2
        }
      }
    }
    ```
    
    **Use Cases:**
    1. **Analytics Page**: Show comprehensive vocabulary statistics
    2. **Progress Tracking**: Monitor mastery progression
    3. **Review Planning**: Identify words needing review
    4. **Category Focus**: Track progress by category
    5. **Goal Setting**: Track progress toward mastery goals
    
    **Frontend Usage:**
    ```javascript
    function VocabularyAnalytics() {
      const [analytics, setAnalytics] = useState(null);
      
      useEffect(() => {
        async function loadAnalytics() {
          const response = await fetch('/api/v1/vocabulary/analytics', {
            headers: {
              'Authorization': `Bearer ${accessToken}`
            }
          });
          const data = await response.json();
          setAnalytics(data);
        }
        
        loadAnalytics();
      }, []);
      
      if (!analytics) return <LoadingSpinner />;
      
      return (
        <div className="analytics">
          <h2>Vocabulary Analytics</h2>
          
          <div className="summary-cards">
            <SummaryCard 
              title="Total Words" 
              value={analytics.total_words} 
            />
            <SummaryCard 
              title="Mastered" 
              value={analytics.words_mastered} 
            />
            <SummaryCard 
              title="Avg Mastery" 
              value={analytics.average_mastery_level} 
            />
            <SummaryCard 
              title="Accuracy" 
              value={`${analytics.accuracy_rate}%`} 
            />
          </div>
          
          <StatusDistribution data={analytics.words_by_status} />
          
          <CategoryBreakdown data={analytics.category_breakdown} />
          
          <MasteryTrendChart data={analytics.mastery_trend} />
        </div>
      );
    }
    ```
    """
    vocabulary_service = VocabularyService(db)
    analytics = vocabulary_service.get_analytics(user_id=current_user.id)
    
    return analytics
