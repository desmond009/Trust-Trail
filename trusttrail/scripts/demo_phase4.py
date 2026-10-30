"""Phase 4 demo: run the three bad services and honest traffic, then print the
detection counts as a Markdown table for the report.

    docker compose exec trusttrail python -m scripts.demo_phase4 [--attempts 5] [--keep]

Starts every service from its base tier (recorded trust resets) and, unless
--keep is given, resets them again at the end so the other demos keep working.
"""
import argparse
import sqlite3
import time

import httpx

from app import db, ledger, settings
from app.demo_login import login, release
from app.demo_service import TRUSTTRAIL, DemoService
from scripts.bad_services import BAD

ADMIN = {"Authorization": f"Bearer {settings.ADMIN_TOKEN}"}
HONEST = ["library", "lms", "exam"]
STUDENTS = ["asha", "rohan", "meera", "kabir", "zoya"]
BEHAVIOUR = {"overasker": ("asks for attributes its declaration doesn't cover", "1 · undeclared attribute"),
             "retainer": ("requests again after its promised deletion time", "2 · after retention"),
             "tiercap": ("asks Keycloak for a profile above its tier cap", "3 · above tier cap")}
RULE = {"overasker": "undeclared_attribute", "retainer": "after_retention", "tiercap": "above_tier_cap"}


def sync() -> dict:
    return httpx.post(f"{TRUSTTRAIL}/trust/sync", headers=ADMIN, timeout=30).raise_for_status().json()


def reset_all(reason: str):
    sync()
    for sid in settings.services():
        httpx.post(f"{TRUSTTRAIL}/trust/{sid}/reset", json={"reason": reason}, headers=ADMIN).raise_for_status()


def violation_entries(after_id: int) -> list[dict]:
    conn = sqlite3.connect(f"file:{db.DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return [e for e in ledger.all_entries(conn) if e["entry_id"] > after_id and e["kind"] == "violation"]


def last_entry_id() -> int:
    conn = sqlite3.connect(f"file:{db.DB_PATH}?mode=ro", uri=True)
    return conn.execute("SELECT COALESCE(MAX(entry_id), 0) FROM ledger").fetchone()[0]


def wait_for_count(service_id: str, more_than: int, timeout: float = 15) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        s = sync()[service_id]
        if s["violations"] > more_than:
            return s
        time.sleep(0.5)
    return sync()[service_id]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--attempts", type=int, default=5)
    p.add_argument("--keep", action="store_true", help="leave the bad services demoted afterwards")
    args = p.parse_args()

    reset_all("start of Phase 4 demo")
    start_id = last_entry_id()

    print(f"Honest traffic: {len(HONEST)} services x {len(STUDENTS)} students x 2 rounds ...")
    honest_releases = 0
    for sid in HONEST:
        decl = DemoService(sid).declare()
        for _ in range(2):
            for student in STUDENTS:
                token = login(sid, student, settings.services()[sid]["wants"]).json()["access_token"]
                honest_releases += release(token, decl["declaration_id"]).status_code == 200

    rows = []
    for sid, cls in BAD.items():
        bad = cls(sid)
        first = sync()[sid]
        tiers, caps, state = [first["tier"]], [first["cap"]], first
        print(f"{sid}: {args.attempts} attempts ...")
        for _ in range(args.attempts):
            bad.misbehave(STUDENTS[0])
            state = wait_for_count(sid, state["violations"])
            tiers.append(state["tier"])
            caps.append(state["cap"])
        caught = [v for v in violation_entries(start_id) if v["service_id"] == sid]
        rows.append({"sid": sid, "detected": sum(v["rule"] == RULE[sid] for v in caught),
                     "wrong_rule": sum(v["rule"] != RULE[sid] for v in caught),
                     "score": (first["score"], state["score"]), "tiers": tiers, "caps": caps})

    honest_violations = [v for v in violation_entries(start_id) if v["service_id"] in HONEST]
    states = sync()

    names = settings.services()
    print("\n### Violation detection (simulated services)\n")
    print("| Service | Misbehaviour | Rule | Attempts | Detected | Missed | Score | Tier after each attempt | Max profile |")
    print("|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        what, rule = BEHAVIOUR[r["sid"]]
        print(f"| {names[r['sid']]['name']} (`{r['sid']}`) | {what} | {rule} | {args.attempts} | {r['detected']} "
              f"| {args.attempts - r['detected']} | {r['score'][0]} → {r['score'][1]} | {' → '.join(r['tiers'])} "
              f"| {r['caps'][0]} → {r['caps'][-1]} |")
    print(f"\n| Honest services | Releases | Violations recorded (false positives) | Tier changes |")
    print("|---|---|---|---|")
    print(f"| {', '.join(names[s]['name'] for s in HONEST)} | {honest_releases} | {len(honest_violations)} "
          f"| {sum(states[s]['tier'] != states[s]['base_tier'] for s in HONEST)} |")
    if any(r["wrong_rule"] for r in rows):
        print("\nWARNING: some violations were recorded under an unexpected rule:",
              {r["sid"]: r["wrong_rule"] for r in rows})
    print("\nScripted clients only; these counts show the rules fire as designed, not how real services behave.")

    if not args.keep:
        reset_all("end of Phase 4 demo")
        print("All services reset to their base tier (recorded in the ledger). Use --keep to inspect the demoted state.")


if __name__ == "__main__":
    main()
