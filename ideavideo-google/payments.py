"""
Capa de pagos agnóstica: Stripe (internacional) y Mercado Pago (Perú/LatAm).
- Si hay claves configuradas, crea una sesión de pago real.
- Si no hay claves (o PAYMENTS_TEST=1), devuelve una URL de SIMULACIÓN para probar todo el flujo sin cobrar.
Las claves reales se ponen en .env cuando estés listo para cobrar.
"""
import os, requests
from plans import get_plan

def has_keys(gateway):
    if gateway == "stripe": return bool(os.getenv("STRIPE_SECRET_KEY"))
    if gateway == "mercadopago": return bool(os.getenv("MP_ACCESS_TOKEN"))
    return False

def test_mode():
    return os.getenv("PAYMENTS_TEST", "1") == "1"

def create_checkout(gateway, plan_id, user, base_url):
    """Devuelve una URL a la que redirigir al usuario para pagar."""
    plan = get_plan(plan_id)
    if test_mode() or not has_keys(gateway):
        # Simulación: permite probar la activación del plan sin cobrar de verdad.
        return f"{base_url}/pay/simulate?plan={plan_id}&gateway={gateway}"
    if gateway == "stripe":
        return _stripe(plan_id, plan, user, base_url)
    if gateway == "mercadopago":
        return _mercadopago(plan_id, plan, user, base_url)
    raise ValueError("Pasarela no soportada")

def _stripe(plan_id, plan, user, base):
    key = os.getenv("STRIPE_SECRET_KEY")
    data = {
        "mode": "subscription",
        "success_url": base + "/?paid=1",
        "cancel_url": base + "/?canceled=1",
        "customer_email": user["email"],
        "line_items[0][price_data][currency]": "usd",
        "line_items[0][price_data][product_data][name]": f"IdeaVideo {plan['name']}",
        "line_items[0][price_data][unit_amount]": str(int(plan["price_usd"]) * 100),
        "line_items[0][price_data][recurring][interval]": "month",
        "line_items[0][quantity]": "1",
        "metadata[user_id]": str(user["id"]),
        "metadata[plan]": plan_id,
    }
    r = requests.post("https://api.stripe.com/v1/checkout/sessions", data=data, auth=(key, ""), timeout=30)
    r.raise_for_status()
    return r.json()["url"]

def _mercadopago(plan_id, plan, user, base):
    # Nota: para suscripción recurrente real usar la API de 'preapproval'. Aquí una preferencia (pago mensual) para el MVP.
    token = os.getenv("MP_ACCESS_TOKEN")
    body = {
        "items": [{"title": f"IdeaVideo {plan['name']}", "quantity": 1,
                   "unit_price": float(plan["price_pen"]), "currency_id": "PEN"}],
        "payer": {"email": user["email"]},
        "back_urls": {"success": base + "/?paid=1"},
        "auto_return": "approved",
        "metadata": {"user_id": user["id"], "plan": plan_id},
        "notification_url": base + "/webhook/mercadopago",
    }
    r = requests.post("https://api.mercadopago.com/checkout/preferences", json=body,
                      headers={"Authorization": f"Bearer {token}"}, timeout=30)
    r.raise_for_status()
    return r.json()["init_point"]

# --- Webhooks reales (se completan con la cuenta de cada pasarela) ---
def parse_stripe_event(payload):
    """Devuelve (user_id, plan) si el pago fue exitoso, o None. (Verificar la firma con STRIPE_WEBHOOK_SECRET en producción.)"""
    try:
        if payload.get("type") in ("checkout.session.completed", "invoice.paid"):
            md = payload["data"]["object"].get("metadata", {})
            return int(md["user_id"]), md["plan"]
    except Exception:
        pass
    return None

def parse_mp_event(payload, args=None):
    """Mercado Pago notifica un pago. En producción: consultar el pago y leer metadata.user_id/plan."""
    try:
        pid = (args or {}).get("data.id") or (payload or {}).get("data", {}).get("id")
        token = os.getenv("MP_ACCESS_TOKEN")
        if pid and token:
            r = requests.get(f"https://api.mercadopago.com/v1/payments/{pid}",
                             headers={"Authorization": f"Bearer {token}"}, timeout=20).json()
            if r.get("status") == "approved":
                md = r.get("metadata", {})
                return int(md["user_id"]), md["plan"]
    except Exception:
        pass
    return None
