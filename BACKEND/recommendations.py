from flask import Blueprint, jsonify, request

recommendations_bp = Blueprint(
    "recommendations", __name__, url_prefix="/api/recommendations"
)


@recommendations_bp.route(
    "/", methods=["GET", "OPTIONS"], strict_slashes=False
)
def get_recommendations():
    if request.method == "OPTIONS":
        return "", 204

    issue = (request.args.get("issue") or "").strip()
    limit = request.args.get("limit", default=6, type=int)

    plumbers = [
        {
            "id": 1,
            "name": "Ramesh Kumar",
            "rating": 4.9,
            "city": "Bangalore",
            "meta": {"skills": ["Leak Repair", "Drain Cleaning"]},
        },
        {
            "id": 2,
            "name": "Suresh Patel",
            "rating": 4.7,
            "city": "Mumbai",
            "meta": {"skills": ["Water Heater", "Bathroom Fittings"]},
        },
        {
            "id": 3,
            "name": "Arun Nair",
            "rating": 4.8,
            "city": "Chennai",
            "meta": {"skills": ["Pipe Replacement", "Emergency Repairs"]},
        },
    ]

    if issue:
        plumbers = [
            p
            for p in plumbers
            if any(issue.lower() in s.lower() for s in p["meta"]["skills"])
        ]

    result = {
        "success": True,
        "count": min(len(plumbers), limit),
        "recommendations": plumbers[:limit],
    }

    return jsonify(result)
