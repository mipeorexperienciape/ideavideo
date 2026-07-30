"""Definición de planes, cuotas y precios (soles e internacional)."""

PLANS = {
    "free": {
        "name": "Gratis", "price_pen": 0, "price_usd": 0,
        "monthly_quota": 0,          # sin cuota mensual: solo 1 demo por IP
        "watermark": True, "support": False,
        "tagline": "Prueba la herramienta sin pagar.",
        "desc": "1 video demo con marca de agua",
        "features": [
            "1 video demo gratis",
            "Voces con IA (español e inglés)",
            "Formatos 16:9 (YouTube) y 9:16 (Shorts)",
            "Subtítulos automáticos",
            "Con marca de agua",
        ],
    },
    "emprendedor": {
        "name": "Emprendedor", "price_pen": 39, "price_usd": 11,
        "monthly_quota": 20, "watermark": False, "support": False,
        "tagline": "Empieza a crear contenido en serio.",
        "desc": "~20 videos/mes · 16:9 y 9:16 · sin marca de agua",
        "features": [
            "20 videos al mes",
            "Sin marca de agua",
            "Voces premium (Perú, México, España, inglés)",
            "Imágenes automáticas por escena",
            "Música de fondo incluida",
            "Subtítulos quemados listos para redes",
            "Descarga en alta definición",
        ],
    },
    "creador": {
        "name": "Creador", "price_pen": 89, "price_usd": 25,
        "monthly_quota": 60, "watermark": False, "support": False,
        "tagline": "Sube shorts todos los días.",
        "desc": "~60 videos/mes · prioridad de render · más voces",
        "features": [
            "60 videos al mes",
            "Todo lo del plan Emprendedor",
            "Prioridad en la cola de render",
            "Más voces y estilos de guion",
            "Soporte por chat",
            "Ideal para creadores y tiendas",
        ],
    },
    "pro": {
        "name": "Pro / Agencia", "price_pen": 199, "price_usd": 55,
        "monthly_quota": 300, "watermark": False, "support": True,
        "tagline": "Para agencias y alto volumen.",
        "desc": "Volumen alto · soporte y mentorías · versión Desktop",
        "features": [
            "300 videos al mes",
            "Todo lo del plan Creador",
            "Soporte y mentorías 1 a 1",
            "Versión Desktop incluida",
            "Licencia de uso comercial / agencia",
            "Máxima prioridad de render",
        ],
    },
}

PAID_PLANS = ["emprendedor", "creador", "pro"]

def get_plan(pid):
    return PLANS.get(pid, PLANS["free"])
