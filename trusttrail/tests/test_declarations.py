"""Unit tests for declaration verification: no network, no database, fixed clock."""
import calendar
import json

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from app.declarations import TYP, check_usable, verify
from app.errors import Refusal
from app.jose_util import public_ec_jwk

NOW = 1_800_000_000          # 2027-01-15, fixed so tests don't depend on the real clock
DAY = 86400
KEY = ec.generate_private_key(ec.SECP256R1())
JWK = public_ec_jwk(KEY)
OTHER_KEY = ec.generate_private_key(ec.SECP256R1())


def key_for(client_id, kid):
    return JWK if (client_id, kid) == ("lms", JWK["kid"]) else None


def payload(**overrides):
    return {"client_id": "lms", "aud": "trusttrail", "attributes": ["sub", "department"],
            "purpose": "Enrol you in courses", "retention_until": "2027-06-30",
            "nonce": "n-1", "iat": NOW, "exp": NOW + 30 * DAY, **overrides}


def sign(p, key=KEY, headers=None):
    return jwt.encode(p, key, algorithm="ES256", headers={"kid": JWK["kid"], "typ": TYP, **(headers or {})})


def refused(jws) -> str:
    with pytest.raises(Refusal) as e:
        verify(jws, key_for, now=NOW)
    return e.value.code


def test_valid_declaration():
    d = verify(sign(payload()), key_for, now=NOW)
    assert (d.client_id, d.attributes, d.retention_until) == ("lms", ["department", "sub"], "2027-06-30")
    assert d.declaration_id == d.jws_sha256[:16]


def test_bad_signature_wrong_key():
    assert refused(sign(payload(), key=OTHER_KEY)) == "bad_signature"


def test_bad_signature_tampered_payload():
    # Swap the payload for one claiming more attributes; keep the original signature.
    header, _, sig = sign(payload()).split(".")
    forged_body = jwt.utils.base64url_encode(json.dumps(payload(attributes=["roll_no"])).encode()).decode()
    assert refused(f"{header}.{forged_body}.{sig}") == "bad_signature"


def test_expired_declaration():
    assert refused(sign(payload(iat=NOW - 40 * DAY, exp=NOW - DAY))) == "expired"


def test_iat_in_future():
    assert refused(sign(payload(iat=NOW + DAY, exp=NOW + 2 * DAY))) == "not_yet_valid"


def test_lifetime_too_long():
    assert refused(sign(payload(exp=NOW + 400 * DAY))) == "lifetime_too_long"


def test_wrong_audience():
    assert refused(sign(payload(aud="someone-else"))) == "wrong_audience"


def test_unknown_attribute():
    assert refused(sign(payload(attributes=["sub", "blood_group"]))) == "unknown_attribute"


def test_retention_already_over():
    assert refused(sign(payload(retention_until="2026-01-01"))) == "retention_in_past"


def test_missing_claim():
    p = payload()
    del p["purpose"]
    assert refused(sign(p)) == "malformed"


def test_wrong_typ_header():
    assert refused(sign(payload(), headers={"typ": "JWT"})) == "malformed"


def test_key_of_another_client_is_not_used():
    assert refused(sign(payload(client_id="exam"))) == "unknown_key"


def test_alg_none_rejected():
    unsigned = jwt.encode(payload(), None, algorithm="none", headers={"kid": JWK["kid"], "typ": TYP})
    assert refused(unsigned) == "unsupported_alg"


def test_check_usable_window():
    d = verify(sign(payload()), key_for, now=NOW)
    check_usable(d, now=NOW + DAY)                          # inside both windows
    with pytest.raises(Refusal) as e:
        check_usable(d, now=NOW + 31 * DAY)                 # declaration expired
    assert e.value.code == "declaration_expired"

    d.expires_at = NOW + 365 * DAY                          # still valid, but...
    after_retention = calendar.timegm((2027, 7, 2, 12, 0, 0))
    with pytest.raises(Refusal) as e:
        check_usable(d, now=after_retention)                # ...retention is over
    assert e.value.code == "retention_passed"
