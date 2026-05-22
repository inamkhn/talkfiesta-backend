"""
api/webhooks.py

Stripe webhook receiver for TalkFiesta.

Security model
──────────────
1. Signature verification (stripe.Webhook.construct_event) — BEFORE any DB work.
2. Idempotency guard via StripeWebhookEvent table (Stripe's evt_xxx as PK).
3. Always return HTTP 200 to Stripe — even on handler errors.
   Returning 4xx/5xx triggers Stripe's retry loop which can cascade.
   Handler failures are logged + stored; fix and replay via Stripe CLI or Dashboard.

IMPORTANT: This endpoint must NOT use FastAPI's default body parser.
Stripe computes the HMAC over the raw request bytes. Parsing JSON first
corrupts the bytes and breaks signature verification.
"""
import logging
from datetime import datetime

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.models.billing import StripeWebhookEvent
from app.services.webhook_service import EVENT_HANDLERS

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])
logger = logging.getLogger(__name__)

# Events we actively handle — anything else is stored as "ignored"
HANDLED_EVENTS = frozenset(EVENT_HANDLERS.keys())


@router.post(
    "/stripe",
    summary="Stripe webhook receiver",
    description=(
        "Receives and processes Stripe webhook events. "
        "This endpoint is called by Stripe — not by your frontend. "
        "It must be publicly reachable (no auth header). "
        "All requests are verified via HMAC signature before any processing."
    ),
    status_code=200,
)
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    # ── Step 1: Read raw bytes (MUST come before any JSON parsing) ────────────
    payload    = await request.body()
    sig_header = request.headers.get("stripe-signature")

    # ── Step 2: Verify Stripe HMAC signature ─────────────────────────────────
    # Never parse `payload` with json.loads() before this step.
    # Stripe signs the raw bytes; parsing first will break signature verification.
    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            settings.STRIPE_WEBHOOK_SECRET,
            # Default tolerance = 300 seconds. Do NOT set tolerance=None — replay attack risk.
        )
    except stripe.error.SignatureVerificationError:
        logger.warning(
            "Stripe webhook signature verification failed "
            f"(sig={sig_header[:30] if sig_header else 'missing'}...)"
        )
        raise HTTPException(status_code=400, detail="Invalid Stripe signature")
    except Exception as exc:
        logger.error(f"Webhook payload parse error: {exc}")
        raise HTTPException(status_code=400, detail="Malformed webhook payload")

    event_id   = event["id"]
    event_type = event["type"]
    data_obj   = event["data"]["object"]

    # ── Step 3: Idempotency check ─────────────────────────────────────────────
    # The PK is Stripe's evt_xxx — a DB unique constraint prevents duplicate inserts.
    existing = db.query(StripeWebhookEvent).filter_by(id=event_id).first()
    if existing and existing.status == "processed":
        logger.info(f"Duplicate webhook ignored: {event_id} ({event_type})")
        return {"status": "duplicate", "event_id": event_id}

    # ── Step 4: Record receipt (before any business logic) ────────────────────
    webhook_log = StripeWebhookEvent(
        id                  = event_id,
        event_type          = event_type,
        api_version         = event.get("api_version"),
        related_object_id   = data_obj.get("id"),
        related_object_type = data_obj.get("object"),
        status              = "received",
        raw_payload         = dict(event),   # full JSON for replay/debugging
        received_at         = datetime.utcnow(),
    )

    try:
        # db.merge handles both INSERT (new event) and UPDATE (retry of a failed event)
        db.merge(webhook_log)
        db.commit()
    except IntegrityError:
        # Race condition: two Stripe deliveries arrived at the exact same moment.
        # The other request won the insert race — let it handle the event.
        db.rollback()
        logger.info(f"Race condition on webhook insert — duplicate: {event_id}")
        return {"status": "duplicate", "event_id": event_id}

    # ── Step 5: Skip unhandled event types ────────────────────────────────────
    if event_type not in HANDLED_EVENTS:
        webhook_log.status = "ignored"
        db.commit()
        logger.debug(f"Unhandled event type ignored: {event_type}")
        return {"status": "ignored", "event_id": event_id}

    # ── Step 6: Dispatch to handler ───────────────────────────────────────────
    handler = EVENT_HANDLERS[event_type]
    try:
        await handler(data_obj, db)

        webhook_log.status       = "processed"
        webhook_log.processed_at = datetime.utcnow()
        db.commit()

        logger.info(f"Webhook processed: {event_id} ({event_type})")
        return {"status": "processed", "event_id": event_id}

    except Exception as exc:
        logger.error(
            f"Webhook handler error [{event_type}] event={event_id}: {exc}",
            exc_info=True,
        )
        try:
            webhook_log.status        = "failed"
            webhook_log.error_message = str(exc)
            db.commit()
        except Exception as db_exc:
            logger.error(f"Failed to record webhook error status: {db_exc}")
            db.rollback()

        # ⚠ ALWAYS return 200 on handler failure.
        # Returning 4xx/5xx causes Stripe to retry — which can cascade on a broken handler.
        # Fix the bug, then replay the event via:
        #   stripe events resend evt_xxx          (CLI)
        #   Stripe Dashboard → Webhooks → Resend  (UI)
        return {"status": "handler_error", "event_id": event_id}
