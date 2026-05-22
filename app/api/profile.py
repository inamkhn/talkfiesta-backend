import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.profile import ProfileResponse, ProfileStatsResponse, ProfileUpdateRequest
from app.services.profile_service import get_profile_stats, update_profile

router = APIRouter(prefix="/profile", tags=["Profile"])
logger = logging.getLogger(__name__)


@router.get("/me", response_model=ProfileResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Current user profile (extended fields for settings / dashboard)."""
    return ProfileResponse.model_validate(current_user)


@router.get("/me/stats", response_model=ProfileStatsResponse)
def get_me_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Aggregated learning stats for the current user."""
    return get_profile_stats(db, current_user)


@router.patch("/me", response_model=ProfileResponse)
def patch_me(
    data: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update editable profile fields (partial update)."""
    updated = update_profile(db, current_user, data)
    return ProfileResponse.model_validate(updated)
