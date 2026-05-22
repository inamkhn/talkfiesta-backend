"""
services/billing_service.py

All Stripe business logic lives here, not in the router.
This keeps the router thin and lets webhook handlers reuse the same functions.
"""
import logging
from datetime import datetime, timedelta

import stripe
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.models.billing import (
    StripeCustomer,
    StripeSubscription,
    StripePaymentRecord,
    StripeCheckoutSession,
    has_active_access,
)

logger = logging.getLogger(__name__)


# ── Stripe SDK initialisation ─────────────────────────────────────────────────

def _init_stripe() -> None:
    """Set the Stripe API key lazily so settings are always fully loaded first."""
    stripe.api_key = settings.STRIPE_SECRET_KEY


# ── Plan catalogue ────────────────────────────────────────────────────────────
# Bug fix: plan dict is built lazily via _get_plans() instead of at module
# import time.  Reading settings.STRIPE_PRICE_* at import time can freeze
# empty strings before .env is loaded, making all price IDs permanently wrong.

def _get_plans() -> dict[str, dict]:
    return {
        "basic_month": {
            "stripe_price_id":  settings.STRIPE_PRICE_BASIC_MONTHLY,
            "plan_tier":        "basic",
            "billing_interval": "month",
            "amount_cents":     499,
            "display_name":     "Basic Monthly",
            "trial_days":       7,
        },
        "basic_year": {
            "stripe_price_id":  settings.STRIPE_PRICE_BASIC_ANNUAL,
            "plan_tier":        "basic",
            "billing_interval": "year",
            "amount_cents":     3999,
            "display_name":     "Basic Annual",
            "trial_days":       7,
        },
        "pro_month": {
            "stripe_price_id":  settings.STRIPE_PRICE_PRO_MONTHLY,
            "plan_tier":        "pro",
            "billing_interval": "month",
            "amount_cents":     999,
            "display_name":     "Pro Monthly",
            "trial_days":       7,
        },
        "pro_year": {
            "stripe_price_id":  settings.STRIPE_PRICE_PRO_ANNUAL,
            "plan_tier":        "pro",
            "billing_interval": "year",
            "amount_cents":     7999,
            "display_name":     "Pro Annual",
            "trial_days":       7,
        },
    }


def resolve_plan_from_price_id(price_id: str) -> dict | None:
    """Reverse-lookup a plan dict by its Stripe price ID."""
    for plan in _get_plans().values():
        if plan["stripe_price_id"] == price_id:
            return plan
    return None


def get_plan_keys() -> list[dict]:
    """Return displayable plan information for the pricing page."""
    return [
        {
            "key":              key,
            "display_name":     plan["display_name"],
            "plan_tier":        plan["plan_tier"],
            "billing_interval": plan["billing_interval"],
            "amount_cents":     plan["amount_cents"],
            "trial_days":       plan["trial_days"],
        }
        for key, plan in _get_plans().items()
    ]


# ── Customer helpers ──────────────────────────────────────────────────────────

def _get_or_create_stripe_customer(user: User, db: Session) -> StripeCustomer:
    """
    Returns the existing StripeCustomer row, or creates one in both Stripe
    and the local DB.  Also populates user.stripe_customer_id_cache.
    """
    existing = db.query(StripeCustomer).filter_by(user_id=user.id).first()
    if existing:
        return existing

    cus = stripe.Customer.create(
        email=user.email,
        name=user.full_name or user.username,
        metadata={"user_id": str(user.id)},
    )
    stripe_customer = StripeCustomer(
        user_id=user.id,
        stripe_customer_id=cus["id"],
        email_at_creation=user.email,
    )
    db.add(stripe_customer)
    db.flush()  # persist before writing the cache column

    user.stripe_customer_id_cache = cus["id"]
    db.commit()
    db.refresh(stripe_customer)
    logger.info(f"Created Stripe customer {cus['id']} for user {user.id}")
    return stripe_customer


