from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import supabase
from datetime import datetime

tracking_bp = Blueprint("tracking_bp", __name__)


@tracking_bp.route("/start", methods=["POST"])
@jwt_required()
def start_shift():
    plumber_id = get_jwt_identity()

    supabase.table("plumbers") \
        .update({"shift_started_at": datetime.utcnow()}) \
        .eq("id", plumber_id) \
        .execute()

    return jsonify({"status": "shift started"})


@tracking_bp.route("/break", methods=["POST"])
@jwt_required()
def take_break():
    plumber_id = get_jwt_identity()

    supabase.table("plumbers") \
        .update({"on_break": True}) \
        .eq("id", plumber_id) \
        .execute()

    return jsonify({"status": "on break"})
    # ...existing code...
