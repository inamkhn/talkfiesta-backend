from fastapi import APIRouter
from app.api.v1.endpoints import auth

api_router = APIRouter()

# Include authentication routes
api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["Authentication"]
)

# TODO: Add more routers here as you build them
# api_router.include_router(users.router, prefix="/users", tags=["Users"])
# api_router.include_router(plans.router, prefix="/plans", tags=["Plans"])
# api_router.include_router(speaking.router, prefix="/speaking", tags=["Speaking"])
# etc.
