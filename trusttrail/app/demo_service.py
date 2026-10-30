"""TEST/DEMO ONLY: act as one of the test services towards TrustTrail.

Has the service's client secret (from .env) and an in-memory signing key, so
tests and demos can register keys and submit good or deliberately bad
declarations. The real service apps do the same in services/app.py.
"""
import os
import time
import uuid
from datetime import date, timedelta

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import ec

from . import settings
from .declarations import TYP
from .jose_util import public_ec_jwk

TRUSTTRAIL = os.environ.get("TRUSTTRAIL_URL", "http://localhost:8000")


class DemoService:
    def __init__(self, service_id: str):
        self.id = service_id
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.jwk = public_ec_jwk(self.key)

    def service_token(self) -> str:
        r = httpx.post(f"{settings.OIDC_BASE}/token", data={
            "grant_type": "client_credentials", "client_id": self.id,
            "client_secret": os.environ[f"{self.id.upper()}_CLIENT_SECRET"]})
        r.raise_for_status()
        return r.json()["access_token"]

    def register_key(self) -> httpx.Response:
        return httpx.post(f"{TRUSTTRAIL}/services/keys", json={"keys": [self.jwk]},
                          headers={"Authorization": f"Bearer {self.service_token()}"})

    def payload(self, **overrides) -> dict:
        spec = settings.services()[self.id]["declaration"]
        now = int(time.time())
        return {"client_id": self.id, "aud": "trusttrail",
                "attributes": spec["attributes"], "purpose": spec["purpose"],
                "retention_until": (date.today() + timedelta(days=spec["retention_days"])).isoformat(),
                "nonce": str(uuid.uuid4()), "iat": now, "exp": now + spec["valid_days"] * 86400,
                **overrides}

    def sign(self, payload: dict, key=None, kid: str | None = None) -> str:
        return jwt.encode(payload, key or self.key, algorithm="ES256",
                          headers={"kid": kid or self.jwk["kid"], "typ": TYP})

    def submit(self, jws: str) -> httpx.Response:
        return httpx.post(f"{TRUSTTRAIL}/declarations", json={"declaration": jws})

    def declare(self, **overrides) -> dict:
        """Register key + submit a valid declaration; returns TrustTrail's response body."""
        self.register_key().raise_for_status()
        r = self.submit(self.sign(self.payload(**overrides)))
        r.raise_for_status()
        return r.json()