def check_trial_eligibility(card_fingerprint: str | None, db: Session) -> bool:
    """
    Returns True if this card fingerprint has NEVER been used for a free trial
    across ANY account in the system.

    How it works:
      Stripe assigns a stable `fingerprint` to every unique card number.
      This fingerprint persists even if the user creates a new Stripe customer
      object (i.e. registers a new TalkFiesta account). By storing the
      fingerprint on StripeCustomer when checkout completes, we can detect
      when a different user account presents the same physical card.

    Called in create_checkout_session() before Stripe is contacted.
    If the fingerprint is already in the DB → deny trial, allow subscription
    without trial_period_days.

    Returns False (trial denied) if the card was already used anywhere.
    Returns True  (trial allowed) if the card is new to the system.
    """
    if not card_fingerprint:
        # No fingerprint provided — allow trial (cannot verify without it)
        return True

    existing = db.query(StripeCustomer).filter(
        StripeCustomer.card_fingerprint == card_fingerprint
    ).first()

    if existing:
        logger.warning(
            f"Trial denied: card fingerprint {card_fingerprint[:8]}... "
            f"already used by user {existing.user_id}"
        )
        return False

    return True


# ── Checkout session ──────────────────────────────────────────────────────────

def create_checkout_session(user: User, plan_key: str, db: Session) -> str:
    """
    Create a Stripe-hosted checkout session and record it locally.
    Returns the Stripe checkout URL to redirect the user to.

    Trial abuse prevention (card fingerprint):
      - If this user's StripeCustomer already has a stored card_fingerprint,
        they've previously completed checkout on this account → no trial.
      - Cross-account detection (same card, different account) is enforced
        inside the checkout.session.completed webhook handler, which has
        access to the actual card fingerprint for the first time.

    Raises:
        HTTPException 400 — unknown plan key
        HTTPException 409 — user already has an active subscription
    """
    _init_stripe()
    plans = _get_plans()

    plan = plans.get(plan_key)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown plan key: '{plan_key}'. "
                   f"Valid options: {list(plans.keys())}",
        )

    # Prevent double-billing
    existing_sub = db.query(StripeSubscription).filter(
        StripeSubscription.user_id == user.id,
        StripeSubscription.status.in_(["trialing", "active"]),
    ).first()
    if existing_sub:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code":    "subscription_already_active",
                "message": "You already have an active subscription.",
                "plan":    existing_sub.plan_tier,
            },
        )

    stripe_customer = _get_or_create_stripe_customer(user, db)

    # Trial eligibility: if this user already has a fingerprint stored,
    # they've used a trial on this account before → no trial this time.
    user_eligible_for_trial = not bool(stripe_customer.card_fingerprint)
    trial_days = plan["trial_days"] if user_eligible_for_trial else 0

    if not user_eligible_for_trial:
        logger.info(
            f"Trial suppressed for user {user.id}: "
            f"card fingerprint already on file for this account"
        )

    subscription_data: dict = {
        "metadata": {
            "plan_tier": plan["plan_tier"],
            "user_id":   str(user.id),
            "plan_key":  plan_key,
        },
    }
    if trial_days > 0:
        subscription_data["trial_period_days"] = trial_days

    session = stripe.checkout.Session.create(
        customer=stripe_customer.stripe_customer_id,
        mode="subscription",
        line_items=[{"price": plan["stripe_price_id"], "quantity": 1}],
        subscription_data=subscription_data,
        metadata={
            "user_id":             str(user.id),
            "plan_key":            plan_key,
            "trial_eligible":      str(user_eligible_for_trial).lower(),
        },
        success_url=settings.STRIPE_SUCCESS_URL,
        cancel_url=settings.STRIPE_CANCEL_URL,
        allow_promotion_codes=True,
        expires_at=int((datetime.utcnow() + timedelta(hours=24)).timestamp()),
    )

    checkout_record = StripeCheckoutSession(
        user_id=user.id,
        stripe_session_id=session["id"],
        stripe_price_id=plan["stripe_price_id"],
        plan_tier=plan["plan_tier"],
        billing_interval=plan["billing_interval"],
        plan_key=plan_key,
        status="pending",
        expires_at=datetime.utcfromtimestamp(session["expires_at"]),
    )
    db.add(checkout_record)
    db.commit()

    logger.info(f"Checkout session {session['id']} created for user {user.id} / {plan_key}")
    return session["url"]


# ── Billing portal ────────────────────────────────────────────────────────────

def create_portal_session(user: User, db: Session) -> str:
    """
    Create a Stripe Billing Portal session so the user can self-serve:
    update card, cancel, switch plan, download invoices.
    Returns the portal URL.

    Raises:
        HTTPException 404 — user has never started checkout (no Stripe customer)
    """
    _init_stripe()

    stripe_customer = db.query(StripeCustomer).filter_by(user_id=user.id).first()
    if not stripe_customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code":    "no_billing_account",
                "message": "No billing account found. Please start a subscription first.",
            },
        )

    portal = stripe.billing_portal.Session.create(
        customer=stripe_customer.stripe_customer_id,
        return_url=settings.BILLING_RETURN_URL,
    )
    logger.info(f"Billing portal session created for user {user.id}")
    # Use dict-style access (consistent with all other Stripe object access in this file)
    return portal["url"]


