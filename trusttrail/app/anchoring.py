"""Anchoring ledger batches on a blockchain.

Every `interval_seconds`, the entries added since the last anchor become one
batch: TrustTrail builds a Merkle tree over their entry hashes and stores the
root (plus the entry-id range) in the TrustTrailAnchor contract. Records stay
off-chain; only fingerprints are anchored on-chain.

What an anchor proves: the anchored entries have not changed since the anchor
was mined. It does not prove they were true when written, and entries newer
than the last anchor are covered only by the hash chain.

The contract is the source of truth for what is anchored. The local `anchors`
table only caches transaction details (hash, gas, block) for proofs and stats.
"""
import json
import logging
import os
import threading
import time
from pathlib import Path

from web3 import Web3

from . import db, ledger, merkle, settings

log = logging.getLogger("trusttrail.anchoring")


class AnchorUnavailable(Exception):
    pass


def rules() -> dict:
    r = dict(settings.load("anchoring"))
    if os.environ.get("ANCHOR_INTERVAL_SECONDS"):
        r["interval_seconds"] = int(os.environ["ANCHOR_INTERVAL_SECONDS"])
    return r


class Anchorer:
    def __init__(self):
        self.rpc_url = os.environ.get("CHAIN_RPC_URL", "http://chain:8545")
        self.deployment_path = Path(os.environ.get("ANCHOR_DEPLOYMENT", "/deployments/localhost.json"))
        self.private_key = os.environ.get("ANCHOR_PRIVATE_KEY", "")
        self._lock = threading.Lock()   # one anchoring transaction at a time

    # --- connecting -----------------------------------------------------------------

    def deployment(self) -> dict:
        if not self.deployment_path.exists():
            raise AnchorUnavailable(f"no contract deployment at {self.deployment_path}")
        return json.loads(self.deployment_path.read_text())

    def contract(self):
        dep = self.deployment()
        w3 = Web3(Web3.HTTPProvider(self.rpc_url, request_kwargs={"timeout": 20}))
        if not w3.is_connected():
            raise AnchorUnavailable(f"chain not reachable at {self.rpc_url}")
        if w3.eth.chain_id != dep["chainId"]:
            raise AnchorUnavailable(f"RPC is chain {w3.eth.chain_id}, deployment is for chain {dep['chainId']}")
        return w3, w3.eth.contract(address=dep["address"], abi=dep["abi"]), dep

    def on_chain_batch(self, batch_id: int) -> dict:
        _, contract, _ = self.contract()
        root, first, last, at = contract.functions.getBatch(batch_id).call()
        return {"root": bytes(root).hex(), "first_entry_id": first, "last_entry_id": last, "anchored_at": at}

    def on_chain_batches(self) -> list[dict]:
        _, contract, _ = self.contract()
        return [self.on_chain_batch(i) | {"batch_id": i} for i in range(contract.functions.batchCount().call())]

    # --- anchoring --------------------------------------------------------------------

    def run_once(self) -> dict | None:
        """Anchor everything after the contract's last anchored entry. Returns the batch, or None."""
        with self._lock:
            w3, contract, dep = self.contract()
            account = w3.eth.account.from_key(self.private_key)
            if account.address != dep["owner"]:
                raise AnchorUnavailable(f"ANCHOR_PRIVATE_KEY is {account.address}, contract owner is {dep['owner']}")

            done = contract.functions.lastAnchoredEntryId().call()
            with db.tx() as conn:
                rows = conn.execute("SELECT entry_id, entry_hash FROM ledger WHERE entry_id > ? "
                                    "ORDER BY entry_id LIMIT ?", (done, rules()["max_batch_entries"])).fetchall()
            if not rows:
                return None
            first, last = rows[0]["entry_id"], rows[-1]["entry_id"]
            root = merkle.root([merkle.leaf_hash(r["entry_hash"]) for r in rows])

            tx = contract.functions.anchor(root, first, last).build_transaction({
                "from": account.address, "nonce": w3.eth.get_transaction_count(account.address),
                "chainId": dep["chainId"]})
            signed = account.sign_transaction(tx)
            tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=rules()["receipt_timeout_seconds"])
            if receipt.status != 1:
                raise AnchorUnavailable(f"anchor transaction 0x{bytes(tx_hash).hex()} reverted")
            event = contract.events.Anchored().process_receipt(receipt)[0]["args"]
            batch = {"deployment": dep["deployedAt"], "contract_address": dep["address"], "chain_id": dep["chainId"], "batch_id": event["batchId"],
                     "first_entry_id": first, "last_entry_id": last, "root": root.hex(),
                     "tx_hash": "0x" + bytes(receipt.transactionHash).hex(), "block_number": receipt.blockNumber,
                     "gas_used": receipt.gasUsed, "anchored_at": event["anchoredAt"]}
            with db.tx() as conn:
                conn.execute(f"INSERT INTO anchors VALUES ({', '.join('?' * len(batch))})", list(batch.values()))
            log.info("anchored entries %s-%s as batch %s (gas %s)", first, last, batch["batch_id"], receipt.gasUsed)
            return batch

    def run_forever(self):
        while True:
            try:
                self.run_once()
            except Exception:   # chain restarting, not deployed yet, ...
                log.exception("anchoring failed; will retry next interval")
            time.sleep(rules()["interval_seconds"])

    def start(self):
        threading.Thread(target=self.run_forever, name="anchoring", daemon=True).start()

    # --- proofs and verification --------------------------------------------------------

    def batch_for(self, conn, entry_id: int) -> dict | None:
        row = conn.execute("SELECT * FROM anchors WHERE deployment = ? AND ? BETWEEN first_entry_id "
                           "AND last_entry_id", (self.deployment()["deployedAt"], entry_id)).fetchone()
        return dict(row) if row else None

    def proof(self, entry_id: int) -> dict:
        """Merkle proof for one entry: its hash, sibling hashes, and where the root is on-chain."""
        with db.tx() as conn:
            batch = self.batch_for(conn, entry_id)
            if batch is None:
                last = conn.execute("SELECT MAX(last_entry_id) AS m FROM anchors WHERE deployment = ?",
                                    (self.deployment()["deployedAt"],)).fetchone()["m"]
                return {"entry_id": entry_id, "anchored": False, "last_anchored_entry_id": last or 0,
                        "next_anchor_within_seconds": rules()["interval_seconds"]}
            hashes = [r["entry_hash"] for r in conn.execute(
                "SELECT entry_hash FROM ledger WHERE entry_id BETWEEN ? AND ? ORDER BY entry_id",
                (batch["first_entry_id"], batch["last_entry_id"]))]
        index = entry_id - batch["first_entry_id"]
        dep = self.deployment()
        return {"entry_id": entry_id, "anchored": True, "entry_hash": hashes[index] if index < len(hashes) else None,
                "proof": merkle.proof([merkle.leaf_hash(h) for h in hashes], index),
                "batch": batch, "network": dep["network"], "chain_id": dep["chainId"], "contract": dep["address"]}

    def verify_entry(self, entry: dict) -> dict:
        """Recompute this entry's leaf from its content, walk the proof, compare with the chain."""
        try:
            p = self.proof(entry["entry_id"])
            if not p["anchored"]:
                return {"status": "pending", "detail": f"not anchored yet; next batch within "
                                                       f"{p['next_anchor_within_seconds']} s"}
            computed = merkle.root_from_proof(merkle.leaf_hash(ledger.compute_hash(entry)), p["proof"]).hex()
            chain = self.on_chain_batch(p["batch"]["batch_id"])
        except Exception as e:   # chain down or reset since the proof was cached
            return {"status": "unavailable", "detail": f"blockchain check unavailable: {e}"}
        ok = computed == chain["root"] and chain["first_entry_id"] <= entry["entry_id"] <= chain["last_entry_id"]
        return {"status": "anchored" if ok else "mismatch", "batch_id": p["batch"]["batch_id"],
                "tx_hash": p["batch"]["tx_hash"], "block_number": p["batch"]["block_number"],
                "network": p["network"], "on_chain_root": chain["root"], "computed_root": computed}


def verify_ledger_against_chain(entries: list[dict], batches: list[dict]) -> list[dict]:
    """For every on-chain batch, recompute its root from the ledger *content* and compare.

    Pure function (entries from any database copy, batches from the contract), so
    the tamper demo can run it against a modified copy.
    """
    by_id = {e["entry_id"]: e for e in entries}
    results = []
    for b in batches:
        ids = range(b["first_entry_id"], b["last_entry_id"] + 1)
        missing = [i for i in ids if i not in by_id]
        if missing:
            results.append({**b, "ok": False, "reason": f"{len(missing)} anchored entries missing (first #{missing[0]})"})
            continue
        computed = merkle.root([merkle.leaf_hash(ledger.compute_hash(by_id[i])) for i in ids]).hex()
        results.append({**b, "ok": computed == b["root"], "computed_root": computed,
                        "reason": None if computed == b["root"] else "root recomputed from the ledger differs"})
    return results
