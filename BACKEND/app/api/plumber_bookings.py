from flask import Blueprint, request, jsonify, current_app
from app.extensions import supabase
import jwt
from datetime import datetime

plumber_bp = Blueprint("plumber_bp", __name__, url_prefix="/api")


def get_plumber_from_token():
    """Extract and validate plumber_id from JWT token."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None, jsonify({"error": "Missing or invalid token"}), 401

    token = auth_header.split(" ")[1]

    try:
        payload = jwt.decode(
            token, current_app.config["SECRET_KEY"], algorithms=["HS256"]
        )
        plumber_id = payload.get("sub")
        if not plumber_id:
            return None, jsonify({"error": "Invalid token payload"}), 401
        return plumber_id, None, 200
    except jwt.ExpiredSignatureError:
        return None, jsonify({"error": "Token expired"}), 401
    except jwt.InvalidTokenError:
        return None, jsonify({"error": "Invalid token"}), 401


# ==================== SHIFT ENDPOINTS ====================


@plumber_bp.route("/shift/online", methods=["POST"])
def go_online():
    """Set plumber status to online."""
    plumber_id, error, status = get_plumber_from_token()
    if error:
        return error, status

    now = datetime.utcnow().isoformat()
    response = (
        supabase.table("plumbers")
        .update({"is_online": True, "last_online_at": now})
        .eq("id", plumber_id)
        .execute()
    )

    if response.data:
        return (
            jsonify({"message": "You are now online", "is_online": True}),
            200,
        )

    return jsonify({"error": "Failed to update status"}), 500


@plumber_bp.route("/shift/offline", methods=["POST"])
def go_offline():
    """Set plumber status to offline."""
    plumber_id, error, status = get_plumber_from_token()
    if error:
        return error, status

    response = (
        supabase.table("plumbers")
        .update({"is_online": False})
        .eq("id", plumber_id)
        .execute()
    )

    if response.data:
        return (
            jsonify(
                {
                    "message": "You are now offline",
                    "is_online": False,
                }
            ),
            200,
        )

    return jsonify({"error": "Failed to update status"}), 500


@plumber_bp.route("/shift/status", methods=["GET"])
def shift_status():
    """Get current online/offline status of plumber."""
    plumber_id, error, status = get_plumber_from_token()
    if error:
        return error, status

    response = (
        supabase.table("plumbers")
        .select("is_online")
        .eq("id", plumber_id)
        .single()
        .execute()
    )

    if response.data:
        return jsonify({"is_online": response.data["is_online"]}), 200

    return jsonify({"error": "Plumber not found"}), 404


# ==================== ACCEPT JOB ====================


@plumber_bp.route("/jobs/<int:booking_id>/accept", methods=["POST"])
def accept_job(booking_id):
    """Accept a pending job and assign it to the plumber."""
    plumber_id, error, status = get_plumber_from_token()
    if error:
        return error, status

    job_check = (
        supabase.table("bookings")
        .select("id, status, plumber_id")
        .eq("id", booking_id)
        .eq("status", "pending")
        .execute()
    )

    if not job_check.data:
        return jsonify({"error": "Job not available or already taken"}), 400

    now = datetime.utcnow().isoformat()
    update_response = (
        supabase.table("bookings")
        .update(
            {
                "plumber_id": plumber_id,
                "status": "assigned",
                "assigned_at": now,
            }
        )
        .eq("id", booking_id)
        .execute()
    )

    if update_response.data:
        return (
            jsonify(
                {
                    "message": "Job accepted successfully",
                    "job_id": booking_id,
                    "status": "assigned",
                }
            ),
            200,
        )

    return jsonify({"error": "Failed to accept job"}), 500


# ==================== FETCH AVAILABLE JOBS ====================


@plumber_bp.route("/jobs/available", methods=["GET"])
def available_jobs():
    """Fetch all pending jobs (ready for future distance filtering)."""
    plumber_id, error, status = get_plumber_from_token()
    if error:
        return error, status

    jobs = (
        supabase.table("bookings")
        .select("id, issue, description, urgency, address, lat, lng, payout")
        .eq("status", "pending")
        .execute()
    )

    return jsonify({"jobs": jobs.data or []}), 200