# Business Rules as Executable Acceptance Criteria with a Partner Report Pack

32 plain-language business rules, each with a named owner and a written
success criterion, compiled into 32 SQL assertions that run on every
load of a simulated retail brokerage's accounts, trades, cash activity,
and fee assessments. One command regenerates a pivot-ready Excel pack a
business partner can open without writing SQL. Every number below was
measured on this machine, not targeted: the rules caught 32 of 32
seeded violations, each attributed to the right rule by name, with 0
unexpected catches, and 0 of 20 independently generated clean loads
were falsely failed.

## Why this exists

A business rule usually lives in two places that can silently drift
apart: a sentence in a requirements document, and whatever code someone
wrote to enforce it. This project collapses that gap by making the rule
and its enforcement the same artifact: `app/rules.py` pairs each plain-
language rule with the exact SQL that checks it, so there is no second
copy of the logic that can go stale. The success criterion a business
partner reads is the same success criterion the load is actually
graded against, and the named owner is who the partner report pack
tells to go look.

## Honest framing, up front

- **This is simulated retail brokerage data, not a connection to any
  real account, trade, or client.** `app/generator.py` generates every
  record below from a fixed seed.
- **The 32 seeded violations are a deliberately corrupted copy of a
  clean load**, one per rule, built in `app/violations.py` specifically
  so each mutation trips exactly the rule it targets. Several of the
  32 mutations needed a second, dependent field corrected alongside the
  primary one (for example, a trade with a corrupted `quantity` also
  needs its `principal_amount` recomputed), precisely because the rules
  are cross-checked against each other; see Findings for the two cases
  where that was missed on the first pass and showed up as an
  unexpected catch under a different rule's name.
- **SQLite, not a managed database service.** Every load lives in a
  fresh in-memory SQLite database (`app/db.py`); SQLite ships with
  Python, so there is no server to stand up and no reachability check
  needed, unlike this portfolio's PostgreSQL-backed siblings.
- **Machine and toolchain.** 8 physical / 16 logical cores (AMD Ryzen 7
  7800X3D), Windows 11 Home, Python 3.12.10, SQLite (via Python's
  built-in `sqlite3`), openpyxl 3.1.5, pytest 9.1.1.

## Architecture

```
app/
  rules.py       32 Rule objects (8 per table): rule_id, plain-language
                 text, named owner, written success criterion, and the
                 exact SQL assertion that enforces it.
  generator.py   deterministic synthetic daily load: 200 accounts plus
                 their trades, cash activity, and fee assessments, built
                 to satisfy every rule exactly.
  db.py          loads one daily load into a fresh in-memory SQLite
                 database (accounts, trades, cash_activity,
                 fee_assessments, load_meta).
  violations.py  injects exactly 32 seeded violations into a clean load
                 copy, one per rule, with a known expected (rule_id,
                 record_id) for each.
  engine.py      runs every rule's SQL against the loaded tables and
                 returns one Violation per (rule, record) that fails.
scripts/
  run_gate_benchmark.py      32-seeded-violation catch rate plus 20 clean loads
  generate_report_pack.py    the one command that (re)writes docs/report_pack.xlsx
tests/           19 pytest tests (rules catalog, generator conformance,
                 violation injection, and the engine's catch rate and
                 false-failure rate; no external service needed)
```

### Why the rule and its SQL live in the same object

An earlier design kept a rules document and a validation script as two
separate files, the way a real firm usually does it. The problem that
design has is exactly the one this project exists to solve: nothing
stops the document and the script from drifting apart. Putting the SQL
string directly on the `Rule` dataclass next to its plain-language text
and success criterion means there is only one artifact to review, and a
change to the rule's enforcement is, by construction, a change to the
rule itself.

### Why violations are seeded into one combined load, not 32 separate loads

Seeding one violation per rule into a single load and asking the engine
to attribute each to the right rule by name is a materially harder test
than running 32 isolated single-rule checks: it only works if the SQL
assertions do not interfere with each other when 32 different things
are simultaneously wrong across the same four tables. Two of the
seeded mutations did interfere on the first attempt (see Findings); a
report pack that ran rules one at a time would never have surfaced
that.

## Validation

### Gate benchmark (32 seeded violations, 20 clean loads)

```
$ python scripts/run_gate_benchmark.py
-- claim: 32 of 32 seeded violations caught and attributed to the rule by name --
seeded violations caught: 32 / 32
unexpected violations on the seeded-violation load: 0

-- claim: 0 of 20 clean loads falsely failed --
false failures across 20 independent clean loads: 0
```

Full output: `docs/gate_benchmark_output.txt`.

### Report pack generation (one command)

```
$ python scripts/generate_report_pack.py --seed-violations
wrote .../docs/report_pack.xlsx (seeded-violation demo load) at ...
```

Full output: `docs/report_pack_generation_output.txt`. The committed
`docs/report_pack.xlsx` (11 KB) is this exact run: a "Rule Catalog"
sheet (32 rows), a "Rule Results" sheet (32 rows, one per rule, PASS or
FAIL with a violation count), and a "Violations Detail" sheet (32 rows,
one per caught violation), every sheet flat and pivot-ready with no
merged headers or summary rows mixed into the data.

### Tests

19 pytest tests: the rule catalog's structural invariants (32 rules, 8
per table, every rule owned and criterioned), the generator's
determinism and its conformance to every rule on a clean load, the
seeded-violation set's shape (32 distinct rules, one violation each),
and the engine's catch rate, attribution accuracy, and false-failure
rate across 10 additional independent clean loads.

