"""Recompute every anchored batch's Merkle root from the ledger and compare it
with the root stored on-chain.

    docker compose exec trusttrail python -m scripts.verify_anchors

Reads the batches from the contract (not from TrustTrail's cache) and the
entries from the database file, recomputing each entry hash from its content.
Exit code 1 if any batch fails.
"""
import sqlite3
import sys

from app import anchoring, db, ledger


def main():
    anchorer = anchoring.Anchorer()
    dep = anchorer.deployment()
    batches = anchorer.on_chain_batches()
    conn = sqlite3.connect(f"file:{db.DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    entries = ledger.all_entries(conn)

    print(f"Contract {dep['address']} on {dep['network']} (chain {dep['chainId']}): {len(batches)} batch(es)\n")
    print(f"{'batch':>5}  {'entries':>13}  {'on-chain root':18}  {'recomputed root':18}  result")
    results = anchoring.verify_ledger_against_chain(entries, batches)
    for r in results:
        span = f"{r['first_entry_id']}-{r['last_entry_id']}"
        computed = (r.get("computed_root") or "-" * 16)[:16]
        print(f"{r['batch_id']:>5}  {span:>13}  {r['root'][:16]}…   {computed}…   "
              f"{'OK' if r['ok'] else 'FAIL: ' + r['reason']}")
    last = batches[-1]["last_entry_id"] if batches else 0
    newest = entries[-1]["entry_id"] if entries else 0
    print(f"\nAnchored up to entry {last}; {max(0, newest - last)} newer entr(y/ies) waiting for the next batch "
          f"(covered by the hash chain only).")
    if newest < last:
        print(f"FAIL: the ledger ends at entry {newest} but entries up to {last} were anchored (truncated).")
    ok = all(r["ok"] for r in results) and newest >= last
    print("\nRESULT:", "every anchored batch matches the chain" if ok else "MISMATCH, ledger differs from what was anchored")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
