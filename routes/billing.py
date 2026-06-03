"""
Routes facturation Stripe — ConstructLearn Pro
"""
import os
import stripe
from datetime import datetime, timezone
from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, current_app, jsonify)
from flask_login import login_required, current_user
from extensions import db
from models import User, Payment

billing_bp = Blueprint("billing", __name__)


def get_stripe():
    stripe.api_key = current_app.config["STRIPE_SECRET_KEY"]
    return stripe


# ── Page des plans ──────────────────────────────────────────
@billing_bp.route("/plans")
def plans():
    return render_template("billing/plans.html",
                           stripe_pk=current_app.config["STRIPE_PUBLISHABLE_KEY"])


# ── Créer une session Checkout Stripe ──────────────────────
@billing_bp.route("/checkout/<plan>")
@login_required
def checkout(plan):
    if plan not in ("monthly", "annual"):
        abort(400)
    s = get_stripe()
    price_id = (current_app.config["STRIPE_PRICE_MONTHLY"] if plan == "monthly"
                else current_app.config["STRIPE_PRICE_ANNUAL"])
    if not price_id:
        flash("Configuration Stripe manquante. Contactez l'administrateur.", "error")
        return redirect(url_for("billing.plans"))

    # Créer ou récupérer le customer Stripe
    if not current_user.stripe_customer_id:
        customer = s.Customer.create(
            email=current_user.email,
            name=current_user.full_name,
            metadata={"user_id": current_user.id},
        )
        current_user.stripe_customer_id = customer.id
        db.session.commit()

    try:
        session = s.checkout.Session.create(
            customer=current_user.stripe_customer_id,
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            success_url=url_for("billing.success", _external=True) + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=url_for("billing.plans", _external=True),
            metadata={"user_id": current_user.id, "plan": plan},
            locale="fr",
            allow_promotion_codes=True,
        )
        return redirect(session.url, code=303)
    except stripe.error.StripeError as e:
        flash(f"Erreur Stripe : {e.user_message}", "error")
        return redirect(url_for("billing.plans"))


# ── Succès paiement ─────────────────────────────────────────
@billing_bp.route("/succes")
@login_required
def success():
    flash("🎉 Abonnement activé ! Bienvenue dans ConstructLearn Pro.", "success")
    return redirect(url_for("main.dashboard"))


# ── Portail client Stripe (gérer / annuler abonnement) ─────
@billing_bp.route("/portail")
@login_required
def portal():
    if not current_user.stripe_customer_id:
        flash("Aucun abonnement actif trouvé.", "warning")
        return redirect(url_for("billing.plans"))
    s = get_stripe()
    try:
        session = s.billing_portal.Session.create(
            customer=current_user.stripe_customer_id,
            return_url=url_for("main.profile", _external=True),
        )
        return redirect(session.url, code=303)
    except stripe.error.StripeError as e:
        flash(f"Erreur lors de l'ouverture du portail : {e.user_message}", "error")
        return redirect(url_for("main.profile"))


# ── Webhook Stripe ──────────────────────────────────────────
@billing_bp.route("/webhook", methods=["POST"])
def webhook():
    payload    = request.get_data()
    sig_header = request.headers.get("Stripe-Signature")
    s = get_stripe()
    try:
        event = s.Webhook.construct_event(
            payload, sig_header, current_app.config["STRIPE_WEBHOOK_SECRET"]
        )
    except (ValueError, stripe.error.SignatureVerificationError):
        return jsonify({"error": "Invalid signature"}), 400

    _handle_event(event, s)
    return jsonify({"ok": True}), 200


def _handle_event(event, s):
    """Dispatch des événements Stripe."""
    etype = event["type"]
    data  = event["data"]["object"]

    # ── Abonnement activé / renouvelé ──────────────────────
    if etype == "invoice.paid":
        sub_id   = data.get("subscription")
        customer = data.get("customer")
        user = User.query.filter_by(stripe_customer_id=customer).first()
        if not user:
            return
        sub = s.Subscription.retrieve(sub_id)
        plan_id  = sub["items"]["data"][0]["price"]["id"]
        from flask import current_app as ca
        plan = "monthly" if plan_id == ca.config["STRIPE_PRICE_MONTHLY"] else "annual"

        user.stripe_subscription_id = sub_id
        user.plan        = plan
        user.plan_status = "active"

        # Date d'expiration
        import datetime as dt
        ts = sub["current_period_end"]
        user.plan_expires_at = dt.datetime.fromtimestamp(ts, tz=timezone.utc)

        # Enregistrer le paiement
        if not Payment.query.filter_by(stripe_invoice_id=data["id"]).first():
            p = Payment(
                user_id=user.id,
                stripe_payment_intent=data.get("payment_intent"),
                stripe_invoice_id=data["id"],
                amount_cents=data["amount_paid"],
                currency=data["currency"],
                plan=plan,
                status="paid",
            )
            db.session.add(p)
        db.session.commit()

    # ── Paiement échoué ─────────────────────────────────────
    elif etype == "invoice.payment_failed":
        customer = data.get("customer")
        user = User.query.filter_by(stripe_customer_id=customer).first()
        if user:
            user.plan_status = "past_due"
            db.session.commit()

    # ── Abonnement annulé ───────────────────────────────────
    elif etype in ("customer.subscription.deleted", "customer.subscription.updated"):
        sub    = data
        customer = sub.get("customer")
        user = User.query.filter_by(stripe_customer_id=customer).first()
        if not user:
            return
        status = sub.get("status")
        if status in ("canceled", "unpaid", "incomplete_expired"):
            user.plan        = "free"
            user.plan_status = "inactive"
            user.stripe_subscription_id = None
        elif status == "past_due":
            user.plan_status = "past_due"
        db.session.commit()
