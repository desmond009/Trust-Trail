"""(d) Analyse the usability study: did participants choose what they intended, and
did they understand what was shared?

    docker compose exec trusttrail python -m eval.analyze_study
    docker compose exec trusttrail python -m eval.analyze_study --delete-all --yes   # after the report

Codes P98 and P99 are reserved for scripts/check_study.py and are excluded
unless --participants names them. Writes eval/results/study.md plus
anonymised CSVs (participant code only; free-text comments in their own file).
"""
import argparse
import json
import math
import sqlite3
import statistics
import sys

from app import study
from eval.common import markdown_table, write_csv, write_markdown

TEST_CODES = study.TEST_CODES
NAMES = {"baseline": "Keycloak default consent", "trusttrail": "TrustTrail consent screen"}


def q1_scores(q1: list[str], received: list[str]) -> tuple[bool, float]:
    """Exact: ticked exactly what the service got. Item accuracy: share of the 8 items judged right."""
    ticked = set(q1) - {study.NOTHING}
    exact = ticked == set(received) and ((study.NOTHING in q1) == (not received))
    items = statistics.mean((o in ticked) == (o in received) for o in study.Q1_OPTIONS)
    return exact, items


def sign_test(better: int, worse: int) -> float:
    """Exact two-sided sign test (ties dropped)."""
    n = better + worse
    if n == 0:
        return 1.0
    k = min(better, worse)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def load(participants: set[str] | None):
    conn = sqlite3.connect(f"file:{study.DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    keep = (lambda p: p in participants) if participants else (lambda p: p not in TEST_CODES)
    trials = [dict(r) for r in conn.execute("SELECT * FROM trials ORDER BY participant, trial") if keep(r["participant"])]
    screens = [dict(r) for r in conn.execute("SELECT * FROM conditions ORDER BY participant") if keep(r["participant"])]
    for t in trials:
        t["received"] = json.loads(t["received"])
        t["q1"] = json.loads(t["q1"]) if t["q1"] else None
        t["q1_exact"], t["q1_items"] = q1_scores(t["q1"], t["received"]) if t["q1"] is not None else (None, None)
    for s in screens:
        s["likert"] = json.loads(s["likert"])
    return trials, screens


def pct(values) -> str:
    values = [v for v in values if v is not None]
    return f"{100 * sum(values) / len(values):.0f}% ({sum(values)}/{len(values)})" if values else "–"


def med(values) -> str:
    values = [v for v in values if v is not None]
    return f"{statistics.median(values):g}" if values else "–"


def analyse(trials, screens) -> dict:
    out = {"participants": sorted({t["participant"] for t in trials}),
           "complete": sorted(p for p in {t["participant"] for t in trials}
                              if sum(t["participant"] == p and t["q1"] is not None for t in trials) == 4
                              and sum(s["participant"] == p for s in screens) == 2)}
    out["intended"] = {f"{c}/{s}": [t["matched"] for t in trials if t["condition"] == c and t["scenario"] == s]
                       for c in NAMES for s in ("P", "F")}
    out["comprehension"] = {c: {"exact": [t["q1_exact"] for t in trials if t["condition"] == c],
                                "items": [t["q1_items"] for t in trials if t["condition"] == c],
                                "confidence": [t["q1_confidence"] for t in trials if t["condition"] == c]}
                            for c in NAMES}
    out["screens"] = {c: {"purpose": [s["purpose_correct"] for s in screens if s["condition"] == c],
                          "retention": [s["retention_correct"] for s in screens if s["condition"] == c],
                          "likert": list(zip(*[s["likert"] for s in screens if s["condition"] == c]))}
                      for c in NAMES}
    out["decision_ms"] = {c: [t["decision_ms"] for t in trials if t["condition"] == c] for c in NAMES}
    # Paired: each participant's mean item accuracy on each screen.
    better = worse = ties = 0
    for p in out["complete"]:
        a = {c: statistics.mean(t["q1_items"] for t in trials if t["participant"] == p and t["condition"] == c)
             for c in NAMES}
        better += a["trusttrail"] > a["baseline"]
        worse += a["trusttrail"] < a["baseline"]
        ties += a["trusttrail"] == a["baseline"]
    out["paired"] = {"better": better, "worse": worse, "ties": ties, "p": sign_test(better, worse)}
    return out


def report(a: dict) -> str:
    n = len(a["complete"])
    parts = [f"Participants with complete data: **{n}** (of {len(a['participants'])} started).", ""]
    parts.append("### Did participants choose what they intended?\n")
    parts.append(markdown_table(["Screen", "Task P: share some, not all", "Task F: share everything"],
                                [[NAMES[c], pct(a["intended"][f"{c}/P"]), pct(a["intended"][f"{c}/F"])] for c in NAMES]))
    parts.append("\nThe Keycloak screen is all-or-nothing, so task P cannot be done there; its row shows how "
                 "many participants shared everything anyway (or refused), not a usability failure of theirs.\n")
    parts.append("### Did participants understand what the service received?\n")
    parts.append(markdown_table(
        ["Screen", "Exactly right", "Items right (mean)", "Confidence (median, 1-5)"],
        [[NAMES[c], pct(a["comprehension"][c]["exact"]),
          f"{statistics.mean(a['comprehension'][c]['items']):.0%}" if a["comprehension"][c]["items"] else "–",
          med(a["comprehension"][c]["confidence"])] for c in NAMES]))
    pr = a["paired"]
    parts.append(f"\nPaired comparison (items right, per participant): TrustTrail better for {pr['better']}, "
                 f"worse for {pr['worse']}, tied for {pr['ties']}; exact sign test p = {pr['p']:.3f}.\n")
    parts.append("### Purpose, retention and opinions\n")
    likert_rows = []
    for c in NAMES:
        L = a["screens"][c]["likert"]
        likert_rows.append([NAMES[c], pct(a["screens"][c]["purpose"]), pct(a["screens"][c]["retention"])]
                           + [med(L[i]) if i < len(L) else "–" for i in range(len(study.cfg()["likert"]))])
    parts.append(markdown_table(["Screen", "Purpose answered correctly", "Retention answered correctly"]
                                + [f"“{t}” (median)" for t in study.cfg()["likert"]], likert_rows))
    parts.append("\n### Time to decide\n")
    parts.append(markdown_table(["Screen", "Median (s)"],
                                [[NAMES[c], f"{statistics.median([v for v in a['decision_ms'][c] if v]) / 1000:.1f}"
                                  if any(a["decision_ms"][c]) else "–"] for c in NAMES]))
    parts.append("\nKeycloak times include the login on the first task, so they are not comparable with "
                 "TrustTrail times; report them only as context.\n")
    parts.append("### Limits\n\nSmall convenience sample of classmates; invented persona; the TrustTrail screen is "
                 "a prototype (students cannot yet deselect attributes in the running system); the facilitator "
                 "is part of the team. Treat the results as indicative, not as evidence of general usability.")
    return "\n".join(parts)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--participants", help="comma-separated codes to include (default: all except P98, P99)")
    p.add_argument("--json", action="store_true", help="print the raw analysis as JSON (for checks)")
    p.add_argument("--delete-all", action="store_true", help="delete study.db (after the report is final)")
    p.add_argument("--yes", action="store_true")
    args = p.parse_args()

    if args.delete_all:
        if not args.yes:
            sys.exit("This permanently deletes all study responses. Re-run with --yes to confirm.")
        study.DB_PATH.unlink(missing_ok=True)
        print(f"Deleted {study.DB_PATH}")
        return
    if not study.DB_PATH.exists():
        sys.exit("No study data yet (study.db does not exist).")

    trials, screens = load(set(args.participants.split(",")) if args.participants else None)
    a = analyse(trials, screens)
    if args.json:
        print(json.dumps(a, default=str))
        return
    if not trials:
        sys.exit("No participants to analyse.")

    write_csv("study_trials.csv", ["participant", "trial", "screen", "scenario", "outcome", "received",
                                   "chose_as_intended", "decision_ms", "q1_answer", "q1_exact", "q1_items_right",
                                   "q1_confidence"],
              [[t["participant"], t["trial"], t["condition"], t["scenario"], t["outcome"], " ".join(t["received"]),
                t["matched"], t["decision_ms"], " ".join(t["q1"] or []), t["q1_exact"],
                round(t["q1_items"], 3) if t["q1_items"] is not None else None, t["q1_confidence"]] for t in trials])
    write_csv("study_screens.csv", ["participant", "screen", "purpose_correct", "retention_correct"]
              + [f"likert_{i + 1}" for i in range(len(study.cfg()["likert"]))],
              [[s["participant"], s["condition"], s["purpose_correct"], s["retention_correct"], *s["likert"]]
               for s in screens])
    write_csv("study_comments.csv", ["participant", "screen", "comment"],
              [[s["participant"], s["condition"], s["comment"]] for s in screens if s["comment"]])
    body = report(a)
    print(body)
    write_markdown("study.md", "Usability study results", body)
    print("\nSaved eval/results/study.md, study_trials.csv, study_screens.csv, study_comments.csv")


if __name__ == "__main__":
    main()
