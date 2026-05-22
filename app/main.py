from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api import auth, profile, plans, speaking, conversation, vocabulary, writing, progress, achievements, cycles, dashboard, billing, webhooks

app = FastAPI(
    title=settings.APP_NAME,
    description="AI-powered English learning platform. 105 days to fluency.",
    version=settings.VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
PREFIX = "/api/v1"

app.include_router(auth.router, prefix=PREFIX)
app.include_router(profile.router, prefix=PREFIX)
app.include_router(plans.router, prefix=PREFIX)
app.include_router(speaking.router, prefix=PREFIX)
app.include_router(conversation.router, prefix=PREFIX)
app.include_router(vocabulary.router, prefix=PREFIX)
app.include_router(writing.router, prefix=PREFIX)
app.include_router(progress.router, prefix=PREFIX)
app.include_router(achievements.router, prefix=PREFIX)
app.include_router(cycles.router, prefix=PREFIX)
app.include_router(dashboard.router, prefix=PREFIX)
app.include_router(billing.router, prefix=PREFIX)
# Webhook endpoint: no JWT auth — Stripe HMAC signature is the security layer
app.include_router(webhooks.router, prefix=PREFIX)


@app.get("/health", tags=["System"])
async def health():
    return {"status": "healthy", "version": settings.VERSION}
