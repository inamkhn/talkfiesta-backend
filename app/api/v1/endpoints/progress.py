"""
Progress & Analytics Endpoints
Handles user progress tracking and dashboard data
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date

from app.db.session import get_db
from app.core.security import get_current_user
from app.services.progress_service import ProgressService
from app.schemas.progress import (
    DashboardResponse,
    DailyProgressResponse
)

router = APIRouter()

# ============================================
# ENDPOINT 1: GET DASHBOARD OVERVIEW
# ============================================

@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard_overview(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive dashboard overview
    
    **CONSOLIDATES MULTIPLE DATA SOURCES INTO ONE RESPONSE**
    
    This endpoint replaces the need for multiple API calls:
    - ❌ OLD: Call /profile/me + /plans + /progress/today + /scores
    - ✅ NEW: Call /progress/dashboard (ONE call)
    
    **Returns:**
    - User profile summary (name, streak, practice time, level)
    - Current cycle number
    - All plans progress (Speaking, Vocabulary, Writing)
    - Today's completion status
    - Recent average scores (last 7 days)
    
    **Example Response:**
    ```json
    {
      "user": {
        "name": "John Doe",
        "streak_days": 5,
        "total_practice_minutes": 120,
        "english_level": "B1"
      },
      "current_cycle": 1,
      "plans": [
        {
          "plan_type": "SPEAKING",
          "current_day": 5,
          "completion_percentage": 23.8,
          "status": "IN_PROGRESS"
        },
        {
          "plan_type": "VOCABULARY",
          "current_day": 3,
          "completion_percentage": 14.3,
          "status": "IN_PROGRESS"
        },
        {
          "plan_type": "WRITING",
          "current_day": 2,
          "completion_percentage": 9.5,
          "status": "IN_PROGRESS"
        }
      ],
      "today_progress": {
        "speaking_completed": true,
        "vocabulary_completed": false,
        "writing_completed": false,
        "total_minutes": 15
      },
      "recent_scores": {
        "speaking_avg": 82.5,
        "vocabulary_avg": 78.0,
        "writing_avg": 80.0
      }
    }
    ```
    
    **Frontend Usage - Dashboard Page:**
    ```javascript
    // ONE API call gets everything!
    const dashboard = await fetch('/api/v1/progress/dashboard');
    
    // Display user info
    showWelcome(dashboard.user.name);
    showStreak(dashboard.user.streak_days);
    showCycle(dashboard.current_cycle);
    
    // Display plan progress cards
    dashboard.plans.forEach(plan => {
      showPlanCard({
        type: plan.plan_type,
        day: plan.current_day,
        progress: plan.completion_percentage
      });
    });
    
    // Display today's progress
    showTodayProgress({
      speaking: dashboard.today_progress.speaking_completed,
      vocabulary: dashboard.today_progress.vocabulary_completed,
      writing: dashboard.today_progress.writing_completed
    });
    
    // Display recent scores
    showScores(dashboard.recent_scores);
    ```
    
    **Performance Benefits:**
    - Reduces network requests from 4-5 to 1
    - Faster page load
    - Less server load
    - Atomic data consistency
    
    **Business Logic:**
    - Current cycle = highest active cycle number
    - Today's progress checks activities completed today
    - Recent scores = average of last 7 days
    - Plans ordered by type (Speaking, Vocabulary, Writing)
    
    **Use Cases:**
    1. Dashboard initial load
    2. Dashboard refresh
    3. After completing an activity (refresh dashboard)
    4. Mobile app home screen
    """
    progress_service = ProgressService(db)
    dashboard = progress_service.get_dashboard_overview(current_user.id)
    
    return dashboard


# ============================================
# ENDPOINT 2: GET DAILY PROGRESS HISTORY
# ============================================

@router.get("/daily", response_model=List[DailyProgressResponse])
async def get_daily_progress(
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    limit: int = Query(30, ge=1, le=365, description="Maximum records to return"),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get daily progress history
    
    Returns historical progress data showing what was completed each day.
    Used for progress tracking, charts, and streak calculation.
    
    **Query Parameters:**
    - **start_date** (optional): Filter from this date (YYYY-MM-DD)
    - **end_date** (optional): Filter to this date (YYYY-MM-DD)
    - **limit** (optional): Max records (default 30, max 365)
    
    **Returns:**
    - Array of daily progress records (most recent first)
    
    **Example Response:**
    ```json
    [
      {
        "date": "2024-01-05",
        "speaking_completed": true,
        "vocabulary_completed": true,
        "writing_completed": false,
        "total_minutes_practiced": 25,
        "words_learned_count": 10,
        "average_score": 81.5,
        "exercises_completed_count": 2,
        "streak_maintained": true
      },
      {
        "date": "2024-01-04",
        "speaking_completed": true,
        "vocabulary_completed": false,
        "writing_completed": true,
        "total_minutes_practiced": 30,
        "words_learned_count": 0,
        "average_score": 85.0,
        "exercises_completed_count": 2,
        "streak_maintained": true
      }
    ]
    ```
    
    **Frontend Usage - Progress Page:**
    ```javascript
    // Get last 30 days
    const progress = await fetch('/api/v1/progress/daily?limit=30');
    
    // Display calendar view
    progress.forEach(day => {
      showDayInCalendar({
        date: day.date,
        completed: day.streak_maintained,
        modules: {
          speaking: day.speaking_completed,
          vocabulary: day.vocabulary_completed,
          writing: day.writing_completed
        }
      });
    });
    
    // Calculate streak
    let streak = 0;
    for (const day of progress) {
      if (day.streak_maintained) streak++;
      else break;
    }
    ```
    
    **Frontend Usage - Analytics Charts:**
    ```javascript
    // Get last 7 days for chart
    const weekData = await fetch('/api/v1/progress/daily?limit=7');
    
    // Create time spent chart
    const chartData = weekData.map(day => ({
      date: day.date,
      minutes: day.total_minutes_practiced,
      score: day.average_score
    }));
    
    renderChart(chartData);
    ```
    
    **Date Range Examples:**
    ```
    // Last 30 days (default)
    GET /progress/daily
    
    // Last 7 days
    GET /progress/daily?limit=7
    
    // Specific month
    GET /progress/daily?start_date=2024-01-01&end_date=2024-01-31
    
    // Last year
    GET /progress/daily?limit=365
    ```
    
    **Business Logic:**
    - Records created when user completes activities
    - One record per day per user
    - Streak maintained if ANY activity completed
    - Average score calculated across all activities that day
    - Words learned only counts vocabulary activities
    
    **Use Cases:**
    1. Progress calendar view
    2. Streak calculation
    3. Activity charts (time, score trends)
    4. Monthly/weekly reports
    5. Habit tracking
    
    **Performance:**
    - Indexed by user_id and date
    - Limited to prevent large responses
    - Ordered by date descending (most recent first)
    """
    progress_service = ProgressService(db)
    progress_records = progress_service.get_daily_progress(
        user_id=current_user.id,
        start_date=start_date,
        end_date=end_date,
        limit=limit
    )
    
    return progress_records
