"""TEST/DEMO ONLY: log a fake student into a test service with the password grant,
so scripts can run without a browser. Real services use the browser flow."""
import os

import httpx
import jwt

from . import settings

PERSONAL_CLAIMS = {"name", "given_name", "family_name", "preferred_username", "email",
                   "roll_no", "department", "program", "year", "affiliation"}


def login(service: str, username: str, profile: str, password: str | None = None) -> httpx.Response:
    return httpx.post(f"{settings.OIDC_BASE}/token", data={
        "grant_type": "password", "client_id": service,
        "client_secret": os.environ[f"{service.upper()}_CLIENT_SECRET"],
        "username": username, "password": password or os.environ["STUDENT_DEMO_PASSWORD"],
        "scope": f"openid profile-{profile}"})


def claims(token: str) -> dict:
    # Display only; TrustTrail verifies signatures in app.tokens.
    return jwt.decode(token, options={"verify_signature": False})


def release(access_token: str, declaration_id: str | None = None,
            attributes: list[str] | None = None, base: str = "http://localhost:8000") -> httpx.Response:
    body = {k: v for k, v in {"declaration_id": declaration_id, "attributes": attributes}.items() if v is not None}
    return httpx.post(f"{base}/release", json=body, headers={"Authorization": f"Bearer {access_token}"})
