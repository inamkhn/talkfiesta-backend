"""
Writing Service
Handles business logic for writing practice
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_, desc
from fastapi import HTTPException, status
from typing import List, Optional
from datetime import datetime
import uuid
import json

from app.models.writing import WritingPrompt, WritingSubmission, PromptType
from app.models.plan import DailyActivity, ActivityStatus
from app.services.plan_service import PlanService
from app.services.progress_service import ProgressService


class WritingService:
    """Service for managing writing practice"""
    
    def __init__(self, db: Session):
        self.db = db
    
    # ============================================
    # GET WRITING PROMPTS
    # ============================================
    
    def get_writing_prompts(
        self,
        day_number: Optional[int] = None,
        cycle_number: Optional[int] = None,
        difficulty_level: Optional[str] = None,
        prompt_type: Optional[PromptType] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[WritingPrompt]:
        """
        Get writing prompts with optional filters
        
        Args:
            day_number: Filter by day (1-21)
            cycle_number: Filter by cycle (1-5)
            difficulty_level: Filter by difficulty
            prompt_type: Filter by prompt type
            limit: Maximum records to return
            offset: Pagination offset
            
        Returns:
            List of WritingPrompt objects
        """
        query = self.db.query(WritingPrompt)
        
        # Apply filters
        if day_number is not None:
            query = query.filter(WritingPrompt.day_number == day_number)
        
        if cycle_number is not None:
            query = query.filter(WritingPrompt.cycle_number == cycle_number)
        
        if difficulty_level is not None:
            query = query.filter(WritingPrompt.difficulty_level == difficulty_level)
        
        if prompt_type is not None:
            query = query.filter(WritingPrompt.prompt_type == prompt_type)
        
        # Order by cycle and day
        prompts = query.order_by(
            WritingPrompt.cycle_number,
            WritingPrompt.day_number
        ).limit(limit).offset(offset).all()
        
        # Parse JSON fields
        for prompt in prompts:
            if isinstance(prompt.focus_areas, str):
                prompt.focus_areas = json.loads(prompt.focus_areas)
            if isinstance(prompt.writing_tips, str):
                prompt.writing_tips = json.loads(prompt.writing_tips)
            if isinstance(prompt.learning_resources, str):
                prompt.learning_resources = json.loads(prompt.learning_resources)
        
        return prompts
    
    # ============================================
    # GET WRITING PROMPT BY ID
    # ============================================
    
    def get_writing_prompt_by_id(self, prompt_id: str) -> WritingPrompt:
        """
        Get specific writing prompt by ID
        
        Args:
            prompt_id: Prompt ID
            
        Returns:
            WritingPrompt object
            
        Raises:
            HTTPException: If prompt not found
        """
        prompt = self.db.query(WritingPrompt).filter(
            WritingPrompt.id == prompt_id
        ).first()
        
        if not prompt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Writing prompt not found"
            )
        
        # Parse JSON fields
        if isinstance(prompt.focus_areas, str):
            prompt.focus_areas = json.loads(prompt.focus_areas)
        if isinstance(prompt.writing_tips, str):
            prompt.writing_tips = json.loads(prompt.writing_tips)
        if isinstance(prompt.learning_resources, str):
            prompt.learning_resources = json.loads(prompt.learning_resources)
        
        return prompt
    
    # ============================================
    # GET WRITING PROMPT FOR DAY
    # ============================================
    
    def get_writing_prompt_for_day(
        self,
        day_number: int,
        cycle_number: int
    ) -> Optional[WritingPrompt]:
        """
        Get writing prompt for specific day and cycle
        
        Args:
            day_number: Day number (1-21)
            cycle_number: Cycle number (1-5)
            
        Returns:
            WritingPrompt object or None
        """
        prompt = self.db.query(WritingPrompt).filter(
            and_(
                WritingPrompt.day_number == day_number,
                WritingPrompt.cycle_number == cycle_number
            )
        ).first()
        
        return prompt
    
    # ============================================
    # SUBMIT WRITING
    # ============================================
    
    def submit_writing(
        self,
        user_id: str,
        prompt_id: str,
        daily_activity_id: str,
        content: str,
        time_spent_seconds: int
    ) -> WritingSubmission:
        """
        Submit writing practice
        
        Args:
            user_id: User ID
            prompt_id: Prompt ID
            daily_activity_id: Daily activity ID
            content: User's writing content
            time_spent_seconds: Time spent in seconds
            
        Returns:
            WritingSubmission object with AI analysis
            
        Raises:
            HTTPException: If prompt not found or validation fails
        """
        # Verify prompt exists
        prompt = self.get_writing_prompt_by_id(prompt_id)
        
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
        
        # Calculate word count
        word_count = len(content.split())
        
        # TODO: Call AI service for writing analysis
        # For now, create mock AI analysis
        mock_grammar_score = 85.0
        mock_structure_score = 80.0
        mock_vocabulary_score = 82.0
        mock_coherence_score = 88.0
        mock_overall_score = (mock_grammar_score + mock_structure_score + 
                             mock_vocabulary_score + mock_coherence_score) / 4
        
        # Create submission with mock AI analysis
        submission = WritingSubmission(
            user_id=user_id,
            prompt_id=prompt_id,
            daily_activity_id=daily_activity_id,
            content=content,
            word_count=word_count,
            time_spent_seconds=time_spent_seconds,
            grammar_score=mock_grammar_score,
            structure_score=mock_structure_score,
            vocabulary_score=mock_vocabulary_score,
            coherence_score=mock_coherence_score,
            overall_score=mock_overall_score,
            grammar_errors=[
                {
                    "type": "minor_grammar",
                    "position": 150,
                    "suggestion": "Consider using a comma here for better readability"
                }
            ],
            vocabulary_suggestions=[
                {
                    "word": "good",
                    "alternatives": ["excellent", "outstanding", "superb"]
                }
            ],
            structure_feedback="Good structure with clear introduction and conclusion.",
            ai_feedback={
                "strengths": [
                    "Clear organization",
                    "Good vocabulary usage",
                    "Strong conclusion"
                ],
                "improvements": [
                    "Add more specific examples",
                    "Vary sentence structure"
                ],
                "tips": [
                    "Read your work aloud to catch errors",
                    "Use transition words between paragraphs"
                ]
            },
            revision_count=0
        )
        
        self.db.add(submission)
        self.db.flush()
        
        # Update daily activity
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
            activity_type="WRITING",
            time_spent_minutes=time_spent_seconds // 60,
            score=submission.overall_score
        )
        
        self.db.refresh(submission)
        return submission
    
    # ============================================
    # UPDATE WRITING SUBMISSION (REVISION)
    # ============================================
    
    def update_writing_submission(
        self,
        user_id: str,
        submission_id: str,
        content: str,
        time_spent_seconds: int
    ) -> WritingSubmission:
        """
        Update writing submission (revision)
        
        Args:
            user_id: User ID
            submission_id: Submission ID
            content: Updated content
            time_spent_seconds: Additional time spent
            
        Returns:
            Updated WritingSubmission object
            
        Raises:
            HTTPException: If submission not found or unauthorized
        """
        submission = self.db.query(WritingSubmission).filter(
            and_(
                WritingSubmission.id == submission_id,
                WritingSubmission.user_id == user_id
            )
        ).first()
        
        if not submission:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Writing submission not found"
            )
        
        # Update content
        submission.content = content
        submission.word_count = len(content.split())
        submission.time_spent_seconds += time_spent_seconds
        submission.revision_count += 1
        submission.last_edited_at = datetime.utcnow()
        
        # Recalculate scores (mock)
        submission.grammar_score = min(100, submission.grammar_score + 2)
        submission.overall_score = (
            submission.grammar_score + submission.structure_score +
            submission.vocabulary_score + submission.coherence_score
        ) / 4
        
        self.db.commit()
        self.db.refresh(submission)
        return submission
    
    # ============================================
    # GET SUBMISSIONS
    # ============================================
    
    def get_submissions(
        self,
        user_id: str,
        prompt_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[WritingSubmission]:
        """
        Get user's writing submissions
        
        Args:
            user_id: User ID
            prompt_id: Optional filter by prompt
            limit: Maximum records to return
            offset: Pagination offset
            
        Returns:
            List of WritingSubmission objects
        """
        query = self.db.query(WritingSubmission).filter(
            WritingSubmission.user_id == user_id
        )
        
        if prompt_id:
            query = query.filter(WritingSubmission.prompt_id == prompt_id)
        
        # Order by most recent first
        submissions = query.order_by(
            desc(WritingSubmission.submitted_at)
        ).limit(limit).offset(offset).all()
        
        return submissions
    
    # ============================================
    # GET SUBMISSION BY ID
    # ============================================
    
    def get_submission_by_id(
        self,
        user_id: str,
        submission_id: str
    ) -> WritingSubmission:
        """
        Get specific submission by ID
        
        Args:
            user_id: User ID (for authorization)
            submission_id: Submission ID
            
        Returns:
            WritingSubmission object
            
        Raises:
            HTTPException: If submission not found or unauthorized
        """
        submission = self.db.query(WritingSubmission).filter(
            and_(
                WritingSubmission.id == submission_id,
                WritingSubmission.user_id == user_id
            )
        ).first()
        
        if not submission:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Submission not found"
            )
        
        return submission
    
    # ============================================
    # GET WRITING ANALYTICS
    # ============================================
    
    def get_analytics(self, user_id: str) -> dict:
        """
        Get writing analytics and statistics
        
        Args:
            user_id: User ID
            
        Returns:
            Analytics dictionary with scores, trends, and metrics
        """
        # Get all user's submissions
        submissions = self.db.query(WritingSubmission).filter(
            WritingSubmission.user_id == user_id
        ).order_by(WritingSubmission.submitted_at).all()
        
        if not submissions:
            return {
                "total_submissions": 0,
                "total_time_minutes": 0,
                "average_overall_score": 0,
                "average_grammar_score": 0,
                "average_structure_score": 0,
                "average_vocabulary_score": 0,
                "average_coherence_score": 0,
                "score_trend": [],
                "prompt_completion": {
                    "total_prompts": 0,
                    "completed_prompts": 0,
                    "completion_rate": 0
                },
                "difficulty_breakdown": {},
                "word_count_trend": []
            }
        
        # Calculate averages
        total_submissions = len(submissions)
        total_time_minutes = sum(s.time_spent_seconds for s in submissions) // 60
        
        avg_overall = sum(s.overall_score for s in submissions) / total_submissions
        avg_grammar = sum(s.grammar_score for s in submissions) / total_submissions
        avg_structure = sum(s.structure_score for s in submissions) / total_submissions
        avg_vocabulary = sum(s.vocabulary_score for s in submissions) / total_submissions
        avg_coherence = sum(s.coherence_score for s in submissions) / total_submissions
        
        # Score trend (last 10 submissions)
        recent_submissions = submissions[-10:]
        score_trend = [
            {
                "date": s.submitted_at.strftime("%Y-%m-%d"),
                "score": s.overall_score
            }
            for s in recent_submissions
        ]
        
        # Word count trend
        word_count_trend = [
            {
                "date": s.submitted_at.strftime("%Y-%m-%d"),
                "word_count": s.word_count
            }
            for s in recent_submissions
        ]
        
        # Prompt completion
        prompts = self.db.query(WritingPrompt).all()
        total_prompts = len(prompts)
        completed_prompts = len(set(s.prompt_id for s in submissions))
        completion_rate = (completed_prompts / total_prompts * 100) if total_prompts > 0 else 0
        
        # Difficulty breakdown
        difficulty_breakdown = {}
        for difficulty in ["BEGINNER", "INTERMEDIATE", "ADVANCED"]:
            difficulty_submissions = [s for s in submissions if s.prompt.difficulty_level == difficulty]
            if difficulty_submissions:
                difficulty_breakdown[difficulty] = {
                    "attempts": len(difficulty_submissions),
                    "average_score": sum(s.overall_score for s in difficulty_submissions) / len(difficulty_submissions)
                }
        
        return {
            "total_submissions": total_submissions,
            "total_time_minutes": total_time_minutes,
            "average_overall_score": round(avg_overall, 1),
            "average_grammar_score": round(avg_grammar, 1),
            "average_structure_score": round(avg_structure, 1),
            "average_vocabulary_score": round(avg_vocabulary, 1),
            "average_coherence_score": round(avg_coherence, 1),
            "score_trend": score_trend,
            "word_count_trend": word_count_trend,
            "prompt_completion": {
                "total_prompts": total_prompts,
                "completed_prompts": completed_prompts,
                "completion_rate": round(completion_rate, 1)
            },
            "difficulty_breakdown": difficulty_breakdown
        }
