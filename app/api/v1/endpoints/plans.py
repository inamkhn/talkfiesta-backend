"""
User Plans Endpoints
Handles user learning plans and daily activities
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.session import get_db
from app.core.security import get_current_user
from app.services.plan_service import PlanService
from app.schemas.plan import (
    PlanCreate,
    UserPlanResponse,
    UserPlanDetail,
    DailyActivityResponse
)

router = APIRouter()

# ============================================
# ENDPOINT 1: GET ALL USER PLANS
# ============================================

@router.get("", response_model=List[UserPlanResponse])
async def get_user_plans(
    cycle_number: Optional[int] = Query(None, ge=1, le=5, description="Filter by cycle (1-5)"),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all plans for authenticated user
    
    Returns list of user's learning plans (Speaking, Vocabulary, Writing).
    Can be filtered by cycle number.
    
    **Query Parameters:**
    - **cycle_number** (optional): Filter by cycle (1-5)
    
    **Returns:**
    - List of plans with progress information
    
    **Example Response:**
    ```json
    [
      {
        "id": "uuid",
        "plan_type": "SPEAKING",
        "status": "IN_PROGRESS",
        "current_day": 5,
        "completion_percentage": 23.8,
        "cycle_number": 1,
        "cycles_completed": 0,
        "started_at": "2024-01-01T00:00:00Z",
        "completed_at": null,
        "is_active": true
      }
    ]
    ```
    
    **Use Case:**
    - Dashboard displays all active plans
    - Shows progress for Speaking, Vocabulary, and Writing modules
    - Frontend can filter by cycle to show specific cycle progress
    """
    plan_service = PlanService(db)
    plans = plan_service.get_user_plans(current_user.id, cycle_number)
    
    return plans


# ============================================
# ENDPOINT 2: START NEW PLAN
# ============================================

@router.post("", response_model=UserPlanResponse, status_code=status.HTTP_201_CREATED)
async def start_plan(
    plan_data: PlanCreate,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Start a new learning plan
    
    Creates a new plan (Speaking, Vocabulary, or Writing) for a specific cycle.
    Automatically creates 21 daily activities.
    
    **Request Body:**
    ```json
    {
      "plan_type": "SPEAKING",
      "cycle_number": 1
    }
    ```
    
    **Plan Types:**
    - `SPEAKING`: Speaking practice plan (21 days)
    - `VOCABULARY`: Vocabulary learning plan (21 days)
    - `WRITING`: Writing practice plan (21 days)
    
    **Cycle Numbers:**
    - 1-5 (each cycle has different difficulty/content)
    
    **Returns:**
    - Created plan with initial status
    
    **Business Rules:**
    - Cannot create duplicate plan (same type + cycle)
    - Day 1 is automatically unlocked
    - Days 2-21 are locked until previous day is completed
    - Plan starts in IN_PROGRESS status
    
    **Errors:**
    - 400: Invalid cycle number
    - 409: Plan already exists for this type and cycle
    """
    plan_service = PlanService(db)
    plan = plan_service.start_plan(current_user.id, plan_data)
    
    return plan


# ============================================
# ENDPOINT 3: GET PLAN DETAILS
# ============================================

@router.get("/{plan_id}", response_model=UserPlanDetail)
async def get_plan_details(
    plan_id: str,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get detailed plan information with all daily activities
    
    Returns complete plan details including all 21 daily activities
    with their status, scores, and completion information.
    
    **Path Parameters:**
    - **plan_id**: Plan UUID
    
    **Returns:**
    - Plan details with array of daily activities
    
    **Example Response:**
    ```json
    {
      "id": "uuid",
      "plan_type": "SPEAKING",
      "status": "IN_PROGRESS",
      "current_day": 5,
      "completion_percentage": 23.8,
      "cycle_number": 1,
      "daily_activities": [
        {
          "id": "uuid",
          "day_number": 1,
          "activity_type": "SPEAKING",
          "status": "COMPLETED",
          "score": 85.5,
          "completed_at": "2024-01-01T10:00:00Z",
          "time_spent_seconds": 300,
          "attempts_count": 1
        },
        {
          "day_number": 2,
          "status": "AVAILABLE",
          "score": null,
          ...
        }
      ]
    }
    ```
    
    **Activity Status:**
    - `LOCKED`: Not yet available (previous day not completed)
    - `AVAILABLE`: Ready to start
    - `COMPLETED`: Finished with score
    
    **Use Case:**
    - Plan overview page showing all days
    - Progress tracking
    - Identifying next available activity
    
    **Errors:**
    - 404: Plan not found or doesn't belong to user
    """
    plan_service = PlanService(db)
    plan = plan_service.get_plan_by_id(current_user.id, plan_id)
    
    return plan


# ============================================
# ENDPOINT 4: GET DAILY ACTIVITY
# ============================================

@router.get("/{plan_id}/days/{day_number}", response_model=DailyActivityResponse)
async def get_daily_activity(
    plan_id: str,
    day_number: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get specific day's activity details
    
    Returns detailed information about a specific day's activity
    within a plan. Used when user clicks on a specific day.
    
    **Path Parameters:**
    - **plan_id**: Plan UUID
    - **day_number**: Day number (1-21)
    
    **Returns:**
    - Daily activity details
    
    **Example Response:**
    ```json
    {
      "id": "uuid",
      "day_number": 5,
      "activity_type": "SPEAKING",
      "status": "AVAILABLE",
      "score": null,
      "completed_at": null,
      "time_spent_seconds": 0,
      "attempts_count": 0
    }
    ```
    
    **Use Case:**
    - User clicks on "Day 5" in the plan
    - Frontend checks if day is available before showing exercise
    - Display previous scores/attempts
    
    **Frontend Flow:**
    1. User clicks on day
    2. Call this endpoint to get activity details
    3. If status is AVAILABLE, show exercise
    4. If status is LOCKED, show "Complete previous day first"
    5. If status is COMPLETED, show results/allow retry
    
    **Errors:**
    - 400: Invalid day number (must be 1-21)
    - 404: Plan or activity not found
    - 404: Plan doesn't belong to user
    """
    plan_service = PlanService(db)
    activity = plan_service.get_daily_activity(
        current_user.id, 
        plan_id, 
        day_number
    )
    
    return activity
