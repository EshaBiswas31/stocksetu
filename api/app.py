"""
app.py
------
The entire backend. One Flask app, organized into six sections:

  1. Setup & helpers
  2. Auth routes            (signup, login, logout, who-am-i)
  3. Password reset          (forgot password, reset password)
  4. Analyze route            (THE main feature - runs all 3 pillars)
  5. Recent list + Watchlist   (star a company, see it again later)
  6. Admin routes              (cPanel-style: list users, add a customer
                                 directly with a password, enable/disable,
                                 promote/demote, reset a user's password)

Login uses Flask's built-in signed-cookie session -- no extra database
table needed for sessions.
"""

import os
import sys
import secrets
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from flask import Flask, request, jsonify, session, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash

from core.db import init_db, fetch_one, fetch_all, execute
from core.yahoo import fetch_all_data
from core.symbols import resolve_and_validate, search_suggestions as search_symbols
from core import fundamental, technical, quant, scoring
from core.mailer import send_reset_email

PUBLIC_DIR = os.path.join(os.path.dirname(__file__), "..", "public")

app = Flask(__name__, static_folder=PUBLIC_DIR, static_url_path="")
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me-in-production")

_db_ready = False


def ensure_db():
    global _db_ready
    if not _db_ready:
        init_db()
        _db_ready = True


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return fetch_one("SELECT id, name, email, role, is_active FROM users WHERE id = %s", (user_id,))


def require_login():
    user = current_user()
    if not user:
        return None, (jsonify({"error": "Please log in first."}), 401)
    if not user["is_active"]:
        return None, (jsonify({"error": "This account has been disabled. Contact an admin."}), 403)
    return user, None


def require_admin():
    user, err = require_login()
    if err:
        return None, err
    if user["role"] != "admin":
        return None, (jsonify({"error": "Admins only."}), 403)
    return user, None


# ======================================================================
# Static pages
# ======================================================================

@app.route("/")
def home():
    return send_from_directory(PUBLIC_DIR, "index.html")


# ======================================================================
# 2. Auth routes
# ======================================================================

