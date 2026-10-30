"""Unit tests for the evaluation scoring logic (Phase 6)."""
import csv
from collections import Counter

import pytest

from app import study
from eval.analyze_study import q1_scores, sign_test
from eval.common import percentile, summarise
from eval.plot_taxonomy import HERE, VALUE

ALL = ["name", "email", "roll_no", "department", "program", "year"]


def test_percentile_is_nearest_rank():
    values = list(range(1, 101))
    assert percentile(values, 95) == 95 and percentile(values, 50) == 50 and percentile([7], 95) == 7
    assert summarise([1, 2, 3, 100])["median"] == 2.5


def test_plan_counterbalances_screens_and_tasks():
    plans = [tuple((s["condition"], s["scenario"]) for s in study.plan_for(f"P{n:02d}")) for n in range(1, 9)]
    assert len(set(plans)) == 4                                   # four groups...
    assert all(c == 2 for c in Counter(plans).values())           # ...equally filled by consecutive codes
    for plan in plans:                                            # each person: both screens x both tasks
        assert sorted(plan) == [("baseline", "F"), ("baseline", "P"), ("trusttrail", "F"), ("trusttrail", "P")]


def test_what_the_service_received():
    assert set(study.received_for("baseline", "shared", [])) == set(ALL) | {"account_id"}
    assert study.received_for("trusttrail", "shared", ["year"]) == ["service_id", "year"]
    assert study.received_for("trusttrail", "declined", ["year"]) == []


@pytest.mark.parametrize("condition,scenario,outcome,chosen,expected", [
    ("trusttrail", "P", "shared", ["department", "program", "year"], True),
    ("trusttrail", "P", "shared", ["department", "program", "year", "email"], False),
    ("trusttrail", "P", "declined", [], False),
    ("baseline", "P", "shared", [], False),         # all-or-nothing: can't do task P
    ("baseline", "F", "shared", [], True),
    ("trusttrail", "F", "shared", ALL, True),
])
def test_chose_as_intended(condition, scenario, outcome, chosen, expected):
    received = study.received_for(condition, outcome, chosen)
    assert study.matched(scenario, outcome, received) is expected


def test_q1_scoring():
    received = ["department", "service_id", "year"]
    assert q1_scores(["department", "service_id", "year"], received) == (True, 1.0)
    exact, items = q1_scores(["department", "year"], received)        # missed one of 8 items
    assert not exact and items == pytest.approx(7 / 8)
    assert q1_scores(["nothing"], []) == (True, 1.0)
    assert q1_scores([], [])[0] is False                              # must tick "Nothing at all"


def test_sign_test():
    assert sign_test(0, 0) == 1.0
    assert sign_test(10, 0) == pytest.approx(2 / 1024)
    assert sign_test(5, 5) == 1.0


def test_taxonomy_sheet_is_well_formed():
    rows = list(csv.DictReader((HERE / "taxonomy.csv").open()))
    assert len(rows) == 9                                             # the nine features
    for r in rows:
        assert r["trusttrail_suggested"] in VALUE and r["trusttrail_evidence"]
        for col in ["trusttrail_score"] + [f"P{i}_score" for i in range(1, 5)]:
            assert r[col].strip().lower() in ("", *VALUE)
    assert len(list(csv.DictReader((HERE / "proposals.csv").open()))) == 4
