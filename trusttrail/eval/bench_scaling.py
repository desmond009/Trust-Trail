"""(g) How ledger and Merkle costs grow with size.

    docker compose exec trusttrail python -m eval.bench_scaling [--sizes 1000,10000,100000]

Builds synthetic ledgers of each size in a temporary SQLite file with the real
ledger code (app.ledger.append, one transaction per entry as in /release), then
measures: append time per entry, time to verify the whole chain, database size
per entry, Merkle root time for a batch of that many entries, proof length, and
time to check one proof. Invented content; nothing touches the live ledger.
"""
import argparse
import os
import random
import sqlite3
import tempfile
import time
from pathlib import Path

from app import db, ledger, merkle
from eval.common import markdown_table, summarise, write_csv, write_markdown

SERVICES = ["library", "lms", "exam"]
PROFILE = {"library": ["affiliation", "sub"], "lms": ["affiliation", "department", "program", "sub", "year"],
           "exam": ["affiliation", "department", "email", "name", "program", "roll_no", "sub", "year"]}


def build(path: Path, n: int, rnd: random.Random) -> float:
    conn = db.init(sqlite3.connect(path))
    t0 = time.perf_counter()
    for i in range(n):
        svc = SERVICES[i % 3]
        with conn:
            ledger.append(conn, {"kind": "release", "service_id": svc,
                                 "student_pseudonym": f"{rnd.getrandbits(128):032x}", "profile": "partial",
                                 "attributes_released": PROFILE[svc], "purpose": "synthetic benchmark entry",
                                 "retention_until": "2027-01-01", "declaration_id": f"{rnd.getrandbits(64):016x}",
                                 "service_signature": f"{rnd.getrandbits(256):064x}"})
    elapsed = time.perf_counter() - t0
    conn.close()
    return elapsed


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--sizes", default="1000,10000,100000")
    p.add_argument("--proofs", type=int, default=200, help="random proofs checked per size")
    args = p.parse_args()
    rnd = random.Random(1)
    rows, raw = [], []
    tmp = Path(tempfile.mkdtemp(prefix="tt-scale-"))
    for n in [int(x) for x in args.sizes.split(",")]:
        path = tmp / f"ledger_{n}.db"
        append_s = build(path, n, rnd)
        conn = db.init(sqlite3.connect(path))
        t0 = time.perf_counter()
        entries = [ledger._row(r) for r in conn.execute("SELECT * FROM ledger ORDER BY entry_id")]
        check = ledger.verify(entries)
        verify_s = time.perf_counter() - t0
        assert check.ok and check.entries_checked == n
        leaves = [merkle.leaf_hash(e["entry_hash"]) for e in entries]
        t0 = time.perf_counter()
        root = merkle.root(leaves)
        root_ms = (time.perf_counter() - t0) * 1000
        lens, check_us = [], []
        for _ in range(args.proofs):
            i = rnd.randrange(n)
            pr = merkle.proof(leaves, i)
            t0 = time.perf_counter()
            ok = merkle.root_from_proof(leaves[i], pr) == root
            check_us.append((time.perf_counter() - t0) * 1e6)
            assert ok
            lens.append(len(pr))
        conn.close()
        size_b = os.path.getsize(path)
        cu = summarise(check_us)
        rows.append([f"{n:,}", f"{append_s / n * 1000:.3f}", f"{verify_s:.2f}", f"{size_b / n:.0f}",
                     f"{root_ms:.1f}", f"{min(lens)}–{max(lens)}", f"{max(lens) * 32 * 2 + 64}", f"{cu['median']:.1f}"])
        raw.append([n, round(append_s, 3), round(verify_s, 3), size_b, round(root_ms, 2), min(lens), max(lens),
                    round(cu["median"], 2)])
        print(f"  {n:>7} entries: append {append_s / n * 1000:.3f} ms/entry, verify {verify_s:.2f} s, "
              f"{size_b / n:.0f} B/entry, root {root_ms:.1f} ms, proof {min(lens)}-{max(lens)} hashes")
        path.unlink()
    write_csv("scaling_raw.csv", ["entries", "append_s", "verify_s", "db_bytes", "root_ms", "proof_min", "proof_max",
                                  "proof_check_us_median"], raw)
    table = markdown_table(["Ledger / batch size", "Append (ms/entry)", "Verify whole chain (s)", "DB size (B/entry)",
                            "Merkle root (ms)", "Proof length (hashes)", "Proof size (hex chars, max)",
                            "Check one proof (µs, median)"], rows)
    note = ("Synthetic entries with realistic field sizes, one transaction per append, temporary SQLite file. "
            "Database size includes indexes; there are no receipts in these ledgers. In TrustTrail a batch holds at "
            "most 5,000 entries (`max_batch_entries`); the larger Merkle sizes show how proofs would grow.")
    print("\n" + table + "\n\n" + note)
    path = write_markdown("scaling.md", "Ledger and Merkle costs by size", f"{table}\n\n{note}\n\nRaw: `scaling_raw.csv`.")
    print(f"Saved {path.relative_to(path.parents[2])}")


if __name__ == "__main__":
    main()
