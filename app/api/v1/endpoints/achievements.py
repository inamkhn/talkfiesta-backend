"""
Achievements Module Endpoints
Handles achievements and user progress
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.session import get_db
from app.core.security import get_current_user
from app.services.achievement_service import AchievementService
from app.schemas.achievement import AchievementResponse, UserAchievementResponse

router = APIRouter()

# ============================================
# ENDPOINT 1: GET ACHIEVEMENTS
# ============================================

@router.get("", response_model=List[AchievementResponse])
async def get_achievements(
    achievement_type: Optional[str] = Query(None, description="Filter by type (learning, streak, milestone, social)"),
    difficulty: Optional[str] = Query(None, description="Filter by difficulty (BEGINNER, INTERMEDIATE, ADVANCED)"),
    limit: int = Query(20, ge=1, le=100, description="Maximum records to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all achievements with optional filters
    
    **Query Parameters:**
    - **achievement_type** (optional): learning, streak, milestone, or social
    - **difficulty** (optional): BEGINNER, INTERMEDIATE, or ADVANCED
    - **limit** (optional): Max records (default 20, max 100)
    - **offset** (optional): Pagination offset (default 0)
    
    **Returns:**
    - Array of achievements
    
    **Example Response:**
    ```json
    [
      {
        "id": "uuid",
        "title": "First Steps",
        "description": "Complete your first speaking exercise",
        "achievement_type": "learning",
        "difficulty": "BEGINNER",
        "points": 10,
        "icon": "🚀",
        "unlocked_count": 150,
        "total_users": 500
      }
    ]
    ```
    
    **Use Cases:**
    1. Show achievements list on profile page
    2. Filter by type to see specific categories
    3. Filter by difficulty to see challenge achievements
    
    **Frontend Usage:**
    ```javascript
    // Get all achievements
    const response = await fetch('/api/v1/achievements', {
      headers: {
        'Authorization': `Bearer ${accessToken}`
      }
    });
    const achievements = await response.json();
    
    // Filter by type
    const response = await fetch(
      '/api/v1/achievements?achievement_type=streak',
      {
        headers: {
          'Authorization': `Bearer ${accessToken}`
        }
      }
    );
    const streakAchievements = await response.json();
    ```
    """
    achievement_service = AchievementService(db)
    achievements = achievement_service.get_achievements(
        achievement_type=achievement_type,
        difficulty=difficulty,
        limit=limit,
        offset=offset
    )
    
    return achievements


# ============================================
# ENDPOINT 2: GET ACHIEVEMENT BY ID
# ============================================

