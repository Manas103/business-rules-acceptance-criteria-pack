"""Runs every rule's compiled SQL assertion against the loaded tables and
names, for each violation, the exact rule and record responsible."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from app.rules import RULES, Rule


@dataclass(frozen=True)
class Violation:
    rule_id: str
    rule_name: str
    table: str
    owner: str
    record_id: str


def run_rule(conn: sqlite3.Connection, rule: Rule) -> list[str]:
    cur = conn.execute(rule.sql)
    return [row[0] for row in cur.fetchall()]


def run_all(conn: sqlite3.Connection) -> list[Violation]:
    violations: list[Violation] = []
    for rule in RULES:
        for record_id in run_rule(conn, rule):
            violations.append(Violation(
                rule_id=rule.rule_id,
                rule_name=rule.name,
                table=rule.table,
                owner=rule.owner,
                record_id=record_id,
            ))
    return violations
