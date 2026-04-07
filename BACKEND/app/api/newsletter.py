from flask import Blueprint, request, jsonify
from ..models import NewsletterSubscriber
from ..extensions import db

newsletter_bp = Blueprint("newsletter", __name__, url_prefix="/api/newsletter")


@newsletter_bp.route("/subscribe", methods=["POST"])
def subscribe():
    data = request.get_json() or {}
    email = data.get("email", "").strip().lower()
    if not email or "@" not in email:
        return jsonify({
            "success": False,
            "error": "Invalid email address."
        }), 400

    try:
        existing = NewsletterSubscriber.query.filter_by(email=email).first()
        if existing:
            return jsonify({
                "success": True,
                "message": "Already subscribed."
            }), 200

        sub = NewsletterSubscriber(email=email)
        db.session.add(sub)
        db.session.commit()
        return jsonify({
            "success": True,
            "message": "Subscribed successfully."
        }), 201
    except Exception:
        # fallback: simple in-memory list stored on blueprint (non-persistent)
        store = getattr(newsletter_bp, '_fallback', None)
        if store is None:
            newsletter_bp._fallback = set()
            store = newsletter_bp._fallback

        if email in store:
            msg = "Already subscribed (fallback)."
            return jsonify({"success": True, "message": msg}), 200
        store.add(email)
        return jsonify({
            "success": True,
            "message": "Subscribed successfully (fallback)."
        }), 201


@newsletter_bp.route("/subscribers", methods=["GET"])
def list_subscribers():
    # For demo only: in production protect this route with auth
    try:
        rows = NewsletterSubscriber.query.order_by(
            NewsletterSubscriber.created_at.desc()
        ).all()
        return jsonify({"subscribers": [r.email for r in rows]}), 200
    except Exception:
        store = getattr(newsletter_bp, '_fallback', set())
        return jsonify({"subscribers": list(store)}), 200
