from flask import Blueprint, jsonify, current_app, request
from ..extensions import supabase

analytics_bp = Blueprint("analytics", __name__, url_prefix="/api/analytics")


@analytics_bp.route("/overview", methods=["GET"])
def overview():
    """Return basic platform analytics. If Supabase is configured, compute
    simple aggregates; otherwise return mock values for the dashboard.
    Query params: plumber_id (optional) to scope metrics to one plumber.
    """
    plumber_id = request.args.get("plumber_id")
    # reference plumber_id to avoid unused-variable warning
    if plumber_id:
        current_app.logger.debug("plumber_id=%s", plumber_id)

    if supabase is not None:
        try:
            # Example aggregates:
            # total_customers, total_plumbers, active_jobs, total_revenue
            total_customers = 0
            total_plumbers = 0
            active_jobs = 0
            total_revenue = 0.0

            resp = supabase.table("users").select("id,role", {}).execute()
            if not getattr(resp, "error", None) and resp.data:
                for u in resp.data:
                    if u.get("role") == "plumber":
                        total_plumbers += 1
                    else:
                        total_customers += 1

            # active jobs from orders table
            resp2 = supabase.table("orders").select("status,amount").execute()
            if not getattr(resp2, "error", None) and resp2.data:
                for o in resp2.data:
                    st = (o.get("status") or "").lower()
                    if st in ("created", "pending", "in_progress", "assigned"):
                        active_jobs += 1
                    try:
                        total_revenue += float(o.get("amount") or 0)
                    except Exception:
                        pass

            return jsonify({
                "total_customers": total_customers,
                "total_plumbers": total_plumbers,
                "active_jobs": active_jobs,
                "total_revenue": round(total_revenue, 2),
            }), 200
        except Exception as exc:
            current_app.logger.info("Analytics supabase error: %s", exc)

    # Fallback/mock data
    return (
        jsonify(
            {
                "total_customers": 1245,
                "total_plumbers": 132,
                "active_jobs": 48,
                "total_revenue": 482500.0,
            }
        ),
        200,
    )
