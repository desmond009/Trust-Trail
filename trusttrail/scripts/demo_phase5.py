"""Phase 5 demo: anchor batches while releases keep arriving, then report the
delay from each entry to its anchor and the gas used per anchor.

    docker compose exec trusttrail python -m scripts.demo_phase5 [--batches 4] [--interval 20] [--every 2]

To keep the demo short it triggers anchoring itself every --interval seconds
(the background job uses config/anchoring.yaml, 300 s by default). Delay
depends on the interval, so the summary also says what to expect at 300 s.
"""
import argparse
import random
import statistics
import time
from datetime import datetime

import httpx

from app import anchoring, db, ledger, settings
from app.demo_login import login, release
from app.demo_service import TRUSTTRAIL, DemoService

ADMIN = {"Authorization": f"Bearer {settings.ADMIN_TOKEN}"}
STUDENTS = ["asha", "rohan", "meera", "kabir", "zoya"]


def anchor_now() -> tuple[dict | None, float]:
    started = time.time()
    r = httpx.post(f"{TRUSTTRAIL}/anchors/run", headers=ADMIN, timeout=300)
    r.raise_for_status()
    return r.json()["batch"], time.time() - started


def entry_time(iso: str) -> float:
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()


def pct(values: list[float], p: float) -> float:
    s = sorted(values)
    return s[min(len(s) - 1, round(p / 100 * (len(s) - 1)))]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--batches", type=int, default=4)
    p.add_argument("--interval", type=int, default=20, help="seconds between anchors in this demo")
    p.add_argument("--every", type=float, default=2.0, help="average seconds between releases")
    args = p.parse_args()

    dep = anchoring.Anchorer().deployment()
    print(f"Contract {dep['address']} on {dep['network']} (chain {dep['chainId']}); "
          f"{args.batches} batches, one every {args.interval} s, a release every ~{args.every} s\n")
    anchor_now()   # start from a fully anchored ledger so every batch below is timed cleanly

    decl = DemoService("lms").declare()
    batches = []
    for b in range(args.batches):
        deadline = time.time() + args.interval
        while time.time() < deadline:
            token = login("lms", random.choice(STUDENTS), "partial").json()["access_token"]
            release(token, decl["declaration_id"])
            time.sleep(random.uniform(0.5, 1.5) * args.every)
        batch, wall = anchor_now()
        if batch:
            batches.append(batch | {"wall_seconds": wall, "confirmed_at": time.time()})
            print(f"  batch #{batch['batch_id']}: entries {batch['first_entry_id']}-{batch['last_entry_id']}, "
                  f"gas {batch['gas_used']}, mined in block {batch['block_number']} ({wall:.2f} s)")

    with db.tx() as conn:
        by_id = {e["entry_id"]: e for e in ledger.all_entries(conn)}
    print(f"\n| Batch | Entries | Gas used | Gas per entry | Delay min (s) | Delay median (s) | Delay max (s) | Tx confirmed in (s) |")
    print("|---|---|---|---|---|---|---|---|")
    all_delays = []
    for b in batches:
        ids = range(b["first_entry_id"], b["last_entry_id"] + 1)
        # Measured to when the anchor transaction was confirmed, on the same clock as the
        # entry times. (Hardhat's block timestamps drift ahead: each block must be at least
        # 1 s after the previous one, so quickly mined blocks push the chain clock forward.)
        delays = [b["confirmed_at"] - entry_time(by_id[i]["time"]) for i in ids]
        all_delays += delays
        n = len(delays)
        print(f"| {b['batch_id']} | {n} | {b['gas_used']} | {b['gas_used'] / n:.0f} | {min(delays):.1f} "
              f"| {statistics.median(delays):.1f} | {max(delays):.1f} | {b['wall_seconds']:.2f} |")

    gas = [b["gas_used"] for b in batches]
    print(f"\nGas per anchor: mean {statistics.mean(gas):.0f}, min {min(gas)}, max {max(gas)}; "
          "it does not grow with batch size, because only one 32-byte root is stored.")
    print(f"Entry -> anchor delay over {len(all_delays)} entries: median {statistics.median(all_delays):.1f} s, "
          f"p95 {pct(all_delays, 95):.1f} s, max {max(all_delays):.1f} s (interval {args.interval} s).")
    print("Expected with the default 300 s interval: median about 150 s, worst case about 300 s plus block time\n"
          "(~12 s on Sepolia). Cost on a public chain = gas x gas price, per batch, not per entry.")

    verify = httpx.get(f"{TRUSTTRAIL}/anchors/verify").json()
    print(f"\n/anchors/verify: ok={verify['ok']}, {verify['batches_checked']} batches, "
          f"anchored up to entry {verify['anchored_up_to']}")


if __name__ == "__main__":
    main()
