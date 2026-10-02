from app.rules import RULES


def test_exactly_32_rules():
    assert len(RULES) == 32


def test_rule_ids_unique():
    assert len({r.rule_id for r in RULES}) == 32


def test_every_rule_has_owner_and_criterion():
    for r in RULES:
        assert r.owner
        assert r.success_criterion
        assert r.plain_language
        assert r.sql.strip()


def test_eight_rules_per_table():
    counts: dict[str, int] = {}
    for r in RULES:
        counts[r.table] = counts.get(r.table, 0) + 1
    assert counts == {
        "accounts": 8, "trades": 8, "cash_activity": 8, "fee_assessments": 8,
    }
