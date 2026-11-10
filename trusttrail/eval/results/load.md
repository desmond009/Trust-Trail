# POST /release under concurrent load

_Generated 2026-11-10 12:13 UTC by `load`; fake data, local machine._

| Concurrent clients | Calls | Errors | Throughput (releases/s) | Median (ms) | p95 (ms) | p99 (ms) | Max (ms) |
|---|---|---|---|---|---|---|---|
| 1 | 299 | 0 | 212 | 2.0 | 2.6 | 3.2 | 4.1 |
| 10 | 295 | 0 | 468 | 18.0 | 27.9 | 34.5 | 41.8 |
| 25 | 295 | 0 | 534 | 41.1 | 66.4 | 82.1 | 93.3 |
| 50 | 295 | 0 | 489 | 90.3 | 139.2 | 184.6 | 209.3 |

LMS tokens obtained beforehand (not timed); every call is a real release with a ledger entry and receipt. Uvicorn with one worker process; all ledger writes pass one lock. Chain after the run: ok=True, 2649 entries.

Raw: `load_raw.csv`.
