"""(e) Where the time inside POST /release goes.

    docker compose exec trusttrail python -m eval.bench_release_steps [--runs 200]

Runs the same steps as app.main.release, in the same order and with the same
functions, inside this process, and times each step separately. It works on a
COPY of the data directory, so the live ledger is not touched. Keycloak calls
(JWKS, user record) are real. Tokens are obtained first and are not timed.

The HTTP /release median from bench_latency minus the in-process total is the
cost of HTTP, FastAPI and request parsing.
"""
import argparse
import os
import shutil
import tempfile
import time
from pathlib import Path

LIVE_DATA = Path(os.environ.get("DATA_DIR", "/data"))
COPY = Path(tempfile.mkdtemp(prefix="tt-steps-"))
os.environ["DATA_DIR"] = str(COPY)          # before any app module reads settings

from app.demo_login import login            # noqa: E402
from app.demo_service import DemoService    # noqa: E402
from eval.common import markdown_table, summarise, write_csv, write_markdown  # noqa: E402

STUDENTS = ["asha", "rohan", "meera", "kabir", "zoya"]
STEPS = ["verify token", "find declaration", "apply trust cap", "rule checks (declaration, retention, attributes)",
         "map pseudonym to student", "fetch attributes from Keycloak", "build release",
         "append ledger entry", "sign receipt (ES256)", "store receipt and commit"]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--runs", type=int, default=200)
    p.add_argument("--warmup", type=int, default=10)
    args = p.parse_args()

    decl_id = DemoService("lms").declare()["declaration_id"]     # stored in the live DB first
    for f in LIVE_DATA.iterdir():                                # then copy everything, declaration included
        if f.is_file():
            shutil.copy2(f, COPY / f.name)

    from app import db, declarations, ledger, receipts          # noqa: E402  (now bound to the copy)
    from app import release as rel                              # noqa: E402
    from app.main import kc, pmap, trust                        # noqa: E402
    from app.tokens import verify_access_token                  # noqa: E402

    def one(token: str) -> list[float]:
        t = [time.perf_counter()]
        claims = verify_access_token(token); t.append(time.perf_counter())
        service = claims["azp"]
        decl = declarations.get(decl_id); t.append(time.perf_counter())
        assert decl and decl.client_id == service
        granted = rel.granted_profile(claims.get("scope", ""))
        profile = rel.lower_profile(granted, trust.current_cap(service)); t.append(time.perf_counter())
        declarations.check_usable(decl)
        names = rel.choose_attributes(None, decl.attributes, rel.profile_attributes(profile),
                                      rel.profile_attributes(trust.entitled_cap(service))); t.append(time.perf_counter())
        user_id = pmap.resolve(service, claims["sub"]); t.append(time.perf_counter())
        user = kc.user(user_id); t.append(time.perf_counter())
        rel.build_release(names, rel.student_attributes(user), claims["sub"]); t.append(time.perf_counter())
        with db.tx() as conn:
            entry = ledger.append(conn, {
                "kind": "release", "service_id": service, "student_pseudonym": claims["sub"],
                "profile": profile, "attributes_released": names, "purpose": decl.purpose,
                "retention_until": decl.retention_until, "declaration_id": decl.declaration_id,
                "service_signature": decl.jws.rsplit(".", 1)[1]}); t.append(time.perf_counter())
            receipt = receipts.sign({
                "service": service, "profile": profile, "attributes": names,
                **({"subject": claims["sub"]} if "sub" in names else {}),
                "purpose": decl.purpose, "retention_until": decl.retention_until,
                "declaration_id": decl.declaration_id, "declaration_sha256": decl.jws_sha256,
                "entry_id": entry["entry_id"], "entry_hash": entry["entry_hash"],
                "released_at": entry["time"]}); t.append(time.perf_counter())
            ledger.store_receipt(conn, entry["entry_id"], receipt)
        t.append(time.perf_counter())
        return [(b - a) * 1000 for a, b in zip(t, t[1:])]

    tokens = lambda n: [login("lms", STUDENTS[i % len(STUDENTS)], "partial").json()["access_token"] for i in range(n)]
    for tok in tokens(args.warmup):
        one(tok)
    raw = [one(tok) for tok in tokens(args.runs)]

    write_csv("release_steps_raw.csv", ["run"] + STEPS, [[i + 1] + [round(x, 4) for x in r] for i, r in enumerate(raw)])
    totals = summarise([sum(r) for r in raw])
    rows = []
    for j, step in enumerate(STEPS):
        s = summarise([r[j] for r in raw])
        rows.append([step, f"{s['median']:.3f}", f"{s['p95']:.3f}", f"{s['mean']:.3f}",
                     f"{100 * s['mean'] / totals['mean']:.0f}%"])
    rows.append(["**total (in process)**", f"{totals['median']:.3f}", f"{totals['p95']:.3f}", f"{totals['mean']:.3f}", "100%"])
    table = markdown_table(["Step", "Median (ms)", "p95 (ms)", "Mean (ms)", "Share of mean"], rows)
    note = (f"{args.runs} runs after {args.warmup} warm-up runs, LMS token (partial profile), on a copy of the data "
            "directory. Keycloak calls are real HTTP requests to the Keycloak container.")
    print("\n" + table + "\n\n" + note)
    path = write_markdown("release_steps.md", "Time per step inside POST /release", f"{table}\n\n{note}\n\nRaw: `release_steps_raw.csv`.")
    print(f"Saved {path.relative_to(path.parents[2])}")
    shutil.rmtree(COPY, ignore_errors=True)


if __name__ == "__main__":
    main()