@router.get("/{achievement_id}", response_model=AchievementResponse)
async def get_achievement(
    achievement_id: str,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get specific achievement by ID
    
    **Path Parameters:**
    - **achievement_id**: Achievement UUID
    
    **Returns:**
    - Single achievement object with all details
    
    **Example Response:**
    ```json
    {
      "id": "uuid",
      "title": "7-Day Streak",
      "description": "Maintain a 7-day practice streak",
      "achievement_type": "streak",
      "difficulty": "INTERMEDIATE",
      "points": 50,
      "icon": "🔥",
      "unlocked_count": 45,
      "total_users": 500
    }
    ```
    
    **Frontend Usage:**
    ```javascript
    // Load achievement details
    async function loadAchievementDetails(achievementId) {
      const response = await fetch(
        `/api/v1/achievements/${achievementId}`,
        {
          headers: {
            'Authorization': `Bearer ${accessToken}`
          }
        }
      );
      const achievement = await response.json();
      
      return (
        <AchievementCard
          title={achievement.title}
          description={achievement.description}
          type={achievement.achievement_type}
          difficulty={achievement.difficulty}
          icon={achievement.icon}
          points={achievement.points}
        />
      );
    }
    ```
    """
    achievement_service = AchievementService(db)
    achievement = achievement_service.get_achievement_by_id(achievement_id)
    
    return achievement


# ============================================
# ENDPOINT 3: GET USER ACHIEVEMENTS
# ============================================

@router.get("/user", response_model=List[UserAchievementResponse])
async def get_user_achievements(
    achievement_type: Optional[str] = Query(None, description="Filter by type"),
    unlocked: Optional[bool] = Query(None, description="Filter by unlocked status"),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get user's achievements
    
    **Query Parameters:**
    - **achievement_type** (optional): Filter by type
    - **unlocked** (optional): Filter by unlocked status
    
    **Returns:**
    - Array of user achievements with unlock status
    
    **Example Response:**
    ```json
    [
      {
        "id": "uuid",
        "achievement": {
          "id": "uuid",
          "title": "First Steps",
          "description": "Complete your first speaking exercise",
          "achievement_type": "learning",
          "difficulty": "BEGINNER",
          "points": 10,
          "icon": "🚀"
        },
        "unlocked_at": "2024-01-05T10:30:00Z",
        "unlocked": true
      }
    ]
    ```
    
    **Use Cases:**
    1. Show user's achievements on profile page
    2. Filter by unlocked to see earned achievements
    3. Filter by type to see specific categories
    
    **Frontend Usage:**
    ```javascript
    // Get all user achievements
    const response = await fetch('/api/v1/achievements/user', {
      headers: {
        'Authorization': `Bearer ${accessToken}`
      }
    });
    const userAchievements = await response.json();
    
    // Filter by unlocked
    const response = await fetch(
      '/api/v1/achievements/user?unlocked=true',
      {
        headers: {
          'Authorization': `Bearer ${accessToken}`
        }
      }
    );
    const unlockedAchievements = await response.json();
    ```
    """
    achievement_service = AchievementService(db)
    user_achievements = achievement_service.get_user_achievements(
        user_id=current_user.id,
        achievement_type=achievement_type,
        unlocked=unlocked
    )
    
    return user_achievements


# ============================================
# ENDPOINT 4: UNLOCK ACHIEVEMENT
# ============================================

@router.post("/{achievement_id}/unlock", response_model=UserAchievementResponse)
async def unlock_achievement(
    achievement_id: str,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Unlock an achievement for the user
    
    **Path Parameters:**
    - **achievement_id**: Achievement UUID
    
    **Returns:**
    - UserAchievement object with unlock timestamp
    
    **Example Response:**
    ```json
    {
      "id": "uuid",
      "achievement": {
        "id": "uuid",
        "title": "First Steps",
        "description": "Complete your first speaking exercise",
        "achievement_type": "learning",
        "difficulty": "BEGINNER",
        "points": 10,
        "icon": "🚀"
      },
      "unlocked_at": "2024-01-05T10:30:00Z",
      "unlocked": true
    }
    ```
    
    **Use Cases:**
    1. Unlock achievement when user completes a milestone
    2. Show unlock animation
    3. Award points
    
    **Frontend Usage:**
    ```javascript
    async function unlockAchievement(achievementId) {
      const response = await fetch(
        `/api/v1/achievements/${achievementId}/unlock`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${accessToken}`
          }
        }
      );
      
      const result = await response.json();
      
      // Show unlock animation
      showUnlockAnimation(result);
      
      // Update points
      updatePoints(result.achievement.points);
    }
    ```
    
    **Error Handling:**
    - 400: Achievement already unlocked
    - 404: Achievement not found
    """
    achievement_service = AchievementService(db)
    user_achievement = achievement_service.unlock_achievement(
        user_id=current_user.id,
        achievement_id=achievement_id
    )
    
    return user_achievement


# ============================================
# ENDPOINT 5: GET ACHIEVEMENT ANALYTICS
# ============================================

@router.get("/analytics", response_model=dict)
async def get_achievement_analytics(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get achievement analytics and statistics
    
    **Returns:**
    - Total achievements count
    - Unlocked count and rate
    - Count by type
    - Count by difficulty
    - Recently unlocked achievements
    
    **Example Response:**
    ```json
    {
      "total_achievements": 25,
      "unlocked_count": 10,
      "locked_count": 15,
      "unlock_rate": 40.0,
      "type_counts": {
        "learning": 5,
        "streak": 3,
        "milestone": 2
      },
      "difficulty_counts": {
        "BEGINNER": 5,
        "INTERMEDIATE": 3,
        "ADVANCED": 2
      },
      "recently_unlocked": [
        {
          "achievement_id": "uuid",
          "title": "First Steps",
          "description": "Complete your first speaking exercise",
          "unlocked_at": "2024-01-05 10:30:00"
        }
      ]
    }
    ```
    
    **Use Cases:**
    1. Show achievement progress on profile
    2. Track unlock rate
    3. Identify achievement categories
    
    **Frontend Usage:**
    ```javascript
    function AchievementAnalytics() {
      const [analytics, setAnalytics] = useState(null);
      
      useEffect(() => {
        async function loadAnalytics() {
          const response = await fetch('/api/v1/achievements/analytics', {
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
          <h2>Achievement Analytics</h2>
          
          <div className="summary-cards">
            <SummaryCard 
              title="Total Achievements" 
              value={analytics.total_achievements} 
            />
            <SummaryCard 
              title="Unlocked" 
              value={analytics.unlocked_count} 
            />
            <SummaryCard 
              title="Unlock Rate" 
              value={`${analytics.unlock_rate}%`} 
            />
          </div>
          
          <TypeDistribution data={analytics.type_counts} />
          
          <DifficultyDistribution data={analytics.difficulty_counts} />
          
          <RecentUnlockList achievements={analytics.recently_unlocked} />
        </div>
      );
    }
    ```
    """
    achievement_service = AchievementService(db)
    analytics = achievement_service.get_analytics(user_id=current_user.id)
    
    return analytics