@app.route("/api/signup", methods=["POST"])
def signup():
    ensure_db()
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not name or not email or not password:
        return jsonify({"error": "Please fill in your name, email and password."}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters."}), 400
    if "@" not in email or "." not in email:
        return jsonify({"error": "Please enter a valid email address."}), 400

    existing = fetch_one("SELECT id FROM users WHERE email = %s", (email,))
    if existing:
        return jsonify({"error": "An account with this email already exists."}), 400

    row = fetch_one(
        """INSERT INTO users (name, email, password_hash, role)
           VALUES (%s, %s, %s, 'user') RETURNING id""",
        (name, email, generate_password_hash(password)),
    )
    session["user_id"] = row["id"]
    return jsonify({"message": "Account created.", "user": {"name": name, "email": email, "role": "user"}})


@app.route("/api/login", methods=["POST"])
def login():
    ensure_db()
    data = request.get_json(force=True, silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    user = fetch_one(
        "SELECT id, name, email, password_hash, role, is_active FROM users WHERE email = %s",
        (email,),
    )
    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Incorrect email or password."}), 401
    if not user["is_active"]:
        return jsonify({"error": "This account has been disabled. Contact an admin."}), 403

    session["user_id"] = user["id"]
    return jsonify({"message": "Logged in.", "user": {
        "name": user["name"], "email": user["email"], "role": user["role"],
    }})


@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Logged out."})


@app.route("/api/me")
def me():
    ensure_db()
    user = current_user()
    if not user:
        return jsonify({"user": None})
    return jsonify({"user": {
        "name": user["name"], "email": user["email"], "role": user["role"],
    }})


# ======================================================================
# 3. Password reset
# ======================================================================

@app.route("/api/forgot", methods=["POST"])
def forgot_password():
    ensure_db()
    data = request.get_json(force=True, silent=True) or {}
    email = (data.get("email") or "").strip().lower()

    user = fetch_one("SELECT id FROM users WHERE email = %s", (email,))
    if user:
        token = secrets.token_urlsafe(32)
        expiry = datetime.now(timezone.utc) + timedelta(hours=1)
        execute(
            "UPDATE users SET reset_token = %s, reset_token_expiry = %s WHERE id = %s",
            (token, expiry, user["id"]),
        )
        reset_link = f"{request.url_root.rstrip('/')}/reset.html?token={token}"
        try:
            send_reset_email(email, reset_link)
        except Exception as e:
            print(f"[mailer error] could not send reset email: {e}")

    return jsonify({"message": "If that email is registered, a reset link has been sent."})


@app.route("/api/reset-password", methods=["POST"])
def reset_password():
    ensure_db()
    data = request.get_json(force=True, silent=True) or {}
    token = data.get("token") or ""
    new_password = data.get("new_password") or ""

    if len(new_password) < 6:
        return jsonify({"error": "Password must be at least 6 characters."}), 400

    user = fetch_one("SELECT id, reset_token_expiry FROM users WHERE reset_token = %s", (token,))
    if not user:
        return jsonify({"error": "This reset link is invalid. Please request a new one."}), 400

    expiry = user["reset_token_expiry"]
    if expiry is None or expiry < datetime.now(timezone.utc):
        return jsonify({"error": "This reset link has expired. Please request a new one."}), 400

    execute(
        "UPDATE users SET password_hash = %s, reset_token = NULL, reset_token_expiry = NULL WHERE id = %s",
        (generate_password_hash(new_password), user["id"]),
    )
    return jsonify({"message": "Password updated. You can now log in."})


# ======================================================================
# 4. Analyze - the main feature. Runs all three pillars and combines them.
# ======================================================================

@app.route("/api/analyze")
def analyze():
    ensure_db()
    user, err = require_login()
    if err:
        return err

    raw_input = request.args.get("symbol") or ""
    exchange = (request.args.get("exchange") or "NSE").strip().upper()
    profile = request.args.get("profile") or scoring.DEFAULT_PROFILE
    if profile not in scoring.PROFILES:
        profile = scoring.DEFAULT_PROFILE

    symbol, validation_error = resolve_and_validate(raw_input, exchange)
    if validation_error:
        return jsonify({"error": validation_error}), 400

    try:
        data = fetch_all_data(symbol, exchange)
    except Exception:
        return jsonify({"error": f"Couldn't find '{raw_input}' on {exchange}. Check the symbol and try again."}), 400

    fundamental_result = fundamental.analyze(data["info"], data["financials"])
    technical_result = technical.analyze(data["intraday"], data["daily"], data["weekly"])
    quant_result = quant.analyze(data["intraday"], data["daily"], data["weekly"])
    combined = scoring.combine(fundamental_result, technical_result, quant_result, profile)

    daily = data["daily"]
    chart = {
        "dates": [d.strftime("%Y-%m-%d") for d in daily.index],
        "close": [round(float(v), 2) for v in daily["Close"]],
        "sma20": _rolling_list(daily["Close"], 20),
        "sma50": _rolling_list(daily["Close"], 50),
    }

    in_watchlist = fetch_one(
        "SELECT 1 FROM watchlist WHERE user_id = %s AND symbol = %s AND exchange = %s",
        (user["id"], symbol, exchange),
    ) is not None

    report = {
        "symbol": symbol,
        "exchange": exchange,
        "company_name": data["company_name"],
        "overall": combined,
        "fundamental": fundamental_result,
        "technical": _strip_raw_events_for_json(technical_result),
        "quant": quant_result,
        "chart": chart,
        "in_watchlist": in_watchlist,
    }

    pillar = combined["pillar_scores"]
    execute(
        """INSERT INTO score_cache
               (symbol, exchange, company_name, overall_score, label,
                fundamental_score, technical_score, quant_score, report)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (symbol, exchange) DO UPDATE SET
               company_name = EXCLUDED.company_name,
               overall_score = EXCLUDED.overall_score,
               label = EXCLUDED.label,
               fundamental_score = EXCLUDED.fundamental_score,
               technical_score = EXCLUDED.technical_score,
               quant_score = EXCLUDED.quant_score,
               report = EXCLUDED.report,
               fetched_at = NOW()""",
        (symbol, exchange, data["company_name"], combined["overall_score"], combined["label"],
         pillar["fundamental"], pillar["technical"], pillar["quant"], _to_json(report)),
    )

    return jsonify(report)


def _rolling_list(series, window):
    rolled = series.rolling(window).mean()
    return [None if (v != v) else round(float(v), 2) for v in rolled]


def _strip_raw_events_for_json(technical_result):
    """The crossover event dicts are already plain dicts (x, y, direction)
    -- nothing to strip, this just documents that technical_result is
    JSON-safe as-is. Kept as a named step in case fields are added later
    that aren't directly serializable."""
    return technical_result


def _to_json(obj):
    import json
    return json.dumps(obj, default=str)


@app.route("/api/recent")
def recent():
    ensure_db()
    user, err = require_login()
    if err:
        return err
    rows = fetch_all(
        """SELECT symbol, exchange, company_name, overall_score, label, fetched_at
           FROM score_cache ORDER BY fetched_at DESC LIMIT 10"""
    )
    for r in rows:
        r["fetched_at"] = r["fetched_at"].strftime("%Y-%m-%d %H:%M")
    return jsonify({"recent": rows})


@app.route("/api/watchlist")
def get_watchlist():
    """Companies this logged-in user has starred, newest first. Joined
    against score_cache so we can show their last known overall score
    AND the three pillar scores, side by side, without hitting Yahoo
    Finance again -- that only happens when the user clicks Refresh."""
    ensure_db()
    user, err = require_login()
    if err:
        return err
    rows = fetch_all(
        """SELECT w.symbol, w.exchange, w.company_name, w.added_at,
                  sc.overall_score, sc.label,
                  sc.fundamental_score, sc.technical_score, sc.quant_score,
                  sc.fetched_at
           FROM watchlist w
           LEFT JOIN score_cache sc ON sc.symbol = w.symbol AND sc.exchange = w.exchange
           WHERE w.user_id = %s
           ORDER BY w.added_at DESC""",
        (user["id"],),
    )
    for r in rows:
        r["added_at"] = r["added_at"].strftime("%Y-%m-%d")
        r["fetched_at"] = r["fetched_at"].isoformat() if r["fetched_at"] else None
    return jsonify({"watchlist": rows})


@app.route("/api/symbols/search")
def symbols_search():
    """Powers the autocomplete dropdown under the search box: as the user
    types, suggest matching company names from the friendly-name list in
    core/symbols.py."""
    ensure_db()
    user, err = require_login()
    if err:
        return err
    query = request.args.get("q") or ""
    return jsonify({"results": search_symbols(query)})


@app.route("/api/watchlist/toggle", methods=["POST"])
def toggle_watchlist():
    """One button, two behaviours: star a company that isn't on the list
    yet, or un-star one that already is. The frontend just calls this
    and reads back whether it ended up added or removed."""
    ensure_db()
    user, err = require_login()
    if err:
        return err

    data = request.get_json(force=True, silent=True) or {}
    symbol = (data.get("symbol") or "").strip().upper()
    exchange = (data.get("exchange") or "NSE").strip().upper()
    company_name = data.get("company_name") or symbol

    if not symbol:
        return jsonify({"error": "Missing symbol."}), 400

    existing = fetch_one(
        "SELECT id FROM watchlist WHERE user_id = %s AND symbol = %s AND exchange = %s",
        (user["id"], symbol, exchange),
    )
    if existing:
        execute("DELETE FROM watchlist WHERE id = %s", (existing["id"],))
        return jsonify({"message": "Removed from watchlist.", "added": False})

    execute(
        """INSERT INTO watchlist (user_id, symbol, exchange, company_name)
           VALUES (%s, %s, %s, %s)
           ON CONFLICT (user_id, symbol, exchange) DO NOTHING""",
        (user["id"], symbol, exchange, company_name),
    )
    return jsonify({"message": "Added to watchlist.", "added": True})


# ======================================================================
# 6. Admin routes (cPanel-style user management)
# ======================================================================

@app.route("/api/admin/users")
def admin_list_users():
    ensure_db()
    admin, err = require_admin()
    if err:
        return err
    rows = fetch_all(
        """SELECT id, name, email, role, is_active, added_by_admin, created_at
           FROM users ORDER BY role DESC, created_at DESC"""
    )
    for r in rows:
        r["created_at"] = r["created_at"].strftime("%Y-%m-%d")
    return jsonify({"users": rows})


@app.route("/api/admin/add-customer", methods=["POST"])
def admin_add_customer():
    """The 'cPanel' feature: an admin directly creates a customer account
    with a name, email and password (no self-signup needed for this
    account), optionally as another admin."""
    ensure_db()
    admin, err = require_admin()
    if err:
        return err

    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    role = "admin" if data.get("role") == "admin" else "user"

    if not name or not email or not password:
        return jsonify({"error": "Please fill in name, email and password."}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters."}), 400

    existing = fetch_one("SELECT id FROM users WHERE email = %s", (email,))
    if existing:
        return jsonify({"error": "An account with this email already exists."}), 400

    execute(
        """INSERT INTO users (name, email, password_hash, role, added_by_admin)
           VALUES (%s, %s, %s, %s, TRUE)""",
        (name, email, generate_password_hash(password), role),
    )
    return jsonify({"message": f"Account created for {name}."})


@app.route("/api/admin/users/<int:user_id>/toggle-active", methods=["POST"])
def admin_toggle_active(user_id):
    ensure_db()
    admin, err = require_admin()
    if err:
        return err
    if user_id == admin["id"]:
        return jsonify({"error": "You can't disable your own account."}), 400
    execute("UPDATE users SET is_active = NOT is_active WHERE id = %s", (user_id,))
    return jsonify({"message": "Updated."})


@app.route("/api/admin/users/<int:user_id>/toggle-role", methods=["POST"])
def admin_toggle_role(user_id):
    ensure_db()
    admin, err = require_admin()
    if err:
        return err
    if user_id == admin["id"]:
        return jsonify({"error": "You can't change your own role."}), 400
    execute(
        "UPDATE users SET role = CASE WHEN role = 'admin' THEN 'user' ELSE 'admin' END WHERE id = %s",
        (user_id,),
    )
    return jsonify({"message": "Updated."})


@app.route("/api/admin/users/<int:user_id>/set-password", methods=["POST"])
def admin_set_password(user_id):
    """Lets an admin directly set a new password for any customer
    (part of the cPanel-style control the admin asked for)."""
    ensure_db()
    admin, err = require_admin()
    if err:
        return err
    data = request.get_json(force=True, silent=True) or {}
    new_password = data.get("new_password") or ""
    if len(new_password) < 6:
        return jsonify({"error": "Password must be at least 6 characters."}), 400
    execute("UPDATE users SET password_hash = %s WHERE id = %s",
            (generate_password_hash(new_password), user_id))
    return jsonify({"message": "Password updated."})


# Local testing: `python api/app.py` runs this on http://localhost:5000
if __name__ == "__main__":
    app.run(debug=True, port=5000)
