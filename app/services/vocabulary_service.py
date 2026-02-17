"""
Vocabulary Service
Handles business logic for vocabulary learning
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, func
from fastapi import HTTPException, status
from typing import List, Optional
from datetime import datetime, timedelta
import uuid
import json

from app.models.vocabulary import (
    VocabularyWord, 
    UserVocabulary, 
    VocabularyPracticeSession,
    ExerciseType,
    VocabularyStatus
)
from app.models.plan import DailyActivity, ActivityStatus
from app.services.plan_service import PlanService
from app.services.progress_service import ProgressService


class VocabularyService:
    """Service for managing vocabulary learning"""
    
    def __init__(self, db: Session):
        self.db = db
    
    # ============================================
    # GET VOCABULARY WORDS
    # ============================================
    
    def get_vocabulary_words(
        self,
        cycle_number: Optional[int] = None,
        difficulty_level: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[VocabularyWord]:
        """
        Get vocabulary words with optional filters
        
        Args:
            cycle_number: Filter by cycle (1-5)
            difficulty_level: Filter by difficulty
            category: Filter by category
            limit: Maximum records to return
            offset: Pagination offset
            
        Returns:
            List of VocabularyWord objects
        """
        query = self.db.query(VocabularyWord)
        
        # Apply filters
        if cycle_number is not None:
            query = query.filter(VocabularyWord.cycle_number == cycle_number)
        
        if difficulty_level is not None:
            query = query.filter(VocabularyWord.difficulty_level == difficulty_level)
        
        if category is not None:
            query = query.filter(VocabularyWord.category == category)
        
        # Order by cycle and word
        words = query.order_by(
            VocabularyWord.cycle_number,
            VocabularyWord.word
        ).limit(limit).offset(offset).all()
        
        # Parse JSON fields
        for word in words:
            if isinstance(word.example_sentences, str):
                word.example_sentences = json.loads(word.example_sentences)
            if isinstance(word.synonyms, str):
                word.synonyms = json.loads(word.synonyms)
            if isinstance(word.antonyms, str):
                word.antonyms = json.loads(word.antonyms)
        
        return words
    
    # ============================================
    # GET VOCABULARY WORD BY ID
    # ============================================
    
    def get_vocabulary_word_by_id(self, word_id: str) -> VocabularyWord:
        """
        Get specific vocabulary word by ID
        
        Args:
            word_id: Word ID
            
        Returns:
            VocabularyWord object
            
        Raises:
            HTTPException: If word not found
        """
        word = self.db.query(VocabularyWord).filter(
            VocabularyWord.id == word_id
        ).first()
        
        if not word:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vocabulary word not found"
            )
        
        # Parse JSON fields
        if isinstance(word.example_sentences, str):
            word.example_sentences = json.loads(word.example_sentences)
        if isinstance(word.synonyms, str):
            word.synonyms = json.loads(word.synonyms)
        if isinstance(word.antonyms, str):
            word.antonyms = json.loads(word.antonyms)
        
        return word
    
    # ============================================
    # GET USER VOCABULARY PROGRESS
    # ============================================
    
    def get_user_vocabulary_progress(
        self,
        user_id: str,
        cycle_number: Optional[int] = None,
        status_filter: Optional[VocabularyStatus] = None
    ) -> List[UserVocabulary]:
        """
        Get user's vocabulary progress
        
        Args:
            user_id: User ID
            cycle_number: Filter by cycle
            status_filter: Filter by status
            
        Returns:
            List of UserVocabulary objects
        """
        query = self.db.query(UserVocabulary).filter(
            UserVocabulary.user_id == user_id
        )
        
        if cycle_number is not None:
            query = query.filter(UserVocabulary.word.has(
                VocabularyWord.cycle_number == cycle_number
            ))
        
        if status_filter is not None:
            query = query.filter(UserVocabulary.status == status_filter)
        
        progress = query.order_by(
            UserVocabulary.day_number
        ).all()
        
        # Parse JSON fields for each word
        for uv in progress:
            if isinstance(uv.word.example_sentences, str):
                uv.word.example_sentences = json.loads(uv.word.example_sentences)
            if isinstance(uv.word.synonyms, str):
                uv.word.synonyms = json.loads(uv.word.synonyms)
            if isinstance(uv.word.antonyms, str):
                uv.word.antonyms = json.loads(uv.word.antonyms)
        
        return progress
    
    # ============================================
    # GET VOCABULARY WORD FOR DAY
    # ============================================
    
    def get_vocabulary_word_for_day(
        self,
        user_id: str,
        day_number: int,
        cycle_number: int
    ) -> Optional[UserVocabulary]:
        """
        Get vocabulary word for specific day and cycle
        
        Args:
            user_id: User ID
            day_number: Day number (1-21)
            cycle_number: Cycle number (1-5)
            
        Returns:
            UserVocabulary object or None
        """
        user_vocabulary = self.db.query(UserVocabulary).filter(
            and_(
                UserVocabulary.user_id == user_id,
                UserVocabulary.day_number == day_number
            )
        ).first()
        
        if user_vocabulary:
            return user_vocabulary
        
        # If not found, create new vocabulary word for this day
        # Get a vocabulary word from the database for this cycle and day
        vocabulary_word = self.db.query(VocabularyWord).filter(
            and_(
                VocabularyWord.cycle_number == cycle_number
            )
        ).order_by(
            func.random()
        ).first()
        
        if not vocabulary_word:
            return None
        
        # Create user vocabulary entry
        user_vocabulary = UserVocabulary(
            user_id=user_id,
            word_id=vocabulary_word.id,
            day_number=day_number,
            status=VocabularyStatus.NEW,
            mastery_level=0,
            times_reviewed=0,
            times_practiced=0
        )
        
        self.db.add(user_vocabulary)
        self.db.commit()
        self.db.refresh(user_vocabulary)
        
        return user_vocabulary
    
    # ============================================
    # SUBMIT VOCABULARY PRACTICE
    # ============================================
    
    def submit_vocabulary_practice(
        self,
        user_id: str,
        user_vocabulary_id: str,
        daily_activity_id: str,
        exercise_type: ExerciseType,
        user_answer: str,
        correct_answer: str,
        is_correct: bool,
        time_taken_seconds: int
    ) -> VocabularyPracticeSession:
        """
        Submit vocabulary practice session
        
        Args:
            user_id: User ID
            user_vocabulary_id: User vocabulary ID
            daily_activity_id: Daily activity ID
            exercise_type: Type of exercise
            user_answer: User's answer
            correct_answer: Correct answer
            is_correct: Whether answer was correct
            time_taken_seconds: Time taken in seconds
            
        Returns:
            VocabularyPracticeSession object
        """
        # Verify user vocabulary exists and belongs to user
        user_vocabulary = self.db.query(UserVocabulary).filter(
            and_(
                UserVocabulary.id == user_vocabulary_id,
                UserVocabulary.user_id == user_id
            )
        ).first()
        
        if not user_vocabulary:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User vocabulary not found"
            )
        
        # Verify daily activity exists and belongs to user
        activity = self.db.query(DailyActivity).filter(
            DailyActivity.id == daily_activity_id
        ).first()
        
        if not activity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Daily activity not found"
            )
        
        if activity.user_plan.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This activity does not belong to you"
            )
        
        # Create practice session
        practice_session = VocabularyPracticeSession(
            user_vocabulary_id=user_vocabulary_id,
            daily_activity_id=daily_activity_id,
            exercise_type=exercise_type,
            is_correct=str(is_correct).lower(),
            user_answer=user_answer,
            correct_answer=correct_answer,
            time_taken_seconds=time_taken_seconds
        )
        
        self.db.add(practice_session)
        self.db.flush()
        
        # Update user vocabulary progress
        user_vocabulary.times_practiced += 1
        user_vocabulary.last_reviewed_at = datetime.utcnow()
        
        # Update mastery level based on correctness
        if is_correct:
            if user_vocabulary.mastery_level < 5:
                user_vocabulary.mastery_level += 1
            
            # Update status based on mastery
            if user_vocabulary.mastery_level == 1:
                user_vocabulary.status = VocabularyStatus.LEARNING
            elif user_vocabulary.mastery_level == 3:
                user_vocabulary.status = VocabularyStatus.REVIEWING
            elif user_vocabulary.mastery_level == 5:
                user_vocabulary.status = VocabularyStatus.MASTERED
                user_vocabulary.mastered_at = datetime.utcnow()
        else:
            # Decrease mastery if wrong (minimum 0)
            if user_vocabulary.mastery_level > 0:
                user_vocabulary.mastery_level -= 1
            
            # Reset status if mastery drops
            if user_vocabulary.mastery_level == 0:
                user_vocabulary.status = VocabularyStatus.NEW
        
        # Calculate next review time based on mastery
        if user_vocabulary.mastery_level == 0:
            user_vocabulary.next_review_at = datetime.utcnow() + timedelta(hours=1)
        elif user_vocabulary.mastery_level == 1:
            user_vocabulary.next_review_at = datetime.utcnow() + timedelta(hours=6)
        elif user_vocabulary.mastery_level == 2:
            user_vocabulary.next_review_at = datetime.utcnow() + timedelta(hours=24)
        elif user_vocabulary.mastery_level == 3:
            user_vocabulary.next_review_at = datetime.utcnow() + timedelta(days=3)
        elif user_vocabulary.mastery_level == 4:
            user_vocabulary.next_review_at = datetime.utcnow() + timedelta(days=7)
        elif user_vocabulary.mastery_level == 5:
            user_vocabulary.next_review_at = datetime.utcnow() + timedelta(days=30)
        
        self.db.commit()
        
        # Update daily activity
        activity.attempts_count += 1
        activity.time_spent_seconds += time_taken_seconds
        
        if activity.status != ActivityStatus.COMPLETED or activity.score is None:
            activity.status = ActivityStatus.COMPLETED
            activity.score = 100.0 if is_correct else 50.0
            activity.completed_at = datetime.utcnow()
        
        self.db.commit()
        
        # Update plan progress
        plan_service = PlanService(self.db)
        plan_service.update_plan_progress(activity.user_plan_id)
        
        # Update daily progress
        progress_service = ProgressService(self.db)
        progress_service.update_daily_progress(
            user_id=user_id,
            activity_type="VOCABULARY",
            time_spent_minutes=time_taken_seconds // 60,
            score=100.0 if is_correct else 50.0
        )
        
        self.db.refresh(practice_session)
        return practice_session
    
    # ============================================
    # GET PRACTICE SESSIONS
    # ============================================
    
    def get_practice_sessions(
        self,
        user_id: str,
        word_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[VocabularyPracticeSession]:
        """
        Get user's vocabulary practice sessions
        
        Args:
            user_id: User ID
            word_id: Optional filter by word ID
            limit: Maximum records to return
            offset: Pagination offset
            
        Returns:
            List of VocabularyPracticeSession objects
        """
        query = self.db.query(VocabularyPracticeSession).join(
            UserVocabulary
        ).filter(
            UserVocabulary.user_id == user_id
        )
        
        if word_id:
            query = query.filter(UserVocabulary.word_id == word_id)
        
        sessions = query.order_by(
            desc(VocabularyPracticeSession.practiced_at)
        ).limit(limit).offset(offset).all()
        
        return sessions
    
    # ============================================
    # GET VOCABULARY ANALYTICS
    # ============================================
    
    def get_analytics(self, user_id: str) -> dict:
        """
        Get vocabulary analytics and statistics
        
        Args:
            user_id: User ID
            
        Returns:
            Analytics dictionary with progress, mastery, and trends
        """
        # Get all user's vocabulary progress
        user_vocabulary_list = self.db.query(UserVocabulary).filter(
            UserVocabulary.user_id == user_id
        ).all()
        
        if not user_vocabulary_list:
            return {
                "total_words": 0,
                "words_by_status": {
                    "NEW": 0,
                    "LEARNING": 0,
                    "REVIEWING": 0,
                    "MASTERED": 0
                },
                "average_mastery_level": 0,
                "total_practice_sessions": 0,
                "accuracy_rate": 0,
                "words_mastered": 0,
                "words_to_review": 0,
                "mastery_trend": [],
                "category_breakdown": {}
            }
        
        # Count words by status
        status_counts = {
            "NEW": 0,
            "LEARNING": 0,
            "REVIEWING": 0,
            "MASTERED": 0
        }
        total_mastery = 0
        words_mastered = 0
        words_to_review = 0
        
        for uv in user_vocabulary_list:
            status_counts[uv.status] += 1
            total_mastery += uv.mastery_level
            
            if uv.status == VocabularyStatus.MASTERED:
                words_mastered += 1
            elif uv.status in [VocabularyStatus.LEARNING, VocabularyStatus.REVIEWING]:
                words_to_review += 1
        
        total_words = len(user_vocabulary_list)
        avg_mastery = total_mastery / total_words if total_words > 0 else 0
        
        # Get practice sessions
        practice_sessions = self.db.query(VocabularyPracticeSession).join(
            UserVocabulary
        ).filter(
            UserVocabulary.user_id == user_id
        ).all()
        
        total_practices = len(practice_sessions)
        correct_practices = sum(1 for s in practice_sessions if s.is_correct == "true")
        accuracy_rate = (correct_practices / total_practices * 100) if total_practices > 0 else 0
        
        # Mastery trend (last 10 words)
        recent_words = user_vocabulary_list[-10:]
        mastery_trend = [
            {
                "word": uv.word.word,
                "mastery_level": uv.mastery_level,
                "updated_at": uv.updated_at.strftime("%Y-%m-%d")
            }
            for uv in recent_words
        ]
        
        # Category breakdown
        category_breakdown = {}
        for uv in user_vocabulary_list:
            category = uv.word.category
            if category not in category_breakdown:
                category_breakdown[category] = {
                    "total_words": 0,
                    "mastered_words": 0,
                    "average_mastery": 0
                }
            category_breakdown[category]["total_words"] += 1
            if uv.status == VocabularyStatus.MASTERED:
                category_breakdown[category]["mastered_words"] += 1
            category_breakdown[category]["average_mastery"] += uv.mastery_level
        
        # Calculate averages for categories
        for category in category_breakdown:
            count = category_breakdown[category]["total_words"]
            if count > 0:
                category_breakdown[category]["average_mastery"] /= count
        
        return {
            "total_words": total_words,
            "words_by_status": status_counts,
            "average_mastery_level": round(avg_mastery, 1),
            "total_practice_sessions": total_practices,
            "accuracy_rate": round(accuracy_rate, 1),
            "words_mastered": words_mastered,
            "words_to_review": words_to_review,
            "mastery_trend": mastery_trend,
            "category_breakdown": category_breakdown
        }
