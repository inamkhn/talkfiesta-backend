"""
services/webhook_service.py

Individual Stripe webhook event handlers.
Each handler is a pure async function that receives the Stripe event data
object and a DB session — no HTTP concerns here.

All handlers are idempotent: safe to call more than once for the same event.
The router's idempotency guard (StripeWebhookEvent table) prevents double-
processing under normal conditions; these handlers are the last line of defence.
"""
import logging
from datetime import datetime
from typing import Callable

import stripe
from sqlalchemy.orm import Session

from app.models.billing import (
    StripeCustomer,
    StripeSubscription,
    StripePaymentRecord,
    StripeCheckoutSession,
)
from app.services.billing_service import resolve_plan_from_price_id, check_trial_eligibility

logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ts(epoch: int | None) -> datetime | None:
    """Convert a Stripe Unix timestamp to a UTC datetime (or None)."""
    return datetime.utcfromtimestamp(epoch) if epoch else None


def _resolve_payment_type(invoice: dict) -> str:
    """
    Detect the real reason for this invoice.

    billing_reason values from Stripe:
      subscription_create  → first invoice when subscription is created
      subscription_cycle   → regular renewal
      subscription_update  → plan change / proration
      manual               → manually created invoice

    Bug fix (from review): original logic was inverted.
      - amount_paid == 0  → trial just started, nothing charged → "subscription"
      - amount_paid  > 0  → real first charge (immediate or trial conversion) → "trial_conversion"
    """
    billing_reason = invoice.get("billing_reason", "")
    if billing_reason == "subscription_cycle":
        return "subscription"
    if billing_reason == "subscription_create":
        # $0 = trial started (nothing charged yet); >$0 = immediate first charge
        return "trial_conversion" if invoice.get("amount_paid", 0) > 0 else "subscription"
    return "subscription"


# ── Handler: checkout.session.completed ──────────────────────────────────────

async def handle_checkout_completed(session: dict, db: Session) -> None:
    """
    Fired when the user successfully completes the Stripe-hosted checkout page.

    This handler does two things:
      1. Marks the local checkout session record as completed.
      2. Enforces cross-account trial abuse prevention:
         - Fetches the card fingerprint from Stripe via the payment_method.
         - Stores it on the user's StripeCustomer row.
         - If that fingerprint already exists on ANOTHER account:
             → Cancel the trial period immediately (update subscription to
               remove trial so Stripe charges on the next cycle).

    Note: Stripe does not include the fingerprint in the webhook payload
    directly — we fetch it via the payment_method ID.
    """
    stripe_session_id = session["id"]
    user_id = session.get("metadata", {}).get("user_id")

    if not user_id:
        raise ValueError(
            f"checkout.session.completed missing user_id in metadata: {stripe_session_id}"
        )

    # ── Mark local checkout record completed ──────────────────────────────────
    checkout = db.query(StripeCheckoutSession).filter_by(
        stripe_session_id=stripe_session_id
    ).first()
    if checkout:
        checkout.status = "completed"
        checkout.completed_at = datetime.utcnow()
        checkout.stripe_subscription_id = session.get("subscription")
        db.commit()

    logger.info(f"Checkout session {stripe_session_id} marked completed for user {user_id}")

    # ── Card fingerprint: fetch and enforce trial eligibility ─────────────────
    payment_method_id = session.get("payment_method")
    if not payment_method_id:
        # No payment method on session (e.g. pure trial start with no card yet)
        logger.debug(f"No payment_method on session {stripe_session_id} — skipping fingerprint check")
        return

    try:
        pm = stripe.PaymentMethod.retrieve(payment_method_id)
        fingerprint = pm.get("card", {}).get("fingerprint")
    except stripe.error.StripeError as e:
        logger.error(f"Failed to retrieve payment method {payment_method_id}: {e}")
        return

    if not fingerprint:
        logger.debug(f"No card fingerprint on payment method {payment_method_id}")
        return

    # Store fingerprint on the StripeCustomer row for this user
    stripe_customer = db.query(StripeCustomer).filter_by(
        stripe_customer_id=session["customer"]
    ).first()
    if stripe_customer and not stripe_customer.card_fingerprint:
        stripe_customer.card_fingerprint = fingerprint
        db.commit()
        logger.info(f"Card fingerprint stored for user {user_id}: {fingerprint[:8]}...")

    # Cross-account trial abuse check
    trial_eligible = check_trial_eligibility(fingerprint, db)
    if not trial_eligible:
        # This card already had a free trial on a different account.
        # Cancel the trial period so Stripe will charge immediately.
        subscription_id = session.get("subscription")
        if subscription_id:
            try:
                stripe.Subscription.modify(
                    subscription_id,
                    trial_end="now",   # End the trial immediately
                )
                logger.warning(
                    f"Trial cancelled for user {user_id} — "
                    f"card fingerprint {fingerprint[:8]}... already used on another account"
                )
            except stripe.error.StripeError as e:
                logger.error(
                    f"Failed to cancel trial for subscription {subscription_id}: {e}"
                )


