"""(b) Tamper test, repeatable: six attacks on copies of the ledger, repeated with a
different target entry each time, checked by three independent kinds of evidence.

    docker compose exec trusttrail python -m eval.tamper_test [--repeat 5]

The live ledger is never modified. Each repetition anchors the ledger first and
adds one release afterwards (for attack F, the anchoring window).
"""
import argparse
import random
import sqlite3

from app import db, ledger
from eval.common import markdown_table, write_csv, write_markdown
from scripts.demo_tamper import tamper_matrix

# What the design says each check should see. A mismatch means the claim in the
# report is wrong, so it is flagged rather than averaged away.
EXPECTED = {  # attack: (hash chain, student receipts, blockchain anchor)
    "A": (True, True, True), "B": (True, True, True), "C": (True, True, True),
    "D": (False, True, True), "E": (False, True, True), "F": (False, True, False)}
DESCRIPTION = {
    "A": "change an entry, leave its hash", "B": "change an entry, recompute its hash",
    "C": "delete an entry", "D": "change an entry, recompute every later hash",
    "E": "cut off the tail of the ledger", "F": "change an entry made after the last anchor, fix its hash"}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repeat", type=int, default=5)
    p.add_argument("--seed", type=int, default=1, help="random seed for choosing target entries")
    args = p.parse_args()
    rng = random.Random(args.seed)

    raw = []
    for rep in range(1, args.repeat + 1):
        conn = sqlite3.connect(f"file:{db.DB_PATH}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        releases = [e["entry_id"] for e in ledger.all_entries(conn) if e["kind"] == "release" and e["entry_id"] > 1]
        target = rng.choice(releases[:-1]) if len(releases) > 2 else None
        rows, info = tamper_matrix(target)
        print(f"  repetition {rep}: {info['entries']} entries, target #{info['target']}")
        for r in rows:
            raw.append([rep, info["target"], r["attack"], r["chain_detected"], r["receipts_failed"] > 0,
                        r["receipts_failed"], r["anchor_detected"]])

    write_csv("tamper_raw.csv", ["repetition", "target_entry", "attack", "chain_detected",
                                 "receipts_detected", "receipts_failed", "anchor_detected"], raw)
    table, all_as_expected = [], True
    for attack, (exp_chain, exp_receipts, exp_anchor) in EXPECTED.items():
        runs = [r for r in raw if r[2] == attack]
        n = len(runs)
        chain, rec, anc = (sum(r[i] for r in runs) for i in (3, 4, 6))
        any_check = sum(r[3] or r[4] or r[6] for r in runs)
        ok = all((r[3], r[4], r[6]) == (exp_chain, exp_receipts, exp_anchor) for r in runs)
        all_as_expected &= ok
        table.append([f"{attack}. {DESCRIPTION[attack]}", f"{chain}/{n}", f"{rec}/{n}", f"{anc}/{n}",
                      f"{any_check}/{n}", "yes" if ok else "**NO**"])

    md = markdown_table(["Attack", "Hash chain", "Student receipts", "Blockchain anchor", "Any check",
                         "As designed"], table)
    verdict = ("Every repetition matched the design." if all_as_expected
               else "**Some results differ from the design; see tamper_raw.csv.**")
    notes = ("Cells count repetitions in which the check detected the attack. Each repetition attacks a "
             "different, randomly chosen release on a fresh copy of the ledger. Receipts are the receipts "
             "TrustTrail issued (as students would hold them); the anchor is the Merkle roots on the local "
             "chain. F is the anchoring window: until the next batch, only receipts protect a new entry.")
    print("\n" + md + "\n\n" + verdict)
    write_markdown("tamper.md", f"Tamper test ({args.repeat} repetitions)", f"{md}\n\n{verdict}\n\n{notes}")
    print("Saved eval/results/tamper.md and tamper_raw.csv")


if __name__ == "__main__":
    main()
