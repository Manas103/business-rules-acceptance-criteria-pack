"""Deterministic synthetic daily loads: 200 accounts plus their trades,
cash activity, and fee assessments, generated to satisfy every rule in
``app/rules.py`` exactly (this is the clean baseline the gate benchmark
in ``scripts/run_gate_benchmark.py`` injects 32 seeded violations into,
and the same generator independently seeded 20 more times to measure
false failures)."""

from __future__ import annotations

import random
from datetime import date, timedelta

from app.rules import US_STATES

TODAY = date(2026, 10, 1)
EARLIEST = date(2015, 1, 1)

N_ACCOUNTS = 200
ACCOUNT_TYPES = ("Retail Brokerage", "Retail IRA", "Advisory Managed", "Education Savings")


def _rand_date(rng: random.Random, start: date, end: date) -> date:
    span = (end - start).days
    return (start + timedelta(days=rng.randint(0, max(span, 0)))).isoformat()


def _gen_accounts(rng: random.Random) -> list[dict]:
    rows = []
    for i in range(N_ACCOUNTS):
        account_type = rng.choice(ACCOUNT_TYPES)
        is_ira = account_type == "Retail IRA"
        is_advisory = account_type == "Advisory Managed"
        rows.append({
            "account_id": f"ACCT-{i:05d}",
            "account_type": account_type,
            "account_status": rng.choice(["Open", "Open", "Open", "Closed", "Restricted", "Pending"]),
            "opened_date": _rand_date(rng, EARLIEST, TODAY - timedelta(days=30)),
            "state": rng.choice(US_STATES),
            "kyc_status": rng.choice(["VERIFIED", "VERIFIED", "VERIFIED", "PENDING", "EXPIRED"]),
            "advisory_fee_bps": rng.randint(25, 120) if is_advisory else None,
            "is_retirement_account": 1 if is_ira else 0,
        })
    return rows


def _gen_trades(rng: random.Random, accounts: list[dict]) -> list[dict]:
    rows = []
    idx = 0
    for acc in accounts:
        for _ in range(rng.randint(2, 8)):
            trade_date = _rand_date(rng, TODAY - timedelta(days=90), TODAY)
            settlement_date = (date.fromisoformat(trade_date) + timedelta(days=rng.choice([1, 1, 2]))).isoformat()
            quantity = round(rng.uniform(1, 500), 2)
            price = round(rng.uniform(5, 400), 2)
            principal = round(quantity * price, 2)
            rows.append({
                "trade_id": f"TRD-{idx:07d}",
                "account_id": acc["account_id"],
                "trade_date": trade_date,
                "side": rng.choice(["BUY", "SELL"]),
                "quantity": quantity,
                "price": price,
                "principal_amount": principal,
                "commission": round(rng.uniform(0, 0.01 * principal), 2),
                "settlement_date": settlement_date,
            })
            idx += 1
    return rows


def _gen_cash_activity(rng: random.Random, accounts: list[dict]) -> list[dict]:
    rows = []
    idx = 0
    positive_types = ("DEPOSIT", "DIVIDEND", "INTEREST")
    negative_types = ("WITHDRAWAL", "FEE")
    for acc in accounts:
        for _ in range(rng.randint(2, 6)):
            activity_type = rng.choice(positive_types + negative_types + ("TRANSFER",))
            if activity_type in positive_types:
                amount = round(rng.uniform(10, 9000), 2)
            elif activity_type in negative_types:
                amount = -round(rng.uniform(10, 9000), 2)
            else:
                amount = round(rng.uniform(-9000, 9000), 2)
                if amount == 0:
                    amount = 10.0
            rows.append({
                "activity_id": f"CASH-{idx:07d}",
                "account_id": acc["account_id"],
                "activity_date": _rand_date(rng, TODAY - timedelta(days=90), TODAY),
                "activity_type": activity_type,
                "amount": amount,
                "settled_flag": rng.choice([0, 1, 1, 1]),
            })
            idx += 1
    return rows


def _gen_fee_assessments(rng: random.Random, accounts: list[dict]) -> list[dict]:
    rows = []
    idx = 0
    for acc in accounts:
        waived = rng.random() < 0.1
        rows.append({
            "fee_id": f"FEE-{idx:06d}",
            "account_id": acc["account_id"],
            "assessment_date": _rand_date(rng, TODAY - timedelta(days=90), TODAY),
            "fee_type": rng.choice(["ADVISORY", "CUSTODY", "TRANSACTION", "FUND_EXPENSE"]),
            "fee_amount": round(rng.uniform(5, 4500), 2),
            "waived_flag": 1 if waived else 0,
            "waiver_reason": "Household relationship pricing" if waived else None,
        })
        idx += 1
    return rows


def generate_clean_load(seed: int = 1) -> dict:
    rng = random.Random(seed)
    accounts = _gen_accounts(rng)
    trades = _gen_trades(rng, accounts)
    cash_activity = _gen_cash_activity(rng, accounts)
    fee_assessments = _gen_fee_assessments(rng, accounts)
    return {
        "as_of_date": TODAY.isoformat(),
        "accounts": accounts,
        "trades": trades,
        "cash_activity": cash_activity,
        "fee_assessments": fee_assessments,
    }
