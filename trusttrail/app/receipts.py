"""TrustTrail's signed release receipts.

TrustTrail signs one receipt per release with its own key. The receipt names
the attributes released (never their values) and embeds the hash of the
service's signed declaration, so it ties "what was released" to "what the
service promised". Anyone can check it against GET /.well-known/jwks.json.
"""
import time
import uuid

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from . import settings
from .jose_util import public_ec_jwk

TYP = "release-receipt+jwt"
_KEY_PATH = settings.DATA_DIR / "receipt_signing_key.pem"
_key = None


def _signing_key():
    # Generated on first use and kept in the data volume, never in the repo.
    global _key
    if _key is None:
        if _KEY_PATH.exists():
            _key = serialization.load_pem_private_key(_KEY_PATH.read_bytes(), password=None)
        else:
            _key = ec.generate_private_key(ec.SECP256R1())
            _KEY_PATH.write_bytes(_key.private_bytes(
                serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption()))
            _KEY_PATH.chmod(0o600)
    return _key


def jwks() -> dict:
    return {"keys": [public_ec_jwk(_signing_key())]}


def sign(claims: dict) -> str:
    key = _signing_key()
    payload = {"iss": "trusttrail", "iat": int(time.time()), "jti": str(uuid.uuid4()), **claims}
    return jwt.encode(payload, key, algorithm="ES256",
                      headers={"kid": public_ec_jwk(key)["kid"], "typ": TYP})


def verify(jws: str) -> dict:
    """Check a receipt against TrustTrail's own public key; raises jwt.PyJWTError if invalid."""
    return jwt.decode(jws, _signing_key().public_key(), algorithms=["ES256"])
