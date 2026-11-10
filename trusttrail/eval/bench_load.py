"""(f) POST /release under concurrent load.

    docker compose exec trusttrail python -m eval.bench_load [--levels 1,10,25,50] [--requests 300]

For each concurrency level, the harness first obtains one LMS student token per
request (password grant, not timed), then sends all /release calls from that
many threads at once and records the latency of each call and the wall-clock
time of the whole level. Every successful call is a real release that writes
a ledger entry and a receipt. After the run it checks that the hash chain is
still intact.
"""
import argparse
import time
from concurrent.futures import ThreadPoolExecutor

import httpx

from app.demo_login import login
from app.demo_service import TRUSTTRAIL, DemoService
from eval.common import markdown_table, percentile, summarise, write_csv, write_markdown

STUDENTS = ["asha", "rohan", "meera", "kabir", "zoya"]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--levels", default="1,10,25,50")
    p.add_argument("--requests", type=int, default=300, help="calls per concurrency level")
    args = p.parse_args()
    levels = [int(x) for x in args.levels.split(",")]
    decl = DemoService("lms").declare()["declaration_id"]
    clients = {}

    def call(tok: str) -> tuple[float, int]:
        import threading
        c = clients.setdefault(threading.get_ident(), httpx.Client(timeout=60))
        t0 = time.perf_counter()
        r = c.post(f"{TRUSTTRAIL}/release", json={"declaration_id": decl}, headers={"Authorization": f"Bearer {tok}"})
        return (time.perf_counter() - t0) * 1000, r.status_code

    raw, rows = [], []
    for level in levels:
        tokens = [login("lms", STUDENTS[i % len(STUDENTS)], "partial").json()["access_token"]
                  for i in range(args.requests)]
        with ThreadPoolExecutor(max_workers=level) as pool:
            list(pool.map(call, tokens[: min(level, 5)]))   # warm the per-thread clients (these also release)
            tokens = tokens[min(level, 5):]
            t0 = time.perf_counter()
            results = list(pool.map(call, tokens))
            wall = time.perf_counter() - t0
        ok = [ms for ms, code in results if code == 200]
        errors = len(results) - len(ok)
        s = summarise(ok)
        rows.append([level, len(results), errors, f"{len(ok) / wall:.0f}", f"{s['median']:.1f}",
                     f"{s['p95']:.1f}", f"{percentile(ok, 99):.1f}", f"{s['max']:.1f}"])
        raw += [[level, round(ms, 2), code] for ms, code in results]
        print(f"  concurrency {level:3}: {len(ok)}/{len(results)} ok, {len(ok) / wall:.0f} releases/s, "
              f"median {s['median']:.1f} ms, p95 {s['p95']:.1f} ms")

    chain = httpx.get(f"{TRUSTTRAIL}/ledger/verify", timeout=120).json()
    write_csv("load_raw.csv", ["concurrency", "latency_ms", "status"], raw)
    table = markdown_table(["Concurrent clients", "Calls", "Errors", "Throughput (releases/s)", "Median (ms)",
                            "p95 (ms)", "p99 (ms)", "Max (ms)"], rows)
    note = (f"LMS tokens obtained beforehand (not timed); every call is a real release with a ledger entry and "
            f"receipt. Uvicorn with one worker process; all ledger writes pass one lock. "
            f"Chain after the run: ok={chain['ok']}, {chain['entries_checked']} entries.")
    print("\n" + table + "\n\n" + note)
    path = write_markdown("load.md", "POST /release under concurrent load", f"{table}\n\n{note}\n\nRaw: `load_raw.csv`.")
    print(f"Saved {path.relative_to(path.parents[2])}")


if __name__ == "__main__":
    main()
