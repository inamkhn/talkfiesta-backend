"""
Writing Module Endpoints
Handles writing practice and submissions
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.session import get_db
from app.core.security import get_current_user
from app.services.writing_service import WritingService
from app.schemas.writing import (
    WritingPromptResponse,
    WritingSubmissionResponse,
    PromptType
)

router = APIRouter()

# ============================================
# ENDPOINT 1: GET WRITING PROMPTS
# ============================================

@router.get("/prompts", response_model=List[WritingPromptResponse])
async def get_writing_prompts(
    day_number: Optional[int] = Query(None, ge=1, le=21, description="Filter by day (1-21)"),
    cycle_number: Optional[int] = Query(None, ge=1, le=5, description="Filter by cycle (1-5)"),
    difficulty_level: Optional[str] = Query(None, description="Filter by difficulty (BEGINNER, INTERMEDIATE, ADVANCED)"),
    prompt_type: Optional[PromptType] = Query(None, description="Filter by prompt type (ESSAY, EMAIL, STORY, OPINION, DESCRIPTION)"),
    limit: int = Query(20, ge=1, le=100, description="Maximum records to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get writing prompts with optional filters
    
    Returns list of writing prompts. Can be filtered by day, cycle, difficulty, or prompt type.
    
    **Query Parameters:**
    - **day_number** (optional): Filter by day (1-21)
    - **cycle_number** (optional): Filter by cycle (1-5)
    - **difficulty_level** (optional): BEGINNER, INTERMEDIATE, or ADVANCED
    - **prompt_type** (optional): ESSAY, EMAIL, STORY, OPINION, or DESCRIPTION
    - **limit** (optional): Max records (default 20, max 100)
    - **offset** (optional): Pagination offset (default 0)
    
    **Returns:**
    - Array of writing prompts
    
    **Example Response:**
    ```json
    [
      {
        "id": "uuid",
        "day_number": 1,
        "cycle_number": 1,
        "difficulty_level": "BEGINNER",
        "prompt_title": "My Daily Routine",
        "prompt_text": "Write about your daily routine. Describe what you do from morning to night.",
        "prompt_type": "ESSAY",
        "target_word_count": 150,
        "time_limit_minutes": 15,
        "focus_areas": ["grammar", "vocabulary", "coherence"],
        "writing_tips": ["Use time transition words", "Be specific about activities"],
        "sample_outline": "Introduction - Morning - Afternoon - Evening - Conclusion",
        "learning_resources": [
          {
            "type": "video",
            "title": "Describing daily routines in English",
            "url": "https://example.com/video",
            "duration": 300
          }
        ]
      }
    ]
    ```
    
    **Use Cases:**
    1. Get all prompts for current cycle
    2. Filter by difficulty level
    3. Browse by prompt type
    4. Get prompt for specific day
    
    **Frontend Usage:**
    ```javascript
    // Get prompts for cycle 1
    const response = await fetch(
      '/api/v1/writing/prompts?cycle_number=1&limit=20',
      {
        headers: {
          'Authorization': `Bearer ${accessToken}`
        }
      }
    );
    const prompts = await response.json();
    
    // Get prompt for specific day
    const response = await fetch(
      '/api/v1/writing/prompts?day_number=5&cycle_number=1',
      {
        headers: {
          'Authorization': `Bearer ${accessToken}`
        }
      }
    );
    const prompt = await response.json();
    ```
    """
    writing_service = WritingService(db)
    prompts = writing_service.get_writing_prompts(
        day_number=day_number,
        cycle_number=cycle_number,
        difficulty_level=difficulty_level,
        prompt_type=prompt_type,
        limit=limit,
        offset=offset
    )
    
    return prompts


# ============================================
# ENDPOINT 2: GET WRITING PROMPT BY ID
# ============================================

