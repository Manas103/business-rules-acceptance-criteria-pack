from app import generator


def test_deterministic():
    a = generator.generate_clean_load(seed=9)
    b = generator.generate_clean_load(seed=9)
    assert a == b


def test_different_seeds_differ():
    a = generator.generate_clean_load(seed=1)
    b = generator.generate_clean_load(seed=2)
    assert a != b


def test_all_tables_present_and_nonempty():
    data = generator.generate_clean_load(seed=1)
    for table in ("accounts", "trades", "cash_activity", "fee_assessments"):
        assert len(data[table]) > 0


def test_foreign_keys_resolve():
    data = generator.generate_clean_load(seed=2)
    account_ids = {a["account_id"] for a in data["accounts"]}
    for table in ("trades", "cash_activity", "fee_assessments"):
        for row in data[table]:
            assert row["account_id"] in account_ids


def test_retirement_flag_matches_account_type():
    data = generator.generate_clean_load(seed=3)
    for a in data["accounts"]:
        if a["account_type"] == "Retail IRA":
            assert a["is_retirement_account"] == 1
        else:
            assert a["is_retirement_account"] == 0


def test_advisory_fee_matches_account_type():
    data = generator.generate_clean_load(seed=3)
    for a in data["accounts"]:
        if a["account_type"] == "Advisory Managed":
            assert a["advisory_fee_bps"] is not None
            assert 0 <= a["advisory_fee_bps"] <= 150
        else:
            assert a["advisory_fee_bps"] is None


def test_cash_activity_sign_matches_type():
    data = generator.generate_clean_load(seed=4)
    for row in data["cash_activity"]:
        if row["activity_type"] in ("DEPOSIT", "DIVIDEND", "INTEREST"):
            assert row["amount"] > 0
        elif row["activity_type"] in ("WITHDRAWAL", "FEE"):
            assert row["amount"] < 0