# ── Handler: customer.subscription.created / updated ─────────────────────────

async def handle_subscription_upsert(sub: dict, db: Session) -> None:
    """
    Handles both subscription creation and any update (plan change, renewal,
    trial end, pause, cancel_at_period_end toggle).

    Safe to call multiple times — always syncs to the latest Stripe state.
    """
    stripe_customer_id = sub["customer"]
    stripe_customer = db.query(StripeCustomer).filter_by(
        stripe_customer_id=stripe_customer_id
    ).first()

    if not stripe_customer:
        raise ValueError(
            f"customer.subscription event for unknown Stripe customer: {stripe_customer_id}"
        )

    user_id = stripe_customer.user_id

    price_id = sub["items"]["data"][0]["price"]["id"]
    plan_meta = resolve_plan_from_price_id(price_id)
    if not plan_meta:
        raise ValueError(
            f"Unknown Stripe price ID in subscription {sub['id']}: {price_id}"
        )

    existing = db.query(StripeSubscription).filter_by(
        stripe_subscription_id=sub["id"]
    ).first()

    fields = dict(
        status                   = sub["status"],
        stripe_price_id          = price_id,
        plan_tier                = plan_meta["plan_tier"],
        billing_interval         = plan_meta["billing_interval"],
        amount_cents             = plan_meta["amount_cents"],
        trial_start              = _ts(sub.get("trial_start")),
        trial_end                = _ts(sub.get("trial_end")),
        current_period_start     = _ts(sub["current_period_start"]),
        current_period_end       = _ts(sub["current_period_end"]),
        cancel_at_period_end     = sub["cancel_at_period_end"],
        canceled_at              = _ts(sub.get("canceled_at")),
        stripe_latest_invoice_id = sub.get("latest_invoice"),
        stripe_metadata          = sub.get("metadata"),
        pause_collection         = sub.get("pause_collection"),
        updated_at               = datetime.utcnow(),
    )

    if existing:
        for k, v in fields.items():
            setattr(existing, k, v)
    else:
        new_sub = StripeSubscription(
            user_id=user_id,
            stripe_subscription_id=sub["id"],
            stripe_customer_id=stripe_customer_id,
            currency=sub.get("currency", "usd"),
            **fields,
        )
        db.add(new_sub)

    db.commit()
    logger.info(
        f"Subscription {sub['id']} upserted — status={sub['status']} "
        f"plan={plan_meta['plan_tier']} user={user_id}"
    )


# ── Handler: customer.subscription.deleted ────────────────────────────────────

async def handle_subscription_deleted(sub: dict, db: Session) -> None:
    """
    Fired when a subscription has fully ended.
    At this point access MUST be revoked.
    """
    existing = db.query(StripeSubscription).filter_by(
        stripe_subscription_id=sub["id"]
    ).first()

    if not existing:
        logger.warning(f"subscription.deleted for unknown sub: {sub['id']}")
        return

    # Bug fix: read actual canceled_at from Stripe, fall back to now()
    existing.status      = "canceled"
    existing.canceled_at = _ts(sub.get("canceled_at")) or datetime.utcnow()
    existing.ended_at    = _ts(sub.get("ended_at")) or datetime.utcnow()
    existing.updated_at  = datetime.utcnow()
    db.commit()

    logger.info(f"Subscription {sub['id']} canceled for user {existing.user_id}")
    await _on_subscription_ended(existing.user_id, db)


# ── Handler: customer.subscription.trial_will_end ─────────────────────────────

