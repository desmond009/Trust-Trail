# Same as trusttrail/app/jose_util.py; copied because the images are built separately.
import base64
import hashlib
import json

from jwt.algorithms import ECAlgorithm


def public_ec_jwk(private_key) -> dict:
    jwk = ECAlgorithm.to_jwk(private_key.public_key(), as_dict=True)
    members = {k: jwk[k] for k in ("crv", "kty", "x", "y")}
    digest = hashlib.sha256(json.dumps(members, separators=(",", ":"), sort_keys=True).encode()).digest()
    kid = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()  # RFC 7638 thumbprint
    return {**jwk, "kid": kid, "alg": "ES256", "use": "sig"}
