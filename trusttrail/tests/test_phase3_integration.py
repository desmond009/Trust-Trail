"""Phase 3 against the running, seeded stack: every release lands in the ledger."""
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import httpx
import jwt
import pytest

from app import db, ledger, settings
from app.demo_login import claims, login, release
from app.demo_service import TRUSTTRAIL, DemoService

try:
    httpx.get(f"{settings.KC_INTERNAL_URL}/realms/{settings.REALM}", timeout=3).raise_for_status()
except Exception:
    pytest.skip("Keycloak realm not reachable; start and seed the stack", allow_module_level=True)

pytestmark = pytest.mark.integration


def read_ledger() -> list[dict]:
    # Read-only view of the live database file (the tests run inside the trusttrail container).
    conn = sqlite3.connect(f"file:{db.DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return ledger.all_entries(conn)


@pytest.fixture(scope="module")
def lms_decl():
    return DemoService("lms").declare()


def test_release_writes_one_matching_entry(lms_decl):
    before = len(read_ledger())
    token = login("lms", "asha", "partial").json()["access_token"]
    body = release(token, lms_decl["declaration_id"]).json()
    entries = read_ledger()
    assert len(entries) == before + 1
    e = entries[-1]
    assert e["entry_id"] == body["entry_id"]
    assert (e["kind"], e["service_id"], e["profile"]) == ("release", "lms", "partial")
    assert e["student_pseudonym"] == claims(token)["sub"]          # pseudonym, not the Keycloak user ID
    assert e["attributes_released"] == sorted(body["released"])
    assert e["purpose"] == lms_decl["purpose"] and e["retention_until"] == lms_decl["retention_until"]
    assert e["declaration_id"] == lms_decl["declaration_id"]
    assert e["service_signature"] == lms_decl["jws"].rsplit(".", 1)[1]
    assert e["entry_hash"] == ledger.compute_hash(e)


def test_receipt_points_at_the_entry(lms_decl):
    body = release(login("lms", "asha", "partial").json()["access_token"], lms_decl["declaration_id"]).json()
    payload = jwt.decode(body["receipt"], options={"verify_signature": False})
    entry = next(e for e in read_ledger() if e["entry_id"] == body["entry_id"])
    assert payload["entry_id"] == entry["entry_id"] and payload["entry_hash"] == entry["entry_hash"]


def test_refusals_never_write_a_release(lms_decl):
    token = login("lms", "asha", "partial").json()["access_token"]
    before = len(read_ledger())
    assert release(token).status_code == 403                 # no declaration: not a rule break
    assert len(read_ledger()) == before

    r = release(token, lms_decl["declaration_id"], attributes=["roll_no"])   # rule 1 (Phase 4)
    assert r.status_code == 403
    lms_new = [e for e in read_ledger()[before:] if e["service_id"] == "lms"]
    assert [e["kind"] for e in lms_new] == ["violation"] and lms_new[0]["attributes_released"] == []


def test_public_verify_matches_ledger():
    result = httpx.get(f"{TRUSTTRAIL}/ledger/verify").json()
    entries = read_ledger()
    assert result["ok"] and result["entries_checked"] == len(entries)
    assert result["head_hash"] == entries[-1]["entry_hash"]


def test_concurrent_releases_keep_the_chain_intact(lms_decl):
    tokens = [login("lms", s, "partial").json()["access_token"]
              for s in ["asha", "rohan", "meera", "kabir", "zoya"] * 2]
    with ThreadPoolExecutor(max_workers=10) as pool:
        codes = list(pool.map(lambda t: release(t, lms_decl["declaration_id"]).status_code, tokens))
    assert codes == [200] * 10
    assert ledger.verify(read_ledger()).ok


def test_dashboard_api_requires_login():
    assert httpx.get(f"{TRUSTTRAIL}/dashboard/api/releases").status_code == 401
    assert httpx.get(f"{TRUSTTRAIL}/dashboard/receipts/1").status_code == 401