async def handle_trial_ending(sub: dict, db: Session) -> None:
    """
    Fired 3 days before a trial ends.
    Send the user a reminder email.
    """
    stripe_customer = db.query(StripeCustomer).filter_by(
        stripe_customer_id=sub["customer"]
    ).first()

    if not stripe_customer:
        logger.warning(f"trial_will_end for unknown customer: {sub['customer']}")
        return

    trial_end = _ts(sub.get("trial_end"))
    logger.info(
        f"Trial ending soon for user {stripe_customer.user_id} "
        f"(trial_end={trial_end})"
    )
    # TODO: plug in your email service here
    # await send_trial_ending_email(stripe_customer.user_id, trial_end)


# ── Handler: invoice.payment_succeeded ───────────────────────────────────────

async def handle_payment_succeeded(invoice: dict, db: Session) -> None:
    """
    Fired on every successful charge.

    Edge case: Stripe fires this with amount_paid=0 when a trial starts.
    We skip those so billing history only shows real charges.
    """
    # Skip $0 trial-start invoices (bug fix from review)
    if invoice.get("amount_paid", 0) == 0:
        logger.debug(f"Skipping $0 invoice {invoice['id']} (trial start)")
        return

    stripe_customer = db.query(StripeCustomer).filter_by(
        stripe_customer_id=invoice["customer"]
    ).first()
    if not stripe_customer:
        raise ValueError(f"invoice.payment_succeeded for unknown customer: {invoice['customer']}")

    # Idempotency: skip if already recorded
    existing = db.query(StripePaymentRecord).filter_by(
        stripe_invoice_id=invoice["id"]
    ).first()
    if existing:
        logger.debug(f"Payment record for invoice {invoice['id']} already exists — skipping")
        return

    subscription = db.query(StripeSubscription).filter_by(
        stripe_subscription_id=invoice.get("subscription")
    ).first()

    record = StripePaymentRecord(
        user_id                  = stripe_customer.user_id,
        subscription_id          = subscription.id if subscription else None,
        stripe_invoice_id        = invoice["id"],
        stripe_payment_intent_id = invoice.get("payment_intent"),
        stripe_charge_id         = invoice.get("charge"),
        amount_cents             = invoice["amount_paid"],
        currency                 = invoice.get("currency", "usd"),
        status                   = "paid",
        payment_type             = _resolve_payment_type(invoice),
        period_start             = _ts(invoice.get("period_start")),
        period_end               = _ts(invoice.get("period_end")),
        invoice_pdf_url          = invoice.get("invoice_pdf"),
    )
    db.add(record)

    # Reset past_due → active on successful payment
    if subscription and subscription.status == "past_due":
        subscription.status     = "active"
        subscription.updated_at = datetime.utcnow()
        logger.info(f"Subscription {subscription.stripe_subscription_id} reset past_due → active")

    db.commit()
    logger.info(
        f"Payment succeeded: invoice {invoice['id']} "
        f"${invoice['amount_paid'] / 100:.2f} for user {stripe_customer.user_id}"
    )


# ── Handler: invoice.payment_failed ──────────────────────────────────────────

async def handle_payment_failed(invoice: dict, db: Session) -> None:
    """
    Fired when a charge attempt fails.
    Marks the subscription past_due and records the failure.
    """
    stripe_customer = db.query(StripeCustomer).filter_by(
        stripe_customer_id=invoice["customer"]
    ).first()
    if not stripe_customer:
        logger.warning(f"invoice.payment_failed for unknown customer: {invoice['customer']}")
        return

    # Bug fix (from review): resolve subscription for failed records too
    subscription = db.query(StripeSubscription).filter_by(
        stripe_subscription_id=invoice.get("subscription")
    ).first()

    existing = db.query(StripePaymentRecord).filter_by(
        stripe_invoice_id=invoice["id"]
    ).first()

    # Bug fix: last_finalization_error is for draft failures, not payment failures.
    # The correct field for payment decline reasons is last_payment_error,
    # which lives on the PaymentIntent — fetch it directly.
    failure_code = None
    failure_message = None
    payment_intent_id = invoice.get("payment_intent")
    if payment_intent_id:
        try:
            pi = stripe.PaymentIntent.retrieve(payment_intent_id)
            last_error = pi.get("last_payment_error") or {}
            failure_code    = last_error.get("code")
            failure_message = last_error.get("message")
        except stripe.error.StripeError as e:
            logger.warning(f"Could not retrieve PaymentIntent {payment_intent_id}: {e}")

    if existing:
        existing.status          = "failed"
        existing.failure_code    = failure_code
        existing.failure_message = failure_message
    else:
        record = StripePaymentRecord(
            user_id           = stripe_customer.user_id,
            subscription_id   = subscription.id if subscription else None,
            stripe_invoice_id = invoice["id"],
            amount_cents      = invoice.get("amount_due", 0),
            currency          = invoice.get("currency", "usd"),
            status            = "failed",
            payment_type      = _resolve_payment_type(invoice),
            failure_code      = failure_code,
            failure_message   = failure_message,
        )
        db.add(record)

    # Mark subscription past_due
    if subscription and subscription.status == "active":
        subscription.status     = "past_due"
        subscription.updated_at = datetime.utcnow()
        logger.info(f"Subscription {subscription.stripe_subscription_id} marked past_due")

    db.commit()
    logger.warning(
        f"Payment failed: invoice {invoice['id']} "
        f"for user {stripe_customer.user_id} — {last_error.get('code', 'unknown error')}"
    )
    # TODO: plug in your email service here
    # await send_payment_failed_email(stripe_customer.user_id, invoice)


