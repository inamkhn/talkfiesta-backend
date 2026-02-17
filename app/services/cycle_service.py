"""
Cycle Service
Handles business logic for cycles
"""

from sqlalchemy.orm import Session
from sqlalchemy import desc
from fastapi import HTTPException, status
from typing import List, Optional
from datetime import datetime
import uuid

from app.models.plan import UserPlan, CycleCompletion, PlanType, PlanStatus


class CycleService:
    """Service for managing cycles"""
    
    def __init__(self, db: Session):
        self.db = db
    
    # ============================================
    # GET CYCLE COMPLETIONS
    # ============================================
    
    def get_cycle_completions(
        self,
        user_id: str,
        cycle_number: Optional[int] = None
    ) -> List[CycleCompletion]:
        """
        Get user's cycle completions
        
        Args:
            user_id: User ID
            cycle_number: Filter by cycle number
            
        Returns:
            List of CycleCompletion objects
        """
        query = self.db.query(CycleCompletion).filter(
            CycleCompletion.user_id == user_id
        )
        
        if cycle_number is not None:
            query = query.filter(CycleCompletion.cycle_number == cycle_number)
        
        # Order by cycle number
        completions = query.order_by(
            CycleCompletion.cycle_number
        ).all()
        
        return completions
    
    # ============================================
    # COMPLETE CYCLE
    # ============================================
    
    def complete_cycle(
        self,
        user_id: str,
        cycle_number: int
    ) -> CycleCompletion:
        """
        Mark a cycle as completed
        
        Args:
            user_id: User ID
            cycle_number: Cycle number (1-5)
            
        Returns:
            CycleCompletion object
            
        Raises:
            HTTPException: If cycle not found or already completed
        """
        # Check if cycle already completed
        existing = self.db.query(CycleCompletion).filter(
            and_(
                CycleCompletion.user_id == user_id,
                CycleCompletion.cycle_number == cycle_number
            )
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cycle already completed"
            )
        
        # Get all plans for this cycle
        plans = self.db.query(UserPlan).filter(
            and_(
                UserPlan.user_id == user_id,
                UserPlan.cycle_number == cycle_number
            )
        ).all()
        
        if not plans:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No plans found for this cycle"
            )
        
        # Check if all plans are completed
        for plan in plans:
            if plan.status != PlanStatus.COMPLETED:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Plan {plan.plan_type} is not yet completed"
                )
        
        # Create cycle completion
        cycle_completion = CycleCompletion(
            id=str(uuid.uuid4()),
            user_id=user_id,
            cycle_number=cycle_number,
            completed_at=datetime.utcnow()
        )
        
        self.db.add(cycle_completion)
        self.db.commit()
        self.db.refresh(cycle_completion)
        
        return cycle_completion
    
    # ============================================
    # GET CYCLE ANALYTICS
    # ============================================
    
    def get_analytics(self, user_id: str) -> dict:
        """
        Get cycle analytics and statistics
        
        Args:
            user_id: User ID
            
        Returns:
            Analytics dictionary with cycle stats
        """
        # Get all cycle completions
        completions = self.db.query(CycleCompletion).filter(
            CycleCompletion.user_id == user_id
        ).all()
        
        total_cycles = 5  # Total possible cycles
        completed_cycles = len(completions)
        completion_rate = (completed_cycles / total_cycles * 100) if total_cycles > 0 else 0
        
        # Get cycle details
        cycle_details = []
        for i in range(1, total_cycles + 1):
            completion = next((c for c in completions if c.cycle_number == i), None)
            cycle_details.append({
                "cycle_number": i,
                "completed": completion is not None,
                "completed_at": completion.completed_at.strftime("%Y-%m-%d %H:%M:%S") if completion else None
            })
        
        return {
            "total_cycles": total_cycles,
            "completed_cycles": completed_cycles,
            "completion_rate": round(completion_rate, 1),
            "cycle_details": cycle_details
        }
