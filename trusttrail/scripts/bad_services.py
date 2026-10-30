"""Three scripted bad services. Each logs students in with an ordinary OIDC client
library (Authlib) and signs an honest-looking declaration, then misbehaves in
exactly one way that TrustTrail can observe:

    overasker  Campus Deals    asks /release for attributes its declaration doesn't cover   (rule 1)
    retainer   Alumni Tracker  keeps requesting after its promised deletion time          (rule 2)
    tiercap    Career Portal   asks Keycloak for a profile above its tier cap             (rule 3)

    docker compose exec trusttrail python -m scripts.bad_services overasker [times]

TEST/DEMO ONLY: logins use the password grant so no browser is needed.
"""
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import httpx
import warnings

import authlib.deprecate  # noqa: F401,E402  (installs an "always show" filter, overridden next)

# Authlib 1.9 marks its httpx integration as deprecated in favour of httpx2; it still works.
warnings.filterwarnings("ignore", message="The httpx module is deprecated")
from authlib.integrations.base_client import OAuthError  # noqa: E402
from authlib.integrations.httpx_client import OAuth2Client  # noqa: E402

from app import settings
from app.demo_service import TRUSTTRAIL, DemoService

TOKEN_URL = f"{settings.OIDC_BASE}/token"


class BadService:
    def __init__(self, service_id: str):
        self.id = service_id
        self.signer = DemoService(service_id)   # its own key + declaration signing

    def current_cap(self) -> str:
        # Public trust state; a service adapting to its cap is ordinary behaviour.
        return httpx.get(f"{TRUSTTRAIL}/trust").json()[self.id]["cap"]

    def login(self, student: str, profile: str) -> dict:
        client = OAuth2Client(self.id, os.environ[f"{self.id.upper()}_CLIENT_SECRET"],
                              scope=f"openid profile-{profile}")
        return client.fetch_token(TOKEN_URL, username=student, password=os.environ["STUDENT_DEMO_PASSWORD"])

    def release(self, token: dict, declaration_id: str, attributes=None) -> httpx.Response:
        body = {"declaration_id": declaration_id, **({"attributes": attributes} if attributes else {})}
        return httpx.post(f"{TRUSTTRAIL}/release", json=body,
                          headers={"Authorization": f"Bearer {token['access_token']}"})

    def wanted_profile(self) -> str:
        order = settings.profiles()["order"]
        return min(settings.services()[self.id]["wants"], self.current_cap(), key=order.index)


class OverAsker(BadService):
    """Declares [sub, affiliation], then asks for department and email too."""

    def misbehave(self, student: str) -> str:
        decl = self.signer.declare()
        token = self.login(student, self.wanted_profile())
        r = self.release(token, decl["declaration_id"], ["sub", "affiliation", "department", "email"])
        return f"asked for department+email under a [sub, affiliation] declaration -> {r.status_code} {r.json()['error']}"


class Retainer(BadService):
    """Promises to delete within seconds, then comes back for more after the deadline."""

    def misbehave(self, student: str, keep_seconds: int = 2) -> str:
        deadline = (datetime.now(timezone.utc) + timedelta(seconds=keep_seconds)).isoformat(timespec="seconds")
        decl = self.signer.declare(retention_until=deadline)
        token = self.login(student, self.wanted_profile())
        first = self.release(token, decl["declaration_id"])
        time.sleep(keep_seconds + 1)
        again = self.release(token, decl["declaration_id"])
        return (f"release before {deadline} -> {first.status_code}; "
                f"same declaration after it -> {again.status_code} {again.json().get('error')}")


class TierCap(BadService):
    """Untrusted (cap: pseudonym) but asks Keycloak for the total profile."""

    def misbehave(self, student: str) -> str:
        try:
            self.login(student, "total")
            return "Keycloak granted profile-total (cap NOT enforced)"
        except OAuthError as e:
            return f"asked Keycloak for profile-total -> refused ({e.error}); TrustTrail reads the login error"


BAD = {"overasker": OverAsker, "retainer": Retainer, "tiercap": TierCap}


if __name__ == "__main__":
    service_id = sys.argv[1]
    times = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    bad = BAD[service_id](service_id)
    for i in range(times):
        print(f"{service_id} #{i + 1}: {bad.misbehave('asha')}")
