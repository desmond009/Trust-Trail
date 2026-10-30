"""Phase 5 against the running stack and local chain: anchoring, proofs, verification."""
import sqlite3

import httpx
import pytest

from app import anchoring, db, ledger, merkle, settings
from app.demo_login import login, release
from app.demo_service import DemoService
from scripts import verify_receipt
from tests.conftest import ADMIN, TRUSTTRAIL

try:
    httpx.get(f"{settings.KC_INTERNAL_URL}/realms/{settings.REALM}", timeout=3).raise_for_status()
    anchoring.Anchorer().contract()
except Exception:
    pytest.skip("stack or chain not reachable; start and seed the stack", allow_module_level=True)

pytestmark = pytest.mark.integration


def anchor_now() -> dict | None:
    r = httpx.post(f"{TRUSTTRAIL}/anchors/run", headers=ADMIN, timeout=120)
    r.raise_for_status()
    return r.json()["batch"]


def new_release() -> dict:
    decl = DemoService("lms").declare()
    return release(login("lms", "asha", "partial").json()["access_token"], decl["declaration_id"]).json()


def read_entries() -> list[dict]:
    conn = sqlite3.connect(f"file:{db.DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return ledger.all_entries(conn)


def test_anchor_covers_the_ledger_up_to_now_and_is_contiguous():
    new_release()
    batch = anchor_now()
    entries = read_entries()
    assert batch["last_entry_id"] == entries[-1]["entry_id"]
    on_chain = anchoring.Anchorer().on_chain_batches()
    assert on_chain[0]["first_entry_id"] == 1
    assert all(b["first_entry_id"] == a["last_entry_id"] + 1 for a, b in zip(on_chain, on_chain[1:]))
    assert on_chain[-1]["root"] == batch["root"]


def test_nothing_new_means_no_transaction():
    anchor_now()
    assert anchor_now() is None


def test_new_entry_is_pending_until_the_next_batch():
    anchor_now()
    entry_id = new_release()["entry_id"]
    assert httpx.get(f"{TRUSTTRAIL}/ledger/proof/{entry_id}").json()["anchored"] is False
    anchor_now()
    assert httpx.get(f"{TRUSTTRAIL}/ledger/proof/{entry_id}").json()["anchored"] is True


def test_proof_leads_to_the_on_chain_root_without_revealing_entries():
    entry_id = new_release()["entry_id"]
    anchor_now()
    p = httpx.get(f"{TRUSTTRAIL}/ledger/proof/{entry_id}").json()
    entry = next(e for e in read_entries() if e["entry_id"] == entry_id)
    computed = merkle.root_from_proof(merkle.leaf_hash(ledger.compute_hash(entry)), p["proof"]).hex()
    assert computed == anchoring.Anchorer().on_chain_batch(p["batch"]["batch_id"])["root"]
    # Only hashes: no purpose, attributes or pseudonyms of any entry.
    assert set(p) == {"entry_id", "anchored", "entry_hash", "proof", "batch", "network", "chain_id", "contract"}
    assert all(set(step) == {"hash", "side"} for step in p["proof"])


def test_whole_ledger_verifies_against_the_chain():
    new_release()
    anchor_now()
    result = httpx.get(f"{TRUSTTRAIL}/anchors/verify").json()
    assert result["ok"] and result["failures"] == [] and result["unanchored_entries"] == 0


def test_standalone_receipt_check_passes_and_catches_edits():
    body = new_release()
    anchor_now()
    entry = next(e for e in read_entries() if e["entry_id"] == body["entry_id"])
    bundle = {"receipt_jws": body["receipt"], "ledger_entry": entry,
              "trusttrail_jwks": httpx.get(f"{TRUSTTRAIL}/.well-known/jwks.json").json(),
              "anchor_proof": httpx.get(f"{TRUSTTRAIL}/ledger/proof/{body['entry_id']}").json()}
    rpc = anchoring.Anchorer().rpc_url
    assert all(ok for _, ok, _ in verify_receipt.check(bundle, rpc))

    forged = {**bundle, "ledger_entry": {**entry, "purpose": "Advertising partners"}}
    results = dict((name, ok) for name, ok, _ in verify_receipt.check(forged, rpc))
    assert not results["ledger entry matches the receipt"] and not results["on-chain root matches"]


def test_anchoring_admin_endpoint_needs_the_token():
    assert httpx.post(f"{TRUSTTRAIL}/anchors/run").status_code == 401
