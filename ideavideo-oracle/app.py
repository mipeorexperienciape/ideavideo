"""
IdeaVideo SaaS — servidor Flask (versión Pro: cola de render, almacenamiento en nube,
correos automáticos, métricas, páginas legales). Sobre la Fase 2.
"""
import os, uuid, secrets, traceback, time, threading, shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from flask import Flask, request, jsonify, session, send_from_directory, send_file, redirect
import pipeline as P
import storage
from db import (get_db, migrate, gen_code, videos_this_month, ip_used_demo, mark_ip_demo,
                active_subscription, expire_if_needed)
from auth import hash_pw, check_pw, current_user, login_required, admin_required
from plans import PLANS, PAID_PLANS, get_plan
import payments

BASE = Path(__file__).parent
OUT = BASE / "output"; OUT.mkdir(exist_ok=True)
WORK = BASE / "work"; WORK.mkdir(exist_ok=True)
(BASE / "assets" / "music").mkdir(parents=True, exist_ok=True)

app = Flask(__name__, static_folder="static", static_url_path="")
app.secret_key = os.getenv("SECRET_KEY", "cambia-esto-en-produccion")
JOBS = {}
# Cola de render con concurrencia limitada (escala: sube RENDER_WORKERS o migra a Redis+workers).
EXECUTOR = ThreadPoolExecutor(max_workers=int(os.getenv("RENDER_WORKERS", "1")))

# --- Limpieza automática de videos (ahorra disco/memoria) ---
# Los videos NO se guardan en el repositorio: se generan en disco temporal del servidor.
# Se borran al descargarlos y, si no se descargan, a las VIDEO_TTL_H horas.
VIDEO_TTL_H = float(os.getenv("VIDEO_TTL_H", "24"))

def _safe_del(path):
    try:
        p = Path(path)
        if p.is_file(): p.unlink()
    except Exception as e:
        print("no se pudo borrar", path, e)

def _sweep_once():
    now = time.time()
    ttl = VIDEO_TTL_H * 3600
    # borra .mp4 vencidos en output/
    for f in OUT.glob("*.mp4"):
        try:
            if now - f.stat().st_mtime > ttl: f.unlink()
        except Exception: pass
    # borra carpetas de trabajo temporales de más de 2 horas
    for d in WORK.iterdir():
        try:
            if d.is_dir() and now - d.stat().st_mtime > 7200: shutil.rmtree(d, ignore_errors=True)
        except Exception: pass

def _sweeper():
    while True:
        try: _sweep_once()
        except Exception as e: print("sweeper error:", e)
        time.sleep(1800)  # cada 30 min

threading.Thread(target=_sweeper, daemon=True).start()

VOICES = [
    {"id":"es-PE-CamilaNeural","label":"Camila — Mujer (Perú)","lang":"es"},
    {"id":"es-PE-AlexNeural","label":"Alex — Hombre (Perú)","lang":"es"},
    {"id":"es-MX-DaliaNeural","label":"Dalia — Mujer (México)","lang":"es"},
    {"id":"es-ES-ElviraNeural","label":"Elvira — Mujer (España)","lang":"es"},
    {"id":"en-US-AriaNeural","label":"Aria — Woman (US)","lang":"en"},
]
REFERRAL_BONUS = 5
APP_NAME = os.getenv("BRAND_A", "Idea") + os.getenv("BRAND_B", "Video")

def client_ip():
    return (request.headers.get("X-Forwarded-For", request.remote_addr) or "0.0.0.0").split(",")[0].strip()

def send_email(to, subject, body):
    host = os.getenv("SMTP_HOST")
    if not host:
        print(f"[correo simulado] Para: {to} | {subject}\n{body}\n"); return False
    try:
        import smtplib
        from email.mime.text import MIMEText
        msg = MIMEText(body); msg["Subject"] = subject
        msg["From"] = os.getenv("SMTP_FROM", os.getenv("SMTP_USER", "")); msg["To"] = to
        s = smtplib.SMTP(host, int(os.getenv("SMTP_PORT", 587))); s.starttls()
        s.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASS")); s.send_message(msg); s.quit()
        return True
    except Exception as e:
        print("correo falló:", e); return False

