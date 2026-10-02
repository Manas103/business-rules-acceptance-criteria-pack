from app import db, engine, generator, violations


def test_clean_load_passes_every_rule():
    data = generator.generate_clean_load(seed=1)
    conn = db.connect()
    db.load(conn, data)
    found = engine.run_all(conn)
    assert found == []


def test_catches_all_32_seeded_violations_attributed_by_rule_name():
    clean = generator.generate_clean_load(seed=1)
    mutated, expected = violations.inject_seeded_violations(clean, seed=777)
    conn = db.connect()
    db.load(conn, mutated)
    found = engine.run_all(conn)
    found_by_rule: dict[str, set[str]] = {}
    for v in found:
        found_by_rule.setdefault(v.rule_id, set()).add(v.record_id)

    for rule_id, record_id in expected:
        assert record_id in found_by_rule.get(rule_id, set()), f"{rule_id} did not catch {record_id}"


def test_no_unexpected_violations_on_the_seeded_load():
    clean = generator.generate_clean_load(seed=1)
    mutated, expected = violations.inject_seeded_violations(clean, seed=777)
    conn = db.connect()
    db.load(conn, mutated)
    found = engine.run_all(conn)
    expected_pairs = set(expected)
    unexpected = [v for v in found if (v.rule_id, v.record_id) not in expected_pairs]
    assert unexpected == []


def test_multiple_clean_loads_pass():
    for seed in range(3000, 3010):
        data = generator.generate_clean_load(seed=seed)
        conn = db.connect()
        db.load(conn, data)
        found = engine.run_all(conn)
        assert found == [], f"seed={seed} produced {len(found)} false failure(s)"
