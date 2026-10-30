"""(b) Violation-detection test, repeatable: the three scripted bad services plus
honest traffic, repeated from base tiers each time.

    docker compose exec trusttrail python -m eval.violation_test [--repeat 3] [--attempts 5]

Each repetition records trust resets first, so every run starts from the same
state; services are reset again at the end so the system is left as found.
"""
import argparse

from app import settings
from eval.common import markdown_table, write_csv, write_markdown
from scripts.demo_phase4 import BEHAVIOUR, HONEST, detection_run, reset_all


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repeat", type=int, default=3)
    p.add_argument("--attempts", type=int, default=5)
    args = p.parse_args()

    raw, honest_total = [], {"releases": 0, "violations": 0, "tier_changes": 0}
    progressions = {}
    for rep in range(1, args.repeat + 1):
        print(f"repetition {rep}/{args.repeat}")
        rows, honest = detection_run(args.attempts, verbose=False)
        for k in honest_total:
            honest_total[k] += honest[k]
        for r in rows:
            raw.append([rep, r["sid"], r["rule"], r["attempts"], r["detected"], r["wrong_rule"],
                        r["score"][0], r["score"][1], " > ".join(r["tiers"]), r["caps"][0], r["caps"][-1]])
            progressions.setdefault(r["sid"], set()).add(" → ".join(r["tiers"]))
    reset_all("end of violation test")

    write_csv("violations_raw.csv", ["repetition", "service", "rule", "attempts", "detected", "wrong_rule",
                                     "score_before", "score_after", "tiers", "cap_before", "cap_after"], raw)
    names = settings.services()
    table = []
    for sid, (what, rule) in BEHAVIOUR.items():
        runs = [r for r in raw if r[1] == sid]
        attempts, detected = sum(r[3] for r in runs), sum(r[4] for r in runs)
        prog = progressions[sid]
        table.append([names[sid]["name"], what, rule, attempts, detected, attempts - detected,
                      sum(r[5] for r in runs), f"{detected / attempts:.0%}",
                      next(iter(prog)) if len(prog) == 1 else "varied: " + " / ".join(sorted(prog)),
                      f"{runs[0][9]} → {runs[0][10]}"])
    md = markdown_table(["Service", "Misbehaviour", "Rule", "Attempts", "Detected", "Missed", "Wrong rule",
                         "Detection rate", "Tier after each attempt (every repetition)", "Max profile"], table)
    honest_md = markdown_table(["Honest services", "Releases", "Violations (false positives)", "Tier changes"],
                               [[", ".join(names[s]["name"] for s in HONEST), honest_total["releases"],
                                 honest_total["violations"], honest_total["tier_changes"]]])
    notes = (f"{args.repeat} repetitions × {args.attempts} attempts per bad service, each repetition starting "
             "from base tiers. Scripted clients only: this shows that the rules fire as designed and that "
             "honest traffic is not flagged. It does not estimate how often real services misbehave, nor how "
             "often subtler misuse (anything after the data leaves TrustTrail) goes unseen.")
    print("\n" + md + "\n\n" + honest_md)
    write_markdown("violations.md", "Violation detection test", f"{md}\n\n{honest_md}\n\n{notes}")
    print("Saved eval/results/violations.md and violations_raw.csv")


if __name__ == "__main__":
    main()