def ensure_admin():
    con = get_db()
    if not con.execute("SELECT 1 FROM users WHERE is_admin=1").fetchone():
        email = os.getenv("ADMIN_EMAIL", "admin@ideavideo.local"); pw = os.getenv("ADMIN_PASSWORD", "admin123")
        if not con.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
            con.execute("INSERT INTO users(name,email,password_hash,plan,is_admin,email_verified,referral_code) VALUES(?,?,?,?,1,1,?)",
                        ("Admin", email, hash_pw(pw), "pro", gen_code())); con.commit()
    con.close()

# ---------------- AUTH ----------------
@app.post("/api/register")
def register():
    d = request.json or {}
    name = (d.get("name") or "").strip(); email = (d.get("email") or "").strip().lower(); pw = d.get("password") or ""
    ref = (d.get("ref") or "").strip()
    if not email or len(pw) < 6:
        return jsonify({"error": "Correo válido y contraseña de al menos 6 caracteres."}), 400
    con = get_db()
    if con.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
        con.close(); return jsonify({"error": "Ese correo ya está registrado."}), 409
    referred_by = None
    if ref:
        row = con.execute("SELECT id FROM users WHERE referral_code=?", (ref,)).fetchone()
        if row: referred_by = row["id"]
    token = secrets.token_urlsafe(16)
    cur = con.execute("INSERT INTO users(name,email,password_hash,plan,email_verified,verify_token,referral_code,referred_by) VALUES(?,?,?,?,0,?,?,?)",
                      (name, email, hash_pw(pw), "free", token, gen_code(), referred_by))
    uid = cur.lastrowid
    if referred_by:
        con.execute("UPDATE users SET bonus_credits = bonus_credits + ? WHERE id=?", (REFERRAL_BONUS, referred_by))
    con.commit(); con.close()
    session["uid"] = uid
    link = request.host_url.rstrip("/") + "/verify?token=" + token
    sent = send_email(email, f"Bienvenido a {APP_NAME} — confirma tu correo",
                      f"¡Hola! Gracias por registrarte en {APP_NAME}.\nConfirma tu cuenta aquí: {link}")
    return jsonify({"ok": True, "verify_link": None if sent else link})

@app.post("/api/login")
def login():
    d = request.json or {}
    con = get_db()
    u = con.execute("SELECT * FROM users WHERE email=?", ((d.get("email") or "").strip().lower(),)).fetchone()
    con.close()
    if not u or not check_pw(d.get("password") or "", u["password_hash"]):
        return jsonify({"error": "Credenciales inválidas."}), 401
    session["uid"] = u["id"]; return jsonify({"ok": True})

@app.post("/api/logout")
def logout():
    session.clear(); return jsonify({"ok": True})

@app.get("/verify")
def verify():
    token = request.args.get("token", "")
    con = get_db(); u = con.execute("SELECT id FROM users WHERE verify_token=?", (token,)).fetchone()
    if u:
        con.execute("UPDATE users SET email_verified=1, verify_token=NULL WHERE id=?", (u["id"],)); con.commit(); con.close()
        return redirect("/?verified=1")
    con.close(); return "Enlace de verificación inválido.", 400

@app.get("/api/me")
def me():
    u = current_user()
    if not u: return jsonify({"user": None})
    expire_if_needed(u["id"]); u = current_user()
    con = get_db()
    f = con.execute("SELECT email_verified,referral_code,bonus_credits FROM users WHERE id=?", (u["id"],)).fetchone()
    ref_count = con.execute("SELECT COUNT(*) c FROM users WHERE referred_by=?", (u["id"],)).fetchone()["c"]
    con.close()
    plan = get_plan(u["plan"]); used = videos_this_month(u["id"]); sub = active_subscription(u["id"])
    u["email_verified"] = f["email_verified"]
    return jsonify({"user": u, "plan": {**plan, "id": u["plan"]},
        "usage": {"used": used, "quota": plan["monthly_quota"], "bonus": f["bonus_credits"]},
        "demo_used": ip_used_demo(client_ip()),
        "referral": {"code": f["referral_code"], "count": ref_count, "bonus": f["bonus_credits"],
                     "link": request.host_url.rstrip("/") + "/?ref=" + (f["referral_code"] or "")},
        "subscription": ({"status": sub["status"], "plan": sub["plan"], "period_end": sub["current_period_end"],
                          "gateway": sub["gateway"]} if sub else None)})

@app.get("/api/plans")
def api_plans():
    return jsonify({"plans": [{"id": k, **v} for k, v in PLANS.items()], "voices": VOICES})

