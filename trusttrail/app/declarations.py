"""Signed purpose declarations: what a service promises before it gets any attribute.

A declaration is a compact JWS signed by the service with a key it registered
earlier. TrustTrail keeps the JWS verbatim, so the service's promise can be
re-verified later by anyone holding its public key. This makes use limitation
declared and auditable; it does not make the service keep its promise.
"""
import json
import sqlite3
import time
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from typing import Callable

import jwt

from . import db, settings
from .errors import Refusal
from .jose_util import sha256_hex

TYP = "purpose-declaration+jwt"
REQUIRED = ["client_id", "aud", "attributes", "purpose", "retention_until", "nonce", "iat", "exp"]


@dataclass
class Declaration:
    declaration_id: str
    client_id: str
    nonce: str
    attributes: list[str]
    purpose: str
    retention_until: str
    issued_at: int
    expires_at: int
    kid: str
    jws: str
    jws_sha256: str

    def public(self) -> dict:
        return asdict(self)


def _bad(code: str, detail: str) -> Refusal:
    return Refusal(400, code, detail)


def _today(now: float) -> date:
    return datetime.fromtimestamp(now, timezone.utc).date()


def verify(jws: str, key_for: Callable[[str, str], dict | None], now: float | None = None,
           rules: dict | None = None, vocabulary: set[str] | None = None) -> Declaration:
    """Check signature, then time window, then content. Raises Refusal(400, code)."""
    rules = rules or settings.declaration_rules()
    vocabulary = vocabulary or settings.attribute_vocabulary()
    now = time.time() if now is None else now

    try:
        header = jwt.get_unverified_header(jws)
        unverified = jwt.decode(jws, options={"verify_signature": False})
    except jwt.PyJWTError as e:
        raise _bad("malformed", f"not a compact JWS: {e}")
    if header.get("typ") != TYP:
        raise _bad("malformed", f"header typ must be {TYP}")
    alg = header.get("alg")
    if alg not in rules["algorithms"]:
        raise _bad("unsupported_alg", f"alg must be one of {rules['algorithms']}")

    # client_id is read before verification only to pick the key; the
    # signature check below then proves the service really sent it.
    client_id, kid = unverified.get("client_id"), header.get("kid")
    jwk = key_for(client_id, kid) if client_id and kid else None
    if jwk is None:
        raise _bad("unknown_key", f"no registered key {kid!r} for client {client_id!r}")

    try:
        key = jwt.PyJWK(jwk, algorithm=alg)
        # Time claims are checked below against `now` so tests can control the clock.
        claims = jwt.decode(jws, key, algorithms=[alg], audience=rules["audience"],
                            options={"require": REQUIRED, "verify_exp": False,
                                     "verify_iat": False, "verify_nbf": False})
    except jwt.InvalidSignatureError:
        raise _bad("bad_signature", "signature does not match the registered key")
    except jwt.InvalidAudienceError:
        raise _bad("wrong_audience", f"aud must be {rules['audience']!r}")
    except (jwt.PyJWTError, jwt.PyJWKError) as e:
        raise _bad("malformed", str(e))

    skew = rules["clock_skew_seconds"]
    iat, exp = claims["iat"], claims["exp"]
    if not all(isinstance(t, int) for t in (iat, exp)):
        raise _bad("malformed", "iat and exp must be integers")
    if exp < now - skew:
        raise _bad("expired", "declaration exp is in the past")
    if iat > now + skew:
        raise _bad("not_yet_valid", "iat is in the future")
    if exp - iat > rules["max_lifetime_days"] * 86400:
        raise _bad("lifetime_too_long", f"exp - iat exceeds {rules['max_lifetime_days']} days")

    attributes = claims["attributes"]
    if not isinstance(attributes, list) or not attributes or not all(isinstance(a, str) for a in attributes):
        raise _bad("malformed", "attributes must be a non-empty list of names")
    unknown = sorted(set(attributes) - vocabulary)
    if unknown:
        raise _bad("unknown_attribute", f"not in the attribute vocabulary: {unknown}")

    purpose = claims["purpose"]
    if not isinstance(purpose, str) or not purpose.strip() or len(purpose) > rules["max_purpose_length"]:
        raise _bad("malformed", f"purpose must be 1-{rules['max_purpose_length']} characters")

    try:
        retention = date.fromisoformat(claims["retention_until"])
    except (TypeError, ValueError):
        raise _bad("malformed", "retention_until must be an ISO date (YYYY-MM-DD)")
    if retention < _today(now):
        raise _bad("retention_in_past", "retention_until is already over")

    digest = sha256_hex(jws)
    return Declaration(
        declaration_id=digest[:16], client_id=client_id, nonce=str(claims["nonce"]),
        attributes=sorted(set(attributes)), purpose=purpose.strip(),
        retention_until=retention.isoformat(), issued_at=iat, expires_at=exp,
        kid=kid, jws=jws, jws_sha256=digest)


def check_usable(decl: Declaration, now: float | None = None):
    """A stored declaration can back a release only inside its validity and retention window."""
    now = time.time() if now is None else now
    if now > decl.expires_at:
        raise Refusal(403, "declaration_expired", f"declaration {decl.declaration_id} expired")
    if _today(now) > date.fromisoformat(decl.retention_until):
        # Phase 4 records this as a violation (rule 2).
        raise Refusal(403, "retention_passed",
                      f"retention period ended {decl.retention_until}; the service promised to delete this data")


def store(decl: Declaration):
    try:
        with db.tx() as conn:
            conn.execute(
                "INSERT INTO declarations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (decl.declaration_id, decl.client_id, decl.nonce, json.dumps(decl.attributes),
                 decl.purpose, decl.retention_until, decl.issued_at, decl.expires_at,
                 decl.kid, decl.jws, decl.jws_sha256, int(time.time())))
    except sqlite3.IntegrityError:
        raise Refusal(409, "replayed_nonce", "this service already used that nonce")


def get(declaration_id: str) -> Declaration | None:
    with db.tx() as conn:
        row = conn.execute("SELECT * FROM declarations WHERE declaration_id = ?", (declaration_id,)).fetchone()
    if row is None:
        return None
    fields = {k: row[k] for k in row.keys() if k != "received_at"}
    fields["attributes"] = json.loads(fields["attributes"])
    return Declaration(**fields)
