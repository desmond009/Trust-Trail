# Ledger and Merkle costs by size

_Generated 2026-11-10 12:13 UTC by `scaling`; fake data, local machine._

| Ledger / batch size | Append (ms/entry) | Verify whole chain (s) | DB size (B/entry) | Merkle root (ms) | Proof length (hashes) | Proof size (hex chars, max) | Check one proof (µs, median) |
|---|---|---|---|---|---|---|---|
| 1,000 | 0.695 | 0.01 | 516 | 0.3 | 8–10 | 704 | 3.8 |
| 10,000 | 0.687 | 0.10 | 462 | 2.7 | 12–14 | 960 | 5.2 |
| 100,000 | 1.315 | 1.10 | 457 | 29.1 | 13–17 | 1152 | 7.0 |

Synthetic entries with realistic field sizes, one transaction per append, temporary SQLite file. Database size includes indexes; there are no receipts in these ledgers. In TrustTrail a batch holds at most 5,000 entries (`max_batch_entries`); the larger Merkle sizes show how proofs would grow.

Raw: `scaling_raw.csv`.