# ---------------- GENERAR (cola) ----------------
def _bonus(uid):
    con = get_db(); r = con.execute("SELECT bonus_credits FROM users WHERE id=?", (uid,)).fetchone(); con.close()
    return r["bonus_credits"] if r else 0
def _verified(uid):
    con = get_db(); r = con.execute("SELECT email_verified FROM users WHERE id=?", (uid,)).fetchone(); con.close()
    return bool(r and r["email_verified"])

@app.post("/api/generate")
@login_required
def generate():
    u = current_user(); d = request.json or {}
    idea = (d.get("idea") or "").strip()
    if len(idea) < 10: return jsonify({"error": "Escribe tu idea con un poco más de detalle."}), 400
    if not _verified(u["id"]):
        return jsonify({"error": "Confirma tu correo antes de generar videos.", "need_verify": True}), 403
    plan = get_plan(u["plan"]); ip = client_ip(); used = videos_this_month(u["id"]); bonus = _bonus(u["id"])
    is_demo = u["plan"] not in PAID_PLANS; watermark = False; consume_credit = False
    if u["plan"] in PAID_PLANS:
        if used < plan["monthly_quota"]: pass
        elif bonus > 0: consume_credit = True
        else: return jsonify({"error": f"Alcanzaste el límite de tu plan ({plan['monthly_quota']}/mes). Sube de plan o invita amigos.", "need_plan": True}), 402
    else:
        if bonus > 0: consume_credit = True
        elif not ip_used_demo(ip): watermark = True
        else: return jsonify({"error": "Ya usaste tu video demo gratis. Elige un plan o invita amigos para ganar créditos.", "need_plan": True}), 402
    cfg = {"idea": idea, "tone": d.get("tone","informativo"), "scenes": max(2, min(8, int(d.get("scenes",5)))),
           "lang": d.get("lang","es"), "voice": d.get("voice","es-PE-CamilaNeural"),
           "format": d.get("format","16:9") if d.get("format") in P.FORMATS else "16:9",
           "burn_subs": bool(d.get("burn_subs", True)), "watermark": watermark,
           "user_id": u["id"], "is_demo": is_demo and watermark, "consume_credit": consume_credit, "ip": ip}
    job_id = uuid.uuid4().hex[:12]
    JOBS[job_id] = {"status":"queued","progress":0,"message":"En cola…","video":None,"error":None}
    EXECUTOR.submit(run_job, job_id, cfg)
    return jsonify({"job_id": job_id})

def run_job(job_id, cfg):
    job = JOBS[job_id]
    try:
        def prog(p, m): job.update(status="running", progress=p, message=m)
        prog(5, "Analizando tu idea…")
        segs = P.expand_idea_with_llm(cfg["idea"], cfg["tone"], cfg["scenes"], cfg["lang"]) \
               or P.build_from_idea(cfg["idea"], cfg["tone"], cfg["scenes"], cfg["lang"])
        out_file = OUT / f"{job_id}.mp4"
        engine = "espeak" if os.getenv("DEMO_MODE") else "auto"
        P.render(segs, cfg["format"], WORK / job_id, str(out_file), voice=cfg["voice"],
                 engine=engine, burn_subs=cfg["burn_subs"], watermark=cfg["watermark"], progress=prog)
        url = storage.publish(str(out_file), f"{job_id}.mp4")
        con = get_db()
        con.execute("INSERT INTO videos(user_id,title,fmt,filename,watermark) VALUES(?,?,?,?,?)",
                    (cfg["user_id"], cfg["idea"][:80], cfg["format"], f"{job_id}.mp4", int(cfg["watermark"])))
        if cfg["consume_credit"]:
            con.execute("UPDATE users SET bonus_credits = MAX(0, bonus_credits-1) WHERE id=?", (cfg["user_id"],))
        con.commit(); con.close()
        if cfg["is_demo"]: mark_ip_demo(cfg["ip"])
        job.update(status="done", video=url, progress=100, message="¡Video listo!")
    except Exception as e:
        traceback.print_exc(); job.update(status="error", error=str(e), message=f"Error: {e}")

@app.get("/api/job/<job_id>")
def job(job_id):
    j = JOBS.get(job_id)
    if not j: return jsonify({"error": "No encontrado"}), 404
    return jsonify({k: j.get(k) for k in ("status", "progress", "message", "video", "error")})

