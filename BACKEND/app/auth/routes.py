"""
Authentication endpoints backed by Supabase
(FIXED: Proper response format + syntax error fixed + CORS ready)
"""

from datetime import datetime, timedelta
from typing import Any, Dict
import uuid
import random
import time
import jwt

from flask import Blueprint, current_app, jsonify, request
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import supabase, get_supabase_status

auth_bp = Blueprint("auth_bp", __name__, url_prefix="/auth")

_OTP_STORE: Dict[str, Dict[str, Any]] = {}


# ======================================================
# HELPERS
# ======================================================
def _ensure_supabase_configured():
    status = get_supabase_status()
    if not status.get("ready") or supabase is None:
        return jsonify({"error": "Supabase not configured"}), 503
    return None


def _create_jwt_token(user: Dict[str, Any]) -> str:
    secret = (
        current_app.config.get("SECRET_KEY")
        or current_app.config.get("JWT_SECRET_KEY")
        or "super-secret-change-in-production"
    )

    payload = {
        "id": str(user["id"]),
        "email": user.get("email", ""),
        "role": user.get("role", "customer"),
        "exp": datetime.utcnow() + timedelta(hours=6),
        "iat": datetime.utcnow(),
    }

    token = jwt.encode(payload, secret, algorithm="HS256")
    return token if isinstance(token, str) else token.decode("utf-8")


def _auth_response(token: str, user: Dict[str, Any]):
    return jsonify({
        "access_token": token,
        "token": token,
        "role": user.get("role", "customer"),
        "user": {
            "id": user["id"],
            "email": user.get("email"),
            "name": user.get("name"),
            "role": user.get("role")
        }
    }), 200


def _extract_field(*names):
    data = request.get_json(silent=True) or {}
    for n in names:
        v = data.get(n)
        if v is not None:
            return str(v).strip()
    for n in names:
        v = request.form.get(n)
        if v is not None:
            return str(v).strip()
    for n in names:
        v = request.args.get(n)
        if v is not None:
            return str(v).strip()
    return ""


# ======================================================
# HEALTH
# ======================================================
@auth_bp.route("/health", methods=["GET"])
def health():
    status = get_supabase_status()
    return jsonify({"status": "ok", "supabase": status}), 200


# ======================================================
# LOGIN (EMAIL / PASSWORD)
# ======================================================
@auth_bp.route("/login", methods=["POST", "OPTIONS"])
def login():
    if request.method == "OPTIONS":
        return "", 204

    err = _ensure_supabase_configured()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    mobile = (data.get("mobile") or "").strip()
    name = (data.get("name") or "").strip()

    # Customer quick login using name + mobile (no password)
    if mobile and name and not (email or password):
        name = name.title()

        try:
            resp = (
                supabase.table("users")
                .select("id, name, email, role")
                .eq("email", mobile)  # using email field for mobile
                .limit(1)
                .execute()
            )
        except Exception as e:
            current_app.logger.error(f"Supabase query error: {e}")
            return jsonify({"error": "Auth service error"}), 500

        if resp.data:
            row = resp.data[0]
            user = {
                "id": row["id"],
                "email": row["email"],
                "role": row.get("role", "customer"),
                "name": row.get("name") or name,
            }
        else:
            # Auto-register new customer
            row_data = {
                "name": name,
                "email": mobile,
                "password_hash": generate_password_hash(str(uuid.uuid4())),
                "role": "customer",
                "created_at": datetime.utcnow().isoformat(),
            }
            try:
                insert_resp = (
                    supabase.table("users")
                    .insert(row_data)
                    .select("id, name, email, role")
                    .single()
                    .execute()
                )
                created = insert_resp.data
                user = {
                    "id": created["id"],
                    "email": created["email"],
                    "role": created["role"],
                    "name": created["name"],
                }
            except Exception as e:
                current_app.logger.error(f"Auto-registration failed: {e}")
                return jsonify({"error": "Registration failed"}), 500

        token = _create_jwt_token(user)
        return _auth_response(token, user)

    # Standard email/password login
    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400

    # Demo users (for testing without DB)
    DEMO_USERS = {
        "admin@plumblink.com": ("admin123", "admin", "11111111-1111-1111-1111-111111111111"),
        "plumber@plumblink.com": ("plumb123", "plumber", "33333333-3333-3333-3333-333333333333"),
        "customer@plumblink.com": ("cust123", "customer", "22222222-2222-2222-2222-222222222222"),
    }

    if email in DEMO_USERS:
        stored_pwd, role, uid = DEMO_USERS[email]
        if password != stored_pwd:
            return jsonify({"error": "Invalid credentials"}), 401

        user = {
            "id": uid,
            "email": email,
            "role": role,
            "name": email.split("@")[0].replace("123", "").capitalize(),
        }
        token = _create_jwt_token(user)
        return _auth_response(token, user)

    # Real Supabase login
    try:
        resp = (
            supabase.table("users")
            .select("id, name, email, password_hash, role")
            .eq("email", email)
            .single()
            .execute()
        )
    except Exception as e:
        current_app.logger.error(f"Supabase query error: {e}")
        return jsonify({"error": "Auth service error"}), 500

    if not resp.data:
        return jsonify({"error": "Invalid credentials"}), 401

    row = resp.data
    if not check_password_hash(row["password_hash"], password):
        return jsonify({"error": "Invalid credentials"}), 401

    user = {
        "id": row["id"],
        "email": row["email"],
        "role": row["role"],
        "name": row.get("name"),
    }

    token = _create_jwt_token(user)
    return _auth_response(token, user)


