"""SQLite-backed storage for one daily load. SQLite ships with Python, so
this project's SQL assertions run with no external database service to
stand up; every table is recreated fresh for each load."""

from __future__ import annotations

import sqlite3

SCHEMA_SQL = """
DROP TABLE IF EXISTS load_meta;
DROP TABLE IF EXISTS accounts;
DROP TABLE IF EXISTS trades;
DROP TABLE IF EXISTS cash_activity;
DROP TABLE IF EXISTS fee_assessments;

CREATE TABLE load_meta (as_of_date TEXT);

CREATE TABLE accounts (
    account_id TEXT,
    account_type TEXT,
    account_status TEXT,
    opened_date TEXT,
    state TEXT,
    kyc_status TEXT,
    advisory_fee_bps INTEGER,
    is_retirement_account INTEGER
);

CREATE TABLE trades (
    trade_id TEXT,
    account_id TEXT,
    trade_date TEXT,
    side TEXT,
    quantity REAL,
    price REAL,
    principal_amount REAL,
    commission REAL,
    settlement_date TEXT
);

CREATE TABLE cash_activity (
    activity_id TEXT,
    account_id TEXT,
    activity_date TEXT,
    activity_type TEXT,
    amount REAL,
    settled_flag INTEGER
);

CREATE TABLE fee_assessments (
    fee_id TEXT,
    account_id TEXT,
    assessment_date TEXT,
    fee_type TEXT,
    fee_amount REAL,
    waived_flag INTEGER,
    waiver_reason TEXT
);
"""


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA_SQL)
    return conn


def load(conn: sqlite3.Connection, data: dict) -> None:
    conn.executescript(SCHEMA_SQL)
    conn.execute("INSERT INTO load_meta VALUES (?)", (data["as_of_date"],))
    conn.executemany(
        "INSERT INTO accounts VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (r["account_id"], r["account_type"], r["account_status"], r["opened_date"],
             r["state"], r["kyc_status"], r["advisory_fee_bps"], r["is_retirement_account"])
            for r in data["accounts"]
        ],
    )
    conn.executemany(
        "INSERT INTO trades VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (r["trade_id"], r["account_id"], r["trade_date"], r["side"], r["quantity"],
             r["price"], r["principal_amount"], r["commission"], r["settlement_date"])
            for r in data["trades"]
        ],
    )
    conn.executemany(
        "INSERT INTO cash_activity VALUES (?, ?, ?, ?, ?, ?)",
        [
            (r["activity_id"], r["account_id"], r["activity_date"], r["activity_type"],
             r["amount"], r["settled_flag"])
            for r in data["cash_activity"]
        ],
    )
    conn.executemany(
        "INSERT INTO fee_assessments VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            (r["fee_id"], r["account_id"], r["assessment_date"], r["fee_type"],
             r["fee_amount"], r["waived_flag"], r["waiver_reason"])
            for r in data["fee_assessments"]
        ],
    )
    conn.commit()
