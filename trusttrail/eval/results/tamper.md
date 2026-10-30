# Tamper test (5 repetitions)

_Generated 2026-10-30 10:00 UTC by `tamper`; fake data, local machine._

| Attack | Hash chain | Student receipts | Blockchain anchor | Any check | As designed |
|---|---|---|---|---|---|
| A. change an entry, leave its hash | 5/5 | 5/5 | 5/5 | 5/5 | yes |
| B. change an entry, recompute its hash | 5/5 | 5/5 | 5/5 | 5/5 | yes |
| C. delete an entry | 5/5 | 5/5 | 5/5 | 5/5 | yes |
| D. change an entry, recompute every later hash | 0/5 | 5/5 | 5/5 | 5/5 | yes |
| E. cut off the tail of the ledger | 0/5 | 5/5 | 5/5 | 5/5 | yes |
| F. change an entry made after the last anchor, fix its hash | 0/5 | 5/5 | 0/5 | 5/5 | yes |

Every repetition matched the design.

Cells count repetitions in which the check detected the attack. Each repetition attacks a different, randomly chosen release on a fresh copy of the ledger. Receipts are the receipts TrustTrail issued (as students would hold them); the anchor is the Merkle roots on the local chain. F is the anchoring window: until the next batch, only receipts protect a new entry.
