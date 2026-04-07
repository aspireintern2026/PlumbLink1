from flask import Blueprint, jsonify, current_app
from ..extensions import supabase
import json
import os

products_bp = Blueprint("products", __name__, url_prefix="/api/products")


@products_bp.route("/", methods=["GET"])
def list_products():
    """Return products from Supabase `products` table, or fall back to
    the bundled JSON file if the table or Supabase client is not available.
    """
    # Try Supabase first
    if supabase is not None:
        try:
            resp = supabase.table("products").select("*").execute()
            if getattr(resp, "error", None):
                current_app.logger.info(
                    "Supabase products read error: %s", resp.error
                )
            else:
                # resp.data is a list of dicts
                return (
                    jsonify(
                        {"source": "supabase", "products": resp.data}
                    ),
                    200,
                )
        except Exception as exc:  # defensive
            current_app.logger.info(
                "Supabase products fetch exception: %s", exc
            )

    # Fallback: local JSON file shipped with the backend
    try:
        here = os.path.dirname(__file__)
        data_file = os.path.join(
            here, "..", "..", "data", "products_a_to_z.json"
        )
        data_file = os.path.normpath(data_file)
        with open(data_file, "r", encoding="utf-8") as fh:
            products = json.load(fh)
        return jsonify({"source": "local", "products": products}), 200
    except Exception as exc:
        current_app.logger.error("Failed to load local products file: %s", exc)
        return jsonify({"error": "no products available"}), 500
