"""
Progress Service
Handles business logic for progress tracking and analytics
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_, func, desc
from datetime import date, datetime, timedelta
from typing import List, Optional

from app.models.user import User
from app.models.plan import UserPlan, DailyActivity, PlanStatus, ActivityStatus
from app.models.progress import DailyProgress
from app.schemas.progress import (
    UserSummary,
    PlanSummary,
    TodayProgressResponse,
    RecentScoresResponse,
    DashboardResponse
)


class ProgressService:
    """Service for managing user progress and analytics"""
    
    def __init__(self, db: Session):
        self.db = db
    
    # ============================================
    # DASHBOARD OVERVIEW
    # ============================================
    
    def get_dashboard_overview(self, user_id: str) -> DashboardResponse:
        """
        Get comprehensive dashboard data
        
        Consolidates multiple queries into one response:
        - User profile summary
        - Current cycle
        - All plans progress
        - Today's progress
        - Recent scores
        
        Args:
            user_id: User ID
            
        Returns:
            DashboardResponse with all dashboard data
        """
        # Get user
        user = self.db.query(User).filter(User.id == user_id).first()
        
        if not user:
            # Return empty dashboard if user not found
            return self._empty_dashboard()
        
        # Build user summary
        user_summary = UserSummary(
            name=user.name,
            streak_days=user.streak_days,
            total_practice_minutes=user.total_practice_minutes,
            english_level=user.english_level.value
        )
        
        # Get current cycle (highest active cycle)
        current_cycle = self._get_current_cycle(user_id)
        
        # Get all active plans
        plans = self._get_plans_summary(user_id)
        
        # Get today's progress
        today_progress = self._get_today_progress(user_id)
        
        # Get recent scores (last 7 days)
        recent_scores = self._get_recent_scores(user_id)
        
        return DashboardResponse(
            user=user_summary,
            current_cycle=current_cycle,
            plans=plans,
            today_progress=today_progress,
            recent_scores=recent_scores
        )
    
    def _empty_dashboard(self) -> DashboardResponse:
        """Return empty dashboard for new users"""
        return DashboardResponse(
            user=UserSummary(
                name="User",
                streak_days=0,
                total_practice_minutes=0,
                english_level="B1"
            ),
            current_cycle=1,
            plans=[],
            today_progress=TodayProgressResponse(
                speaking_completed=False,
                vocabulary_completed=False,
                writing_completed=False,
                total_minutes=0
            ),
            recent_scores=RecentScoresResponse(
                speaking_avg=None,
                vocabulary_avg=None,
                writing_avg=None
            )
        )
    
    def _get_current_cycle(self, user_id: str) -> int:
        """Get user's current cycle (highest active cycle)"""
        max_cycle = self.db.query(func.max(UserPlan.cycle_number)).filter(
            and_(
                UserPlan.user_id == user_id,
                UserPlan.is_active == True
            )
        ).scalar()
        
        return max_cycle or 1
    
    def _get_plans_summary(self, user_id: str) -> List[PlanSummary]:
        """Get summary of all active plans"""
        plans = self.db.query(UserPlan).filter(
            and_(
                UserPlan.user_id == user_id,
                UserPlan.is_active == True
            )
        ).order_by(UserPlan.plan_type).all()
        
        return [
            PlanSummary(
                plan_type=plan.plan_type.value,
                current_day=plan.current_day,
                completion_percentage=plan.completion_percentage,
                status=plan.status.value
            )
            for plan in plans
        ]
    
    def _get_today_progress(self, user_id: str) -> TodayProgressResponse:
        """Get today's progress across all modules"""
        today = date.today()
        
        # Check if daily progress record exists for today
        daily_progress = self.db.query(DailyProgress).filter(
            and_(
                DailyProgress.user_id == user_id,
                DailyProgress.date == today
            )
        ).first()
        
        if daily_progress:
            return TodayProgressResponse(
                speaking_completed=daily_progress.speaking_completed,
                vocabulary_completed=daily_progress.vocabulary_completed,
                writing_completed=daily_progress.writing_completed,
                total_minutes=daily_progress.total_minutes_practiced
            )
        
        # If no record, check completed activities today
        today_start = datetime.combine(today, datetime.min.time())
        
        # Get all plans for user
        plans = self.db.query(UserPlan).filter(
            UserPlan.user_id == user_id
        ).all()
        
        speaking_completed = False
        vocabulary_completed = False
        writing_completed = False
        total_minutes = 0
        
        for plan in plans:
            # Check if any activity was completed today
            completed_today = self.db.query(DailyActivity).filter(
                and_(
                    DailyActivity.user_plan_id == plan.id,
                    DailyActivity.status == ActivityStatus.COMPLETED,
                    DailyActivity.completed_at >= today_start
                )
            ).first()
            
            if completed_today:
                if plan.plan_type.value == "SPEAKING":
                    speaking_completed = True
                elif plan.plan_type.value == "VOCABULARY":
                    vocabulary_completed = True
                elif plan.plan_type.value == "WRITING":
                    writing_completed = True
                
                total_minutes += completed_today.time_spent_seconds // 60
        
        return TodayProgressResponse(
            speaking_completed=speaking_completed,
            vocabulary_completed=vocabulary_completed,
            writing_completed=writing_completed,
            total_minutes=total_minutes
        )
    
    def _get_recent_scores(self, user_id: str) -> RecentScoresResponse:
        """Get average scores for last 7 days"""
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        
        # Get all plans for user
        plans = self.db.query(UserPlan).filter(
            UserPlan.user_id == user_id
        ).all()
        
        speaking_scores = []
        vocabulary_scores = []
        writing_scores = []
        
        for plan in plans:
            # Get completed activities in last 7 days
            activities = self.db.query(DailyActivity).filter(
                and_(
                    DailyActivity.user_plan_id == plan.id,
                    DailyActivity.status == ActivityStatus.COMPLETED,
                    DailyActivity.completed_at >= seven_days_ago,
                    DailyActivity.score.isnot(None)
                )
            ).all()
            
            for activity in activities:
                if plan.plan_type.value == "SPEAKING":
                    speaking_scores.append(activity.score)
                elif plan.plan_type.value == "VOCABULARY":
                    vocabulary_scores.append(activity.score)
                elif plan.plan_type.value == "WRITING":
                    writing_scores.append(activity.score)
        
        return RecentScoresResponse(
            speaking_avg=sum(speaking_scores) / len(speaking_scores) if speaking_scores else None,
            vocabulary_avg=sum(vocabulary_scores) / len(vocabulary_scores) if vocabulary_scores else None,
            writing_avg=sum(writing_scores) / len(writing_scores) if writing_scores else None
        )
    
    # ============================================
    # DAILY PROGRESS
    # ============================================
    
    def get_daily_progress(
        self,
        user_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 30
    ) -> List[DailyProgress]:
        """
        Get daily progress history
        
        Args:
            user_id: User ID
            start_date: Optional start date filter
            end_date: Optional end date filter
            limit: Maximum number of records (default 30)
            
        Returns:
            List of DailyProgress records
        """
        query = self.db.query(DailyProgress).filter(
            DailyProgress.user_id == user_id
        )
        
        # Apply date filters
        if start_date:
            query = query.filter(DailyProgress.date >= start_date)
        
        if end_date:
            query = query.filter(DailyProgress.date <= end_date)
        
        # Order by date descending and limit
        progress_records = query.order_by(
            desc(DailyProgress.date)
        ).limit(limit).all()
        
        return progress_records
    
    # ============================================
    # UPDATE DAILY PROGRESS
    # ============================================
    
    def update_daily_progress(
        self,
        user_id: str,
        activity_type: str,
        time_spent_minutes: int,
        score: Optional[float] = None,
        words_learned: int = 0
    ):
        """
        Update or create daily progress record
        
        Called when user completes an activity.
        Updates today's progress record.
        
        Args:
            user_id: User ID
            activity_type: SPEAKING, VOCABULARY, or WRITING
            time_spent_minutes: Time spent in minutes
            score: Activity score (0-100)
            words_learned: Number of words learned (for vocabulary)
        """
        today = date.today()
        
        # Get or create today's progress record
        daily_progress = self.db.query(DailyProgress).filter(
            and_(
                DailyProgress.user_id == user_id,
                DailyProgress.date == today
            )
        ).first()
        
        if not daily_progress:
            daily_progress = DailyProgress(
                user_id=user_id,
                date=today,
                speaking_completed=False,
                vocabulary_completed=False,
                writing_completed=False,
                total_minutes_practiced=0,
                words_learned_count=0,
                exercises_completed_count=0,
                streak_maintained=False
            )
            self.db.add(daily_progress)
        
        # Update completion status
        if activity_type == "SPEAKING":
            daily_progress.speaking_completed = True
        elif activity_type == "VOCABULARY":
            daily_progress.vocabulary_completed = True
        elif activity_type == "WRITING":
            daily_progress.writing_completed = True
        
        # Update metrics
        daily_progress.total_minutes_practiced += time_spent_minutes
        daily_progress.words_learned_count += words_learned
        daily_progress.exercises_completed_count += 1
        
        # Update average score
        if score is not None:
            if daily_progress.average_score is None:
                daily_progress.average_score = score
            else:
                # Calculate new average
                total_exercises = daily_progress.exercises_completed_count
                old_total = daily_progress.average_score * (total_exercises - 1)
                daily_progress.average_score = (old_total + score) / total_exercises
        
        # Check if streak is maintained (at least one activity completed)
        daily_progress.streak_maintained = (
            daily_progress.speaking_completed or
            daily_progress.vocabulary_completed or
            daily_progress.writing_completed
        )
        
        self.db.commit()
        
        # Update user's total practice time
        user = self.db.query(User).filter(User.id == user_id).first()
        if user:
            user.total_practice_minutes += time_spent_minutes
            self.db.commit()
