"""
Speaking Module Endpoints
Handles speaking exercises and submissions
"""

from fastapi import APIRouter, Depends, Query, Form, File, UploadFile, status
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.session import get_db
from app.core.security import get_current_user
from app.services.speaking_service import SpeakingService
from app.schemas.speaking import (
    SpeakingExerciseResponse,
    SpeakingSubmissionResponse,
    DifficultyLevel
)

router = APIRouter()

# ============================================
# ENDPOINT 1: GET SPEAKING EXERCISES
# ============================================

@router.get("/exercises", response_model=List[SpeakingExerciseResponse])
async def get_speaking_exercises(
    day_number: Optional[int] = Query(None, ge=1, le=21, description="Filter by day (1-21)"),
    cycle_number: Optional[int] = Query(None, ge=1, le=5, description="Filter by cycle (1-5)"),
    difficulty_level: Optional[DifficultyLevel] = Query(None, description="Filter by difficulty"),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all speaking exercises with optional filters
    
    Returns list of speaking exercises. Can be filtered by day, cycle, or difficulty.
    
    **Query Parameters:**
    - **day_number** (optional): Filter by day (1-21)
    - **cycle_number** (optional): Filter by cycle (1-5)
    - **difficulty_level** (optional): BEGINNER, INTERMEDIATE, or ADVANCED
    
    **Returns:**
    - Array of speaking exercises
    
    **Example Response:**
    ```json
    [
      {
        "id": "uuid",
        "day_number": 1,
        "cycle_number": 1,
        "difficulty_level": "BEGINNER",
        "topic": "Self Introduction",
        "prompt_text": "Introduce yourself. Talk about your name, where you're from, and what you do.",
        "target_duration_seconds": 60,
        "instructions": "Speak clearly and naturally. Try to speak for at least 60 seconds without long pauses.",
        "example_response": "Hello, my name is John...",
        "focus_areas": ["grammar", "fluency", "pronunciation"],
        "learning_resources": [
          {
            "type": "video",
            "title": "How to introduce yourself in English",
            "url": "https://example.com/video",
            "duration": 300
          }
        ]
      }
    ]
    ```
    
    **Use Cases:**
    
    1. **Get all exercises** (for admin/content review):
    ```
    GET /speaking/exercises
    ```
    
    2. **Get exercises for specific day** (when user clicks on Day 5):
    ```
    GET /speaking/exercises?day_number=5
    ```
    
    3. **Get exercises for specific cycle** (show all Cycle 1 exercises):
    ```
    GET /speaking/exercises?cycle_number=1
    ```
    
    4. **Get exercises by difficulty** (filter by level):
    ```
    GET /speaking/exercises?difficulty_level=BEGINNER
    ```
    
    5. **Combine filters** (Day 5 of Cycle 1):
    ```
    GET /speaking/exercises?day_number=5&cycle_number=1
    ```
    
    **Frontend Usage - Exercise Selection:**
    ```javascript
    // User clicks on "Day 5" in Speaking plan
    async function loadExerciseForDay(day) {
      const response = await fetch(
        `/api/v1/speaking/exercises?day_number=${day}&cycle_number=1`,
        {
          headers: {
            'Authorization': `Bearer ${accessToken}`
          }
        }
      );
      const exercises = await response.json();
      
      if (exercises.length > 0) {
        const exercise = exercises[0];
        showExercise({
          topic: exercise.topic,
          prompt: exercise.prompt_text,
          duration: exercise.target_duration_seconds,
          instructions: exercise.instructions,
          resources: exercise.learning_resources
        });
      }
    }
    ```
    
    **Frontend Usage - Exercise List:**
    ```javascript
    // Show all exercises for current cycle
    async function loadCycleExercises(cycle) {
      const response = await fetch(
        `/api/v1/speaking/exercises?cycle_number=${cycle}`,
        {
          headers: {
            'Authorization': `Bearer ${accessToken}`
          }
        }
      );
      const exercises = await response.json();
      
      return exercises.map(ex => ({
        day: ex.day_number,
        topic: ex.topic,
        difficulty: ex.difficulty_level,
        duration: ex.target_duration_seconds
      }));
    }
    ```
    
    **Business Logic:**
    - Exercises are pre-created by admin
    - One exercise per day per cycle (21 days × 5 cycles = 105 exercises)
    - Difficulty increases across cycles
    - Focus areas guide the AI feedback
    - Learning resources help users prepare
    
    **Data Structure:**
    - **focus_areas**: Array of strings (e.g., ["grammar", "fluency"])
    - **learning_resources**: Array of objects with type, title, url, duration
    - **example_response**: Optional example to guide users
    
    **Performance:**
    - Indexed by day_number and cycle_number
    - Efficient filtering with query parameters
    - Ordered by cycle and day for consistent display
    """
    speaking_service = SpeakingService(db)
    exercises = speaking_service.get_exercises(
        day_number=day_number,
        cycle_number=cycle_number,
        difficulty_level=difficulty_level
    )
    
    return exercises


# ============================================
# ENDPOINT 2: GET EXERCISE BY ID
# ============================================

@router.get("/exercises/{exercise_id}", response_model=SpeakingExerciseResponse)
async def get_speaking_exercise(
    exercise_id: str,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get specific speaking exercise by ID
    
    Returns detailed information about a specific exercise.
    Used when user starts an exercise or reviews exercise details.
    
    **Path Parameters:**
    - **exercise_id**: Exercise UUID
    
    **Returns:**
    - Single exercise object with all details
    
    **Example Response:**
    ```json
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "day_number": 1,
      "cycle_number": 1,
      "difficulty_level": "BEGINNER",
      "topic": "Self Introduction",
      "prompt_text": "Introduce yourself. Talk about your name, where you're from, what you do, and your hobbies. Try to speak naturally and confidently.",
      "target_duration_seconds": 60,
      "instructions": "Speak clearly and naturally. Try to speak for at least 60 seconds. Don't worry about making mistakes - focus on expressing yourself!",
      "example_response": "Hello, my name is John Smith. I'm from New York, and I work as a software engineer. In my free time, I enjoy reading books and playing basketball.",
      "focus_areas": ["grammar", "fluency", "pronunciation"],
      "learning_resources": [
        {
          "type": "video",
          "title": "How to introduce yourself in English",
          "url": "https://example.com/intro-video",
          "duration": 300
        },
        {
          "type": "article",
          "title": "Common phrases for introductions",
          "url": "https://example.com/intro-phrases",
          "duration": 180
        }
      ]
    }
    ```
    
    **Frontend Usage - Exercise Page:**
    ```javascript
    // Load exercise details when user starts exercise
    async function startExercise(exerciseId) {
      const response = await fetch(
        `/api/v1/speaking/exercises/${exerciseId}`,
        {
          headers: {
            'Authorization': `Bearer ${accessToken}`
          }
        }
      );
      const exercise = await response.json();
      
      return (
        <ExercisePage>
          <ExerciseHeader 
            topic={exercise.topic}
            difficulty={exercise.difficulty_level}
            duration={exercise.target_duration_seconds}
          />
          
          <PromptSection>
            <h2>Your Task</h2>
            <p>{exercise.prompt_text}</p>
          </PromptSection>
          
          <InstructionsSection>
            <h3>Instructions</h3>
            <p>{exercise.instructions}</p>
          </InstructionsSection>
          
          {exercise.example_response && (
            <ExampleSection>
              <h3>Example Response</h3>
              <p>{exercise.example_response}</p>
            </ExampleSection>
          )}
          
          <FocusAreas areas={exercise.focus_areas} />
          
          <LearningResources resources={exercise.learning_resources} />
          
          <RecordingSection 
            targetDuration={exercise.target_duration_seconds}
            onSubmit={(audioBlob) => submitRecording(exerciseId, audioBlob)}
          />
        </ExercisePage>
      );
    }
    ```
    
    **Frontend Usage - Pre-Exercise Preparation:**
    ```javascript
    // Show learning resources before recording
    function PreparationScreen({ exerciseId }) {
      const [exercise, setExercise] = useState(null);
      
      useEffect(() => {
        async function loadExercise() {
          const response = await fetch(
            `/api/v1/speaking/exercises/${exerciseId}`,
            {
              headers: {
                'Authorization': `Bearer ${accessToken}`
              }
            }
          );
          const data = await response.json();
          setExercise(data);
        }
        
        loadExercise();
      }, [exerciseId]);
      
      if (!exercise) return <LoadingSpinner />;
      
      return (
        <div className="preparation">
          <h2>Prepare for: {exercise.topic}</h2>
          
          <div className="resources">
            <h3>Learning Resources</h3>
            {exercise.learning_resources.map((resource, index) => (
              <ResourceCard
                key={index}
                type={resource.type}
                title={resource.title}
                url={resource.url}
                duration={resource.duration}
              />
            ))}
          </div>
          
          <div className="tips">
            <h3>Focus On</h3>
            <ul>
              {exercise.focus_areas.map((area, index) => (
                <li key={index}>{area}</li>
              ))}
            </ul>
          </div>
          
          <button onClick={() => startRecording(exercise)}>
            Start Recording
          </button>
        </div>
      );
    }
    ```
    
    **Use Cases:**
    1. User clicks "Start Exercise" from plan
    2. Display exercise details before recording
    3. Show learning resources for preparation
    4. Provide example response as guidance
    5. Display focus areas for user awareness
    
    **Business Logic:**
    - Exercise ID comes from daily activity
    - Learning resources help users prepare
    - Example response is optional (not all exercises have it)
    - Focus areas determine what AI will evaluate
    - Target duration is a guideline, not enforced
    
    **Error Handling:**
    - 404: Exercise not found (invalid ID)
    - 401: Unauthorized (no token)
    
    **Performance:**
    - Single query by primary key (very fast)
    - No joins needed (exercise is self-contained)
    """
    speaking_service = SpeakingService(db)
    exercise = speaking_service.get_exercise_by_id(exercise_id)
    
    return exercise



# ============================================
# ENDPOINT 3: SUBMIT SPEAKING EXERCISE
# ============================================

@router.post("/submissions", response_model=SpeakingSubmissionResponse, status_code=status.HTTP_201_CREATED)
async def submit_speaking_exercise(
    exercise_id: str = Form(...),
    daily_activity_id: str = Form(...),
    audio_file: UploadFile = File(...),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submit audio recording for speaking exercise
    
    **CRITICAL ENDPOINT**: This is where users submit their speaking practice.
    
    Handles:
    - Audio file upload
    - AI transcription and analysis
    - Scoring (fluency, grammar, vocabulary, pronunciation)
    - Feedback generation
    - Progress tracking
    - Activity completion
    
    **Content-Type**: `multipart/form-data`
    
    **Form Data:**
    - **audio_file**: Audio file (webm, mp3, wav, m4a)
    - **exercise_id**: Exercise UUID
    - **daily_activity_id**: Daily activity UUID
    
    **File Requirements:**
    - Max size: 10MB
    - Formats: audio/webm, audio/mp3, audio/wav, audio/m4a
    - Recommended: webm (best browser support)
    
    **Returns:**
    - Complete submission with AI analysis
    
    **Example Response:**
    ```json
    {
      "id": "uuid",
      "audio_url": "https://storage.../audio.webm",
      "transcription": "Hello, my name is John...",
      "duration_seconds": 45,
      "word_count": 28,
      "words_per_minute": 37.3,
      "fluency_score": 82.0,
      "grammar_score": 75.0,
      "vocabulary_score": 80.0,
      "pronunciation_score": 85.0,
      "overall_score": 80.5,
      "pause_count": 3,
      "filler_words_count": 2,
      "filler_words_list": ["um", "uh"],
      "ai_feedback": {
        "strengths": [
          "Clear pronunciation",
          "Good pace"
        ],
        "improvements": [
          "Use more varied vocabulary"
        ],
        "tips": [
          "Practice transition words"
        ]
      },
      "grammar_corrections": [
        {
          "error": "I enjoys reading",
          "correction": "I enjoy reading",
          "explanation": "Subject-verb agreement"
        }
      ],
      "vocabulary_suggestions": [
        {
          "word": "good",
          "better_options": ["excellent", "outstanding"]
        }
      ],
      "submitted_at": "2024-01-05T10:30:00Z"
    }
    ```
    
    **Frontend Usage - Recording & Submission:**
    ```javascript
    // 1. Record audio
    const mediaRecorder = new MediaRecorder(stream);
    const audioChunks = [];
    
    mediaRecorder.ondataavailable = (event) => {
      audioChunks.push(event.data);
    };
    
    mediaRecorder.onstop = async () => {
      const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
      await submitRecording(audioBlob);
    };
    
    // 2. Submit recording
    async function submitRecording(audioBlob) {
      const formData = new FormData();
      formData.append('audio_file', audioBlob, 'recording.webm');
      formData.append('exercise_id', exerciseId);
      formData.append('daily_activity_id', activityId);
      
      const response = await fetch('/api/v1/speaking/submissions', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${accessToken}`
        },
        body: formData
      });
      
      const result = await response.json();
      
      // Show results
      showResults({
        score: result.overall_score,
        transcription: result.transcription,
        feedback: result.ai_feedback,
        corrections: result.grammar_corrections
      });
    }
    ```
    
    **Frontend Usage - Complete Recording Component:**
    ```javascript
    function RecordingInterface({ exerciseId, activityId }) {
      const [isRecording, setIsRecording] = useState(false);
      const [audioBlob, setAudioBlob] = useState(null);
      const [submitting, setSubmitting] = useState(false);
      const mediaRecorderRef = useRef(null);
      
      const startRecording = async () => {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const mediaRecorder = new MediaRecorder(stream);
        mediaRecorderRef.current = mediaRecorder;
        
        const chunks = [];
        mediaRecorder.ondataavailable = (e) => chunks.push(e.data);
        mediaRecorder.onstop = () => {
          const blob = new Blob(chunks, { type: 'audio/webm' });
          setAudioBlob(blob);
        };
        
        mediaRecorder.start();
        setIsRecording(true);
      };
      
      const stopRecording = () => {
        mediaRecorderRef.current?.stop();
        setIsRecording(false);
      };
      
      const submitRecording = async () => {
        if (!audioBlob) return;
        
        setSubmitting(true);
        
        const formData = new FormData();
        formData.append('audio_file', audioBlob, 'recording.webm');
        formData.append('exercise_id', exerciseId);
        formData.append('daily_activity_id', activityId);
        
        try {
          const response = await fetch('/api/v1/speaking/submissions', {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${accessToken}`
            },
            body: formData
          });
          
          const result = await response.json();
          navigate(`/speaking/results/${result.id}`);
        } catch (error) {
          console.error('Submission failed:', error);
        } finally {
          setSubmitting(false);
        }
      };
      
      return (
        <div className="recording-interface">
          {!isRecording && !audioBlob && (
            <button onClick={startRecording}>
              Start Recording
            </button>
          )}
          
          {isRecording && (
            <button onClick={stopRecording}>
              Stop Recording
            </button>
          )}
          
          {audioBlob && !submitting && (
            <>
              <audio src={URL.createObjectURL(audioBlob)} controls />
              <button onClick={submitRecording}>
                Submit
              </button>
              <button onClick={() => setAudioBlob(null)}>
                Re-record
              </button>
            </>
          )}
          
          {submitting && <LoadingSpinner text="Analyzing your speech..." />}
        </div>
      );
    }
    ```
    
    **Business Logic:**
    1. Validates audio file (type, size)
    2. Uploads to cloud storage
    3. Calls AI service for transcription
    4. Analyzes speech (fluency, grammar, vocabulary, pronunciation)
    5. Generates personalized feedback
    6. Updates daily activity (marks as completed)
    7. Updates plan progress
    8. Updates daily progress tracking
    9. Unlocks next day if applicable
    
    **AI Analysis Includes:**
    - Transcription (speech-to-text)
    - Duration and word count
    - Words per minute (speaking pace)
    - Fluency score (smoothness, pauses)
    - Grammar score (correctness)
    - Vocabulary score (word choice, variety)
    - Pronunciation score (clarity)
    - Overall score (weighted average)
    - Filler words detection (um, uh, like)
    - Grammar corrections with explanations
    - Vocabulary suggestions
    - Personalized feedback (strengths, improvements, tips)
    
    **Progress Updates:**
    - Daily activity marked as COMPLETED
    - Activity score updated (if better than previous)
    - Next day unlocked
    - Plan completion percentage updated
    - Daily progress record created/updated
    - User's total practice time updated
    
    **Error Handling:**
    - 400: Invalid file type or size
    - 403: Activity doesn't belong to user
    - 404: Exercise or activity not found
    - 413: File too large (>10MB)
    
    **Performance:**
    - Async file upload
    - Background AI processing (can be made async)
    - Efficient database updates
    
    **TODO for Production:**
    - Integrate real cloud storage (AWS S3, Google Cloud Storage)
    - Integrate real AI service (OpenAI Whisper, Google Speech-to-Text)
    - Add retry logic for AI failures
    - Add webhook for async processing
    - Add audio format conversion if needed
    """
    speaking_service = SpeakingService(db)
    submission = await speaking_service.submit_speaking_exercise(
        user_id=current_user.id,
        exercise_id=exercise_id,
        daily_activity_id=daily_activity_id,
        audio_file=audio_file
    )
    
    return submission


# ============================================
# ENDPOINT 4: GET SUBMISSION HISTORY
# ============================================

@router.get("/submissions", response_model=List[SpeakingSubmissionResponse])
async def get_speaking_submissions(
    exercise_id: Optional[str] = Query(None, description="Filter by exercise ID"),
    limit: int = Query(20, ge=1, le=100, description="Maximum records to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get user's speaking submission history
    
    Returns list of all speaking submissions with scores and feedback.
    Used for progress tracking, reviewing past attempts, and showing improvement over time.
    
    **Query Parameters:**
    - **exercise_id** (optional): Filter by specific exercise
    - **limit** (optional): Max records (default 20, max 100)
    - **offset** (optional): Pagination offset (default 0)
    
    **Returns:**
    - Array of submissions (most recent first)
    
    **Example Response:**
    ```json
    [
      {
        "id": "uuid",
        "audio_url": "https://storage.../audio.webm",
        "transcription": "Hello, my name is John...",
        "duration_seconds": 45,
        "word_count": 28,
        "words_per_minute": 37.3,
        "fluency_score": 82.0,
        "grammar_score": 75.0,
        "vocabulary_score": 80.0,
        "pronunciation_score": 85.0,
        "overall_score": 80.5,
        "pause_count": 3,
        "filler_words_count": 2,
        "filler_words_list": ["um", "uh"],
        "ai_feedback": {...},
        "grammar_corrections": [...],
        "vocabulary_suggestions": [...],
        "submitted_at": "2024-01-05T10:30:00Z"
      }
    ]
    ```
    
    **Frontend Usage - Submission History:**
    ```javascript
    // Get all submissions
    async function loadSubmissionHistory() {
      const response = await fetch('/api/v1/speaking/submissions', {
        headers: {
          'Authorization': `Bearer ${accessToken}`
        }
      });
      const submissions = await response.json();
      
      return submissions.map(sub => ({
        id: sub.id,
        date: new Date(sub.submitted_at),
        score: sub.overall_score,
        duration: sub.duration_seconds,
        transcription: sub.transcription
      }));
    }
    ```
    
    **Frontend Usage - Exercise-Specific History:**
    ```javascript
    // Get submissions for specific exercise
    async function loadExerciseAttempts(exerciseId) {
      const response = await fetch(
        `/api/v1/speaking/submissions?exercise_id=${exerciseId}`,
        {
          headers: {
            'Authorization': `Bearer ${accessToken}`
          }
        }
      );
      const attempts = await response.json();
      
      // Show improvement over time
      const scores = attempts.map(a => a.overall_score);
      const improvement = scores[0] - scores[scores.length - 1];
      
      return {
        attempts: attempts.length,
        latestScore: scores[0],
        firstScore: scores[scores.length - 1],
        improvement: improvement
      };
    }
    ```
    
    **Frontend Usage - Progress Chart:**
    ```javascript
    function ProgressChart() {
      const [submissions, setSubmissions] = useState([]);
      
      useEffect(() => {
        async function loadData() {
          const response = await fetch('/api/v1/speaking/submissions?limit=50', {
            headers: {
              'Authorization': `Bearer ${accessToken}`
            }
          });
          const data = await response.json();
          setSubmissions(data.reverse()); // Oldest first for chart
        }
        
        loadData();
      }, []);
      
      const chartData = submissions.map(sub => ({
        date: new Date(sub.submitted_at).toLocaleDateString(),
        overall: sub.overall_score,
        fluency: sub.fluency_score,
        grammar: sub.grammar_score,
        vocabulary: sub.vocabulary_score,
        pronunciation: sub.pronunciation_score
      }));
      
      return <LineChart data={chartData} />;
    }
    ```
    
    **Frontend Usage - Pagination:**
    ```javascript
    function SubmissionList() {
      const [submissions, setSubmissions] = useState([]);
      const [page, setPage] = useState(0);
      const pageSize = 20;
      
      useEffect(() => {
        async function loadPage() {
          const response = await fetch(
            `/api/v1/speaking/submissions?limit=${pageSize}&offset=${page * pageSize}`,
            {
              headers: {
                'Authorization': `Bearer ${accessToken}`
              }
            }
          );
          const data = await response.json();
          setSubmissions(data);
        }
        
        loadPage();
      }, [page]);
      
      return (
        <div>
          {submissions.map(sub => (
            <SubmissionCard key={sub.id} submission={sub} />
          ))}
          <Pagination page={page} onPageChange={setPage} />
        </div>
      );
    }
    ```
    
    **Use Cases:**
    1. **History Page**: Show all past submissions
    2. **Progress Tracking**: Chart showing improvement over time
    3. **Exercise Review**: See all attempts for specific exercise
    4. **Statistics**: Calculate averages, trends, improvements
    5. **Replay**: Listen to past recordings
    6. **Compare**: Compare current vs previous attempts
    
    **Business Logic:**
    - Submissions ordered by most recent first
    - Only returns user's own submissions (authorization)
    - Pagination for large datasets
    - Can filter by specific exercise
    - Includes complete AI analysis for each submission
    
    **Performance:**
    - Indexed by user_id and submitted_at
    - Limit prevents large responses
    - Offset enables pagination
    - Efficient query with filters
    
    **Data Insights:**
    - Track improvement over time
    - Identify weak areas (low scores)
    - See progress in specific skills
    - Monitor speaking pace (WPM)
    - Track filler word reduction
    """
    speaking_service = SpeakingService(db)
    submissions = speaking_service.get_submissions(
        user_id=current_user.id,
        exercise_id=exercise_id,
        limit=limit,
        offset=offset
    )
    
    return submissions


# ============================================
# ENDPOINT 5: GET SUBMISSION BY ID
# ============================================

@router.get("/submissions/{submission_id}", response_model=SpeakingSubmissionResponse)
async def get_speaking_submission(
    submission_id: str,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get specific speaking submission by ID
    
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
      "audio_url": "https://storage.../audio.webm",
      "transcription": "Hello, my name is John...",
      "duration_seconds": 45,
      "word_count": 28,
      "words_per_minute": 37.3,
      "fluency_score": 82.0,
      "grammar_score": 75.0,
      "vocabulary_score": 80.0,
      "pronunciation_score": 85.0,
      "overall_score": 80.5,
      "pause_count": 3,
      "filler_words_count": 2,
      "filler_words_list": ["um", "uh"],
      "ai_feedback": {
        "strengths": ["Clear pronunciation", "Good pace"],
        "improvements": ["Use more varied vocabulary"],
        "tips": ["Practice transition words"]
      },
      "grammar_corrections": [...],
      "vocabulary_suggestions": [...],
      "submitted_at": "2024-01-05T10:30:00Z"
    }
    ```
    
    **Frontend Usage - Submission Details:**
    ```javascript
    // Load submission details for review
    async function loadSubmissionDetails(submissionId) {
      const response = await fetch(
        `/api/v1/speaking/submissions/${submissionId}`,
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
          
          <Transcription>
            <h3>Transcription</h3>
            <p>{submission.transcription}</p>
          </Transcription>
          
          <ScoresGrid
            fluency={submission.fluency_score}
            grammar={submission.grammar_score}
            vocabulary={submission.vocabulary_score}
            pronunciation={submission.pronunciation_score}
          />
          
          <FeedbackSection feedback={submission.ai_feedback} />
          
          <CorrectionsList corrections={submission.grammar_corrections} />
          
          <VocabularySuggestions suggestions={submission.vocabulary_suggestions} />
          
          <AudioPlayer src={submission.audio_url} />
        </SubmissionDetails>
      );
    }
    ```
    
    **Use Cases:**
    1. Show submission details page
    2. Review past attempts with full AI analysis
    3. Compare current vs previous scores
    4. Listen to past recordings
    5. View detailed feedback and suggestions
    
    **Business Logic:**
    - Only returns user's own submissions (authorization)
    - Includes complete AI analysis
    - Audio URL for playback
    - All scores and feedback included
    
    **Error Handling:**
    - 404: Submission not found or unauthorized
    - 401: Unauthorized (no token)
    
    **Performance:**
    - Single query by primary key
    - No joins needed (submission is self-contained)
    """
    speaking_service = SpeakingService(db)
    submission = speaking_service.get_submission_by_id(
        user_id=current_user.id,
        submission_id=submission_id
    )
    
    return submission


# ============================================
# ENDPOINT 6: GET SPEAKING ANALYTICS
# ============================================

@router.get("/analytics", response_model=dict)
async def get_speaking_analytics(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get speaking analytics and statistics
    
    Returns comprehensive analytics about user's speaking practice
    including trends, scores, and progress metrics.
    
    **Returns:**
    - Total submissions count
    - Average scores (overall, fluency, grammar, vocabulary, pronunciation)
    - Score trends over time
    - Exercise completion statistics
    - Time spent practicing
    - Performance breakdown by difficulty
    
    **Example Response:**
    ```json
    {
      "total_submissions": 15,
      "total_time_minutes": 45,
      "average_overall_score": 82.5,
      "average_fluency_score": 80.0,
      "average_grammar_score": 78.0,
      "average_vocabulary_score": 81.0,
      "average_pronunciation_score": 85.0,
      "score_trend": [
        {"date": "2024-01-01", "score": 75.0},
        {"date": "2024-01-02", "score": 78.0},
        {"date": "2024-01-03", "score": 82.0}
      ],
      "exercise_completion": {
        "total_exercises": 5,
        "completed_exercises": 3,
        "completion_rate": 60.0
      },
      "difficulty_breakdown": {
        "BEGINNER": {
          "attempts": 5,
          "average_score": 85.0
        },
        "INTERMEDIATE": {
          "attempts": 8,
          "average_score": 80.0
        },
        "ADVANCED": {
          "attempts": 2,
          "average_score": 75.0
        }
      },
      "filler_word_reduction": {
        "first_attempt": 5,
        "latest_attempt": 2,
        "improvement": 60.0
      },
      "fluency_improvement": {
        "first_attempt_wpm": 100,
        "latest_attempt_wpm": 120,
        "improvement": 20.0
      }
    }
    ```
    
    **Frontend Usage - Analytics Dashboard:**
    ```javascript
    function SpeakingAnalytics() {
      const [analytics, setAnalytics] = useState(null);
      
      useEffect(() => {
        async function loadAnalytics() {
          const response = await fetch('/api/v1/speaking/analytics', {
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
          <h2>Speaking Analytics</h2>
          
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
          
          <DifficultyBreakdown data={analytics.difficulty_breakdown} />
          
          <ImprovementMetrics 
            fillerWordReduction={analytics.filler_word_reduction}
            fluencyImprovement={analytics.fluency_improvement}
          />
        </div>
      );
    }
    ```
    
    **Use Cases:**
    1. **Analytics Page**: Show comprehensive speaking statistics
    2. **Progress Tracking**: Monitor improvement over time
    3. **Performance Review**: Identify strengths and weaknesses
    4. **Motivation**: Show improvement metrics
    5. **Goal Setting**: Track progress toward targets
    
    **Business Logic:**
    - Only returns user's own analytics
    - Calculates averages across all submissions
    - Tracks score trends over time
    - Breaks down performance by difficulty
    - Calculates improvement metrics
    
    **Performance:**
    - Aggregates data from user's submissions
    - Efficient database queries with grouping
    - Caching recommended for production
    
    **Data Insights:**
    - Overall improvement trends
    - Weak areas (low scores)
    - Difficulty progression
    - Filler word reduction
    - Speaking pace improvement
    """
    speaking_service = SpeakingService(db)
    analytics = speaking_service.get_analytics(user_id=current_user.id)
    
    return analytics