# ── Handler: invoice.finalized ────────────────────────────────────────────────

async def handle_invoice_finalized(invoice: dict, db: Session) -> None:
    """
    Fired when an invoice is finalised by Stripe.
    Store the PDF URL so users can download their receipts.
    """
    pdf_url = invoice.get("invoice_pdf")
    if not pdf_url:
        return

    record = db.query(StripePaymentRecord).filter_by(
        stripe_invoice_id=invoice["id"]
    ).first()

    if record:
        record.invoice_pdf_url = pdf_url
        db.commit()
        logger.debug(f"invoice_pdf_url stored for invoice {invoice['id']}")


# ── Handler: charge.refunded ──────────────────────────────────────────────────

async def handle_charge_refunded(charge: dict, db: Session) -> None:
    """
    Fired when a refund is issued (full or partial).
    Updates the payment record status and refund amounts.
    """
    record = db.query(StripePaymentRecord).filter_by(
        stripe_charge_id=charge["id"]
    ).first()

    if not record:
        logger.warning(f"charge.refunded for unknown charge: {charge['id']}")
        return

    amount_refunded = charge.get("amount_refunded", 0)
    fully_refunded  = charge.get("refunded", False)

    record.amount_refunded_cents = amount_refunded
    record.refunded_at           = datetime.utcnow()
    record.status = "refunded" if fully_refunded else "partially_refunded"

    db.commit()
    logger.info(
        f"Charge {charge['id']} refunded "
        f"${amount_refunded / 100:.2f} ({'full' if fully_refunded else 'partial'})"
    )


# ── Handler: customer.updated ─────────────────────────────────────────────────

async def handle_customer_updated(customer: dict, db: Session) -> None:
    """
    Fired when customer data changes in Stripe (e.g. email update from portal).
    Sync email back to our StripeCustomer record.
    """
    stripe_customer = db.query(StripeCustomer).filter_by(
        stripe_customer_id=customer["id"]
    ).first()

    if not stripe_customer:
        logger.debug(f"customer.updated for unknown customer: {customer['id']}")
        return

    new_email = customer.get("email")
    if new_email and new_email != stripe_customer.email_at_creation:
        stripe_customer.email_at_creation = new_email
        db.commit()
        logger.info(f"Synced email from Stripe for customer {customer['id']} → {new_email}")


# ── Post-cancellation hook ────────────────────────────────────────────────────

async def _on_subscription_ended(user_id: str, db: Session) -> None:
    """
    Called after a subscription is fully canceled.
    Hook in any cleanup you need: feature downgrade, send email, etc.
    """
    logger.info(f"Subscription ended for user {user_id} — running post-cancel hooks")
    # TODO: send cancellation confirmation email
    # TODO: downgrade user features / reset premium flags


# ── Dispatch map ──────────────────────────────────────────────────────────────

EVENT_HANDLERS: dict[str, Callable] = {
    "checkout.session.completed":           handle_checkout_completed,
    "customer.subscription.created":        handle_subscription_upsert,
    "customer.subscription.updated":        handle_subscription_upsert,
    "customer.subscription.deleted":        handle_subscription_deleted,
    "customer.subscription.trial_will_end": handle_trial_ending,
    "invoice.payment_succeeded":            handle_payment_succeeded,
    "invoice.payment_failed":               handle_payment_failed,
    "invoice.finalized":                    handle_invoice_finalized,
    "charge.refunded":                      handle_charge_refunded,
    "customer.updated":                     handle_customer_updated,
}