# ── Subscription status ───────────────────────────────────────────────────────

def get_subscription_status(user: User, db: Session) -> dict:
    """
    Returns the current subscription state for the authenticated user.
    Safe to call on every app load to decide what features to show.
    """
    sub = (
        db.query(StripeSubscription)
        .filter(StripeSubscription.user_id == user.id)
        .order_by(StripeSubscription.created_at.desc())
        .first()
    )

    if not sub:
        return {
            "has_subscription":     False,
            "has_access":           False,
            "status":               None,
            "plan_tier":            None,
            "billing_interval":     None,
            "trial_end":            None,
            "current_period_end":   None,
            "cancel_at_period_end": False,
        }

    return {
        "has_subscription":     True,
        "has_access":           has_active_access(sub),
        "status":               sub.status,
        "plan_tier":            sub.plan_tier,
        "billing_interval":     sub.billing_interval,
        "amount_cents":         sub.amount_cents,
        "currency":             sub.currency,
        "trial_end":            sub.trial_end.isoformat() if sub.trial_end else None,
        "current_period_start": sub.current_period_start.isoformat(),
        "current_period_end":   sub.current_period_end.isoformat(),
        "cancel_at_period_end": sub.cancel_at_period_end,
        "canceled_at":          sub.canceled_at.isoformat() if sub.canceled_at else None,
    }


# ── Payment history ───────────────────────────────────────────────────────────

def get_payment_history(user: User, db: Session, limit: int = 20) -> list[dict]:
    """
    Returns a list of the user's past payment records (most recent first).
    Filters out $0 trial-start invoices so only real charges appear.
    """
    records = (
        db.query(StripePaymentRecord)
        .filter(
            StripePaymentRecord.user_id == user.id,
            StripePaymentRecord.amount_cents > 0,   # exclude $0 trial-start invoices
        )
        .order_by(StripePaymentRecord.created_at.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "id":              r.id,
            "amount_cents":    r.amount_cents,
            "currency":        r.currency,
            "status":          r.status,
            "payment_type":    r.payment_type,
            "period_start":    r.period_start.isoformat() if r.period_start else None,
            "period_end":      r.period_end.isoformat() if r.period_end else None,
            "invoice_pdf_url": r.invoice_pdf_url,
            "created_at":      r.created_at.isoformat(),
        }
        for r in records
    ]


# ── Email sync ────────────────────────────────────────────────────────────────

def sync_stripe_email(user: User, new_email: str, db: Session) -> None:
    """
    Call this whenever a user changes their email in TalkFiesta so Stripe
    stays in sync and receipts reach the right inbox.
    """
    _init_stripe()
    stripe_customer = db.query(StripeCustomer).filter_by(user_id=user.id).first()
    if stripe_customer:
        stripe.Customer.modify(
            stripe_customer.stripe_customer_id,
            email=new_email,
        )
        stripe_customer.email_at_creation = new_email
        db.commit()
        logger.info(f"Synced Stripe email for user {user.id} → {new_email}")


# ── Subscription access guard (dependency factory) ────────────────────────────

def require_subscription(minimum_tier: str = "basic"):
    """
    FastAPI dependency factory. Protects routes behind a subscription tier check.

    Usage:
        @router.get("/pro-feature", dependencies=[Depends(require_subscription("pro"))])

    Raises:
        402 — no active subscription
        403 — subscription tier is too low
    """
    TIER_RANK = {"basic": 1, "pro": 2}

    async def _guard(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        sub = (
            db.query(StripeSubscription)
            .filter(StripeSubscription.user_id == current_user.id)
            .order_by(StripeSubscription.created_at.desc())
            .first()
        )

        if not sub or not has_active_access(sub):
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={
                    "code":        "subscription_required",
                    "message":     "An active subscription is required to access this feature.",
                    "upgrade_url": "/pricing",
                },
            )

        if TIER_RANK.get(sub.plan_tier, 0) < TIER_RANK.get(minimum_tier, 0):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code":        "tier_insufficient",
                    "message":     f"This feature requires the '{minimum_tier}' plan or higher.",
                    "upgrade_url": "/pricing",
                },
            )

        return current_user

    return _guard
