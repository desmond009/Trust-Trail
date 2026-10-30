"""Public keys that services use to sign their purpose declarations.

Keys are only ever added, never replaced or deleted, so a declaration signed
with an old key stays verifiable (that is what makes it non-repudiable).
"""
import json
import time

from . import db
from .errors import Refusal
from .jose_util import PRIVATE_JWK_MEMBERS


def register(client_id: str, keys: list[dict]) -> list[str]:
    if not keys:
        raise Refusal(400, "invalid_jwks", "no keys")
    for jwk in keys:
        if PRIVATE_JWK_MEMBERS & jwk.keys():
            raise Refusal(400, "invalid_jwks", "JWKS contains private key material; send public keys only")
        if jwk.get("kty") not in ("EC", "RSA") or not jwk.get("kid"):
            raise Refusal(400, "invalid_jwks", "each key needs kty EC or RSA and a kid")

    with db.tx() as conn:
        for jwk in keys:
            row = conn.execute("SELECT client_id, jwk FROM service_keys WHERE kid = ?", (jwk["kid"],)).fetchone()
            if row is None:
                conn.execute("INSERT INTO service_keys VALUES (?, ?, ?, ?)",
                             (jwk["kid"], client_id, json.dumps(jwk, sort_keys=True), int(time.time())))
            elif row["client_id"] != client_id or json.loads(row["jwk"]) != jwk:
                # Same kid, different key or owner: refuse rather than overwrite history.
                raise Refusal(409, "kid_conflict", f"kid {jwk['kid']} is already registered with a different key")
    return [jwk["kid"] for jwk in keys]


def key_for(client_id: str, kid: str) -> dict | None:
    with db.tx() as conn:
        row = conn.execute("SELECT jwk FROM service_keys WHERE kid = ? AND client_id = ?",
                           (kid, client_id)).fetchone()
    return json.loads(row["jwk"]) if row else None
