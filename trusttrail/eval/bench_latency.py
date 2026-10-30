"""(a) Login latency with and without the privacy layer.

    docker compose exec trusttrail python -m eval.bench_latency [--runs 200] [--warmup 10]

Baseline (no privacy layer): a plain Keycloak client (`bench-baseline`) logs a
student in and receives every attribute in its ID token, in one token request.

TrustTrail: the Learning System logs the student in (pairwise ID, sid stripped,
profile scope; no attributes in the token), then calls POST /release. That call
verifies the token, applies the trust cap, checks the signed declaration, maps
the pseudonym, fetches the attributes, and writes a ledger entry and a signed
receipt. Anchoring runs in the background and is not on the login path.

Both use the password grant so no browser is needed. A real browser login adds
the same redirects to both, so the *difference* is the privacy layer's cost.
Runs alternate in random order so drift (caches, GC) affects both equally.
Note: every TrustTrail run is a real release and adds a ledger entry.
"""
import argparse
import os
import random
import time

import httpx

from app import settings
from app.demo_service import TRUSTTRAIL, DemoService
from eval.common import markdown_table, summarise, write_csv, write_markdown

STUDENTS = ["asha", "rohan", "meera", "kabir", "zoya"]
http = httpx.Client(timeout=30)


def token(client_id: str, secret: str, student: str, scope: str) -> dict:
    r = http.post(f"{settings.OIDC_BASE}/token", data={
        "grant_type": "password", "client_id": client_id, "client_secret": secret, "scope": scope,
        "username": student, "password": os.environ["STUDENT_DEMO_PASSWORD"]})
    r.raise_for_status()
    return r.json()


def baseline_run(student: str) -> dict:
    t0 = time.perf_counter()
    token("bench-baseline", os.environ["BENCH_BASELINE_CLIENT_SECRET"], student, "openid")
    return {"total_ms": (time.perf_counter() - t0) * 1000}


def trusttrail_run(student: str, declaration_id: str) -> dict:
    t0 = time.perf_counter()
    tok = token("lms", os.environ["LMS_CLIENT_SECRET"], student, "openid profile-partial")
    t1 = time.perf_counter()
    r = http.post(f"{TRUSTTRAIL}/release", json={"declaration_id": declaration_id},
                  headers={"Authorization": f"Bearer {tok['access_token']}"})
    r.raise_for_status()
    t2 = time.perf_counter()
    return {"total_ms": (t2 - t0) * 1000, "token_ms": (t1 - t0) * 1000, "release_ms": (t2 - t1) * 1000}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--runs", type=int, default=200, help="measured runs per variant")
    p.add_argument("--warmup", type=int, default=10)
    args = p.parse_args()

    decl = DemoService("lms").declare()["declaration_id"]
    for _ in range(args.warmup):
        baseline_run("asha")
        trusttrail_run("asha", decl)

    plan = ["baseline"] * args.runs + ["trusttrail"] * args.runs
    random.shuffle(plan)
    raw = []
    for i, variant in enumerate(plan):
        student = STUDENTS[i % len(STUDENTS)]
        m = baseline_run(student) if variant == "baseline" else trusttrail_run(student, decl)
        raw.append([variant, student, round(m["total_ms"], 2),
                    round(m.get("token_ms", m["total_ms"]), 2), round(m.get("release_ms", 0.0), 2)])
        if (i + 1) % 100 == 0:
            print(f"  {i + 1}/{len(plan)} runs")

    write_csv("latency_raw.csv", ["variant", "student", "total_ms", "token_ms", "release_ms"], raw)
    base = summarise([r[2] for r in raw if r[0] == "baseline"])
    tt = summarise([r[2] for r in raw if r[0] == "trusttrail"])
    tt_token = summarise([r[3] for r in raw if r[0] == "trusttrail"])
    tt_release = summarise([r[4] for r in raw if r[0] == "trusttrail"])

    def row(name, s):
        return [name, s["n"], f"{s['median']:.1f}", f"{s['p95']:.1f}", f"{s['mean']:.1f}", f"{s['min']:.1f}", f"{s['max']:.1f}"]

    header = ["Variant", "Runs", "Median (ms)", "p95 (ms)", "Mean (ms)", "Min (ms)", "Max (ms)"]
    table = markdown_table(header, [
        row("Plain OIDC login (no privacy layer)", base),
        row("TrustTrail login + release (total)", tt),
        row("  of which: Keycloak token", tt_token),
        row("  of which: TrustTrail /release", tt_release)])
    overhead = (f"Overhead of the privacy layer: median **{tt['median'] - base['median']:+.1f} ms** "
                f"({(tt['median'] / base['median'] - 1) * 100:+.0f}%), p95 **{tt['p95'] - base['p95']:+.1f} ms**.")
    notes = ("Password grant on one laptop, all containers local; a browser login adds the same redirects to "
             "both variants. TrustTrail's token request is itself slightly different (pairwise ID, sid "
             "stripped, no claim mappers). Anchoring is asynchronous and not included.")
    print("\n" + table + "\n\n" + overhead + "\n")
    path = write_markdown("latency.md", "Login latency with and without the privacy layer",
                          f"{table}\n\n{overhead}\n\n{notes}\n\nRaw runs: `latency_raw.csv`.")
    print(f"Saved {path.relative_to(path.parents[2])} and latency_raw.csv")


if __name__ == "__main__":
    main()
