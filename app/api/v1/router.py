from fastapi import APIRouter
from app.api.v1.endpoints import auth, google_oauth, profile, plans, progress, speaking, vocabulary, writing, achievements, cycles, admin

api_router = APIRouter()

# Include authentication routes
api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["Authentication"]
)

# Include Google OAuth routes
api_router.include_router(
    google_oauth.router,
    prefix="/auth/google",
    tags=["Google OAuth"]
)

# Include profile routes
api_router.include_router(
    profile.router,
    prefix="/profile",
    tags=["User Profile"]
)

# Include plans routes
api_router.include_router(
    plans.router,
    prefix="/plans",
    tags=["User Plans"]
)

# Include progress routes
api_router.include_router(
    progress.router,
    prefix="/progress",
    tags=["Progress & Analytics"]
)

# Include speaking routes
api_router.include_router(
    speaking.router,
    prefix="/speaking",
    tags=["Speaking Module"]
)

# Include vocabulary routes
api_router.include_router(
    vocabulary.router,
    prefix="/vocabulary",
    tags=["Vocabulary Module"]
)

# Include writing routes
api_router.include_router(
    writing.router,
    prefix="/writing",
    tags=["Writing Module"]
)

# Include achievements routes
api_router.include_router(
    achievements.router,
    prefix="/achievements",
    tags=["Achievements Module"]
)

# Include cycles routes
api_router.include_router(
    cycles.router,
    prefix="/cycles",
    tags=["Cycles Module"]
)

# Include admin routes
api_router.include_router(
    admin.router,
    prefix="/admin",
    tags=["Admin"]
)
