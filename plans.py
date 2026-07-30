"""Definición de planes, cuotas y precios (soles e internacional)."""

PLANS = {
    "free": {
        "name": "Gratis", "price_pen": 0, "price_usd": 0,
        "monthly_quota": 0,          # sin cuota mensual: solo 1 demo por IP
        "watermark": True, "support": False,
        "desc": "1 video demo con marca de agua",
    },
    "emprendedor": {
        "name": "Emprendedor", "price_pen": 39, "price_usd": 11,
        "monthly_quota": 20, "watermark": False, "support": False,
        "desc": "~20 videos/mes · 16:9 y 9:16 · sin marca de agua",
    },
    "creador": {
        "name": "Creador", "price_pen": 89, "price_usd": 25,
        "monthly_quota": 60, "watermark": False, "support": False,
        "desc": "~60 videos/mes · prioridad de render · más voces",
    },
    "pro": {
        "name": "Pro / Agencia", "price_pen": 199, "price_usd": 55,
        "monthly_quota": 300, "watermark": False, "support": True,
        "desc": "Volumen alto · soporte y mentorías · versión Desktop",
    },
}

PAID_PLANS = ["emprendedor", "creador", "pro"]

def get_plan(pid):
    return PLANS.get(pid, PLANS["free"])
