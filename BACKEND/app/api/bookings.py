# app/api/bookings.py

from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
import jwt
import math
from math import atan2, radians

from app.extensions import supabase
from app.notifications import notify_plumber_booking_assigned

bookings_bp = Blueprint("bookings_bp", __name__, url_prefix="/api/bookings")


def get_auth_payload():
    """Extract and decode JWT payload from Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None, (jsonify({"error": "Invalid auth header"}), 401)

    try:
        token = auth_header.split(" ", 1)[1].strip()
    except IndexError:
        return None, (jsonify({"error": "Invalid auth header"}), 401)

    secret = current_app.config.get("SECRET_KEY")
    if not secret:
        current_app.logger.error("SECRET_KEY not configured")
        return None, (jsonify({"error": "Server config error"}), 500)

    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        return payload, None
    except jwt.ExpiredSignatureError:
        return None, (jsonify({"error": "Token expired"}), 401)
    except jwt.InvalidTokenError:
        return None, (jsonify({"error": "Invalid token"}), 401)


@bookings_bp.route("/", methods=["POST"])
def create_booking():
    if supabase is None:
        current_app.logger.error("Supabase client not initialized")
        return jsonify({"error": "Server config error"}), 500

    payload, err = get_auth_payload()
    if err:
        return err
    user_id = payload.get("id")
    if not user_id:
        return jsonify({"error": "Invalid token payload"}), 401

    data = request.get_json() or {}
    issue = data.get("issue")
    description = data.get("description")
    urgency = data.get("urgency", "medium").lower()
    preferred_time_str = data.get("preferred_time")
    address = data.get("address")
    addons = data.get("addons", "")
    lat = data.get("lat")
    lng = data.get("lng")

    required = ["issue", "description", "preferred_time", "address"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        msg = f"Missing fields: {', '.join(missing)}"
        return jsonify({"error": msg}), 400

    urgency_map = {"low": 1, "medium": 2, "high": 3}
    if urgency not in urgency_map:
        return jsonify(
            {"error": "Urgency must be low, medium, or high"}
        ), 400

    try:
        dt_str = preferred_time_str.replace("Z", "+00:00")
        preferred_time = datetime.fromisoformat(dt_str)
    except ValueError:
        return jsonify(
            {"error": "preferred_time must be valid ISO format"}
        ), 400

    payload_data = {
        "user_id": user_id,
        "issue": issue,
        "description": description,
        "urgency": urgency_map[urgency],
        "preferred_time": preferred_time.isoformat(),
        "address": address,
        "addons": addons,
        "status": "pending",
    }

    response = supabase.table("bookings").insert(payload_data).execute()
    if hasattr(response, "error") and response.error:
        current_app.logger.error(f"Booking insert failed: {response.error}")
        return jsonify({"error": "Failed to create booking"}), 500

    booking = response.data[0]
    result = {"message": "Booking created", "booking": booking}

    if lat is not None and lng is not None:
        try:
            lat_float = float(lat)
            lng_float = float(lng)
            plumber = find_nearest_plumber(lat_float, lng_float)
            if plumber:
                plumber_id = plumber["id"]
                upd = (
                    supabase.table("bookings")
                    .update(
                        {"plumber_id": plumber_id, "status": "assigned"}
                    )
                    .eq("id", booking["id"])
                    .execute()
                )
                if not hasattr(upd, "error") or not upd.error:
                    booking.update(
                        {"plumber_id": plumber_id, "status": "assigned"}
                    )
                    result["assigned_plumber"] = {
                        "id": plumber.get("id"),
                        "name": plumber.get("name"),
                        "mobile": plumber.get("mobile"),
                    }
                    # Notify plumber that a booking has been assigned.
                    try:
                        notify_plumber_booking_assigned(
                            supabase, plumber_id, booking
                        )
                    except Exception:
                        current_app.logger.exception(
                            "Failed to notify plumber after "
                            "auto-assignment"
                        )
        except (ValueError, TypeError):
            current_app.logger.warning(
                "Invalid lat/lng provided for auto-assignment"
            )

    return jsonify(result), 201


@bookings_bp.route("/", methods=["GET"])
def list_bookings():
    if supabase is None:
        return jsonify({"error": "Server config error"}), 500

    payload, err = get_auth_payload()
    if err:
        return err
    user_id = payload.get("id")

    resp = (
        supabase.table("bookings")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )

    if hasattr(resp, "error") and resp.error:
        current_app.logger.error(f"Fetch bookings failed: {resp.error}")
        return jsonify({"error": "Failed to fetch bookings"}), 500

    return jsonify({"bookings": resp.data or []}), 200


@bookings_bp.route("/admin", methods=["GET"])
def list_all_bookings_admin():
    if supabase is None:
        return jsonify({"error": "Server config error"}), 500

    payload, err = get_auth_payload()
    if err:
        return err

    if payload.get("role") != "admin":
        return jsonify({"error": "Admin access required"}), 403

    bookings_resp = (
        supabase.table("bookings")
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )
    if hasattr(bookings_resp, "error") and bookings_resp.error:
        return jsonify({"error": "Failed to fetch bookings"}), 500

    bookings = bookings_resp.data or []
    user_ids = {b["user_id"] for b in bookings if b["user_id"]}

    users = {}
    if user_ids:
        users_resp = (
            supabase.table("app_users")
            .select("id, name, email, mobile")
            .in_("id", list(user_ids))
            .execute()
        )
        if not hasattr(users_resp, "error") or not users_resp.error:
            for u in users_resp.data or []:
                users[u["id"]] = u

    for booking in bookings:
        user = users.get(booking.get("user_id"))
        if user:
            name = user.get("name") or user.get("email") or "Unknown"
            booking["user_name"] = name
            booking["user_mobile"] = user.get("mobile") or ""
        else:
            booking["user_name"] = "Unknown"
            booking["user_mobile"] = ""

    return jsonify({"bookings": bookings}), 200


@bookings_bp.route("/<int:booking_id>", methods=["GET"])
def get_booking(booking_id):
    if supabase is None:
        return jsonify({"error": "Server config error"}), 500

    payload, err = get_auth_payload()
    if err:
        return err

    user_id = payload.get("id")
    role = payload.get("role")

    resp = (
        supabase.table("bookings")
        .select("*")
        .eq("id", booking_id)
        .single()
        .execute()
    )
    if hasattr(resp, "error") or not resp.data:
        return jsonify({"error": "Booking not found"}), 404

    booking = resp.data

    allowed = (
        role == "admin"
        or user_id == booking.get("user_id")
        or user_id == booking.get("plumber_id")
    )
    if allowed:
        return jsonify({"booking": booking}), 200

    return jsonify({"error": "Unauthorized"}), 403


@bookings_bp.route("/<int:booking_id>/assign", methods=["POST"])
def assign_booking(booking_id):
    payload, err = get_auth_payload()
    if err:
        return err

    if payload.get("role") != "admin":
        return jsonify({"error": "Admin required"}), 403

    data = request.get_json() or {}
    plumber_id = data.get("plumber_id")
    if not plumber_id:
        return jsonify({"error": "plumber_id required"}), 400

    update_data = {"plumber_id": plumber_id, "status": "assigned"}
    if data.get("scheduled_time"):
        update_data["scheduled_time"] = data.get("scheduled_time")

    resp = (
        supabase.table("bookings")
        .update(update_data)
        .eq("id", booking_id)
        .execute()
    )
    if hasattr(resp, "error") and resp.error:
        return jsonify({"error": "Assignment failed"}), 500

    booking_data = resp.data[0] if resp.data else None
    # Notify plumber when admin assigns a booking
    try:
        if booking_data and booking_data.get("plumber_id"):
            plumber_id = booking_data.get("plumber_id")
            notify_plumber_booking_assigned(
                supabase, plumber_id, booking_data
            )
    except Exception:
        current_app.logger.exception(
            "Failed to notify plumber after admin assignment"
        )
    return jsonify(
        {"message": "Booking assigned", "booking": booking_data}
    ), 200


@bookings_bp.route("/plumber", methods=["GET"])
def list_bookings_for_plumber():
    payload, err = get_auth_payload()
    if err:
        return err

    if payload.get("role") != "plumber":
        return jsonify({"error": "Plumber access required"}), 403

    user_id = payload.get("id")
    resp = (
        supabase.table("bookings")
        .select("*")
        .eq("plumber_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )

    if hasattr(resp, "error") and resp.error:
        return jsonify({"error": "Failed to fetch bookings"}), 500

    return jsonify({"bookings": resp.data or []}), 200


@bookings_bp.route("/<int:booking_id>/status", methods=["POST"])
def update_booking_status(booking_id):
    payload, err = get_auth_payload()
    if err:
        return err

    if payload.get("role") != "plumber":
        return jsonify({"error": "Plumber required"}), 403

    data = request.get_json() or {}
    status = data.get("status", "").strip()
    valid_statuses = {"assigned", "in_progress", "completed", "cancelled"}
    if status not in valid_statuses:
        msg = f"Status must be one of: {', '.join(valid_statuses)}"
        return jsonify({"error": msg}), 400

    user_id = payload.get("id")

    probe = (
        supabase.table("bookings")
        .select("plumber_id")
        .eq("id", booking_id)
        .single()
        .execute()
    )
    if (
        hasattr(probe, "error")
        or not probe.data
        or probe.data.get("plumber_id") != user_id
    ):
        return jsonify({"error": "Booking not assigned to you"}), 403

    resp = (
        supabase.table("bookings")
        .update({"status": status})
        .eq("id", booking_id)
        .execute()
    )
    if hasattr(resp, "error") and resp.error:
        return jsonify({"error": "Status update failed"}), 500

    booking_data = resp.data[0] if resp.data else None
    return jsonify(
        {"message": "Status updated", "booking": booking_data}
    ), 200


@bookings_bp.route("/<int:booking_id>/admin_status", methods=["POST"])
def admin_update_booking_status(booking_id):
    payload, err = get_auth_payload()
    if err:
        return err

    if payload.get("role") != "admin":
        return jsonify({"error": "Admin required"}), 403

    data = request.get_json() or {}
    status = data.get("status", "").strip()
    valid_statuses = {
        "pending",
        "assigned",
        "in_progress",
        "completed",
        "cancelled",
    }
    if status not in valid_statuses:
        return jsonify({"error": "Invalid status"}), 400

    resp = (
        supabase.table("bookings")
        .update({"status": status})
        .eq("id", booking_id)
        .execute()
    )
    if hasattr(resp, "error") and resp.error:
        return jsonify({"error": "Update failed"}), 500

    booking_data = resp.data[0] if resp.data else None
    return jsonify(
        {"message": "Status updated", "booking": booking_data}
    ), 200


def _haversine_distance(lat1, lng1, lat2, lng2):
    """Return distance in meters between two points (Haversine)."""
    R = 6371000  # Earth radius in meters
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lng2 - lng1)

    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    c = 2 * atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def find_nearest_plumber(lat, lng):
    """Find nearest plumber based on stored coordinates."""
    if supabase is None:
        return None

    resp = (
        supabase.table("app_users")
        .select("id, name, mobile, latitude, longitude, lat, lng")
        .eq("user_role", "plumber")
        .execute()
    )

    if hasattr(resp, "error") or not resp.data:
        return None

    candidates = []
    for p in resp.data:
        plat = p.get("latitude") or p.get("lat")
        plng = p.get("longitude") or p.get("lng")
        if plat is not None and plng is not None:
            try:
                plat = float(plat)
                plng = float(plng)
                distance = _haversine_distance(lat, lng, plat, plng)
                candidates.append({"plumber": p, "distance": distance})
            except (ValueError, TypeError):
                continue

    if not candidates:
        return None

    nearest = min(candidates, key=lambda x: x["distance"])
    return nearest["plumber"]


# Debug token endpoint for frontend dev
@bookings_bp.route("/debug/token", methods=["GET", "OPTIONS"])
def debug_token():
    if request.method == "OPTIONS":
        return "", 200

    payload, err = get_auth_payload()
    if err:
        return err

    return jsonify({"valid": True, "payload": payload}), 200
