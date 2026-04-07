# app/api/plumbers.py

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
from app.extensions import supabase

# Blueprint with URL prefix so routes become:
# /api/plumbers/me
# /api/plumbers/me/location
plumbers_bp = Blueprint("plumbers", __name__, url_prefix="/api/plumbers")


# -------- Auth routes --------

@plumbers_bp.route("/login", methods=["POST"])
def login():
    """
    Demo login disabled.
    Authentication should be provided by the real auth system
    (e.g. Supabase Auth).
    This endpoint intentionally returns 404 to avoid shipping demo
    credentials in production.
    """
    return (
        jsonify({
            "error": (
                "Demo login disabled. Use real authentication "
                "(Supabase/Auth)."
            )
        }),
        404,
    )


# -------- Profile routes --------

@plumbers_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    """
    Get current plumber details.
    Requires Authorization: Bearer <token>
    """
    user_id = get_jwt_identity()
    if supabase is None:
        current_app.logger.error(
            "Supabase client not initialized for /api/plumbers/me"
        )
        return (
            jsonify({"error": "Server not configured for user lookup"}),
            500,
        )

    resp = (
        supabase.table("plumbers")
        .select("*")
        .eq("id", user_id)
        .single()
        .execute()
    )
    if hasattr(resp, "error") and resp.error:
        current_app.logger.error(
            "Supabase plumbers lookup failed: %s", resp.error
        )
        return jsonify({"error": "Failed to fetch user"}), 500

    if not resp.data:
        return jsonify({"error": "user not found"}), 404

    user = resp.data
    # remove any sensitive fields if present
    user.pop("password", None)
    return jsonify({"status": "ok", "user": user})


# -------- Location routes --------

@plumbers_bp.route("/me/location", methods=["POST"])
@jwt_required()
def save_location():
    """
    Save current GPS location for the logged-in plumber.
    Request JSON: { "lat": <float>, "lng": <float> }
    """
    user_id = get_jwt_identity()
    if supabase is None:
        current_app.logger.error(
            "Supabase client not initialized for "
            "/api/plumbers/me/location"
        )
        return (
            jsonify(
                {"error": "Server not configured for location updates"}
            ),
            500,
        )

    data = request.get_json() or {}
    lat = data.get("lat")
    lng = data.get("lng")

    if lat is None or lng is None:
        return jsonify({"error": "lat and lng required"}), 400

    now = datetime.utcnow().isoformat()
    try:
        resp = (
            supabase.table("plumbers")
            .update({
                "latitude": float(lat),
                "longitude": float(lng),
                "location_updated_at": now
            })
            .eq("id", user_id)
            .execute()
        )
        if hasattr(resp, "error") and resp.error:
            current_app.logger.error(
                "Supabase plumbers update failed: %s", resp.error
            )
            return jsonify({"error": "Failed to save location"}), 500

        return (
            jsonify({
                "status": "ok",
                "lat": float(lat),
                "lng": float(lng),
                "location_updated_at": now
            }),
            200,
        )
    except Exception as exc:
        current_app.logger.exception(
            "Exception saving plumber location: %s", exc
        )
        return jsonify({"error": "Failed to save location"}), 500