```
$ python -m pytest tests -q
...................                                                     [100%]
19 passed in 0.34s
```

Full transcript: `docs/test_output.txt`.

## Findings

### A corrupted quantity or price also broke two other rules, under their own names, until the mutation repaired what it did not mean to break

**Symptom.** The first run of the gate benchmark reported 32 of 32
seeded violations caught, which looked like success, but also reported
5 unexpected violations: `R14` (principal consistency) fired twice and
`R21` (cash activity sign) fired once more than intended, and 5 of the
20 clean-load runs each produced one spurious `R14` failure.

**Wrong hypothesis first.** The first guess was a floating-point
comparison bug in `R14`'s SQL, since it compared a stored
`principal_amount` against a freshly computed `ROUND(quantity * price, 2)`
and SQLite's `ROUND` does not necessarily break rounding ties the same
way Python's `round()` does.

**The measurement that discriminated.** Removing the SQL-side `ROUND()`
and comparing against the raw, unrounded product with the same $0.01
tolerance fixed the 5 clean-load false failures immediately, confirming
that part was a genuine double-rounding mismatch. But it did not fix
the 2 remaining unexpected hits on the seeded-violation load. Printing
the two flagged trades showed `quantity * price` had changed to a
different number than the `principal_amount` field still on the
record, because the seeded mutations for `R12` (invalid quantity) and
`R13` (invalid price) changed `quantity` or `price` directly and left
`principal_amount` computed from the pre-mutation values.

**Root cause.** Two different bugs, not one: SQLite's `ROUND()` versus
Python's `round()` disagreeing at exact rounding-tie boundaries (fixed
by comparing against the raw product instead of re-rounding in SQL),
and `R12`/`R13`'s mutations breaking `R14`'s invariant as an unintended
side effect, because `principal_amount` is derived from `quantity` and
`price` and the mutation only touched one of the three.

**Fix.** `R12` and `R13`'s seeded mutations now zero the quantity or
price (rather than using an arbitrary negative number) and recompute
`principal_amount` and `commission` to match, specifically because a
negative `principal_amount` makes `R16`'s commission bound
(`commission <= 1% of principal_amount`) unsatisfiable by any
non-negative commission, which would have been a third incidental
failure mode from the same root cause. Separately, `R20` and `R24`'s
amount-only mutations now also pin `activity_type` to `TRANSFER`, the
one activity type `R21`'s sign-consistency check does not look at,
after the same class of bug showed up a second time in the cash
activity table: a mutation that changes a value `R21` cares about
(`amount`) without checking whether the record's existing
`activity_type` makes that value's new sign a violation too.

**Why the method mattered.** "32 of 32 caught" was true on the very
first run; it was the *unexpected-violations* count, not the catch
rate, that exposed both bugs. A benchmark that only checks whether the
rules it meant to trip actually tripped would have shipped silently
wrong seed data: 5 rules were, by coincidence, each costing the clean
load an undeserved failure, and 2 of the 32 "successes" were really
two rules firing on one mutation rather than the one rule that mutation
was meant to test.

## Measured results

8 physical / 16 logical cores, Windows 11 Home, Python 3.12.10, SQLite
(Python 3.12's bundled version).

| Metric | Measured | Claim |
|---|---|---|
| **Business rules** | **32**, each with a named owner and written success criterion | 32 plain-language business rules, each with a named owner and a written success criterion |
| Compiled to SQL | 32 / 32 rules have an executable SQL assertion | compiled into SQL assertions that run on every load |
| **Seeded violations caught, attributed by rule name** | **32 / 32**, 0 unexpected | 32 of 32 seeded violations caught and attributed to the rule by name |
| **False failures, 20 clean loads** | **0** | 0 of 20 clean loads falsely failed |
| Report pack regeneration | 1 command, 3 sheets (32 + 32 + 32 rows) | one command regenerates the pivot-ready Excel pack |

## Building and running

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

python -m pytest tests -q                           # docs/test_output.txt
python scripts/run_gate_benchmark.py                # docs/gate_benchmark_output.txt
python scripts/generate_report_pack.py --seed-violations   # docs/report_pack.xlsx
```

## Sibling comparison

[`requirements-traceability-workbench`](https://github.com/Manas103/requirements-traceability-workbench)
and [`validation-protocol-traceability-manager`](https://github.com/Manas103/validation-protocol-traceability-manager)
are this portfolio's other requirements-to-verification tools (86
requirements traced with 11/11 orphan catches, and a requirements to
risk to IQ/OQ/PQ bidirectional matrix, respectively). Both trace a
requirement to a test someone else already wrote. This project runs the
opposite direction: a business rule stated in plain English *becomes*
the test over the data, with no separate test suite to keep in sync,
which is why a drift between a rule's stated intent and its enforcement
is structurally impossible here rather than merely checked for.

## Limitations

- **32 rules is a fixed, hand-authored catalog**, not a rules-authoring
  tool; adding a new business rule means writing a new `Rule` entry, not
  configuring one through an interface a business partner could use
  directly.
- **Every rule here is a single-table assertion.** None of the 32 spans
  more than one table in its SQL (foreign-key existence checks read a
  second table but assert about rows in the first); a rule like "the
  sum of a household's advisory fees must not exceed X" would need a
  different shape of rule than any of the 32 above.
- **The report pack's "Rule Results" sheet reflects a single run**, not
  a time series; a daily-trend pivot would need the script to append
  rather than overwrite, which it does not do.
- **The $0.01 and similar tolerances (commission bound, principal
  consistency) are fixed constants**, not per-security-type or
  per-account-type parameters a real firm's tolerance table would need.
