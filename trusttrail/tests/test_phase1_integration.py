"""Against the running, seeded stack. Run inside the trusttrail container:
    docker compose exec trusttrail pytest
"""
import httpx
import pytest

from app import settings
from app.demo_login import PERSONAL_CLAIMS, claims, login, release
from app.keycloak import KeycloakAdmin
from app.pseudonyms import pairwise_sub, sector_identifier

try:
    httpx.get(f"{settings.KC_INTERNAL_URL}/realms/{settings.REALM}", timeout=3).raise_for_status()
except Exception:
    pytest.skip("Keycloak realm not reachable; start and seed the stack", allow_module_level=True)

pytestmark = pytest.mark.integration
SERVICES = settings.services()
STUDENTS = [s["username"] for s in settings.load("students")["students"]]
ORDER = settings.profiles()["order"]


def sub_for(service, student):
    r = login(service, student, SERVICES[service]["wants"])
    assert r.status_code == 200, r.text
    return claims(r.json()["id_token"])["sub"]


@pytest.mark.parametrize("student", STUDENTS)
def test_each_service_sees_a_different_id(student):
    subs = {sid: sub_for(sid, student) for sid in SERVICES}
    assert len(set(subs.values())) == len(SERVICES), subs


def test_pseudonym_is_stable_across_logins():
    assert sub_for("library", "asha") == sub_for("library", "asha")


def test_trusttrail_recomputes_keycloak_pseudonyms():
    kc = KeycloakAdmin()
    users = {u["username"]: u["id"] for u in kc.users()}
    for sid in SERVICES:
        client = kc.client(sid)
        salt = kc.pairwise_mapper(client["id"])["config"]["pairwiseSubAlgorithmSalt"]
        for student in STUDENTS:
            assert pairwise_sub(sector_identifier(client), users[student], salt) == sub_for(sid, student)


@pytest.mark.parametrize("service", list(SERVICES))
def test_keycloak_tokens_carry_no_personal_claims(service):
    tok = login(service, "asha", SERVICES[service]["wants"]).json()
    for t in (tok["id_token"], tok["access_token"]):
        assert not PERSONAL_CLAIMS & claims(t).keys()


@pytest.mark.parametrize("service", list(SERVICES))
def test_nothing_links_sessions_across_services(service):
    # sid/session_state are the SSO session ID, identical for every service the
    # student visits in one session; the strip-sid mapper must remove them.
    body = login(service, "asha", SERVICES[service]["wants"]).json()
    assert "session_state" not in body and "refresh_token" not in body
    for t in (body["id_token"], body["access_token"]):
        assert not {"sid", "session_state", "auth_time"} & claims(t).keys()


@pytest.mark.parametrize("service", list(SERVICES))
def test_release_matches_profile(service):
    wants = SERVICES[service]["wants"]
    tok = login(service, "asha", wants).json()
    body = release(tok["access_token"]).json()
    spec = settings.profiles()["profiles"][wants]
    assert body["profile"] == wants
    assert set(body["released"]) == set(spec["attributes"]) | ({"sub"} if spec["sub"] else set())
    if spec["sub"]:
        assert body["released"]["sub"] == claims(tok["id_token"])["sub"]


@pytest.mark.parametrize("service", list(SERVICES))
def test_keycloak_enforces_tier_cap(service):
    cap = settings.tier_cap(SERVICES[service]["tier"])
    for profile in ORDER:
        r = login(service, "asha", profile)
        if ORDER.index(profile) <= ORDER.index(cap):
            assert r.status_code == 200, (profile, r.text)
        else:
            assert r.status_code == 400 and r.json()["error"] == "invalid_scope", profile


def test_release_rejects_forged_token():
    tok = login("library", "asha", "pseudonym").json()["access_token"]
    head, body, sig = tok.split(".")
    assert release(f"{head}.{body}.{sig[:-4]}AAAA").status_code == 401
