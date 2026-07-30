"""Autenticación por sesión (cookie firmada de Flask)."""
import functools
import bcrypt
from flask import session, jsonify
from db import get_db

def hash_pw(pw): return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
def check_pw(pw, h):
    try: return bcrypt.checkpw(pw.encode(), h.encode())
    except Exception: return False

def current_user():
    uid = session.get("uid")
    if not uid: return None
    con = get_db()
    u = con.execute("SELECT id,name,email,plan,is_admin FROM users WHERE id=?", (uid,)).fetchone()
    con.close()
    return dict(u) if u else None

def login_required(f):
    @functools.wraps(f)
    def w(*a, **k):
        if not session.get("uid"):
            return jsonify({"error": "Debes iniciar sesión."}), 401
        return f(*a, **k)
    return w

def admin_required(f):
    @functools.wraps(f)
    def w(*a, **k):
        u = current_user()
        if not u or not u["is_admin"]:
            return jsonify({"error": "Solo administradores."}), 403
        return f(*a, **k)
    return w
