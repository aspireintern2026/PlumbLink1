from flask import Blueprint, request, jsonify, current_app
from ..extensions import supabase
import os
import uuid
import urllib.parse

checkout_bp = Blueprint("checkout", __name__, url_prefix="/api/checkout")

# In-memory fallback for orders when Supabase table is missing
_ORDERS_FALLBACK = []


def _make_upi_uri(
    payee_vpa: str,
    payee_name: str,
    amount: float,
    note: str | None = None,
):
    """Return a UPI uri suitable for QR encoding."""
    # Example: upi://pay?pa=merchant@upi&pn=Merchant+Name&am=100.00
    # &cu=INR&tn=Order+123
    params = {
        "pa": payee_vpa,
        "pn": payee_name,
        "am": f"{amount:.2f}",
        "cu": "INR"
    }
    if note:
        params["tn"] = note
    uri = "upi://pay?" + urllib.parse.urlencode(
        params, quote_via=urllib.parse.quote
    )
    return uri


@checkout_bp.route("/create", methods=["POST"])
def create_checkout():
    """Create an order + payment info.

    Request JSON: {cart:[], amount: number,
    payment_method: 'qr'|'card'|'upi'|'cash'}
    """
    data = request.get_json(silent=True) or {}
    cart = data.get("cart") or []
    amount = data.get("amount") or sum(
        (float(i.get("price", 0)) for i in cart)
    )
    amount = float(amount)
    payment_method = data.get("payment_method", "qr")

    order = {
        "id": str(uuid.uuid4()),
        "cart": cart,
        "amount": amount,
        "payment_method": payment_method,
        "status": "created",
    }

    # Add payment-specific payloads
    if payment_method in ("qr", "upi"):
        # Use a demo UPI id; replace with your merchant VPA in production
        merchant_vpa = os.getenv("UPI_MERCHANT_VPA", "plumblink@upi")
        merchant_name = os.getenv("UPI_MERCHANT_NAME", "PlumbLink")
        upi_uri = _make_upi_uri(
            merchant_vpa, merchant_name, amount, note=f"Order {order['id']}"
        )
        # Public QR generation via Google Chart API (free): encode the UPI URI
        qr_base = "https://chart.googleapis.com/chart?chs=300x300&cht=qr&chl="
        qr_url = qr_base + urllib.parse.quote(upi_uri)
        order["upi_uri"] = upi_uri
        order["qr_url"] = qr_url

    if payment_method == "card":
        # No real card processing here — return a simulated payment token/url
        order["card_checkout_token"] = f"card_mock_{order['id']}"

    if payment_method == "cash":
        order["status"] = "pending_cash_on_delivery"

    # Try to persist to Supabase; fallback to in-memory list
    if supabase is not None:
        try:
            payload = {
                "id": order["id"],
                "amount": amount,
                "payment_method": payment_method,
                "status": order["status"],
                "cart": cart,
            }
            resp = supabase.table("orders").insert(payload).execute()
            if getattr(resp, "error", None):
                current_app.logger.info(
                    "Supabase orders insert error: %s", resp.error
                )
            else:
                order["persisted"] = True
        except Exception as exc:
            current_app.logger.info(
                "Supabase orders insert exception: %s", exc
            )

    if not order.get("persisted"):
        _ORDERS_FALLBACK.append(order)

    return jsonify({"success": True, "order": order}), 201


@checkout_bp.route("/confirm", methods=["POST"])
def confirm_payment():
    """Confirm payment for an order (simulate).

    Request JSON: {order_id, method: 'card'|'upi'|'cash'}
    """
    data = request.get_json(silent=True) or {}
    order_id = data.get("order_id")
    if not order_id:
        return jsonify({"success": False, "error": "order_id required"}), 400

    # Try Supabase first
    if supabase is not None:
        try:
            resp = (
                supabase.table("orders")
                .update({"status": "paid"})
                .eq("id", order_id)
                .execute()
            )
            if getattr(resp, "error", None):
                current_app.logger.info(
                    "Supabase orders update error: %s", resp.error
                )
            else:
                return (
                    jsonify(
                        {
                            "success": True,
                            "order_id": order_id,
                            "status": "paid",
                        }
                    ),
                    200,
                )
        except Exception as exc:
            current_app.logger.info(
                "Supabase orders update exception: %s", exc
            )

    # Fallback: update in-memory
    for o in _ORDERS_FALLBACK:
        if o.get("id") == order_id:
            o["status"] = "paid"
            return (
                jsonify(
                    {
                        "success": True,
                        "order_id": order_id,
                        "status": "paid",
                    }
                ),
                200,
            )

    return jsonify({"success": False, "error": "order not found"}), 404