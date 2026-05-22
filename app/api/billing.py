"""
api/billing.py

Billing endpoints for TalkFiesta.

Endpoints
─────────
GET  /billing/plans                 → list available plans (public)
POST /billing/checkout              → start Stripe checkout session
POST /billing/portal                → open Stripe billing portal (self-serve)
GET  /billing/status                → current subscription state
GET  /billing/history               → payment history
GET  /billing/success               → post-checkout landing (read-only)
"""
import logging
from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services.billing_service import (
    create_checkout_session,
    create_portal_session,
    get_subscription_status,
    get_payment_history,
    get_plan_keys,
    require_subscription,
)

router = APIRouter(prefix="/billing", tags=["Billing"])
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────────────────────

class CheckoutRequest(BaseModel):
    plan_key: Literal["basic_month", "basic_year", "pro_month", "pro_year"] = Field(
        ...,
        description="Which plan to subscribe to.",
        examples=["pro_month"],
    )


class CheckoutResponse(BaseModel):
    checkout_url: str = Field(..., description="Stripe-hosted checkout page URL. Redirect the user here.")


class PortalResponse(BaseModel):
    portal_url: str = Field(..., description="Stripe Billing Portal URL. Redirect the user here.")


class PlanInfo(BaseModel):
    key: str
    display_name: str
    plan_tier: str
    billing_interval: str
    amount_cents: int
    trial_days: int


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/plans",
    response_model=list[PlanInfo],
    summary="List available subscription plans",
    description=(
        "Returns all purchasable plans with pricing. "
        "No authentication required — safe to call from the public pricing page."
    ),
)
def list_plans():
    """Public endpoint — returns the plan catalogue for the pricing page."""
    return get_plan_keys()


# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/checkout",
    response_model=CheckoutResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a Stripe Checkout session",
    description=(
        "Creates a Stripe-hosted checkout session for the requested plan. "
        "Redirect the user's browser to `checkout_url` to complete payment. "
        "**Never** use the checkout redirect back to confirm payment — "
        "wait for the `checkout.session.completed` webhook."
    ),
)
def start_checkout(
    data: CheckoutRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start a Stripe checkout flow for the authenticated user."""
    url = create_checkout_session(current_user, data.plan_key, db)
    return CheckoutResponse(checkout_url=url)


# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/portal",
    response_model=PortalResponse,
    summary="Open Stripe Billing Portal",
    description=(
        "Creates a Stripe Billing Portal session so the user can self-serve: "
        "update their payment method, cancel, switch plans, or download invoices. "
        "Redirect the user's browser to `portal_url`."
    ),
)
def open_portal(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return a Stripe Billing Portal URL for the authenticated user."""
    url = create_portal_session(current_user, db)
    return PortalResponse(portal_url=url)


# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/status",
    summary="Get current subscription status",
    description=(
        "Returns the authenticated user's current billing state. "
        "Call this on app load to decide which features to enable. "
        "`has_access: true` means the user may use paid features right now."
    ),
)
def subscription_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the current subscription state for the authenticated user."""
    return get_subscription_status(current_user, db)


# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/history",
    summary="Get payment history",
    description=(
        "Returns a paginated list of past charges (most recent first). "
        "Excludes $0 trial-start invoices. "
        "Each record includes an `invoice_pdf_url` when available."
    ),
)
def payment_history(
    limit: int = Query(default=20, ge=1, le=100, description="Max records to return"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the authenticated user's payment history."""
    return get_payment_history(current_user, db, limit=limit)


# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/success",
    summary="Post-checkout success landing",
    description=(
        "The page Stripe redirects users to after completing checkout. "
        "Use `session_id` (from the `?session_id={CHECKOUT_SESSION_ID}` query param) "
        "only for display purposes — **never** to confirm payment. "
        "Access is gated on `subscription.status` set by the webhook, not this redirect."
    ),
)
def checkout_success(
    session_id: str = Query(..., description="Stripe checkout session ID from the redirect URL"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Post-checkout landing. Returns current subscription status so the
    frontend can show a confirmation screen while waiting for the webhook.
    """
    logger.info(f"User {current_user.id} returned from checkout (session={session_id})")
    sub_status = get_subscription_status(current_user, db)
    return {
        "message": "Thank you! Your subscription is being activated.",
        "subscription": sub_status,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Example: Tier-gated route (copy this pattern for any premium endpoint)
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/pro-demo",
    summary="[Demo] Pro-tier gated endpoint",
    description="Example of a Pro-only endpoint. Remove or repurpose in production.",
    dependencies=[Depends(require_subscription("pro"))],
    include_in_schema=False,   # hide from Swagger in production
)
def pro_demo(current_user: User = Depends(get_current_user)):
    """Demonstrates the require_subscription dependency guard."""
    return {"message": f"Hello, {current_user.username}! You have Pro access."}