@app.get("/api/videos")
@login_required
def my_videos():
    u = current_user(); con = get_db()
    rows = con.execute("SELECT id,title,fmt,filename,watermark,created_at FROM videos WHERE user_id=? ORDER BY id DESC LIMIT 50", (u["id"],)).fetchall()
    con.close(); return jsonify({"videos": [dict(r) for r in rows]})

@app.get("/videos/<path:name>")
def videos(name):
    # Seguridad: solo nombre de archivo simple dentro de output/
    safe = os.path.basename(name)
    fpath = OUT / safe
    if not fpath.is_file():
        return jsonify({"error": "Este video ya no está disponible (se elimina tras descargarlo o a las 24 h)."}), 404
    if request.args.get("dl"):
        # Descarga explícita: envía el archivo por streaming y lo borra al terminar.
        from flask import Response
        size = fpath.stat().st_size
        def stream():
            try:
                with open(fpath, "rb") as f:
                    while True:
                        chunk = f.read(262144)
                        if not chunk: break
                        yield chunk
            finally:
                _safe_del(fpath)
        resp = Response(stream(), mimetype="video/mp4")
        resp.headers["Content-Length"] = str(size)
        resp.headers["Content-Disposition"] = f'attachment; filename="{safe}"'
        return resp
    # Reproducción en el sitio: send_file normal (permite adelantar/retroceder).
    return send_file(fpath)

# ---------------- PAGOS ----------------
@app.post("/api/checkout")
@login_required
def checkout():
    d = request.json or {}; plan_id, gateway = d.get("plan"), d.get("gateway", "stripe")
    if plan_id not in PAID_PLANS: return jsonify({"error": "Plan inválido."}), 400
    try:
        return jsonify({"url": payments.create_checkout(gateway, plan_id, current_user(), request.host_url.rstrip("/"))})
    except Exception as e:
        return jsonify({"error": f"No se pudo iniciar el pago: {e}"}), 500

@app.get("/pay/simulate")
@login_required
def pay_simulate():
    plan_id = request.args.get("plan"); gateway = request.args.get("gateway", "stripe"); plan = get_plan(plan_id)
    return f"""<html><head><meta charset='utf-8'><title>Simulación de pago</title><style>
    body{{font-family:system-ui;background:#0d0a1a;color:#fff;display:flex;min-height:100vh;align-items:center;justify-content:center}}
    .c{{background:#171331;border:1px solid #332a5a;border-radius:16px;padding:30px;max-width:380px;text-align:center}}
    .b{{background:linear-gradient(135deg,#7c3aed,#22c55e);border:0;color:#fff;font-weight:800;padding:14px 22px;border-radius:12px;font-size:16px;cursor:pointer;margin-top:16px}}
    small{{color:#a99fce}}</style></head><body><div class='c'><h2>Simulación de pago</h2>
    <p>Plan <b>{plan['name']}</b> · {gateway.title()}<br>S/ {plan['price_pen']} / US$ {plan['price_usd']} al mes</p>
    <small>Modo de prueba: no se cobra. En producción iría el checkout real de {gateway.title()}.</small><br>
    <button class='b' onclick="fetch('/api/pay/confirm',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{plan:'{plan_id}',gateway:'{gateway}'}})}}).then(()=>location.href='/?paid=1')">Confirmar pago (simulado)</button>
    </div></body></html>"""

@app.post("/api/pay/confirm")
@login_required
def pay_confirm():
    d = request.json or {}; plan_id = d.get("plan"); gateway = d.get("gateway", "stripe")
    if plan_id not in PAID_PLANS: return jsonify({"error": "Plan inválido."}), 400
    if not (payments.test_mode() or not payments.has_keys(gateway)):
        return jsonify({"error": "En modo real la activación llega por webhook."}), 403
    _activate(current_user()["id"], plan_id, gateway, "sim"); return jsonify({"ok": True})

def _activate(user_id, plan_id, gateway, external_id, renew=False):
    plan = get_plan(plan_id); con = get_db()
    con.execute("UPDATE users SET plan=? WHERE id=?", (plan_id, user_id))
    end = con.execute("SELECT datetime('now','+30 day') e").fetchone()["e"]
    con.execute("INSERT INTO subscriptions(user_id,plan,gateway,external_id,status,current_period_end) VALUES(?,?,?,?, 'active', ?)",
                (user_id, plan_id, gateway, external_id, end))
    email = con.execute("SELECT email FROM users WHERE id=?", (user_id,)).fetchone()["email"]
    con.commit(); con.close()
    send_email(email, f"Recibo — Plan {plan['name']} en {APP_NAME}",
               f"¡Gracias por tu pago!\nPlan: {plan['name']}\nPrecio: S/ {plan['price_pen']} / US$ {plan['price_usd']} al mes\nRenueva: {end}\nDisfruta creando videos en {APP_NAME}.")

