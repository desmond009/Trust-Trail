"""Phase 2 against the running, seeded stack: keys, declarations, refusals, receipts."""
import json
import time

import httpx
import jwt
import pytest

from app import settings
from app.demo_login import login, release
from app.demo_service import TRUSTTRAIL, DemoService

try:
    httpx.get(f"{settings.KC_INTERNAL_URL}/realms/{settings.REALM}", timeout=3).raise_for_status()
except Exception:
    pytest.skip("Keycloak realm not reachable; start and seed the stack", allow_module_level=True)

pytestmark = pytest.mark.integration


@pytest.fixture
def lms():
    svc = DemoService("lms")
    assert svc.register_key().status_code == 200
    return svc


def student_token(service="lms", profile="partial"):
    return login(service, "asha", profile).json()["access_token"]


def error(r: httpx.Response) -> str:
    return r.json().get("error")


# --- key registration ---------------------------------------------------------

def test_key_registration_needs_the_services_own_token():
    svc = DemoService("lms")
    r = httpx.post(f"{TRUSTTRAIL}/services/keys", json={"keys": [svc.jwk]},
                   headers={"Authorization": f"Bearer {student_token()}"})
    assert r.status_code == 401


def test_private_key_material_is_rejected(lms):
    r = httpx.post(f"{TRUSTTRAIL}/services/keys", json={"keys": [{**lms.jwk, "d": "secret"}]},
                   headers={"Authorization": f"Bearer {lms.service_token()}"})
    assert r.status_code == 400 and error(r) == "invalid_jwks"


# --- the four required cases ----------------------------------------------------

def test_valid_signature_is_accepted_and_stored(lms):
    r = lms.submit(lms.sign(lms.payload()))
    assert r.status_code == 201, r.text
    stored = httpx.get(f"{TRUSTTRAIL}/declarations/{r.json()['declaration_id']}").json()
    assert stored["client_id"] == "lms" and stored["jws"] == r.json()["jws"]


def test_bad_signature_is_refused(lms):
    impostor = DemoService("lms")      # different key, unregistered, claims lms's kid
    r = lms.submit(impostor.sign(lms.payload(), kid=lms.jwk["kid"]))
    assert r.status_code == 400 and error(r) == "bad_signature"


def test_expired_declaration_is_refused_at_submission(lms):
    now = int(time.time())
    r = lms.submit(lms.sign(lms.payload(iat=now - 7200, exp=now - 3600)))
    assert r.status_code == 400 and error(r) == "expired"


def test_expired_declaration_cannot_back_a_release(lms):
    now = int(time.time())
    decl = lms.submit(lms.sign(lms.payload(iat=now, exp=now + 2))).json()
    time.sleep(3)
    r = release(student_token(), decl["declaration_id"])
    assert r.status_code == 403 and error(r) == "declaration_expired"


def test_attribute_not_covered_by_purpose_is_refused(lms):
    decl = lms.declare(attributes=["sub", "affiliation"])          # promises only these
    r = release(student_token(), decl["declaration_id"], attributes=["sub", "department"])
    assert r.status_code == 403 and error(r) == "attribute_not_declared"


# --- other refusals -----------------------------------------------------------------

def test_release_without_declaration_is_refused():
    r = release(student_token())
    assert r.status_code == 403 and error(r) == "no_declaration"


def test_cannot_use_another_services_declaration():
    exam_decl = DemoService("exam").declare()
    r = release(student_token("lms"), exam_decl["declaration_id"])
    assert r.status_code == 403 and error(r) == "no_declaration"


def test_replayed_nonce_is_refused(lms):
    nonce = f"nonce-{time.time_ns()}"
    assert lms.submit(lms.sign(lms.payload(nonce=nonce))).status_code == 201
    r = lms.submit(lms.sign(lms.payload(nonce=nonce, purpose="same nonce, new text")))
    assert r.status_code == 409 and error(r) == "replayed_nonce"


def test_declared_but_above_tier_cap_is_refused():
    library = DemoService("library")
    decl = library.declare(attributes=["sub", "affiliation", "roll_no"])   # declares more than its tier
    r = release(student_token("library", "pseudonym"), decl["declaration_id"], attributes=["roll_no"])
    assert r.status_code == 403 and error(r) == "attribute_above_tier_cap"
    assert r.json()["violation"]["rule"] == "above_tier_cap"          # rule 3 (Phase 4)


def test_above_granted_profile_within_cap_is_refused_without_violation(lms):
    decl = lms.declare()
    r = release(student_token("lms", "pseudonym"), decl["declaration_id"], attributes=["department"])
    assert r.status_code == 403 and error(r) == "attribute_above_profile"
    assert "violation" not in r.json()


# --- receipts -----------------------------------------------------------------------

def test_release_returns_receipt_signed_by_trusttrail(lms):
    decl = lms.declare()
    body = release(student_token(), decl["declaration_id"]).json()
    jwks = jwt.PyJWKSet.from_dict(httpx.get(f"{TRUSTTRAIL}/.well-known/jwks.json").json())
    kid = jwt.get_unverified_header(body["receipt"])["kid"]
    receipt = jwt.decode(body["receipt"], jwks[kid].key, algorithms=["ES256"])
    assert receipt["attributes"] == sorted(body["released"])
    assert receipt["declaration_sha256"] == decl["jws_sha256"]
    assert receipt["purpose"] == decl["purpose"] and receipt["subject"] == body["released"]["sub"]
    assert "Computer Science" not in json.dumps(receipt)    # names only, never values
