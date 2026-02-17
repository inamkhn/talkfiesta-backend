"""
Plan Service
Handles business logic for user plans and daily activities
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_
from fastapi import HTTPException, status
from datetime import datetime
from typing import List, Optional

from app.models.plan import UserPlan, DailyActivity, PlanType, PlanStatus, ActivityStatus
from app.schemas.plan import PlanCreate


class PlanService:
    """Service for managing user plans and daily activities"""
    
    def __init__(self, db: Session):
        self.db = db
    
    # ============================================
    # GET USER PLANS
    # ============================================
    
    def get_user_plans(
        self, 
        user_id: str, 
        cycle_number: Optional[int] = None
    ) -> List[UserPlan]:
        """
        Get all plans for a user, optionally filtered by cycle
        
        Args:
            user_id: User ID
            cycle_number: Optional cycle filter (1-5)
            
        Returns:
            List of UserPlan objects
        """
        query = self.db.query(UserPlan).filter(UserPlan.user_id == user_id)
        
        if cycle_number:
            query = query.filter(UserPlan.cycle_number == cycle_number)
        
        # Order by cycle and plan type for consistent display
        plans = query.order_by(
            UserPlan.cycle_number.desc(),
            UserPlan.plan_type
        ).all()
        
        return plans
    
    # ============================================
    # START NEW PLAN
    # ============================================
    
    def start_plan(self, user_id: str, plan_data: PlanCreate) -> UserPlan:
        """
        Start a new plan for a user
        
        Args:
            user_id: User ID
            plan_data: Plan creation data (type and cycle)
            
        Returns:
            Created UserPlan object
            
        Raises:
            HTTPException: If plan already exists or invalid cycle
        """
        # Validate cycle number
        if plan_data.cycle_number < 1 or plan_data.cycle_number > 5:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cycle number must be between 1 and 5"
            )
        
        # Check if plan already exists for this user, type, and cycle
        existing_plan = self.db.query(UserPlan).filter(
            and_(
                UserPlan.user_id == user_id,
                UserPlan.plan_type == plan_data.plan_type,
                UserPlan.cycle_number == plan_data.cycle_number
            )
        ).first()
        
        if existing_plan:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"{plan_data.plan_type.value} plan for cycle {plan_data.cycle_number} already exists"
            )
        
        # Create new plan
        new_plan = UserPlan(
            user_id=user_id,
            plan_type=plan_data.plan_type,
            cycle_number=plan_data.cycle_number,
            status=PlanStatus.IN_PROGRESS,
            current_day=1,
            completion_percentage=0.0,
            started_at=datetime.utcnow(),
            is_active=True
        )
        
        self.db.add(new_plan)
        self.db.flush()  # Get the plan ID
        
        # Create 21 daily activities for this plan
        self._create_daily_activities(new_plan.id, plan_data.plan_type)
        
        self.db.commit()
        self.db.refresh(new_plan)
        
        return new_plan
    
    def _create_daily_activities(self, plan_id: str, plan_type: PlanType):
        """
        Create 21 daily activities for a plan
        
        Args:
            plan_id: Plan ID
            plan_type: Type of plan (SPEAKING, VOCABULARY, WRITING)
        """
        activities = []
        
        for day in range(1, 22):  # Days 1-21
            activity = DailyActivity(
                user_plan_id=plan_id,
                day_number=day,
                activity_type=plan_type,
                status=ActivityStatus.AVAILABLE if day == 1 else ActivityStatus.LOCKED,
                time_spent_seconds=0,
                attempts_count=0
            )
            activities.append(activity)
        
        self.db.add_all(activities)
    
    # ============================================
    # GET PLAN DETAILS
    # ============================================
    
    def get_plan_by_id(self, user_id: str, plan_id: str) -> UserPlan:
        """
        Get plan details by ID
        
        Args:
            user_id: User ID (for authorization)
            plan_id: Plan ID
            
        Returns:
            UserPlan object with daily activities
            
        Raises:
            HTTPException: If plan not found or unauthorized
        """
        plan = self.db.query(UserPlan).filter(
            and_(
                UserPlan.id == plan_id,
                UserPlan.user_id == user_id
            )
        ).first()
        
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Plan not found"
            )
        
        return plan
    
    # ============================================
    # GET DAILY ACTIVITY
    # ============================================
    
    def get_daily_activity(
        self, 
        user_id: str, 
        plan_id: str, 
        day_number: int
    ) -> DailyActivity:
        """
        Get specific day's activity details
        
        Args:
            user_id: User ID (for authorization)
            plan_id: Plan ID
            day_number: Day number (1-21)
            
        Returns:
            DailyActivity object
            
        Raises:
            HTTPException: If activity not found or unauthorized
        """
        # Validate day number
        if day_number < 1 or day_number > 21:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Day number must be between 1 and 21"
            )
        
        # First verify the plan belongs to the user
        plan = self.get_plan_by_id(user_id, plan_id)
        
        # Get the daily activity
        activity = self.db.query(DailyActivity).filter(
            and_(
                DailyActivity.user_plan_id == plan_id,
                DailyActivity.day_number == day_number
            )
        ).first()
        
        if not activity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Activity for day {day_number} not found"
            )
        
        return activity
    
    # ============================================
    # UPDATE PLAN PROGRESS
    # ============================================
    
    def update_plan_progress(self, plan_id: str):
        """
        Update plan completion percentage and status
        
        Args:
            plan_id: Plan ID
        """
        plan = self.db.query(UserPlan).filter(UserPlan.id == plan_id).first()
        
        if not plan:
            return
        
        # Count completed activities
        completed_count = self.db.query(DailyActivity).filter(
            and_(
                DailyActivity.user_plan_id == plan_id,
                DailyActivity.status == ActivityStatus.COMPLETED
            )
        ).count()
        
        # Calculate completion percentage
        plan.completion_percentage = (completed_count / 21) * 100
        
        # Update status
        if completed_count == 21:
            plan.status = PlanStatus.COMPLETED
            plan.completed_at = datetime.utcnow()
        elif completed_count > 0:
            plan.status = PlanStatus.IN_PROGRESS
        
        # Update current day (next incomplete day)
        next_activity = self.db.query(DailyActivity).filter(
            and_(
                DailyActivity.user_plan_id == plan_id,
                DailyActivity.status != ActivityStatus.COMPLETED
            )
        ).order_by(DailyActivity.day_number).first()
        
        if next_activity:
            plan.current_day = next_activity.day_number
        else:
            plan.current_day = 21  # All completed
        
        self.db.commit()
    
    # ============================================
    # COMPLETE DAILY ACTIVITY
    # ============================================
    
    def complete_activity(
        self, 
        activity_id: str, 
        score: float, 
        time_spent: int
    ):
        """
        Mark activity as completed with score
        
        Args:
            activity_id: Activity ID
            score: Score (0-100)
            time_spent: Time spent in seconds
        """
        activity = self.db.query(DailyActivity).filter(
            DailyActivity.id == activity_id
        ).first()
        
        if not activity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Activity not found"
            )
        
        # Update activity
        activity.status = ActivityStatus.COMPLETED
        activity.score = score
        activity.completed_at = datetime.utcnow()
        activity.time_spent_seconds += time_spent
        activity.attempts_count += 1
        
        # Unlock next day
        next_activity = self.db.query(DailyActivity).filter(
            and_(
                DailyActivity.user_plan_id == activity.user_plan_id,
                DailyActivity.day_number == activity.day_number + 1
            )
        ).first()
        
        if next_activity and next_activity.status == ActivityStatus.LOCKED:
            next_activity.status = ActivityStatus.AVAILABLE
        
        self.db.commit()
        
        # Update plan progress
        self.update_plan_progress(activity.user_plan_id)
