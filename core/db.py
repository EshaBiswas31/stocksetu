"""
db.py
-----
All database access lives here, as plain SQL (no ORM) so it's easy to
read and explain. PostgreSQL, hosted for free via Vercel Postgres (Neon).

Three tables:
  users        - one row per person who can log in: name, email, hashed
                 password, role (admin/user), active flag, password-reset
                 token. Rows get created two ways: a person signs
                 themselves up, OR an admin adds them directly from the
                 Admin Panel (the "cPanel-style" add-customer feature).
  score_cache  - the last full report computed for each company, so
                 repeat searches are instant and "Recently Analyzed"
                 has something to show.
  watchlist    - which companies each logged-in user has starred, so
                 they can jump straight back to the ones they track.
"""

import os
import psycopg2
import psycopg2.extras
from werkzeug.security import generate_password_hash


def get_conn():
    db_url = os.environ["DATABASE_URL"]
    return psycopg2.connect(db_url)


def init_db():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user',
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    added_by_admin BOOLEAN NOT NULL DEFAULT FALSE,
                    reset_token TEXT,
                    reset_token_expiry TIMESTAMPTZ,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS score_cache (
                    id SERIAL PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    exchange TEXT NOT NULL,
                    company_name TEXT,
                    overall_score NUMERIC,
                    label TEXT,
                    report JSONB,
                    fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE (symbol, exchange)
                );
            """)
            # The watchlist table wants the three pillar scores as their
            # own plain columns, not buried inside the `report` JSON, so
            # the SQL that reads them stays simple. ADD COLUMN IF NOT
            # EXISTS makes this safe to run again even on a database that
            # already has score_cache from before these columns existed.
            cur.execute("ALTER TABLE score_cache ADD COLUMN IF NOT EXISTS fundamental_score NUMERIC;")
            cur.execute("ALTER TABLE score_cache ADD COLUMN IF NOT EXISTS technical_score NUMERIC;")
            cur.execute("ALTER TABLE score_cache ADD COLUMN IF NOT EXISTS quant_score NUMERIC;")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS watchlist (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    symbol TEXT NOT NULL,
                    exchange TEXT NOT NULL,
                    company_name TEXT,
                    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE (user_id, symbol, exchange)
                );
            """)
            conn.commit()

            cur.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
            (admin_count,) = cur.fetchone()
            if admin_count == 0:
                admin_email = os.environ.get("ADMIN_EMAIL")
                admin_password = os.environ.get("ADMIN_PASSWORD")
                admin_name = os.environ.get("ADMIN_NAME", "Admin")
                if admin_email and admin_password:
                    cur.execute(
                        """INSERT INTO users (name, email, password_hash, role, added_by_admin)
                           VALUES (%s, %s, %s, 'admin', TRUE)
                           ON CONFLICT (email) DO NOTHING""",
                        (admin_name, admin_email.lower(), generate_password_hash(admin_password)),
                    )
                    conn.commit()
    finally:
        conn.close()


def fetch_one(sql, params=()):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return cur.fetchone()
    finally:
        conn.close()


def fetch_all(sql, params=()):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return cur.fetchall()
    finally:
        conn.close()


def execute(sql, params=()):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            conn.commit()
    finally:
        conn.close()
