import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime,
    ForeignKey, Index, Text, JSON, Enum
)
from sqlalchemy.orm import relationship
from app.db.base import Base


# ── 1. StripeCustomer ─────────────────────────────────────────────────────────

class StripeCustomer(Base):
    """
    Links a User to a Stripe Customer object (cus_xxx).
    Created once per user on their first checkout attempt and reused on all
    subsequent subscriptions.
    """
    __tablename__ = "stripe_customers"

    id                 = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id            = Column(
        String, ForeignKey("users.id", ondelete="CASCADE"),
        unique=True, nullable=False
    )
    stripe_customer_id = Column(String(64), unique=True, nullable=False, index=True)
    # format: cus_xxxxxxxxxxxxxxxx

    email_at_creation  = Column(String(255), nullable=False)
    # Snapshot of email at creation — useful if user changes email later

    card_fingerprint   = Column(String(64), nullable=True, index=True)
    # Stripe card fingerprint — stable identifier for a physical card across customers.
    # Used to block repeat free-trial abuse (same card, different account).
    # Populated on checkout.session.completed via the payment_method details.

    created_at         = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at         = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="stripe_customer")

    __table_args__ = (
        Index("idx_stripe_customer_stripe_id",   "stripe_customer_id"),
        Index("idx_stripe_customer_fingerprint", "card_fingerprint"),
    )


# ── 2. StripeSubscription ─────────────────────────────────────────────────────

