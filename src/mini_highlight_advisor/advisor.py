# src/mini_highlight_advisor/advisor.py
from __future__ import annotations

from dataclasses import dataclass
from itertools import zip_longest

from .consistency import annotate
from .matching import MatchResult, Target, match
from .palette import PaintColor


@dataclass(frozen=True)
class AdviceRow:
    role: str
    result: MatchResult
    note: str


def advise(targets: list[Target], roles: list[str], owned: list[PaintColor],
           catalog: list[PaintColor]) -> list[AdviceRow]:
    rows: list[AdviceRow] = []
    for target, role in zip_longest(targets, roles, fillvalue=""):
        if target == "":            # more roles than targets -> ignore extra roles
            continue
        role = role or ""
        result = match(target, owned, catalog)
        rows.append(AdviceRow(role, result, annotate(result, role)))
    return rows
