"""Phase 4 against the running, seeded stack: the loop
signed promise -> ledger record -> violation detected -> trust lowered -> less data released.
"""
import sqlite3
import time

import httpx
import pytest

from app import db, ledger, settings
from app.demo_login import login, release
from app.demo_service import DemoService
from app.keycloak import KeycloakAdmin
from scripts.bad_services import BAD
from tests.conftest import ADMIN, TRUSTTRAIL, admin_sync

try:
    httpx.get(f"{settings.KC_INTERNAL_URL}/realms/{settings.REALM}", timeout=3).raise_for_status()
except Exception:
    pytest.skip("Keycloak realm not reachable; start and seed the stack", allow_module_level=True)

pytestmark = pytest.mark.integration
EXPECTED_RULE = {"overasker": "undeclared_attribute", "retainer": "after_retention", "tiercap": "above_tier_cap"}
PROFILES = settings.profiles()["order"]
TIERS = settings.trust_rules()["tier_order"]
STEP = settings.trust_rules()["score"]["violation_step"]


def state(service_id: str) -> dict:
    return httpx.get(f"{TRUSTTRAIL}/trust").json()[service_id]


def wait_for_violations(service_id: str, more_than: int, timeout: float = 15) -> dict:
    # Rule 3 arrives via Keycloak's event log, so give the sync a moment.
    deadline = time.time() + timeout
    while time.time() < deadline:
        s = admin_sync()[service_id]
        if s["violations"] > more_than:
            return s
        time.sleep(0.5)
    raise AssertionError(f"no new violation for {service_id}")


def violations(service_id: str) -> list[dict]:
    conn = sqlite3.connect(f"file:{db.DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return [e for e in ledger.all_entries(conn) if e["kind"] == "violation" and e["service_id"] == service_id]


@pytest.mark.parametrize("service_id", list(EXPECTED_RULE))
def test_bad_service_is_caught_scored_down_and_capped(service_id):
    before = state(service_id)
    seen = len(violations(service_id))

    BAD[service_id](service_id).misbehave("asha")
    after = wait_for_violations(service_id, before["violations"])

    # 1. caught: a violation entry with the right rule, nothing released
    new = violations(service_id)[seen:]
    assert [v["rule"] for v in new] == [EXPECTED_RULE[service_id]]
    assert new[0]["attributes_released"] == []
    # 2. score dropped by one step
    assert after["score"] == before["score"] - STEP
    # 3. tier and maximum profile dropped exactly one step
    assert TIERS.index(after["tier"]) == TIERS.index(before["tier"]) - 1
    assert PROFILES.index(after["cap"]) == PROFILES.index(before["cap"]) - 1
    # 4. enforced by Keycloak itself: the old cap's scope is gone and logins asking for it fail
    kc = KeycloakAdmin()
    assigned = kc.optional_scopes(kc.client(service_id)["id"])
    assert f"profile-{before['cap']}" not in assigned and f"profile-{after['cap']}" in assigned
    r = login(service_id, "asha", before["cap"])
    assert r.status_code == 400 and r.json()["error"] == "invalid_scope"


def test_repeated_violations_drop_one_tier_at_a_time_down_to_anonymous():
    bad = BAD["overasker"]("overasker")
    tiers = [state("overasker")["tier"]]
    for _ in range(3):
        before = state("overasker")["violations"]
        bad.misbehave("asha")
        tiers.append(wait_for_violations("overasker", before)["tier"])
    assert tiers == ["semi_trusted", "untrusted", "blocked", "blocked"]
    assert state("overasker")["cap"] == "anonymous"

    # Still usable at the bottom tier, but it learns nothing beyond "a student".
    decl = DemoService("overasker").declare()
    body = release(login("overasker", "asha", "anonymous").json()["access_token"], decl["declaration_id"]).json()
    assert body["profile"] == "anonymous" and body["released"] == {"affiliation": "student"}


def test_demoted_service_is_not_punished_again_for_its_old_entitlement():
    BAD["overasker"]("overasker").misbehave("asha")
    demoted = wait_for_violations("overasker", 0)
    assert demoted["cap"] == "pseudonym"
    # It still asks Keycloak for `partial` (allowed by its agreement, not by its new cap).
    assert login("overasker", "asha", "partial").status_code == 400
    time.sleep(1)
    assert admin_sync()["overasker"]["violations"] == demoted["violations"]


def test_token_issued_before_demotion_gets_only_the_new_cap():
    decl = DemoService("lms").declare()
    old_token = login("lms", "asha", "partial").json()["access_token"]   # issued while semi-trusted
    r = release(old_token, decl["declaration_id"], attributes=["sub", "roll_no"])   # rule 1 -> demoted
    assert r.json()["violation"]["rule"] == "undeclared_attribute"
    body = release(old_token, decl["declaration_id"]).json()
    assert body["profile"] == "pseudonym" and set(body["released"]) == {"sub", "affiliation"}


def test_honest_services_collect_no_violations():
    for service_id in ("library", "lms", "exam"):
        decl = DemoService(service_id).declare()
        for student in ("asha", "rohan", "meera", "kabir", "zoya"):
            token = login(service_id, student, settings.services()[service_id]["wants"]).json()["access_token"]
            assert release(token, decl["declaration_id"]).status_code == 200
    states = admin_sync()
    for service_id in ("library", "lms", "exam"):
        assert states[service_id]["violations"] == 0 and states[service_id]["tier"] == states[service_id]["base_tier"]


def test_reset_restores_the_base_tier_and_is_recorded():
    BAD["tiercap"]("tiercap").misbehave("asha")
    assert wait_for_violations("tiercap", 0)["tier"] == "blocked"
    r = httpx.post(f"{TRUSTTRAIL}/trust/tiercap/reset", json={"reason": "reviewed by privacy officer"}, headers=ADMIN)
    assert r.status_code == 200 and r.json()["state"]["tier"] == "untrusted"
    assert len(violations("tiercap")) >= 1          # the violation stays in the append-only ledger
    assert login("tiercap", "asha", "pseudonym").status_code == 200


def test_admin_endpoints_need_the_admin_token():
    assert httpx.post(f"{TRUSTTRAIL}/trust/sync").status_code == 401
    assert httpx.post(f"{TRUSTTRAIL}/trust/lms/reset", json={"reason": "x"},
                      headers={"Authorization": "Bearer wrong"}).status_code == 401
