# Anchoring measurement, 2026-11-10 (local Hardhat chain)

Command: `docker compose exec -T trusttrail python -m scripts.demo_phase5 --batches 3 --interval 12`

| Batch | Entries | Gas used | Gas per entry | Delay min (s) | Delay median (s) | Delay max (s) | Tx confirmed in (s) |
|---|---|---|---|---|---|---|---|
| 11 | 6 | 77268 | 12878 | 3.0 | 6.9 | 12.3 | 0.05 |
| 12 | 6 | 77268 | 12878 | 2.2 | 7.0 | 12.8 | 0.03 |
| 13 | 7 | 77268 | 11038 | 1.3 | 7.9 | 12.8 | 0.05 |

Entry -> anchor delay over 19 entries: median 7.6 s, p95 12.8 s, max 12.8 s (interval 12 s).
/anchors/verify: ok=True, 14 batches, anchored up to entry 936.
Contract tests (npx hardhat test, same day): first anchor 91,659 gas; later anchor of 100,000 entries 77,268 gas.
