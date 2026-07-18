"""The Postgres-backed spend ledger.

This is the hard backstop on what a day of public traffic can cost. Only
consulted in real mode; mock answers are free. Both caps cover a rolling
24 hours, which sidesteps timezone questions entirely.
"""

import psycopg

from . import config

_SCHEMA = """
    CREATE TABLE IF NOT EXISTS gateway_spend (
        id bigserial PRIMARY KEY,
        ts timestamptz NOT NULL DEFAULT now(),
        ip text NOT NULL,
        question_chars integer NOT NULL,
        input_tokens_est integer NOT NULL,
        output_tokens_est integer NOT NULL,
        cost_usd_est numeric(10, 6) NOT NULL
    )
"""


def _connect() -> psycopg.Connection:
    conn = psycopg.connect(config.DATABASE_URL)
    conn.execute(_SCHEMA)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_gateway_spend_ts ON gateway_spend(ts)")
    conn.commit()
    return conn


def spent_today() -> float:
    """Total estimated dollars spent in the last 24 hours."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(cost_usd_est), 0) FROM gateway_spend "
            "WHERE ts >= now() - interval '24 hours'"
        ).fetchone()
        return float(row[0])


def questions_today(ip: str) -> int:
    """Questions this IP has asked in the last 24 hours."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM gateway_spend "
            "WHERE ip = %s AND ts >= now() - interval '24 hours'",
            (ip,),
        ).fetchone()
        return int(row[0])


def record(
    ip: str,
    question_chars: int,
    input_tokens_est: int,
    output_tokens_est: int,
    cost_usd_est: float,
) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO gateway_spend "
            "(ip, question_chars, input_tokens_est, output_tokens_est, cost_usd_est) "
            "VALUES (%s, %s, %s, %s, %s)",
            (ip, question_chars, input_tokens_est, output_tokens_est, cost_usd_est),
        )
        conn.commit()