@app.post("/api/subscription/cancel")
@login_required
def cancel_sub():
    u = current_user(); con = get_db()
    s = con.execute("SELECT id FROM subscriptions WHERE user_id=? ORDER BY id DESC LIMIT 1", (u["id"],)).fetchone()
    if s: con.execute("UPDATE subscriptions SET status='canceled' WHERE id=?", (s["id"],)); con.commit()
    con.close()
    return jsonify({"ok": True, "message": "Suscripción cancelada. Mantienes el acceso hasta el fin del período."})

@app.post("/webhook/stripe")
def wh_stripe():
    r = payments.parse_stripe_event(request.json or {})
    if r: _activate(r[0], r[1], "stripe", "wh", renew=True)
    return "", 200

@app.post("/webhook/mercadopago")
def wh_mp():
    r = payments.parse_mp_event(request.json or {}, request.args)
    if r: _activate(r[0], r[1], "mercadopago", "wh", renew=True)
    return "", 200

# ---------------- CORREOS PROGRAMADOS ----------------
@app.post("/api/admin/run-expiry-warnings")
@admin_required
def run_expiry():
    """Avisa a quienes vencen en ~3 días. En producción, llámalo con un cron diario."""
    con = get_db()
    rows = con.execute("""SELECT u.email, s.current_period_end FROM subscriptions s JOIN users u ON u.id=s.user_id
        WHERE s.status='active' AND s.current_period_end BETWEEN datetime('now') AND datetime('now','+3 day')""").fetchall()
    con.close()
    for r in rows:
        send_email(r["email"], f"Tu plan en {APP_NAME} vence pronto",
                   f"Tu suscripción vence el {r['current_period_end']}. Renuévala para seguir creando videos sin interrupción.")
    return jsonify({"notified": len(rows)})

# ---------------- ADMIN / MÉTRICAS ----------------
@app.get("/api/admin/overview")
@admin_required
def admin_overview():
    con = get_db()
    users = con.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
    paid = con.execute("SELECT COUNT(*) c FROM users WHERE plan!='free'").fetchone()["c"]
    vids = con.execute("SELECT COUNT(*) c FROM videos").fetchone()["c"]
    refs = con.execute("SELECT COUNT(*) c FROM users WHERE referred_by IS NOT NULL").fetchone()["c"]
    canceled = con.execute("SELECT COUNT(*) c FROM subscriptions WHERE status='canceled'").fetchone()["c"]
    by_plan = con.execute("SELECT plan, COUNT(*) c FROM users GROUP BY plan").fetchall()
    mrr = sum(get_plan(r["plan"])["price_pen"] * r["c"] for r in by_plan)
    users_by_day = con.execute("SELECT date(created_at) d, COUNT(*) c FROM users GROUP BY d ORDER BY d").fetchall()
    videos_by_day = con.execute("SELECT date(created_at) d, COUNT(*) c FROM videos WHERE created_at>=date('now','-14 day') GROUP BY d ORDER BY d").fetchall()
    con.close()
    return jsonify({"users": users, "paid": paid, "videos": vids, "referrals": refs, "canceled": canceled,
                    "mrr_pen": mrr, "by_plan": {r["plan"]: r["c"] for r in by_plan},
                    "users_by_day": [dict(r) for r in users_by_day],
                    "videos_by_day": [dict(r) for r in videos_by_day]})

# ---------------- LEGAL ----------------
@app.get("/terminos")
def terminos(): return send_from_directory("static/legal", "terminos.html")
@app.get("/privacidad")
def privacidad(): return send_from_directory("static/legal", "privacidad.html")
@app.get("/reembolsos")
def reembolsos(): return send_from_directory("static/legal", "reembolsos.html")

@app.get("/")
def index():
    return send_from_directory("static", "index.html")

if __name__ == "__main__":
    migrate(); ensure_admin()
    port = int(os.getenv("PORT", 8000))
    print(f"{APP_NAME} SaaS en http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, threaded=True)
