import base64
import hashlib
import json

from jwt.algorithms import ECAlgorithm

PRIVATE_JWK_MEMBERS = {"d", "p", "q", "dp", "dq", "qi", "oth", "k"}
THUMBPRINT_MEMBERS = {"EC": ("crv", "kty", "x", "y"), "RSA": ("e", "kty", "n")}


def thumbprint(jwk: dict) -> str:
    """RFC 7638 JWK thumbprint, used as a stable key ID."""
    members = {k: jwk[k] for k in THUMBPRINT_MEMBERS[jwk["kty"]]}
    digest = hashlib.sha256(json.dumps(members, separators=(",", ":"), sort_keys=True).encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def public_ec_jwk(private_key) -> dict:
    jwk = ECAlgorithm.to_jwk(private_key.public_key(), as_dict=True)
    return {**jwk, "kid": thumbprint(jwk), "alg": "ES256", "use": "sig"}


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()
