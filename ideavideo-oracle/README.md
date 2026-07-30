
# IdeaVideo SaaS — Generación de videos con IA (suscripción)

Web completa para vender la generación de videos por suscripción: las personas se **registran**, crean **1 video demo gratis por IP** (con marca de agua) y pagan un **plan mensual** (con cuota de videos) mediante **Stripe** (internacional) y **Mercado Pago** (Perú/LatAm). Incluye panel de usuario y panel de administración.

*(IdeaVideo es un nombre de trabajo, editable — cambia la marca con `BRAND_A`/`BRAND_B`.)*


## Qué incluye (Fase 1 · MVP)

- **Registro e inicio de sesión** (por sesión segura).
- **Demo gratis por IP** con marca de agua; al agotarlo, invita a elegir un plan.
- **Planes con cuota mensual** (Gratis / Emprendedor / Creador / Pro).
- **Pagos con Stripe + Mercado Pago** mediante una capa agnóstica, con **modo simulación** para probar todo el flujo sin cobrar.
- **Motor de video** (idea → guion → voz → escenas → montaje) con voz **Piper** (comercial/offline) y respaldos edge-tts/espeak.
- **Panel de usuario** (mis videos, plan, consumo) y **panel de administración** (usuarios, ingresos estimados, videos).

## Requisitos

- **Python 3.10+**, **ffmpeg** (obligatorio), **espeak-ng** (respaldo de voz).
- Mac: `brew install ffmpeg espeak-ng` · Ubuntu: `sudo apt install ffmpeg espeak-ng`.

## Cómo correrlo

```bash
pip install -r requirements.txt
python app.py
```

Abre **http://localhost:8000**. Regístrate y crea tu video demo. Para probar sin conexión: `DEMO_MODE=1 python app.py`.

**Cuenta de administrador** (se crea sola en el primer arranque): `admin@ideavideo.local` / `admin123` (cámbiala en `.env`).

## Cómo funciona el negocio

| Plan | Precio | Cuota | Marca de agua |
|------|--------|-------|----------------|
| Gratis | S/ 0 | 1 demo por IP | Sí |
| Emprendedor | S/ 39 / US$ 11 | ~20 videos/mes | No |
| Creador | S/ 89 / US$ 25 | ~60 videos/mes | No |
| Pro / Agencia | S/ 199 / US$ 55 | volumen alto + soporte | No |

Edita precios y cuotas en `plans.py`.

## Activar los pagos reales

Por defecto `PAYMENTS_TEST=1` (simulación: el flujo funciona pero no cobra). Para cobrar de verdad:

1. **Stripe** (internacional): crea tu cuenta en https://dashboard.stripe.com, copia tu `STRIPE_SECRET_KEY` al `.env` y configura el webhook a `/webhook/stripe`.
2. **Mercado Pago** (Perú/LatAm): crea tu app en https://www.mercadopago.com.pe/developers, copia tu `MP_ACCESS_TOKEN` al `.env` y configura la notificación a `/webhook/mercadopago`.
3. Pon `PAYMENTS_TEST=0`.

La web enruta al pago según lo que elija el cliente (botón "Perú · Mercado Pago" o "Internacional · Stripe").

## Voz comercial: Piper (recomendado)

Para el producto de venta conviene **Piper TTS** (open source, comercial, offline). Instala el binario `piper`, descarga una voz en español (`.onnx`) y añade en `.env`:

```
PIPER_MODEL=/ruta/es_ES-voz.onnx
```

Si no está configurado, usa edge-tts (gratis, requiere internet) y, en último caso, espeak (offline).

## Publicar en internet (Railway)

Sube esta carpeta a GitHub → Railway → **Deploy from GitHub repo**. `nixpacks.toml` instala ffmpeg/espeak; `Procfile` arranca la app. Configura las variables de entorno (`SECRET_KEY`, claves de pago, etc.). Para persistencia, monta un disco para `ideavideo.db` y `output/`.

## Estructura

```
app.py         servidor Flask (rutas, cuotas, jobs)
db.py          base de datos SQLite
auth.py        registro/login por sesión
plans.py       planes, precios y cuotas
payments.py    Stripe + Mercado Pago (con modo simulación)
pipeline.py    motor de video (Piper/edge/espeak + marca de agua + ffmpeg)
static/        frontend (landing, auth, generador, planes, admin)
```

## Roadmap (siguientes fases)

Fase 2: facturación recurrente real (webhooks completos), programa de referidos, imágenes por escena y música. Fase 3: versión **Desktop Pro** (ejecutable con licencia) apoyada en Piper offline.

## Notas

- Cada render usa CPU; en producción usa un host con CPU suficiente y considera una cola con workers para varios usuarios a la vez.
- El límite "1 demo por IP" es un filtro razonable, no infalible (VPN); combínalo con verificación de correo.


## Novedades de la Fase 2

- **Imágenes por escena** desde el banco gratuito **Pexels** (configura `PEXELS_API_KEY`). Sin clave, usa fondos de marca.
- **Música de fondo**: deja un `.mp3` libre de derechos en `assets/music/`.
- **Verificación de correo**: al registrarse se exige confirmar el correo antes de generar. Con SMTP configurado se envía por email; sin SMTP, el enlace se muestra en pantalla (modo prueba).
- **Programa de referidos**: cada usuario tiene un enlace `/?ref=CODIGO`; por cada referido registrado gana **5 créditos** (videos extra sin marca de agua).
- **Suscripción completa**: activación con **vencimiento a 30 días**, **cancelación** (mantiene acceso hasta el fin del período) y **webhooks** de Stripe y Mercado Pago para renovaciones.
