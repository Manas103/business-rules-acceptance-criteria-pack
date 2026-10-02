"""32 plain-language business rules, each with a named owner and a written
success criterion, each compiled into one SQL assertion that names the
record it fails on.

Every rule's ``sql`` returns the natural key of every record that breaks
it; a rule that returns no rows has passed. The plain-language text and
the success criterion are what a business partner reads; the SQL is
what actually runs on every load. ``app/engine.py`` is the only thing
that runs this SQL, so a rule's text and its enforcement can never
drift apart silently, the way a rule described in a wiki and a rule
implemented in code can.
"""

from __future__ import annotations

from dataclasses import dataclass

ACCOUNTS_OWNER = "Accounts Domain Steward (R. Alvarez)"
TRADES_OWNER = "Trading Operations Steward (M. Chen)"
CASH_OWNER = "Cash Operations Steward (D. Okafor)"
FEES_OWNER = "Pricing & Fees Steward (J. Kowalski)"

US_STATES = (
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
)


@dataclass(frozen=True)
class Rule:
    rule_id: str
    name: str
    table: str
    owner: str
    plain_language: str
    success_criterion: str
    sql: str


RULES: tuple[Rule, ...] = (
    # --- accounts (8) -----------------------------------------------
    Rule("R01", "Account id present and unique", "accounts", ACCOUNTS_OWNER,
         "Every account record must carry an account_id, and no account_id "
         "may appear on more than one record.",
         "0 missing or duplicated account_id values.",
         "SELECT account_id FROM accounts WHERE account_id IS NULL "
         "UNION "
         "SELECT account_id FROM accounts GROUP BY account_id HAVING COUNT(*) > 1"),
    Rule("R02", "Account type is a recognized product", "accounts", ACCOUNTS_OWNER,
         "account_type must be one of the firm's four retail product lines.",
         "0 accounts with an account_type outside the declared set.",
         "SELECT account_id FROM accounts WHERE account_type NOT IN "
         "('Retail Brokerage', 'Retail IRA', 'Advisory Managed', 'Education Savings')"),
    Rule("R03", "Account status is a recognized lifecycle state", "accounts", ACCOUNTS_OWNER,
         "account_status must be one of Open, Closed, Restricted, Pending.",
         "0 accounts with an account_status outside the declared set.",
         "SELECT account_id FROM accounts WHERE account_status NOT IN "
         "('Open', 'Closed', 'Restricted', 'Pending')"),
    Rule("R04", "Account was not opened in the future", "accounts", ACCOUNTS_OWNER,
         "opened_date must not be later than today.",
         "0 accounts with opened_date after the load's as-of date.",
         "SELECT account_id FROM accounts WHERE opened_date > (SELECT as_of_date FROM load_meta)"),
    Rule("R05", "KYC status is a recognized value", "accounts", ACCOUNTS_OWNER,
         "kyc_status must be one of VERIFIED, PENDING, EXPIRED.",
         "0 accounts with a kyc_status outside the declared set.",
         "SELECT account_id FROM accounts WHERE kyc_status NOT IN ('VERIFIED', 'PENDING', 'EXPIRED')"),
    Rule("R06", "Advisory fee is present only for Advisory Managed accounts", "accounts", ACCOUNTS_OWNER,
         "advisory_fee_bps must be between 0 and 150 for Advisory Managed "
         "accounts, and must be null for every other account type.",
         "0 accounts where advisory_fee_bps contradicts account_type.",
         "SELECT account_id FROM accounts WHERE "
         "(account_type = 'Advisory Managed' AND (advisory_fee_bps IS NULL OR advisory_fee_bps < 0 OR advisory_fee_bps > 150)) "
         "OR (account_type != 'Advisory Managed' AND advisory_fee_bps IS NOT NULL)"),
    Rule("R07", "Retirement flag matches account type", "accounts", ACCOUNTS_OWNER,
         "is_retirement_account must be true for Retail IRA accounts and "
         "false for every other account type.",
         "0 accounts where is_retirement_account contradicts account_type.",
         "SELECT account_id FROM accounts WHERE "
         "(account_type = 'Retail IRA' AND is_retirement_account = 0) "
         "OR (account_type != 'Retail IRA' AND is_retirement_account = 1)"),
    Rule("R08", "State of residence is a valid US state code", "accounts", ACCOUNTS_OWNER,
         "state must be a valid two-letter US state abbreviation.",
         "0 accounts with a state outside the 50-state reference list.",
         "SELECT account_id FROM accounts WHERE state NOT IN (" +
         ", ".join(f"'{s}'" for s in US_STATES) + ")"),

    # --- trades (8) ---------------------------------------------------
    Rule("R09", "Trade id present and unique", "trades", TRADES_OWNER,
         "Every trade record must carry a trade_id, and no trade_id may "
         "appear on more than one record.",
         "0 missing or duplicated trade_id values.",
         "SELECT trade_id FROM trades WHERE trade_id IS NULL "
         "UNION "
         "SELECT trade_id FROM trades GROUP BY trade_id HAVING COUNT(*) > 1"),
    Rule("R10", "Trade references an existing account", "trades", TRADES_OWNER,
         "Every trade's account_id must exist in the accounts extract.",
         "0 trades whose account_id has no matching account record.",
         "SELECT t.trade_id FROM trades t LEFT JOIN accounts a ON t.account_id = a.account_id "
         "WHERE a.account_id IS NULL"),
    Rule("R11", "Trade side is BUY or SELL", "trades", TRADES_OWNER,
         "side must be either BUY or SELL.",
         "0 trades with a side outside {BUY, SELL}.",
         "SELECT trade_id FROM trades WHERE side NOT IN ('BUY', 'SELL')"),
    Rule("R12", "Trade quantity is positive", "trades", TRADES_OWNER,
         "quantity must be greater than zero.",
         "0 trades with quantity <= 0.",
         "SELECT trade_id FROM trades WHERE quantity <= 0"),
    Rule("R13", "Trade price is positive", "trades", TRADES_OWNER,
         "price must be greater than zero.",
         "0 trades with price <= 0.",
         "SELECT trade_id FROM trades WHERE price <= 0"),
    Rule("R14", "Principal amount equals quantity times price", "trades", TRADES_OWNER,
         "principal_amount must equal quantity * price, to the cent.",
         "0 trades where principal_amount differs from quantity * price by more than $0.01.",
         "SELECT trade_id FROM trades WHERE ABS(principal_amount - quantity * price) > 0.01"),
    Rule("R15", "Settlement date is not before trade date", "trades", TRADES_OWNER,
         "settlement_date must be on or after trade_date.",
         "0 trades where settlement_date precedes trade_date.",
         "SELECT trade_id FROM trades WHERE settlement_date < trade_date"),
    Rule("R16", "Commission is within a reasonable bound", "trades", TRADES_OWNER,
         "commission must be between 0 and 1% of principal_amount.",
         "0 trades with commission outside [0, 1% of principal_amount].",
         "SELECT trade_id FROM trades WHERE commission < 0 OR commission > 0.01 * principal_amount"),

    # --- cash_activity (8) ----------------------------------------------
    Rule("R17", "Activity id present and unique", "cash_activity", CASH_OWNER,
         "Every cash activity record must carry an activity_id, and no "
         "activity_id may appear on more than one record.",
         "0 missing or duplicated activity_id values.",
         "SELECT activity_id FROM cash_activity WHERE activity_id IS NULL "
         "UNION "
         "SELECT activity_id FROM cash_activity GROUP BY activity_id HAVING COUNT(*) > 1"),
    Rule("R18", "Cash activity references an existing account", "cash_activity", CASH_OWNER,
         "Every cash activity's account_id must exist in the accounts extract.",
         "0 activity rows whose account_id has no matching account record.",
         "SELECT c.activity_id FROM cash_activity c LEFT JOIN accounts a ON c.account_id = a.account_id "
         "WHERE a.account_id IS NULL"),
    Rule("R19", "Activity type is a recognized value", "cash_activity", CASH_OWNER,
         "activity_type must be one of DEPOSIT, WITHDRAWAL, DIVIDEND, INTEREST, FEE, TRANSFER.",
         "0 activity rows with an activity_type outside the declared set.",
         "SELECT activity_id FROM cash_activity WHERE activity_type NOT IN "
         "('DEPOSIT', 'WITHDRAWAL', 'DIVIDEND', 'INTEREST', 'FEE', 'TRANSFER')"),
    Rule("R20", "Activity amount is never exactly zero", "cash_activity", CASH_OWNER,
         "amount must be nonzero; a zero-dollar activity record is not a real movement.",
         "0 activity rows with amount = 0.",
         "SELECT activity_id FROM cash_activity WHERE amount = 0"),
    Rule("R21", "Activity amount sign matches activity type", "cash_activity", CASH_OWNER,
         "WITHDRAWAL and FEE amounts must be negative; DEPOSIT, DIVIDEND, "
         "and INTEREST amounts must be positive.",
         "0 activity rows where the amount's sign contradicts activity_type.",
         "SELECT activity_id FROM cash_activity WHERE "
         "(activity_type IN ('WITHDRAWAL', 'FEE') AND amount >= 0) "
         "OR (activity_type IN ('DEPOSIT', 'DIVIDEND', 'INTEREST') AND amount <= 0)"),
    Rule("R22", "Settled flag is a recognized boolean", "cash_activity", CASH_OWNER,
         "settled_flag must be 0 or 1.",
         "0 activity rows with settled_flag outside {0, 1}.",
         "SELECT activity_id FROM cash_activity WHERE settled_flag NOT IN (0, 1)"),
    Rule("R23", "Activity was not posted in the future", "cash_activity", CASH_OWNER,
         "activity_date must not be later than today.",
         "0 activity rows with activity_date after the load's as-of date.",
         "SELECT activity_id FROM cash_activity WHERE activity_date > (SELECT as_of_date FROM load_meta)"),
    Rule("R24", "Activity amount is within a reasonable bound", "cash_activity", CASH_OWNER,
         "The magnitude of amount must not exceed $100,000 for a single activity line.",
         "0 activity rows with |amount| > $100,000.",
         "SELECT activity_id FROM cash_activity WHERE ABS(amount) > 100000"),

    # --- fee_assessments (8) ---------------------------------------------
    Rule("R25", "Fee id present and unique", "fee_assessments", FEES_OWNER,
         "Every fee assessment must carry a fee_id, and no fee_id may "
         "appear on more than one record.",
         "0 missing or duplicated fee_id values.",
         "SELECT fee_id FROM fee_assessments WHERE fee_id IS NULL "
         "UNION "
         "SELECT fee_id FROM fee_assessments GROUP BY fee_id HAVING COUNT(*) > 1"),
    Rule("R26", "Fee assessment references an existing account", "fee_assessments", FEES_OWNER,
         "Every fee assessment's account_id must exist in the accounts extract.",
         "0 fee rows whose account_id has no matching account record.",
         "SELECT f.fee_id FROM fee_assessments f LEFT JOIN accounts a ON f.account_id = a.account_id "
         "WHERE a.account_id IS NULL"),
    Rule("R27", "Fee type is a recognized value", "fee_assessments", FEES_OWNER,
         "fee_type must be one of ADVISORY, CUSTODY, TRANSACTION, FUND_EXPENSE.",
         "0 fee rows with a fee_type outside the declared set.",
         "SELECT fee_id FROM fee_assessments WHERE fee_type NOT IN "
         "('ADVISORY', 'CUSTODY', 'TRANSACTION', 'FUND_EXPENSE')"),
    Rule("R28", "Fee amount is never negative", "fee_assessments", FEES_OWNER,
         "fee_amount must be greater than or equal to zero.",
         "0 fee rows with fee_amount < 0.",
         "SELECT fee_id FROM fee_assessments WHERE fee_amount < 0"),
    Rule("R29", "Waived flag is a recognized boolean", "fee_assessments", FEES_OWNER,
         "waived_flag must be 0 or 1.",
         "0 fee rows with waived_flag outside {0, 1}.",
         "SELECT fee_id FROM fee_assessments WHERE waived_flag NOT IN (0, 1)"),
    Rule("R30", "Waiver reason is present only when a fee is waived", "fee_assessments", FEES_OWNER,
         "waiver_reason must be non-null when waived_flag is true, and "
         "null when waived_flag is false.",
         "0 fee rows where waiver_reason contradicts waived_flag.",
         "SELECT fee_id FROM fee_assessments WHERE "
         "(waived_flag = 1 AND waiver_reason IS NULL) "
         "OR (waived_flag = 0 AND waiver_reason IS NOT NULL)"),
    Rule("R31", "Fee was not assessed in the future", "fee_assessments", FEES_OWNER,
         "assessment_date must not be later than today.",
         "0 fee rows with assessment_date after the load's as-of date.",
         "SELECT fee_id FROM fee_assessments WHERE assessment_date > (SELECT as_of_date FROM load_meta)"),
    Rule("R32", "Fee amount is within a reasonable bound", "fee_assessments", FEES_OWNER,
         "fee_amount must not exceed $5,000 for a single assessment.",
         "0 fee rows with fee_amount > $5,000.",
         "SELECT fee_id FROM fee_assessments WHERE fee_amount > 5000"),
)


def by_id(rule_id: str) -> Rule:
    for r in RULES:
        if r.rule_id == rule_id:
            return r
    raise KeyError(rule_id)


assert len(RULES) == 32
assert len({r.rule_id for r in RULES}) == 32
