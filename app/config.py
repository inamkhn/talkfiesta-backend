from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_NAME: str = "TalkFiesta API"
    VERSION: str = "2.0.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "postgresql://postgres:admin@localhost:5432/talkfiesta"

    # Auth
    SECRET_KEY: str = "adasdasdadasdadfds"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Google AI
    GOOGLE_AI_STUDIO_API_KEY: str = "IzaSyDUoUbXteB4GeS-XjYNAcPx4PvdW50H56w"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Storage
    AUDIO_STORAGE_DIR: str = "./storage/audio"
    
    # AWS S3
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    AWS_S3_BUCKET: str = "talkfiesta-audio-bucket"
    
    # External APIs
    OPENAI_API_KEY: str = ""

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "https://talkfiesta.com"]

    # Frontend (used in email links)
    FRONTEND_URL: str = "http://localhost:3000"

    # SMTP (leave empty to use console logging in dev)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_TLS: bool = True
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@talkfiesta.com"

    # Stripe
    STRIPE_SECRET_KEY: str = "sk_test_51PucFIBP6AViHPnpr9z2uts6IFw4ZQnOMosI38uJ3BUt2yy4kNK7CZ6sT5jnda7JKIbGsAtw1Y8QVhE2iiNtEYtx00MYwoiOc7"           # sk_live_... or sk_test_...
    STRIPE_PUBLISHABLE_KEY: str = "pk_test_51PucFIBP6AViHPnpkVKbx7eU6dsm9NfLMu3em41pwqc6bRjBn9aw92suyt8L5rI2YyNc0BbpDem0TCboldhIbyjU00daSwEx1r"      # pk_live_... or pk_test_...
    STRIPE_WEBHOOK_SECRET: str = ""       # whsec_... from Stripe Dashboard › Webhooks
    STRIPE_PRICE_BASIC_MONTHLY: str = "prod_UXtzbrxCi4ELCo"  # price_...
    STRIPE_PRICE_BASIC_ANNUAL: str = "prod_UXu2Qsoa3QtJhf"   # price_...
    STRIPE_PRICE_PRO_MONTHLY: str = "prod_UXu2IAi9fkGn1Y"    # price_...
    STRIPE_PRICE_PRO_ANNUAL: str = "prod_UXu3E5OIRWVIIZ"     # price_...
    STRIPE_SUCCESS_URL: str = "http://localhost:3000/billing/success?session_id={CHECKOUT_SESSION_ID}"
    STRIPE_CANCEL_URL: str = "http://localhost:3000/pricing"
    BILLING_RETURN_URL: str = "http://localhost:3000/account"

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings():
    return Settings()


settings = get_settings()