# ======================================================
# OTP REQUEST
# ======================================================
@auth_bp.route("/request-otp", methods=["POST", "OPTIONS"])
def request_otp():
    if request.method == "OPTIONS":
        return "", 204

    mobile = _extract_field("mobile", "phone", "number", "phone_number", "mobile_number")
    if not mobile:
        return jsonify({"error": "Mobile number required"}), 400

    otp = f"{random.randint(100000, 999999):06d}"
    _OTP_STORE[mobile] = {
        "otp": otp,
        "expires": time.time() + 300,  # 5 minutes
    }

    current_app.logger.info(f"[DEMO OTP] Mobile: {mobile} | OTP: {otp}")
    return jsonify({"message": "OTP sent (check server logs)", "otp": otp}), 200


# ======================================================
# OTP VERIFY
# ======================================================
@auth_bp.route("/verify-otp", methods=["POST", "OPTIONS"])
def verify_otp():
    if request.method == "OPTIONS":
        return "", 204

    err = _ensure_supabase_configured()
    if err:
        return err

    mobile = _extract_field("mobile", "phone", "number", "phone_number", "mobile_number")
    otp = _extract_field("otp", "code", "verification_code", "one_time_password")

    if not mobile or not otp:
        return jsonify({"error": "Mobile and OTP required"}), 400

    record = _OTP_STORE.get(mobile)
    if not record or record["otp"] != otp or record["expires"] < time.time():
        return jsonify({"error": "Invalid or expired OTP"}), 401

    # OTP valid — clean it
    _OTP_STORE.pop(mobile, None)

    # Auto-register/login customer
    try:
        resp = (
            supabase.table("users")
            .select("id, name, email, role")
            .eq("email", mobile)
            .limit(1)
            .execute()
        )
        if resp.data:
            row = resp.data[0]
            user = {
                "id": row["id"],
                "email": row["email"],
                "role": row.get("role", "customer"),
                "name": row.get("name", "Customer"),
            }
        else:
            row_data = {
                "name": "Customer",
                "email": mobile,
                "password_hash": generate_password_hash(str(uuid.uuid4())),
                "role": "customer",
                "created_at": datetime.utcnow().isoformat(),
            }
            insert_resp = (
                supabase.table("users")
                .insert(row_data)
                .select("id, name, email, role")
                .single()
                .execute()
            )
            created = insert_resp.data
            user = {
                "id": created["id"],
                "email": created["email"],
                "role": created["role"],
                "name": created["name"],
            }
    except Exception as e:
        current_app.logger.error(f"OTP login error: {e}")
        return jsonify({"error": "Login failed"}), 500

    token = _create_jwt_token(user)
    return _auth_response(token, user)


# ======================================================
# REGISTER (Customer only)
# ======================================================
@auth_bp.route("/register", methods=["POST", "OPTIONS"])
def register():
    if request.method == "OPTIONS":
        return "", 204

    err = _ensure_supabase_configured()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    name = data.get("name")
    email = (data.get("email") or "").strip().lower()
    password = data.get("password")

    if not all([name, email, password]):
        return jsonify({"error": "Name, email, and password required"}), 400

    # Check if user exists
    try:
        existing = (
            supabase.table("users")
            .select("id")
            .eq("email", email)
            .limit(1)
            .execute()
        )
        if existing.data:
            return jsonify({"error": "Email already registered"}), 409
    except Exception:
        pass

    row = {
        "name": name,
        "email": email,
        "password_hash": generate_password_hash(password),
        "role": "customer",
        "created_at": datetime.utcnow().isoformat(),
    }

    try:
        supabase.table("users").insert(row).execute()
    except Exception as e:
        current_app.logger.error(f"Registration failed: {e}")
        return jsonify({"error": "Registration failed"}), 500

    return jsonify({"message": "Registration successful! You can now login."}), 201