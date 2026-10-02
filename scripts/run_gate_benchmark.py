"""Runs all 32 rules against 32 seeded violations and 20 clean loads.

    python scripts/run_gate_benchmark.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import db, engine, generator, violations


def main() -> int:
    print("=== Business Rules as Executable Acceptance Criteria -- gate benchmark ===")

    clean = generator.generate_clean_load(seed=1)
    mutated, expected = violations.inject_seeded_violations(clean, seed=777)
    conn = db.connect()
    db.load(conn, mutated)
    found = engine.run_all(conn)
    found_by_rule: dict[str, set[str]] = {}
    for v in found:
        found_by_rule.setdefault(v.rule_id, set()).add(v.record_id)

    caught = 0
    for rule_id, record_id in expected:
        if record_id in found_by_rule.get(rule_id, set()):
            caught += 1
        else:
            print(f"  MISSED: {rule_id} record={record_id}")

    expected_pairs = set(expected)
    unexpected = [v for v in found if (v.rule_id, v.record_id) not in expected_pairs]

    print()
    print("-- claim: 32 of 32 seeded violations caught and attributed to the rule by name --")
    print(f"seeded violations caught: {caught} / {len(expected)}")
    print(f"unexpected violations on the seeded-violation load: {len(unexpected)}")
    for v in unexpected:
        print(f"  UNEXPECTED: {v.rule_id} ({v.rule_name}) record={v.record_id}")

    false_failures_total = 0
    for i in range(20):
        clean_i = generator.generate_clean_load(seed=2000 + i)
        conn_i = db.connect()
        db.load(conn_i, clean_i)
        found_i = engine.run_all(conn_i)
        false_failures_total += len(found_i)
        if found_i:
            print(f"  clean load seed={2000 + i} produced {len(found_i)} false failure(s):")
            for v in found_i:
                print(f"    {v.rule_id} ({v.rule_name}) record={v.record_id}")

    print()
    print("-- claim: 0 of 20 clean loads falsely failed --")
    print(f"false failures across 20 independent clean loads: {false_failures_total}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
