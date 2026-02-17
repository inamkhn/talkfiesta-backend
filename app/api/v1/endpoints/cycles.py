"""
Cycles Module Endpoints
Handles cycle progress and completion
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.session import get_db
from app.core.security import get_current_user
from app.services.cycle_service import CycleService

router = APIRouter()

# ============================================
# ENDPOINT 1: GET CYCLE COMPLETIONS
# ============================================

@router.get("/completions", response_model=List[dict])
async def get_cycle_completions(
    cycle_number: Optional[int] = Query(None, ge=1, le=5, description="Filter by cycle number (1-5)"),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get user's cycle completion history
    
    Returns list of completed cycles with completion dates.
    
    **Query Parameters:**
    - **cycle_number** (optional): Filter by cycle number (1-5)
    
    **Returns:**
    - Array of cycle completions
    
    **Example Response:**
    ```json
    [
      {
        "id": "uuid",
        "cycle_number": 1,
        "completed_at": "2024-01-15T10:30:00Z"
      }
    ]
    ```
    
    **Use Cases:**
    1. Show cycle progress on dashboard
    2. Track completion history
    3. Display completed cycles
    
    **Frontend Usage:**
    ```javascript
    // Get all cycle completions
    const response = await fetch('/api/v1/cycles/completions', {
      headers: {
        'Authorization': `Bearer ${accessToken}`
      }
    });
    const completions = await response.json();
    
    // Filter by cycle
    const response = await fetch(
      '/api/v1/cycles/completions?cycle_number=1',
      {
        headers: {
          'Authorization': `Bearer ${accessToken}`
        }
      }
    );
    const cycle1 = await response.json();
    ```
    """
    cycle_service = CycleService(db)
    completions = cycle_service.get_cycle_completions(
        user_id=current_user.id,
        cycle_number=cycle_number
    )
    
    return [
        {
            "id": c.id,
            "cycle_number": c.cycle_number,
            "completed_at": c.completed_at.strftime("%Y-%m-%d %H:%M:%S") if c.completed_at else None
        }
        for c in completions
    ]


# ============================================
# ENDPOINT 2: COMPLETE CYCLE
# ============================================

@router.post("/complete", response_model=dict)
async def complete_cycle(
    cycle_number: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mark a cycle as completed
    
    **CRITICAL ENDPOINT**: This is where users complete a cycle.
    
    Handles:
    - Cycle validation
    - All plans completion check
    - Cycle completion creation
    
    **Request Body:**
    ```json
    {
      "cycle_number": 1
    }
    ```
    
    **Returns:**
    - CycleCompletion object
    
    **Example Response:**
    ```json
    {
      "id": "uuid",
      "cycle_number": 1,
      "completed_at": "2024-01-15T10:30:00Z"
    }
    ```
    
    **Frontend Usage:**
    ```javascript
    async function completeCycle(cycleNumber) {
      const response = await fetch('/api/v1/cycles/complete', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          cycle_number: cycleNumber
        })
      });
      
      const result = await response.json();
      
      // Show completion celebration
      showCompletionCelebration(result);
      
      // Update cycle progress
      updateCycleProgress(result);
    }
    ```
    
    **Business Logic:**
    - Validates cycle number (1-5)
    - Checks if cycle already completed
    - Verifies all plans are completed
    - Creates cycle completion record
    - Returns completion timestamp
    
    **Error Handling:**
    - 400: Cycle already completed
    - 400: Not all plans completed
    - 404: No plans found for cycle
    - 401: Unauthorized
    
    **Performance:**
    - Single query for existing completion
    - Query for plans
    - Single insert for cycle completion
    """
    cycle_service = CycleService(db)
    cycle_completion = cycle_service.complete_cycle(
        user_id=current_user.id,
        cycle_number=cycle_number
    )
    
    return {
        "id": cycle_completion.id,
        "cycle_number": cycle_completion.cycle_number,
        "completed_at": cycle_completion.completed_at.strftime("%Y-%m-%d %H:%M:%S") if cycle_completion.completed_at else None
    }


# ============================================
# ENDPOINT 3: GET CYCLE ANALYTICS
# ============================================

@router.get("/analytics", response_model=dict)
async def get_cycle_analytics(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get cycle analytics and statistics
    
    Returns comprehensive analytics about user's cycle progress.
    
    **Returns:**
    - Total cycles count
    - Completed cycles count
    - Completion rate
    - Cycle details (each cycle's status)
    
    **Example Response:**
    ```json
    {
      "total_cycles": 5,
      "completed_cycles": 1,
      "completion_rate": 20.0,
      "cycle_details": [
        {
          "cycle_number": 1,
          "completed": true,
          "completed_at": "2024-01-15 10:30:00"
        },
        {
          "cycle_number": 2,
          "completed": false,
          "completed_at": null
        }
      ]
    }
    ```
    
    **Frontend Usage:**
    ```javascript
    function CycleProgress() {
      const [analytics, setAnalytics] = useState(null);
      
      useEffect(() => {
        async function loadAnalytics() {
          const response = await fetch('/api/v1/cycles/analytics', {
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
        <div className="cycle-progress">
          <h2>Cycle Progress</h2>
          
          <div className="progress-bar">
            <div 
              className="progress-fill" 
              style={{ width: `${analytics.completion_rate}%` }}
            />
          </div>
          
          <div className="cycle-details">
            {analytics.cycle_details.map((cycle, index) => (
              <CycleCard 
                key={index}
                cycle={cycle}
                isCompleted={cycle.completed}
              />
            ))}
          </div>
        </div>
      );
    }
    ```
    
    **Use Cases:**
    1. **Dashboard**: Show cycle progress
    2. **Progress Tracking**: Monitor completion rate
    3. **Motivation**: Show how close to completion
    4. **Planning**: Identify which cycles to focus on
    
    **Business Logic:**
    - Only returns user's own analytics
    - Calculates completion rate
    - Tracks each cycle's status
    
    **Performance:**
    - Aggregates data from cycle completions
    - Efficient database queries
    
    **Data Insights:**
    - Overall completion rate
    - Which cycles completed
    - Which cycles pending
    """
    cycle_service = CycleService(db)
    analytics = cycle_service.get_analytics(user_id=current_user.id)
    
    return analytics
