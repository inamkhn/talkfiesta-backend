from celery import Celery
from app.config import settings

celery_app = Celery(
    "talkfiesta_tasks",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.workers.speaking_tasks",
        "app.services.vocabulary_generator",
        "app.services.writing_generator",
        "app.services.speaking_generator",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=50,
    task_time_limit=60,
    result_expires=3600,
    task_routes={
        "speaking.process_audio": {"queue": "audio_processing"},
        "app.services.vocabulary_generator.generate_cycle_vocabulary": {"queue": "ai_generation"},
        "app.services.writing_generator.generate_cycle_writing_prompts": {"queue": "ai_generation"},
        "app.services.speaking_generator.generate_cycle_speaking_exercises": {"queue": "ai_generation"},
    },
)
