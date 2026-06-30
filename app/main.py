from app.core.logging_config import setup_logging
setup_logging()

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from slowapi.middleware import SlowAPIMiddleware
from slowapi.errors import RateLimitExceeded
from asgi_correlation_id import CorrelationIdMiddleware
from app.config import settings
from app.core.rate_limiter import limiter
from app.core.middleware import ContentSizeLimitMiddleware, SecurityHeadersMiddleware
from app.core.lifespan import lifespan
from prometheus_fastapi_instrumentator import Instrumentator
from app.api import auth, profile, plans, speaking, conversation, vocabulary, writing, progress, achievements, cycles, dashboard, billing, webhooks

def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """
    Custom exception handler for RateLimitExceeded exceptions, conforming to RFC 7807.
    """
    response_body = {
        "type": "https://talkfiesta.com/errors/rate-limit-exceeded",
        "title": "Rate Limit Exceeded",
        "status": 429,
        "detail": f"Rate limit exceeded: {exc.detail}. Please try again later.",
        "instance": request.url.path,
    }
    headers = {}
    if hasattr(exc, "retry_after") and exc.retry_after:
        headers["Retry-After"] = str(exc.retry_after)
    return JSONResponse(
        status_code=429,
        content=response_body,
        headers=headers
    )

app = FastAPI(
    title=settings.APP_NAME,
    description="AI-powered English learning platform. 105 days to fluency.",
    version=settings.VERSION,
    lifespan=lifespan,
)

# Attach limiter to app state and register custom handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(ContentSizeLimitMiddleware, max_content_size=15 * 1024 * 1024)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)

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


# Instrument the FastAPI app and expose standard /metrics Prometheus endpoint
Instrumentator().instrument(app).expose(app)
