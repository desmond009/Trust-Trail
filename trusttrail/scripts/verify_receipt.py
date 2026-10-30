"""Check a downloaded TrustTrail receipt using only the file and the blockchain.

    docker compose exec -T trusttrail python -m scripts.verify_receipt - < trusttrail-receipt-12.json
    python -m scripts.verify_receipt receipt.json --rpc https://<sepolia rpc>

Does not call TrustTrail's API or read its database, so a student (or an
auditor) can run it without trusting TrustTrail's server. It checks:
  1. the receipt is signed by the key in the file (compare that key with
     TrustTrail's published /.well-known/jwks.json once, out of band);
  2. the ledger entry in the file hashes to the entry_hash in the receipt;
  3. the Merkle proof leads from that hash to a root;
  4. that root is the one stored on-chain for the batch.
"""
import argparse
import json
import os
import sys

import jwt
from web3 import Web3

from app import ledger, merkle

# Just the view function we need, so this script doesn't depend on deployment files.
GET_BATCH_ABI = [{"type": "function", "name": "getBatch", "stateMutability": "view",
                  "inputs": [{"name": "batchId", "type": "uint256"}],
                  "outputs": [{"name": "", "type": "tuple", "components": [
                      {"name": "root", "type": "bytes32"}, {"name": "firstEntryId", "type": "uint64"},
                      {"name": "lastEntryId", "type": "uint64"}, {"name": "anchoredAt", "type": "uint64"}]}]}]


def check(bundle: dict, rpc_url: str) -> list[tuple[str, bool, str]]:
    results = []
    entry = bundle["ledger_entry"]

    try:
        jwks = jwt.PyJWKSet.from_dict(bundle["trusttrail_jwks"])
        kid = jwt.get_unverified_header(bundle["receipt_jws"])["kid"]
        receipt = jwt.decode(bundle["receipt_jws"], jwks[kid].key, algorithms=["ES256"])
        results.append(("receipt signature valid", True, f"key {kid[:12]}…"))
    except Exception as e:
        return results + [("receipt signature valid", False, str(e))]

    content_hash = ledger.compute_hash(entry)
    results.append(("ledger entry matches the receipt", content_hash == receipt["entry_hash"] == entry["entry_hash"],
                    f"entry #{entry['entry_id']}, hash {content_hash[:16]}…"))

    p = bundle.get("anchor_proof") or {}
    if not p.get("anchored"):
        results.append(("anchored on-chain", False, "not anchored when downloaded; download again after the next batch"))
        return results
    root = merkle.root_from_proof(merkle.leaf_hash(content_hash), p["proof"]).hex()
    results.append(("Merkle proof computed", True, f"root {root[:16]}… from {len(p['proof'])} sibling hashes"))

    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if w3.eth.chain_id != p["chain_id"]:
        return results + [("on-chain root matches", False, f"RPC is chain {w3.eth.chain_id}, proof is for {p['chain_id']}")]
    contract = w3.eth.contract(address=p["contract"], abi=GET_BATCH_ABI)
    on_chain_root, first, last, _ = contract.functions.getBatch(p["batch"]["batch_id"]).call()
    ok = bytes(on_chain_root).hex() == root and first <= entry["entry_id"] <= last
    results.append(("on-chain root matches", ok,
                    f"batch #{p['batch']['batch_id']} at {p['contract'][:10]}… on chain {p['chain_id']}"))
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("bundle", help="receipt file downloaded from the dashboard, or - for stdin")
    parser.add_argument("--rpc", default=os.environ.get("CHAIN_RPC_URL", "http://127.0.0.1:8545"))
    args = parser.parse_args()
    bundle = json.load(sys.stdin if args.bundle == "-" else open(args.bundle))
    results = check(bundle, args.rpc)
    for name, ok, detail in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name:34} {detail}")
    sys.exit(0 if all(ok for _, ok, _ in results) else 1)


if __name__ == "__main__":
    main()
