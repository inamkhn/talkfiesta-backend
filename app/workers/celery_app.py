"""
TalkFiesta — Celery Application
================================
Re-export of the canonical Celery instance from app.core.celery_app.
Import this wherever you need to register or call tasks.
"""
from app.core.celery_app import celery_app
