"""
Speaking Service
Handles business logic for speaking exercises and submissions
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_, desc
from fastapi import HTTPException, status, UploadFile
from typing import List, Optional
from datetime import datetime
import uuid

from app.models.speaking import SpeakingExercise, SpeakingSubmission, DifficultyLevel
from app.models.plan import DailyActivity, ActivityStatus
from app.services.plan_service import PlanService
from app.services.progress_service import ProgressService


class SpeakingService:
    """Service for managing speaking exercises and submissions"""
    
    def __init__(self, db: Session):
        self.db = db
    
    # ============================================
    # GET SPEAKING EXERCISES
    # ============================================
    
    def get_exercises(
        self,
        day_number: Optional[int] = None,
        cycle_number: Optional[int] = None,
        difficulty_level: Optional[DifficultyLevel] = None
    ) -> List[SpeakingExercise]:
        """
        Get speaking exercises with optional filters
        
        Args:
            day_number: Filter by day (1-21)
            cycle_number: Filter by cycle (1-5)
            difficulty_level: Filter by difficulty
            
        Returns:
            List of SpeakingExercise objects
        """
        query = self.db.query(SpeakingExercise)
        
        # Apply filters
        if day_number is not None:
            query = query.filter(SpeakingExercise.day_number == day_number)
        
        if cycle_number is not None:
            query = query.filter(SpeakingExercise.cycle_number == cycle_number)
        
        if difficulty_level is not None:
            query = query.filter(SpeakingExercise.difficulty_level == difficulty_level)
        
        # Order by cycle and day
        exercises = query.order_by(
            SpeakingExercise.cycle_number,
            SpeakingExercise.day_number
        ).all()
        
        return exercises
    
    # ============================================
    # GET EXERCISE BY ID
    # ============================================
    
    def get_exercise_by_id(self, exercise_id: str) -> SpeakingExercise:
        """
        Get specific exercise by ID
        
        Args:
            exercise_id: Exercise ID
            
        Returns:
            SpeakingExercise object
            
        Raises:
            HTTPException: If exercise not found
        """
        exercise = self.db.query(SpeakingExercise).filter(
            SpeakingExercise.id == exercise_id
        ).first()
        
        if not exercise:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Speaking exercise not found"
            )
        
        return exercise
    
    # ============================================
    # GET EXERCISE FOR DAY AND CYCLE
    # ============================================
    
    def get_exercise_for_day(
        self, 
        day_number: int, 
        cycle_number: int
    ) -> Optional[SpeakingExercise]:
        """
        Get exercise for specific day and cycle
        
        Args:
            day_number: Day number (1-21)
            cycle_number: Cycle number (1-5)
            
        Returns:
            SpeakingExercise object or None
        """
        exercise = self.db.query(SpeakingExercise).filter(
            and_(
                SpeakingExercise.day_number == day_number,
                SpeakingExercise.cycle_number == cycle_number
            )
        ).first()
        
        return exercise

    
    # ============================================
    # SUBMIT SPEAKING EXERCISE
    # ============================================
    
    async def submit_speaking_exercise(
        self,
        user_id: str,
        exercise_id: str,
        daily_activity_id: str,
        audio_file: UploadFile
    ) -> SpeakingSubmission:
        """
        Submit speaking exercise with audio recording
        
        Args:
            user_id: User ID
            exercise_id: Exercise ID
            daily_activity_id: Daily activity ID
            audio_file: Audio file upload
            
        Returns:
            SpeakingSubmission object with AI analysis
            
        Raises:
            HTTPException: If exercise not found or validation fails
        """
        # Verify exercise exists
        exercise = self.get_exercise_by_id(exercise_id)
        
        # Verify daily activity exists and belongs to user
        activity = self.db.query(DailyActivity).filter(
            DailyActivity.id == daily_activity_id
        ).first()
        
        if not activity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Daily activity not found"
            )
        
        # Verify activity belongs to user's plan
        if activity.user_plan.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This activity does not belong to you"
            )
        
        # Validate file type
        if not audio_file.content_type.startswith('audio/'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be an audio file"
            )
        
        # Validate file size (10MB max)
        audio_file.file.seek(0, 2)
        file_size = audio_file.file.tell()
        audio_file.file.seek(0)
        
        if file_size > 10 * 1024 * 1024:  # 10MB
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Audio file must be less than 10MB"
            )
        
        # TODO: Upload audio to cloud storage
        # For now, create a mock URL
        audio_url = f"https://storage.example.com/audio/{uuid.uuid4()}.webm"
        
        # TODO: Call AI service for transcription and analysis
        # For now, create mock AI analysis
        mock_transcription = "Hello, my name is John. I'm from New York and I work as a software engineer. In my free time, I enjoy reading books and playing basketball."
        mock_duration = 45
        mock_word_count = len(mock_transcription.split())
        mock_wpm = (mock_word_count / mock_duration) * 60
        
        # Create submission with mock AI analysis
        submission = SpeakingSubmission(
            user_id=user_id,
            exercise_id=exercise_id,
            daily_activity_id=daily_activity_id,
            audio_url=audio_url,
            transcription=mock_transcription,
            duration_seconds=mock_duration,
            word_count=mock_word_count,
            words_per_minute=mock_wpm,
            fluency_score=82.0,
            grammar_score=75.0,
            vocabulary_score=80.0,
            pronunciation_score=85.0,
            overall_score=80.5,
            pause_count=3,
            filler_words_count=2,
            filler_words_list=["um", "uh"],
            ai_feedback={
                "strengths": [
                    "Clear pronunciation",
                    "Good pace and rhythm",
                    "Natural flow"
                ],
                "improvements": [
                    "Use more varied vocabulary",
                    "Reduce filler words",
                    "Add more details"
                ],
                "tips": [
                    "Practice transition words",
                    "Record yourself and listen back",
                    "Read the example response for ideas"
                ]
            },
            grammar_corrections=[
                {
                    "error": "I enjoys reading",
                    "correction": "I enjoy reading",
                    "explanation": "Subject-verb agreement: 'I' takes the base form of the verb"
                }
            ],
            vocabulary_suggestions=[
                {
                    "word": "good",
                    "better_options": ["excellent", "outstanding", "remarkable"]
                }
            ]
        )
        
        self.db.add(submission)
        self.db.flush()
        
        # Update daily activity
        time_spent_seconds = mock_duration
        activity.attempts_count += 1
        activity.time_spent_seconds += time_spent_seconds
        
        # Mark as completed if first attempt or better score
        if activity.status != ActivityStatus.COMPLETED or activity.score is None or submission.overall_score > activity.score:
            activity.status = ActivityStatus.COMPLETED
            activity.score = submission.overall_score
            activity.completed_at = datetime.utcnow()
        
        self.db.commit()
        
        # Update plan progress
        plan_service = PlanService(self.db)
        plan_service.update_plan_progress(activity.user_plan_id)
        
        # Update daily progress
        progress_service = ProgressService(self.db)
        progress_service.update_daily_progress(
            user_id=user_id,
            activity_type="SPEAKING",
            time_spent_minutes=time_spent_seconds // 60,
            score=submission.overall_score
        )
        
        self.db.refresh(submission)
        return submission
    
    # ============================================
    # GET SUBMISSION HISTORY
    # ============================================
    
    def get_submissions(
        self,
        user_id: str,
        exercise_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[SpeakingSubmission]:
        """
        Get user's speaking submission history
        
        Args:
            user_id: User ID
            exercise_id: Optional filter by exercise
            limit: Maximum records to return
            offset: Pagination offset
            
        Returns:
            List of SpeakingSubmission objects
        """
        query = self.db.query(SpeakingSubmission).filter(
            SpeakingSubmission.user_id == user_id
        )
        
        # Filter by exercise if provided
        if exercise_id:
            query = query.filter(SpeakingSubmission.exercise_id == exercise_id)
        
        # Order by most recent first
        submissions = query.order_by(
            desc(SpeakingSubmission.submitted_at)
        ).limit(limit).offset(offset).all()
        
        return submissions
    
    # ============================================
    # GET SUBMISSION BY ID
    # ============================================
    
    def get_submission_by_id(
        self,
        user_id: str,
        submission_id: str
    ) -> SpeakingSubmission:
        """
        Get specific submission by ID
        
        Args:
            user_id: User ID (for authorization)
            submission_id: Submission ID
            
        Returns:
            SpeakingSubmission object
            
        Raises:
            HTTPException: If submission not found or unauthorized
        """
        submission = self.db.query(SpeakingSubmission).filter(
            and_(
                SpeakingSubmission.id == submission_id,
                SpeakingSubmission.user_id == user_id
            )
        ).first()
        
        if not submission:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Submission not found"
            )
        
        return submission
    
    # ============================================
    # GET ANALYTICS
    # ============================================
    
    def get_analytics(self, user_id: str) -> dict:
        """
        Get speaking analytics and statistics
        
        Args:
            user_id: User ID
            
        Returns:
            Analytics dictionary with scores, trends, and metrics
        """
        # Get all user's submissions
        submissions = self.db.query(SpeakingSubmission).filter(
            SpeakingSubmission.user_id == user_id
        ).order_by(SpeakingSubmission.submitted_at).all()
        
        if not submissions:
            return {
                "total_submissions": 0,
                "total_time_minutes": 0,
                "average_overall_score": 0,
                "average_fluency_score": 0,
                "average_grammar_score": 0,
                "average_vocabulary_score": 0,
                "average_pronunciation_score": 0,
                "score_trend": [],
                "exercise_completion": {
                    "total_exercises": 0,
                    "completed_exercises": 0,
                    "completion_rate": 0
                },
                "difficulty_breakdown": {},
                "filler_word_reduction": {
                    "first_attempt": 0,
                    "latest_attempt": 0,
                    "improvement": 0
                },
                "fluency_improvement": {
                    "first_attempt_wpm": 0,
                    "latest_attempt_wpm": 0,
                    "improvement": 0
                }
            }
        
        # Calculate averages
        total_submissions = len(submissions)
        total_time_minutes = sum(s.duration_seconds for s in submissions) // 60
        
        avg_overall = sum(s.overall_score for s in submissions) / total_submissions
        avg_fluency = sum(s.fluency_score for s in submissions) / total_submissions
        avg_grammar = sum(s.grammar_score for s in submissions) / total_submissions
        avg_vocabulary = sum(s.vocabulary_score for s in submissions) / total_submissions
        avg_pronunciation = sum(s.pronunciation_score for s in submissions) / total_submissions
        
        # Score trend (last 10 submissions)
        recent_submissions = submissions[-10:]
        score_trend = [
            {
                "date": s.submitted_at.strftime("%Y-%m-%d"),
                "score": s.overall_score
            }
            for s in recent_submissions
        ]
        
        # Exercise completion
        exercises = self.db.query(SpeakingExercise).all()
        total_exercises = len(exercises)
        completed_exercises = len(set(s.exercise_id for s in submissions))
        completion_rate = (completed_exercises / total_exercises * 100) if total_exercises > 0 else 0
        
        # Difficulty breakdown
        difficulty_breakdown = {}
        for difficulty in ["BEGINNER", "INTERMEDIATE", "ADVANCED"]:
            difficulty_submissions = [s for s in submissions if s.exercise.difficulty_level == difficulty]
            if difficulty_submissions:
                difficulty_breakdown[difficulty] = {
                    "attempts": len(difficulty_submissions),
                    "average_score": sum(s.overall_score for s in difficulty_submissions) / len(difficulty_submissions)
                }
        
        # Filler word reduction
        first_attempt_fillers = submissions[0].filler_words_count
        latest_attempt_fillers = submissions[-1].filler_words_count
        filler_reduction = ((first_attempt_fillers - latest_attempt_fillers) / first_attempt_fillers * 100) if first_attempt_fillers > 0 else 0
        
        # Fluency improvement (WPM)
        first_attempt_wpm = submissions[0].words_per_minute
        latest_attempt_wpm = submissions[-1].words_per_minute
        wpm_improvement = ((latest_attempt_wpm - first_attempt_wpm) / first_attempt_wpm * 100) if first_attempt_wpm > 0 else 0
        
        return {
            "total_submissions": total_submissions,
            "total_time_minutes": total_time_minutes,
            "average_overall_score": round(avg_overall, 1),
            "average_fluency_score": round(avg_fluency, 1),
            "average_grammar_score": round(avg_grammar, 1),
            "average_vocabulary_score": round(avg_vocabulary, 1),
            "average_pronunciation_score": round(avg_pronunciation, 1),
            "score_trend": score_trend,
            "exercise_completion": {
                "total_exercises": total_exercises,
                "completed_exercises": completed_exercises,
                "completion_rate": round(completion_rate, 1)
            },
            "difficulty_breakdown": difficulty_breakdown,
            "filler_word_reduction": {
                "first_attempt": first_attempt_fillers,
                "latest_attempt": latest_attempt_fillers,
                "improvement": round(filler_reduction, 1)
            },
            "fluency_improvement": {
                "first_attempt_wpm": round(first_attempt_wpm, 1),
                "latest_attempt_wpm": round(latest_attempt_wpm, 1),
                "improvement": round(wpm_improvement, 1)
            }
        }
