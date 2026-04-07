"""
Plumber Online / Offline (Shift) API
"""

from flask import Blueprint, request, jsonify, current_app
from flask_cors import cross_origin 
import jwt
from datetime import datetime, timezone

from app.extensions import supabase

shift_bp = Blueprint(
    "shift_bp",
    __name__,
    url_prefix="/api/shift",
)

# --------------------------------------------------
def get_plumber_from_token():
    auth_header = request.headers.get("Authorization", "")

    if not auth_header.startswith("Bearer "):
        return None, (jsonify({"error": "Missing or invalid Authorization header"}), 401)

    token = auth_header.split(" ", 1)[1]

    try:
        payload = jwt.decode(
            token,
            current_app.config["SECRET_KEY"],
            algorithms=["HS256"],
        )

        if payload.get("role") != "plumber":
            return None, (jsonify({"error": "Plumber access only"}), 403)

        plumber_id = payload.get("id")
        if not plumber_id:
            return None, (jsonify({"error": "Invalid token - missing user ID"}), 401)

        return plumber_id, None

    except jwt.ExpiredSignatureError:
        return None, (jsonify({"error": "Token has expired"}), 401)

    except jwt.InvalidTokenError:
        return None, (jsonify({"error": "Invalid token"}), 401)


# --------------------------------------------------
# POST /api/shift/online
# --------------------------------------------------
@shift_bp.route("/online", methods=["POST", "OPTIONS"])
@cross_origin(
    origins=["http://127.0.0.1:5500", "http://localhost:5500"],
    allow_headers=["Authorization", "Content-Type"],
    methods=["POST", "OPTIONS"],
    supports_credentials=False  # Important: we use Bearer token, not cookies
)
def go_online():
    # Handle preflight OPTIONS request automatically via flask-cors
    if request.method == "OPTIONS":
        return "", 204

    plumber_id, error = get_plumber_from_token()
    if error:
        return error

    now = datetime.now(timezone.utc).isoformat()

    supabase.table("app_users").update({
        "is_online": True,
        "last_seen": now,
    }).eq("id", plumber_id).execute()

    return jsonify({
        "message": "You are now online",
        "is_online": True,
        "last_seen": now
    }), 200


# --------------------------------------------------
# POST /api/shift/offline
# --------------------------------------------------
@shift_bp.route("/offline", methods=["POST", "OPTIONS"])
@cross_origin(
    origins=["http://127.0.0.1:5500", "http://localhost:5500"],
    allow_headers=["Authorization", "Content-Type"],
    methods=["POST", "OPTIONS"],
    supports_credentials=False
)
def go_offline():
    if request.method == "OPTIONS":
        return "", 204

    plumber_id, error = get_plumber_from_token()
    if error:
        return error

    now = datetime.now(timezone.utc).isoformat()

    supabase.table("app_users").update({
        "is_online": False,
        "last_seen": now,
    }).eq("id", plumber_id).execute()

    return jsonify({
        "message": "You are now offline",
        "is_online": False,
        "last_seen": now
    }), 200


# --------------------------------------------------
# GET /api/shift/status
# --------------------------------------------------
@shift_bp.route("/status", methods=["GET", "OPTIONS"])
@cross_origin(
    origins=["http://127.0.0.1:5500", "http://localhost:5500"],
    allow_headers=["Authorization", "Content-Type"],
    methods=["GET", "OPTIONS"],
    supports_credentials=False
)
def get_status():
    if request.method == "OPTIONS":
        return "", 204

    plumber_id, error = get_plumber_from_token()
    if error:
        return error

    resp = (
        supabase.table("app_users")
        .select("is_online, last_seen")
        .eq("id", plumber_id)
        .limit(1)
        .execute()
    )

    status = resp.data[0] if resp.data else {}

    return jsonify({
        "is_online": bool(status.get("is_online", False)),
        "last_seen": status.get("last_seen"),
    }), 200