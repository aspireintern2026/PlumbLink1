"""
Plumber Jobs API
Handles jobs assigned to plumbers.
"""

from flask import Blueprint, request, jsonify, current_app
import jwt

from app.extensions import supabase


jobs_bp = Blueprint(
    "jobs_bp",
    __name__,
    url_prefix="/api/plumber/jobs",
)


def get_plumber_from_token():
    """
    Validate JWT and return plumber user ID.
    """
    auth_header = request.headers.get("Authorization", "")

    if not auth_header.startswith("Bearer "):
        return None, jsonify({"error": "Missing token"}), 401

    token = auth_header.split(" ", 1)[1]

    try:
        payload = jwt.decode(
            token,
            current_app.config["SECRET_KEY"],
            algorithms=["HS256"],
        )

        if payload.get("role") != "plumber":
            return None, jsonify({"error": "Plumber access only"}), 403

        return payload.get("id"), None

    except jwt.ExpiredSignatureError:
        return None, jsonify({"error": "Token expired"}), 401
    except jwt.InvalidTokenError:
        return None, jsonify({"error": "Invalid token"}), 401


@jobs_bp.route("", methods=["GET"])
def list_my_jobs():
    """
    List jobs assigned to the logged-in plumber.
    """
    plumber_id, error = get_plumber_from_token()
    if error:
        return error

    response = (
        supabase.table("bookings")
        .select("*")
        .eq("plumber_id", plumber_id)
        .order("created_at", desc=True)
        .execute()
    )

    return jsonify({"jobs": response.data or []}), 200


@jobs_bp.route("/<job_id>/status", methods=["POST"])
def update_job_status(job_id):
    """
    Update job status by plumber.
    """
    plumber_id, error = get_plumber_from_token()
    if error:
        return error

    data = request.get_json() or {}
    status = data.get("status")

    allowed_statuses = (
        "assigned",
        "in_progress",
        "completed",
        "cancelled",
    )

    if status not in allowed_statuses:
        return jsonify({"error": "Invalid status"}), 400

    supabase.table("bookings") \
        .update({"status": status}) \
        .eq("id", job_id) \
        .eq("plumber_id", plumber_id) \
        .execute()

    return jsonify({"message": "Status updated"}), 200