@router.get("/prompts/{prompt_id}", response_model=WritingPromptResponse)
async def get_writing_prompt(
    prompt_id: str,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get specific writing prompt by ID
    
    Returns detailed information about a specific writing prompt.
    
    **Path Parameters:**
    - **prompt_id**: Prompt UUID
    
    **Returns:**
    - Single writing prompt object with all details
    
    **Example Response:**
    ```json
    {
      "id": "uuid",
      "day_number": 1,
      "cycle_number": 1,
      "difficulty_level": "BEGINNER",
      "prompt_title": "My Daily Routine",
      "prompt_text": "Write about your daily routine. Describe what you do from morning to night.",
      "prompt_type": "ESSAY",
      "target_word_count": 150,
      "time_limit_minutes": 15,
      "focus_areas": ["grammar", "vocabulary", "coherence"],
      "writing_tips": ["Use time transition words", "Be specific about activities"],
      "sample_outline": "Introduction - Morning - Afternoon - Evening - Conclusion",
      "learning_resources": [...]
    }
    ```
    
    **Frontend Usage:**
    ```javascript
    // Load prompt details before writing
    async function loadPromptDetails(promptId) {
      const response = await fetch(
        `/api/v1/writing/prompts/${promptId}`,
        {
          headers: {
            'Authorization': `Bearer ${accessToken}`
          }
        }
      );
      const prompt = await response.json();
      
      return (
        <PromptPage>
          <PromptHeader 
            title={prompt.prompt_title}
            type={prompt.prompt_type}
            difficulty={prompt.difficulty_level}
            targetWords={prompt.target_word_count}
          />
          
          <PromptContent>
            <h2>Your Task</h2>
            <p>{prompt.prompt_text}</p>
          </PromptContent>
          
          <TipsSection tips={prompt.writing_tips} />
          
          {prompt.sample_outline && (
            <OutlineSection outline={prompt.sample_outline} />
          )}
          
          <LearningResources resources={prompt.learning_resources} />
          
          <WritingEditor 
            targetWords={prompt.target_word_count}
            onSubmit={(content) => submitWriting(promptId, content)}
          />
        </PromptPage>
      );
    }
    ```
    """
    writing_service = WritingService(db)
    prompt = writing_service.get_writing_prompt_by_id(prompt_id)
    
    return prompt


# ============================================
# ENDPOINT 3: SUBMIT WRITING
# ============================================

@router.post("/submissions", response_model=WritingSubmissionResponse, status_code=201)
async def submit_writing(
    prompt_id: str,
    daily_activity_id: str,
    content: str,
    time_spent_seconds: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submit writing practice
    
    **CRITICAL ENDPOINT**: This is where users submit their writing practice.
    
    Handles:
    - Writing content submission
    - AI analysis (grammar, structure, vocabulary, coherence)
    - Scoring
    - Feedback generation
    - Progress tracking
    - Activity completion
    
    **Request Body:**
    ```json
    {
      "prompt_id": "uuid",
      "daily_activity_id": "uuid",
      "content": "My daily routine starts at 7am...",
      "time_spent_seconds": 900
    }
    ```
    
    **Returns:**
    - Complete submission with AI analysis
    
    **Example Response:**
    ```json
    {
      "id": "uuid",
      "content": "My daily routine starts at 7am...",
      "word_count": 250,
      "time_spent_seconds": 900,
      "grammar_score": 85.0,
      "structure_score": 80.0,
      "vocabulary_score": 82.0,
      "coherence_score": 88.0,
      "overall_score": 83.75,
      "grammar_errors": [...],
      "vocabulary_suggestions": [...],
      "structure_feedback": "Good structure with clear introduction and conclusion.",
      "ai_feedback": {
        "strengths": ["Clear organization", "Good vocabulary"],
        "improvements": ["Add more specific examples"],
        "tips": ["Read your work aloud"]
      },
      "revision_count": 0,
      "submitted_at": "2024-01-05T10:30:00Z",
      "last_edited_at": "2024-01-05T10:30:00Z"
    }
    ```
    
    **Frontend Usage:**
    ```javascript
    async function submitWriting(promptId, content, timeSpent) {
      const response = await fetch('/api/v1/writing/submissions', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          prompt_id: promptId,
          daily_activity_id: activityId,
          content: content,
          time_spent_seconds: timeSpent
        })
      });
      
      const result = await response.json();
      
      // Show results
      showResults({
        score: result.overall_score,
        feedback: result.ai_feedback,
        errors: result.grammar_errors
      });
    }
    ```
    
    **Business Logic:**
    1. Validates content (min 10 words)
    2. Calculates word count
    3. Calls AI service for analysis (mock implementation)
    4. Calculates scores (grammar, structure, vocabulary, coherence)
    5. Generates personalized feedback
    6. Updates daily activity (marks as completed)
    7. Updates plan progress
    8. Updates daily progress tracking
    9. Unlocks next day if applicable
    
    **AI Analysis Includes:**
    - Grammar score (0-100)
    - Structure score (0-100)
    - Vocabulary score (0-100)
    - Coherence score (0-100)
    - Overall score (average of all scores)
    - Grammar errors with suggestions
    - Vocabulary suggestions
    - Structure feedback
    - Personalized feedback (strengths, improvements, tips)
    
    **Progress Updates:**
    - Daily activity marked as COMPLETED
    - Activity score updated (if better than previous)
    - Next day unlocked
    - Plan completion percentage updated
    - Daily progress record created/updated
    - User's total practice time updated
    
    **Error Handling:**
    - 400: Content too short (< 10 words)
    - 403: Activity doesn't belong to user
    - 404: Prompt or activity not found
    
    **Performance:**
    - Async content processing
    - Background AI processing (can be made async)
    - Efficient database updates
    
    **TODO for Production:**
    - Integrate real AI service (OpenAI GPT, Grammarly API)
    - Add content moderation
    - Add plagiarism detection
    - Add async processing with webhooks
    """
    writing_service = WritingService(db)
    submission = writing_service.submit_writing(
        user_id=current_user.id,
        prompt_id=prompt_id,
        daily_activity_id=daily_activity_id,
        content=content,
        time_spent_seconds=time_spent_seconds
    )
    
    return submission


# ============================================
# ENDPOINT 4: UPDATE WRITING SUBMISSION (REVISION)
# ============================================

@router.patch("/submissions/{submission_id}", response_model=WritingSubmissionResponse)
async def update_writing_submission(
    submission_id: str,
    content: str,
    time_spent_seconds: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update writing submission (revision)
    
    Allows users to revise their writing after initial submission.
    Updates scores and tracks revision count.
    
    **Path Parameters:**
    - **submission_id**: Submission UUID
    
    **Request Body:**
    ```json
    {
      "content": "Revised content with improvements...",
      "time_spent_seconds": 300
    }
    ```
    
    **Returns:**
    - Updated submission with new scores
    
    **Example Response:**
    ```json
    {
      "id": "uuid",
      "content": "Revised content...",
      "word_count": 260,
      "time_spent_seconds": 1200,
      "grammar_score": 87.0,
      "structure_score": 82.0,
      "vocabulary_score": 84.0,
      "coherence_score": 89.0,
      "overall_score": 85.5,
      "grammar_errors": [...],
      "vocabulary_suggestions": [...],
      "structure_feedback": "Improved structure.",
      "ai_feedback": {...},
      "revision_count": 1,
      "submitted_at": "2024-01-05T10:30:00Z",
      "last_edited_at": "2024-01-05T11:00:00Z"
    }
    ```
    
    **Frontend Usage:**
    ```javascript
    async function reviseWriting(submissionId, content, timeSpent) {
      const response = await fetch(
        `/api/v1/writing/submissions/${submissionId}`,
        {
          method: 'PATCH',
          headers: {
            'Authorization': `Bearer ${accessToken}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            content: content,
            time_spent_seconds: timeSpent
          })
        }
      );
      
      const result = await response.json();
      
      // Update UI with new scores
      updateScores(result);
    }
    ```
    
    **Business Logic:**
    - Only allows revisions of user's own submissions
    - Updates content and word count
    - Adds time spent to total
    - Increments revision count
    - Recalculates scores (slight improvement)
    - Updates last_edited_at timestamp
    
    **Error Handling:**
    - 404: Submission not found or unauthorized
    - 403: Not the submission owner
    """
    writing_service = WritingService(db)
    submission = writing_service.update_writing_submission(
        user_id=current_user.id,
        submission_id=submission_id,
        content=content,
        time_spent_seconds=time_spent_seconds
    )
    
    return submission


# ============================================
# ENDPOINT 5: GET SUBMISSIONS
# ============================================

@router.get("/submissions", response_model=List[WritingSubmissionResponse])
async def get_writing_submissions(
    prompt_id: Optional[str] = Query(None, description="Filter by prompt ID"),
    limit: int = Query(20, ge=1, le=100, description="Maximum records to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get user's writing submission history
    
    Returns list of all writing submissions with scores and feedback.
    Used for progress tracking and reviewing past attempts.
    
    **Query Parameters:**
    - **prompt_id** (optional): Filter by specific prompt
    - **limit** (optional): Max records (default 20, max 100)
    - **offset** (optional): Pagination offset (default 0)
    
    **Returns:**
    - Array of submissions (most recent first)
    
    **Example Response:**
    ```json
    [
      {
        "id": "uuid",
        "content": "My daily routine...",
        "word_count": 250,
        "time_spent_seconds": 900,
        "grammar_score": 85.0,
        "structure_score": 80.0,
        "vocabulary_score": 82.0,
        "coherence_score": 88.0,
        "overall_score": 83.75,
        "grammar_errors": [...],
        "vocabulary_suggestions": [...],
        "structure_feedback": "Good structure...",
        "ai_feedback": {...},
        "revision_count": 0,
        "submitted_at": "2024-01-05T10:30:00Z",
        "last_edited_at": "2024-01-05T10:30:00Z"
      }
    ]
    ```
    
    **Frontend Usage:**
    ```javascript
    // Get all submissions
    const response = await fetch('/api/v1/writing/submissions', {
      headers: {
        'Authorization': `Bearer ${accessToken}`
      }
    });
    const submissions = await response.json();
    
    // Filter by prompt
    const response = await fetch(
      `/api/v1/writing/submissions?prompt_id=${promptId}`,
      {
        headers: {
          'Authorization': `Bearer ${accessToken}`
        }
      }
    );
    const promptSubmissions = await response.json();
    
    // Pagination
    const response = await fetch(
      `/api/v1/writing/submissions?limit=20&offset=20`,
      {
        headers: {
          'Authorization': `Bearer ${accessToken}`
        }
      }
    );
    const page2 = await response.json();
    ```
    
    **Use Cases:**
    1. Show submission history page
    2. Track progress over time
    3. Review past attempts for specific prompt
    4. Calculate statistics and trends
    5. Compare current vs previous attempts
    
    **Business Logic:**
    - Submissions ordered by most recent first
    - Only returns user's own submissions (authorization)
    - Pagination for large datasets
    - Can filter by specific prompt
    - Includes complete AI analysis for each submission
    
    **Performance:**
    - Indexed by user_id and submitted_at
    - Limit prevents large responses
    - Offset enables pagination
    - Efficient query with filters
    """
    writing_service = WritingService(db)
    submissions = writing_service.get_submissions(
        user_id=current_user.id,
        prompt_id=prompt_id,
        limit=limit,
        offset=offset
    )
    
    return submissions


# ============================================
# ENDPOINT 6: GET SUBMISSION BY ID
# ============================================

@router.get("/submissions/{submission_id}", response_model=WritingSubmissionResponse)
async def get_writing_submission(
    submission_id: str,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get specific writing submission by ID
    
    Returns detailed information about a specific submission including
    AI analysis, scores, and feedback.
    
    **Path Parameters:**
    - **submission_id**: Submission UUID
    
    **Returns:**
    - Single submission object with all details
    
    **Example Response:**
    ```json
    {
      "id": "uuid",
      "content": "My daily routine...",
      "word_count": 250,
      "time_spent_seconds": 900,
      "grammar_score": 85.0,
      "structure_score": 80.0,
      "vocabulary_score": 82.0,
      "coherence_score": 88.0,
      "overall_score": 83.75,
      "grammar_errors": [...],
      "vocabulary_suggestions": [...],
      "structure_feedback": "Good structure...",
      "ai_feedback": {
        "strengths": ["Clear organization", "Good vocabulary"],
        "improvements": ["Add more specific examples"],
        "tips": ["Read your work aloud"]
      },
      "revision_count": 0,
      "submitted_at": "2024-01-05T10:30:00Z",
      "last_edited_at": "2024-01-05T10:30:00Z"
    }
    ```
    
    **Frontend Usage:**
    ```javascript
    // Load submission details for review
    async function loadSubmissionDetails(submissionId) {
      const response = await fetch(
        `/api/v1/writing/submissions/${submissionId}`,
        {
          headers: {
            'Authorization': `Bearer ${accessToken}`
          }
        }
      );
      const submission = await response.json();
      
      return (
        <SubmissionDetails>
          <ScoreCard score={submission.overall_score} />
          
          <ContentDisplay content={submission.content} />
          
          <ScoresGrid
            grammar={submission.grammar_score}
            structure={submission.structure_score}
            vocabulary={submission.vocabulary_score}
            coherence={submission.coherence_score}
          />
          
          <FeedbackSection feedback={submission.ai_feedback} />
          
          <ErrorsList errors={submission.grammar_errors} />
          
          <VocabularySuggestions suggestions={submission.vocabulary_suggestions} />
          
          <RevisionInfo count={submission.revision_count} />
        </SubmissionDetails>
      );
    }
    ```
    
    **Use Cases:**
    1. Show submission details page
    2. Review past attempts with full AI analysis
    3. Compare current vs previous scores
    4. View detailed feedback and suggestions
    
    **Business Logic:**
    - Only returns user's own submissions (authorization)
    - Includes complete AI analysis
    - All scores and feedback included
    
    **Error Handling:**
    - 404: Submission not found or unauthorized
    - 401: Unauthorized (no token)
    
    **Performance:**
    - Single query by primary key
    - No joins needed (submission is self-contained)
    """
    writing_service = WritingService(db)
    submission = writing_service.get_submission_by_id(
        user_id=current_user.id,
        submission_id=submission_id
    )
    
    return submission


# ============================================
# ENDPOINT 7: GET WRITING ANALYTICS
# ============================================

@router.get("/analytics", response_model=dict)
async def get_writing_analytics(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get writing analytics and statistics
    
    Returns comprehensive analytics about user's writing practice
    including scores, trends, and progress metrics.
    
    **Returns:**
    - Total submissions count
    - Average scores (overall, grammar, structure, vocabulary, coherence)
    - Score trends over time
    - Prompt completion statistics
    - Time spent practicing
    - Performance breakdown by difficulty
    
    **Example Response:**
    ```json
    {
      "total_submissions": 10,
      "total_time_minutes": 150,
      "average_overall_score": 82.5,
      "average_grammar_score": 80.0,
      "average_structure_score": 78.0,
      "average_vocabulary_score": 81.0,
      "average_coherence_score": 85.0,
      "score_trend": [
        {"date": "2024-01-01", "score": 75.0},
        {"date": "2024-01-02", "score": 78.0},
        {"date": "2024-01-03", "score": 82.0}
      ],
      "word_count_trend": [
        {"date": "2024-01-01", "word_count": 200},
        {"date": "2024-01-02", "word_count": 250}
      ],
      "prompt_completion": {
        "total_prompts": 5,
        "completed_prompts": 3,
        "completion_rate": 60.0
      },
      "difficulty_breakdown": {
        "BEGINNER": {
          "attempts": 5,
          "average_score": 85.0
        },
        "INTERMEDIATE": {
          "attempts": 3,
          "average_score": 80.0
        }
      }
    }
    ```
    
    **Frontend Usage:**
    ```javascript
    function WritingAnalytics() {
      const [analytics, setAnalytics] = useState(null);
      
      useEffect(() => {
        async function loadAnalytics() {
          const response = await fetch('/api/v1/writing/analytics', {
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
          <h2>Writing Analytics</h2>
          
          <div className="summary-cards">
            <SummaryCard 
              title="Total Submissions" 
              value={analytics.total_submissions} 
            />
            <SummaryCard 
              title="Average Score" 
              value={analytics.average_overall_score} 
            />
            <SummaryCard 
              title="Time Practiced" 
              value={`${analytics.total_time_minutes} min`} 
            />
          </div>
          
          <ScoreTrendChart data={analytics.score_trend} />
          
          <WordCountTrend data={analytics.word_count_trend} />
          
          <DifficultyBreakdown data={analytics.difficulty_breakdown} />
        </div>
      );
    }
    ```
    
    **Use Cases:**
    1. **Analytics Page**: Show comprehensive writing statistics
    2. **Progress Tracking**: Monitor improvement over time
    3. **Performance Review**: Identify strengths and weaknesses
    4. **Motivation**: Show improvement metrics
    5. **Goal Setting**: Track progress toward targets
    
    **Business Logic:**
    - Only returns user's own analytics
    - Calculates averages across all submissions
    - Tracks score trends over time
    - Breaks down performance by difficulty
    - Tracks word count trends
    
    **Performance:**
    - Aggregates data from user's submissions
    - Efficient database queries with grouping
    - Caching recommended for production
    
    **Data Insights:**
    - Overall improvement trends
    - Weak areas (low scores)
    - Difficulty progression
    - Writing pace (word count)
    """
    writing_service = WritingService(db)
    analytics = writing_service.get_analytics(user_id=current_user.id)
    
    return analytics