class StripeSubscription(Base):
    """
    Source of truth for a user's billing state.
    MUST be updated exclusively via Stripe webhook events — never from
    checkout redirects.

    Status lifecycle:
        trialing ──► active ──► past_due ──► unpaid ──► canceled
            │                      │
            └──────────────────────┴──► canceled (immediate cancel)
    """
    __tablename__ = "stripe_subscriptions"

    id                       = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id                  = Column(
        String, ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    stripe_subscription_id   = Column(String(64), unique=True, nullable=False, index=True)
    # format: sub_xxxxxxxxxxxxxxxx

    stripe_customer_id       = Column(String(64), nullable=False, index=True)
    # Denormalised for fast webhook lookups without joining stripe_customers

    stripe_price_id          = Column(String(64), nullable=False)
    # format: price_xxxxxxxxxxxxxxxx

    # ── Plan metadata (denormalised to avoid Stripe API calls on reads) ───────
    plan_tier                = Column(
        Enum("basic", "pro", name="plan_tier_enum"),
        nullable=False
    )
    billing_interval         = Column(
        Enum("month", "year", name="billing_interval_enum"),
        nullable=False
    )
    amount_cents             = Column(Integer, nullable=False)
    currency                 = Column(String(3), default="usd", nullable=False)

    # ── Lifecycle state ───────────────────────────────────────────────────────
    status                   = Column(
        Enum(
            "trialing",
            "active",
            "past_due",
            "canceled",
            "unpaid",
            "incomplete",
            "incomplete_expired",
            "paused",
            name="subscription_status_enum"
        ),
        nullable=False,
        index=True
    )

    trial_start              = Column(DateTime, nullable=True)
    trial_end                = Column(DateTime, nullable=True)
    # trial_end is the canonical field to show "Your trial ends on …"

    current_period_start     = Column(DateTime, nullable=False)
    current_period_end       = Column(DateTime, nullable=False)

    cancel_at_period_end     = Column(Boolean, default=False, nullable=False)
    # True when user requested cancellation but access continues until period end

    canceled_at              = Column(DateTime, nullable=True)
    # Set when Stripe fires customer.subscription.deleted

    ended_at                 = Column(DateTime, nullable=True)
    # Set when subscription is fully terminated

    # ── Extra Stripe metadata ─────────────────────────────────────────────────
    stripe_latest_invoice_id = Column(String(64), nullable=True)
    # in_xxx — useful for payment failure recovery UX

    stripe_metadata          = Column(JSON, nullable=True)
    # Stores sub["metadata"] from Stripe for debugging and custom attributes
    # (Bug fix: was missing from original schema)

    pause_collection         = Column(JSON, nullable=True)
    # Stores Stripe's pause_collection object when status = "paused"
    # e.g. {"behavior": "mark_uncollectible"}
    # (Bug fix: was missing despite "paused" being in the status enum)

    created_at               = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at               = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user            = relationship("User", back_populates="stripe_subscription")
    payment_records = relationship("StripePaymentRecord", back_populates="subscription")

    __table_args__ = (
        Index("idx_stripe_sub_user_status",   "user_id", "status"),
        Index("idx_stripe_sub_stripe_id",     "stripe_subscription_id"),
        Index("idx_stripe_sub_customer_id",   "stripe_customer_id"),
    )


def has_active_access(sub: "StripeSubscription") -> bool:
    """
    Returns True if the user currently has platform access based on their
    subscription state.

    Rules:
      - trialing / active          → always has access
      - canceled + cancel_at_period_end → access until current_period_end
      - paused / past_due / unpaid → no access (explicit policy)
    (Bug fix: name standardised to has_active_access everywhere; paused is explicit)
    """
    now = datetime.utcnow()
    if sub.status in ("trialing", "active"):
        return True
    if sub.status == "canceled" and sub.cancel_at_period_end:
        return sub.current_period_end > now
    if sub.status == "paused":
        return False  # Intentional: paused = no access
    return False


# ── 3. StripePaymentRecord ────────────────────────────────────────────────────

class StripePaymentRecord(Base):
    """
    Immutable audit log of every invoice payment event.
    One row per invoice.payment_succeeded or invoice.payment_failed webhook.
    """
    __tablename__ = "stripe_payment_records"

    id                       = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id                  = Column(
        String, ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    subscription_id          = Column(
        String, ForeignKey("stripe_subscriptions.id"),
        nullable=True
    )
    # Nullable: one-off charges (if ever added) won't have a subscription

    stripe_invoice_id        = Column(String(64), unique=True, nullable=True, index=True)
    # in_xxxxxxxxxxxxxxxx

    stripe_payment_intent_id = Column(String(64), nullable=True, index=True)
    # pi_xxxxxxxxxxxxxxxx — present on successful charges

    stripe_charge_id         = Column(String(64), nullable=True)
    # ch_xxxxxxxxxxxxxxxx

    amount_cents             = Column(Integer, nullable=False)
    amount_refunded_cents    = Column(Integer, default=0, nullable=False)
    currency                 = Column(String(3), default="usd", nullable=False)

    status                   = Column(
        Enum(
            "paid", "failed", "refunded", "partially_refunded", "void",
            name="payment_status_enum"
        ),
        nullable=False,
        index=True
    )

    payment_type             = Column(
        Enum(
            "subscription", "trial_conversion", "one_time",
            name="payment_type_enum"
        ),
        nullable=False
    )

    failure_code             = Column(String(100), nullable=True)
    # e.g. "card_declined", "insufficient_funds" — from Stripe
    failure_message          = Column(String(500), nullable=True)
    # Human-readable; safe to surface to user

    period_start             = Column(DateTime, nullable=True)
    period_end               = Column(DateTime, nullable=True)
    # Billing period this invoice covers

    invoice_pdf_url          = Column(String(500), nullable=True)
    # Stripe-hosted PDF link for user billing history page

    refunded_at              = Column(DateTime, nullable=True)
    created_at               = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    subscription = relationship("StripeSubscription", back_populates="payment_records")
    user         = relationship("User", back_populates="stripe_payment_records")

    __table_args__ = (
        Index("idx_payment_records_user_created", "user_id", "created_at"),
        Index("idx_payment_records_status",       "status"),
    )


# ── 4. StripeWebhookEvent ─────────────────────────────────────────────────────

class StripeWebhookEvent(Base):
    """
    Idempotency guard and audit log for every incoming Stripe webhook.

    The PK is Stripe's own evt_xxx ID — this enforces idempotency at the
    database level. Combined with a DB unique constraint, this prevents
    duplicate processing even under concurrent delivery.

    status flow: received → processed | failed | ignored
    """
    __tablename__ = "stripe_webhook_events"

    id                  = Column(String, primary_key=True)
    # Use Stripe's evt_xxxxxxxxxxxxxxxx as PK directly — enforces DB-level idempotency

    event_type          = Column(String(100), nullable=False, index=True)
    # e.g. "customer.subscription.updated"

    api_version         = Column(String(20), nullable=True)
    # Stripe API version from the event — helps debug version mismatches

    related_object_id   = Column(String(64), nullable=True, index=True)
    # sub_xxx / cus_xxx / in_xxx — the primary object this event is about

    related_object_type = Column(String(50), nullable=True)
    # "subscription" / "customer" / "invoice"

    status              = Column(
        Enum(
            "received", "processed", "failed", "ignored",
            name="webhook_status_enum"
        ),
        nullable=False,
        default="received",
        index=True
    )

    error_message       = Column(Text, nullable=True)
    # Populated when status = "failed"; critical for debugging

    raw_payload         = Column(JSON, nullable=False)
    # Full Stripe event JSON — invaluable for replaying failed events manually

    processed_at        = Column(DateTime, nullable=True)
    received_at         = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("idx_webhook_events_type_status", "event_type", "status"),
        Index("idx_webhook_events_object",      "related_object_id"),
    )


# ── 5. StripeCheckoutSession ──────────────────────────────────────────────────

class StripeCheckoutSession(Base):
    """
    Tracks pending Stripe Checkout sessions before they resolve into
    subscriptions. Enables:
      - Abandoned checkout recovery
      - Correlating cs_xxx session → sub_xxx subscription
      - Preventing duplicate checkouts for the same user
    """
    __tablename__ = "stripe_checkout_sessions"

    id                     = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id                = Column(
        String, ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    stripe_session_id      = Column(String(128), unique=True, nullable=False, index=True)
    # cs_xxxxxxxxxxxxxxxx

    stripe_price_id        = Column(String(64), nullable=False)
    plan_tier              = Column(String(20), nullable=False)
    billing_interval       = Column(String(10), nullable=False)

    plan_key               = Column(String(50), nullable=True)
    # e.g. "pro_year" — stored from checkout session metadata
    # (Bug fix: was missing from original schema — easier than parsing price+interval)

    status                 = Column(
        Enum(
            "pending", "completed", "expired", "abandoned",
            name="checkout_session_status_enum"
        ),
        nullable=False,
        default="pending",
        index=True
    )

    stripe_subscription_id = Column(String(64), nullable=True)
    # Populated once checkout.session.completed fires

    expires_at             = Column(DateTime, nullable=False)
    # Stripe checkout sessions expire after 24 hours

    created_at             = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at           = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User")

    __table_args__ = (
        Index("idx_checkout_sessions_user_status", "user_id", "status"),
    )
