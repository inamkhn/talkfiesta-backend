"""
TalkFiesta — S3 Audio Storage Service
======================================
Handles audio file storage with two modes:

  DEV MODE  (AWS_S3_BUCKET is empty or AWS keys not set)
  → Saves files to local disk (AUDIO_STORAGE_DIR)
  → Returns a fake presigned URL pointing to a local upload endpoint
  → Zero AWS dependency for local development

  PRODUCTION MODE  (AWS keys configured)
  → Generates real S3 presigned POST URLs for direct browser upload
  → Uploads server-side audio bytes directly to S3
  → Returns real S3 object URLs
"""

import os
import uuid
import logging
from pathlib import Path
from datetime import datetime

from app.config import settings

logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_s3_configured() -> bool:
    """Return True only when all required AWS credentials are present."""
    return bool(
        settings.AWS_S3_BUCKET
        and settings.AWS_ACCESS_KEY_ID
        and settings.AWS_SECRET_ACCESS_KEY
    )


def _get_s3_client():
    """Lazy-import boto3 and return an S3 client."""
    try:
        import boto3
        return boto3.client(
            "s3",
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )
    except ImportError:
        raise RuntimeError(
            "boto3 is not installed. Run: pip install boto3"
        )


def _build_s3_key(user_id: str, filename: str) -> str:
    """Build a namespaced S3 key: audio/{user_id}/{date}/{filename}"""
    date_prefix = datetime.utcnow().strftime("%Y/%m/%d")
    return f"audio/{user_id}/{date_prefix}/{filename}"


def _ensure_local_dir() -> Path:
    """Create local audio storage directory if it doesn't exist."""
    path = Path(settings.AUDIO_STORAGE_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════════════════════

def generate_presigned_upload_url(filename: str, content_type: str = "audio/webm") -> dict:
    """
    Generate a presigned POST URL so the browser can upload audio directly
    without routing the file through the API server.

    Returns:
        {
            "url":     str   — POST target URL
            "fields":  dict  — form fields to include in the multipart POST
            "s3_key":  str   — key/path to pass back in POST /speaking/submissions
        }

    DEV:  Returns a local upload URL (POST /speaking/upload-local)
    PROD: Returns a real S3 presigned POST
    """
    if not _is_s3_configured():
        # ── Dev mode ──────────────────────────────────────────────────────────
        local_key = f"local/{uuid.uuid4().hex}_{filename}"
        logger.debug(f"[S3 DEV] Presigned URL for local storage: {local_key}")
        return {
            "url": f"{settings.FRONTEND_URL.rstrip('/')}/api/upload-local",
            "fields": {
                "key": local_key,
                "Content-Type": content_type,
            },
            "s3_key": local_key,
        }

    # ── Production mode ───────────────────────────────────────────────────────
    s3 = _get_s3_client()
    s3_key = filename  # caller already built the full key

    try:
        presigned = s3.generate_presigned_post(
            Bucket=settings.AWS_S3_BUCKET,
            Key=s3_key,
            Fields={"Content-Type": content_type},
            Conditions=[
                {"Content-Type": content_type},
                ["content-length-range", 1000, 10 * 1024 * 1024],  # 1 KB – 10 MB
            ],
            ExpiresIn=300,  # 5 minutes
        )
        logger.info(f"[S3] Generated presigned POST for key: {s3_key}")
        return {
            "url": presigned["url"],
            "fields": presigned["fields"],
            "s3_key": s3_key,
        }
    except Exception:
        logger.exception(f"[S3] Failed to generate presigned URL for {s3_key}")
        raise


def upload_audio(audio_bytes: bytes, user_id: str, content_type: str = "audio/webm") -> str:
    """
    Upload raw audio bytes from the server side (used by Celery worker or
    direct-upload fallback).

    Returns the storage path/key that gets saved in SpeakingSubmission.audio_file_path.

    DEV:  Saves to local disk, returns relative file path.
    PROD: Uploads to S3, returns the full S3 URL.
    """
    ext = content_type.split("/")[-1].replace("webm", "webm")
    filename = f"{uuid.uuid4().hex}.{ext}"

    if not _is_s3_configured():
        # ── Dev mode ──────────────────────────────────────────────────────────
        storage_dir = _ensure_local_dir() / user_id
        storage_dir.mkdir(parents=True, exist_ok=True)
        file_path = storage_dir / filename

        with open(file_path, "wb") as f:
            f.write(audio_bytes)

        logger.info(f"[S3 DEV] Audio saved locally: {file_path}")
        return str(file_path)

    # ── Production mode ───────────────────────────────────────────────────────
    s3 = _get_s3_client()
    s3_key = _build_s3_key(user_id, filename)

    try:
        s3.put_object(
            Bucket=settings.AWS_S3_BUCKET,
            Key=s3_key,
            Body=audio_bytes,
            ContentType=content_type,
        )
        s3_url = f"https://{settings.AWS_S3_BUCKET}.s3.{settings.AWS_REGION}.amazonaws.com/{s3_key}"
        logger.info(f"[S3] Audio uploaded: {s3_url}")
        return s3_url
    except Exception:
        logger.exception(f"[S3] Failed to upload audio for user {user_id}")
        raise


def get_audio_bytes(file_path_or_key: str) -> bytes:
    """
    Download audio bytes for processing by the Celery worker.

    DEV:  Reads from local disk.
    PROD: Downloads from S3.
    """
    if not _is_s3_configured():
        # ── Dev mode ──────────────────────────────────────────────────────────
        path = Path(file_path_or_key)
        if not path.exists():
            raise FileNotFoundError(f"Local audio file not found: {file_path_or_key}")
        with open(path, "rb") as f:
            return f.read()

    # ── Production mode ───────────────────────────────────────────────────────
    # Strip the full URL to get just the key
    s3_key = file_path_or_key
    if file_path_or_key.startswith("https://"):
        # e.g. https://bucket.s3.region.amazonaws.com/audio/user/...
        s3_key = "/".join(file_path_or_key.split("/")[3:])

    s3 = _get_s3_client()
    try:
        response = s3.get_object(Bucket=settings.AWS_S3_BUCKET, Key=s3_key)
        return response["Body"].read()
    except Exception:
        logger.exception(f"[S3] Failed to download audio: {s3_key}")
        raise


def delete_audio(file_path_or_key: str) -> None:
    """
    Delete an audio file (used for cleanup after processing or retention policy).

    DEV:  Deletes from local disk.
    PROD: Deletes from S3.
    """
    if not _is_s3_configured():
        path = Path(file_path_or_key)
        if path.exists():
            path.unlink()
            logger.info(f"[S3 DEV] Deleted local audio: {file_path_or_key}")
        return

    s3_key = file_path_or_key
    if file_path_or_key.startswith("https://"):
        s3_key = "/".join(file_path_or_key.split("/")[3:])

    s3 = _get_s3_client()
    try:
        s3.delete_object(Bucket=settings.AWS_S3_BUCKET, Key=s3_key)
        logger.info(f"[S3] Deleted S3 object: {s3_key}")
    except Exception:
        logger.exception(f"[S3] Failed to delete audio: {s3_key}")
        raise
