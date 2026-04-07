from flask import Blueprint, request, jsonify, current_app
import re
import json
import os

chatbot_bp = Blueprint("chatbot", __name__, url_prefix="/api/chatbot")

# Load intents from data/chat_intents.json


def _load_intents():
    here = os.path.dirname(__file__)
    data_file = os.path.normpath(
        os.path.join(here, "..", "..", "data", "chat_intents.json")
    )
    try:
        with open(data_file, "r", encoding="utf-8") as fh:
            return json.load(fh).get("intents", [])
    except Exception as exc:
        current_app.logger.info("Failed to load chat intents: %s", exc)
        return []


INTENTS = None


def _ensure_intents():
    global INTENTS
    if INTENTS is None:
        INTENTS = _load_intents()


def _match_intent(text: str):
    """Very small rule-based matcher using keyword presence and regex.

    Returns an intent dict or None.
    """
    _ensure_intents()
    if not text:
        return None
    t = text.lower().strip()

    # exact/keyword checks (order matters)
    checks = [
        ("greeting", r"\b(hi|hello|hey|good\s(morning|evening))\b"),
        (
            "book_plumber",
            r"\b(book|need|send|appoint).*(plumb|plumber|technician)|"
            r"\b(i need a plumber|book a plumber)\b",
        ),
        ("inquire_price", r"\b(price|cost|how much|estimate)\b"),
        (
            "cancel_booking",
            r"\b(cancel|call off).*(booking|appointment|order)\b",
        ),
        ("operating_hours", r"\b(hours|open|24/7|working time|when open)\b"),
        ("thanks", r"\b(thank|thanks|thx)\b"),
    ]

    for name, pattern in checks:
        if re.search(pattern, t):
            for intent in INTENTS:
                if intent.get("name") == name:
                    return intent

    # fallback to simple keyword matching inside intent examples
    for intent in INTENTS:
        for ex in intent.get("examples", [])[:6]:
            if ex and ex in t:
                return intent

    # If nothing matched, return fallback intent
    for intent in INTENTS:
        if intent.get("name") == "fallback":
            return intent
    return None


@chatbot_bp.route("/intents", methods=["GET"])
def list_intents():
    _ensure_intents()
    names = [i.get("name") for i in INTENTS]
    return jsonify({"intents": names}), 200


@chatbot_bp.route("/message", methods=["POST"])
def message():
    """Accepts {message: str, context: {}} and returns a reply.

    This is a rule-based prototype. For booking/cancellation flows the
    endpoint returns suggested next steps and, when possible, calls
    existing APIs (e.g. create a booking) — currently it only suggests.
    """
    payload = request.get_json(silent=True) or {}
    text = (payload.get("message") or "").strip()
    # context provided in payload is currently unused
    intent = _match_intent(text)
    if not intent:
        return jsonify(
            {
                "success": True,
                "reply": "I didn't understand that. Could you rephrase?"
            }
        ), 200

    # choose a random response from the intent (deterministic pick: first)
    responses = intent.get("responses", [])
    reply = responses[0] if responses else (
        "Sorry, I can't help with that right now."
    )

    # Small example: if user wants to book, provide suggested payload structure
    meta = {}
    if intent.get("name") == "book_plumber":
        meta["next_step"] = "collect_booking_details"
        meta["required_fields"] = [
            "issue",
            "description",
            "preferred_time",
            "contact_email",
        ]
        reply = (
            reply
            + " You can provide: issue, description, "
            + "preferred_time (ISO) and contact_email."
        )

    if intent.get("name") == "cancel_booking":
        meta["next_step"] = "collect_booking_id"
        meta["required_fields"] = ["booking_id"]

    return jsonify(
        {
            "success": True,
            "intent": intent.get("name"),
            "reply": reply,
            "meta": meta,
        }
    ), 200
