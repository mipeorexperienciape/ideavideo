"""Base de datos SQLite del SaaS (Fase 2: verificación, referidos, ciclo de suscripción)."""
import sqlite3, os, secrets
from pathlib import Path

DB_PATH = os.getenv("DB_PATH", str(Path(__file__).parent / "ideavideo.db"))

def get_db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    return con

def _add_col(con, table, col, decl):
    cols = [r["name"] for r in con.execute(f"PRAGMA table_info({table})").fetchall()]
    if col not in cols:
        con.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")

def migrate():
    con = get_db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
        plan TEXT NOT NULL DEFAULT 'free', is_admin INTEGER NOT NULL DEFAULT 0,
        email_verified INTEGER NOT NULL DEFAULT 0, verify_token TEXT,
        referral_code TEXT, referred_by INTEGER, bonus_credits INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS videos (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, title TEXT, fmt TEXT,
        filename TEXT, watermark INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS ip_demos ( ip TEXT PRIMARY KEY, created_at TEXT NOT NULL DEFAULT (datetime('now')) );
    CREATE TABLE IF NOT EXISTS subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, plan TEXT NOT NULL,
        gateway TEXT, external_id TEXT, status TEXT DEFAULT 'active', current_period_end TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    """)
    # columnas nuevas para bases de datos de la Fase 1
    for c, d in [("email_verified","INTEGER NOT NULL DEFAULT 0"),("verify_token","TEXT"),
                 ("referral_code","TEXT"),("referred_by","INTEGER"),("bonus_credits","INTEGER NOT NULL DEFAULT 0")]:
        _add_col(con, "users", c, d)
    con.commit(); con.close()

def gen_code(n=8):
    return secrets.token_hex(4)[:n]

def videos_this_month(user_id):
    con = get_db()
    n = con.execute("SELECT COUNT(*) c FROM videos WHERE user_id=? AND strftime('%Y-%m',created_at)=strftime('%Y-%m','now')",(user_id,)).fetchone()["c"]
    con.close(); return n

def ip_used_demo(ip):
    con = get_db(); r = con.execute("SELECT 1 FROM ip_demos WHERE ip=?", (ip,)).fetchone(); con.close(); return bool(r)

def mark_ip_demo(ip):
    con = get_db(); con.execute("INSERT OR IGNORE INTO ip_demos(ip) VALUES(?)", (ip,)); con.commit(); con.close()

def active_subscription(user_id):
    con = get_db()
    s = con.execute("SELECT * FROM subscriptions WHERE user_id=? ORDER BY id DESC LIMIT 1", (user_id,)).fetchone()
    con.close(); return dict(s) if s else None

def expire_if_needed(user_id):
    """Si la suscripción venció, baja al plan gratis (verificación perezosa)."""
    con = get_db()
    u = con.execute("SELECT plan FROM users WHERE id=?", (user_id,)).fetchone()
    s = con.execute("SELECT * FROM subscriptions WHERE user_id=? ORDER BY id DESC LIMIT 1", (user_id,)).fetchone()
    if u and u["plan"] != "free" and s and s["current_period_end"]:
        end = con.execute("SELECT ? < datetime('now') AS ended", (s["current_period_end"],)).fetchone()["ended"]
        if end and s["status"] != "active_renew":
            con.execute("UPDATE users SET plan='free' WHERE id=?", (user_id,))
            con.execute("UPDATE subscriptions SET status='expired' WHERE id=?", (s["id"],))
            con.commit()
    con.close()
