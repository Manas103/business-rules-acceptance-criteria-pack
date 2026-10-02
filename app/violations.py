"""Injects exactly 32 seeded violations into a copy of a clean load, one
per rule in ``app/rules.py``, each chosen (and, for cross-field rules,
each candidate record filtered) so that it trips its own rule and only
its own rule."""

from __future__ import annotations

import copy
import random
from datetime import date, timedelta

NONEXISTENT_ACCOUNT_ID = "ACCT-99999"
TODAY = date(2026, 10, 1)


def _clone(data: dict) -> dict:
    out = {"as_of_date": data["as_of_date"]}
    for table in ("accounts", "trades", "cash_activity", "fee_assessments"):
        out[table] = [dict(row) for row in data[table]]
    return out


def inject_seeded_violations(data: dict, seed: int = 777):
    """Returns (mutated_data, expected) where expected is a list of
    (rule_id, record_id) tuples, one per seeded violation."""
    rng = random.Random(seed)
    mutated = _clone(data)
    expected: list[tuple[str, str]] = []

    # --- accounts ------------------------------------------------------
    # account_type, advisory_fee_bps, and is_retirement_account are cross
    # checked against each other (R06, R07), so the mutations below that
    # touch account_type-adjacent fields are drawn only from accounts
    # that are neither Advisory Managed nor Retail IRA to begin with,
    # so flipping one field never incidentally trips the other rule.
    accounts = mutated["accounts"]
    plain_idx = [i for i, r in enumerate(accounts)
                 if r["account_type"] not in ("Advisory Managed", "Retail IRA")]
    i_type, i_fee, i_retire, i_state = rng.sample(plain_idx, 4)
    remaining = [i for i in range(len(accounts)) if i not in (i_type, i_fee, i_retire, i_state)]
    i_dup, i_status, i_date, i_kyc = rng.sample(remaining, 4)

    dup_clone = dict(accounts[i_dup])
    accounts.append(dup_clone)
    expected.append(("R01", dup_clone["account_id"]))

    accounts[i_type]["account_type"] = "Joint Brokerage"
    expected.append(("R02", accounts[i_type]["account_id"]))

    accounts[i_fee]["advisory_fee_bps"] = 75
    expected.append(("R06", accounts[i_fee]["account_id"]))

    accounts[i_retire]["is_retirement_account"] = 1
    expected.append(("R07", accounts[i_retire]["account_id"]))

    accounts[i_state]["state"] = "ZZ"
    expected.append(("R08", accounts[i_state]["account_id"]))

    accounts[i_status]["account_status"] = "Suspended"
    expected.append(("R03", accounts[i_status]["account_id"]))

    accounts[i_date]["opened_date"] = (TODAY + timedelta(days=10)).isoformat()
    expected.append(("R04", accounts[i_date]["account_id"]))

    accounts[i_kyc]["kyc_status"] = "UNKNOWN"
    expected.append(("R05", accounts[i_kyc]["account_id"]))

    # --- trades ----------------------------------------------------------
    trades = mutated["trades"]
    t_idx = rng.sample(range(len(trades)), 8)
    i_dup, i_orphan, i_side, i_qty, i_price, i_principal, i_settle, i_comm = t_idx

    dup_clone = dict(trades[i_dup])
    trades.append(dup_clone)
    expected.append(("R09", dup_clone["trade_id"]))

    trades[i_orphan]["account_id"] = NONEXISTENT_ACCOUNT_ID
    expected.append(("R10", trades[i_orphan]["trade_id"]))

    trades[i_side]["side"] = "SHORT"
    expected.append(("R11", trades[i_side]["trade_id"]))

    # quantity and price feed into both R14 (principal consistency) and
    # R16 (commission bound, which breaks down arithmetically if
    # principal_amount goes negative); zero rather than negative keeps
    # principal_amount at exactly 0 so both downstream rules still pass
    # cleanly, leaving this an isolated R12/R13 violation.
    trades[i_qty]["quantity"] = 0.0
    trades[i_qty]["principal_amount"] = 0.0
    trades[i_qty]["commission"] = 0.0
    expected.append(("R12", trades[i_qty]["trade_id"]))

    trades[i_price]["price"] = 0.0
    trades[i_price]["principal_amount"] = 0.0
    trades[i_price]["commission"] = 0.0
    expected.append(("R13", trades[i_price]["trade_id"]))

    trades[i_principal]["principal_amount"] = round(
        trades[i_principal]["quantity"] * trades[i_principal]["price"], 2
    ) + 50.0
    expected.append(("R14", trades[i_principal]["trade_id"]))

    t_date = date.fromisoformat(trades[i_settle]["trade_date"])
    trades[i_settle]["settlement_date"] = (t_date - timedelta(days=1)).isoformat()
    expected.append(("R15", trades[i_settle]["trade_id"]))

    trades[i_comm]["commission"] = round(0.02 * trades[i_comm]["principal_amount"] + 10, 2)
    expected.append(("R16", trades[i_comm]["trade_id"]))

    # --- cash_activity -----------------------------------------------------
    cash = mutated["cash_activity"]
    c_idx = rng.sample(range(len(cash)), 8)
    i_dup, i_orphan, i_type, i_zero, i_sign, i_flag, i_future, i_magnitude = c_idx

    dup_clone = dict(cash[i_dup])
    cash.append(dup_clone)
    expected.append(("R17", dup_clone["activity_id"]))

    cash[i_orphan]["account_id"] = NONEXISTENT_ACCOUNT_ID
    expected.append(("R18", cash[i_orphan]["activity_id"]))

    cash[i_type]["activity_type"] = "CRYPTO_BUY"
    expected.append(("R19", cash[i_type]["activity_id"]))

    # R20 and R24 only touch amount; activity_type is pinned to TRANSFER
    # first (the one type R21 never checks), so a zero or oversized
    # amount here can never also trip the sign-consistency rule.
    cash[i_zero]["activity_type"] = "TRANSFER"
    cash[i_zero]["amount"] = 0.0
    expected.append(("R20", cash[i_zero]["activity_id"]))

    cash[i_sign]["activity_type"] = "DEPOSIT"
    cash[i_sign]["amount"] = -500.0
    expected.append(("R21", cash[i_sign]["activity_id"]))

    cash[i_flag]["settled_flag"] = 2
    expected.append(("R22", cash[i_flag]["activity_id"]))

    cash[i_future]["activity_date"] = (TODAY + timedelta(days=5)).isoformat()
    expected.append(("R23", cash[i_future]["activity_id"]))

    cash[i_magnitude]["activity_type"] = "TRANSFER"
    cash[i_magnitude]["amount"] = 250000.0
    expected.append(("R24", cash[i_magnitude]["activity_id"]))

    # --- fee_assessments -----------------------------------------------------
    fees = mutated["fee_assessments"]
    f_idx = rng.sample(range(len(fees)), 8)
    i_dup, i_orphan, i_type, i_neg, i_flag, i_waiver, i_future, i_toobig = f_idx

    dup_clone = dict(fees[i_dup])
    fees.append(dup_clone)
    expected.append(("R25", dup_clone["fee_id"]))

    fees[i_orphan]["account_id"] = NONEXISTENT_ACCOUNT_ID
    expected.append(("R26", fees[i_orphan]["fee_id"]))

    fees[i_type]["fee_type"] = "PENALTY"
    expected.append(("R27", fees[i_type]["fee_id"]))

    fees[i_neg]["fee_amount"] = -100.0
    expected.append(("R28", fees[i_neg]["fee_id"]))

    fees[i_flag]["waived_flag"] = 5
    expected.append(("R29", fees[i_flag]["fee_id"]))

    fees[i_waiver]["waived_flag"] = 0
    fees[i_waiver]["waiver_reason"] = "Erroneously retained reason"
    expected.append(("R30", fees[i_waiver]["fee_id"]))

    fees[i_future]["assessment_date"] = (TODAY + timedelta(days=5)).isoformat()
    expected.append(("R31", fees[i_future]["fee_id"]))

    fees[i_toobig]["fee_amount"] = 6000.0
    expected.append(("R32", fees[i_toobig]["fee_id"]))

    assert len(expected) == 32, f"expected exactly 32 seeded violations, built {len(expected)}"
    assert len({r for r, _ in expected}) == 32, "each rule must be seeded exactly once"
    return mutated, expected
