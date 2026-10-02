from app import generator, violations


def test_exactly_32_seeded_violations():
    clean = generator.generate_clean_load(seed=1)
    _, expected = violations.inject_seeded_violations(clean, seed=777)
    assert len(expected) == 32


def test_one_violation_per_rule():
    clean = generator.generate_clean_load(seed=1)
    _, expected = violations.inject_seeded_violations(clean, seed=777)
    rule_ids = [r for r, _ in expected]
    assert len(rule_ids) == len(set(rule_ids)) == 32


def test_deterministic():
    clean = generator.generate_clean_load(seed=1)
    m1, e1 = violations.inject_seeded_violations(clean, seed=42)
    m2, e2 = violations.inject_seeded_violations(clean, seed=42)
    assert e1 == e2
    assert m1 == m2


def test_does_not_mutate_the_original():
    clean = generator.generate_clean_load(seed=1)
    original_len = len(clean["accounts"])
    violations.inject_seeded_violations(clean, seed=777)
    assert len(clean["accounts"]) == original_len
