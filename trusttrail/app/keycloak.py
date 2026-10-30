"""Thin client for the Keycloak Admin REST API, used with TrustTrail's own service account."""
import time

import httpx

from . import settings

PAIRWISE_MAPPER = "oidc-sha256-pairwise-sub-mapper"


class KeycloakAdmin:
    def __init__(self, base=settings.KC_INTERNAL_URL, realm=settings.REALM,
                 client_id=settings.TT_CLIENT_ID, secret=settings.TT_CLIENT_SECRET):
        self.base, self.realm = base, realm
        self.client_id, self.secret = client_id, secret
        self._token, self._expires = None, 0.0
        self.http = httpx.Client(timeout=10)

    def _bearer(self) -> str:
        if time.time() > self._expires - 30:
            r = self.http.post(
                f"{self.base}/realms/{self.realm}/protocol/openid-connect/token",
                data={"grant_type": "client_credentials",
                      "client_id": self.client_id, "client_secret": self.secret})
            r.raise_for_status()
            body = r.json()
            self._token, self._expires = body["access_token"], time.time() + body["expires_in"]
        return self._token

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        url = f"{self.base}/admin/realms/{self.realm}{path}"
        r = self.http.request(method, url, headers={"Authorization": f"Bearer {self._bearer()}"}, **kwargs)
        if r.status_code == 401:
            # Cached token died early, e.g. the realm was re-seeded. Retry once with a fresh one.
            self._expires = 0.0
            r = self.http.request(method, url, headers={"Authorization": f"Bearer {self._bearer()}"}, **kwargs)
        r.raise_for_status()
        return r

    def get(self, path: str, **params):
        return self._request("GET", path, params=params).json()

    def client(self, client_id: str) -> dict:
        found = self.get("/clients", clientId=client_id)
        if not found:
            raise LookupError(f"no Keycloak client {client_id!r}")
        return found[0]

    def pairwise_mapper(self, client_uuid: str) -> dict | None:
        for m in self.get(f"/clients/{client_uuid}/protocol-mappers/models"):
            if m["protocolMapper"] == PAIRWISE_MAPPER:
                return m
        return None

    def client_scope_ids(self) -> dict[str, str]:
        return {s["name"]: s["id"] for s in self.get("/client-scopes")}

    def optional_scopes(self, client_uuid: str) -> set[str]:
        return {s["name"] for s in self.get(f"/clients/{client_uuid}/optional-client-scopes")}

    def set_optional_scope(self, client_uuid: str, scope_id: str, assigned: bool):
        # Needs the realm-management "manage-clients" role (granted to TrustTrail by the seed).
        self._request("PUT" if assigned else "DELETE", f"/clients/{client_uuid}/optional-client-scopes/{scope_id}")

    def login_errors(self, max_events: int = 200) -> list[dict]:
        """Recent LOGIN_ERROR events, newest first (needs "view-events")."""
        return self.get("/events", type="LOGIN_ERROR", max=max_events)

    def users(self) -> list[dict]:
        return self.get("/users", max=1000, briefRepresentation="false")

    def user(self, user_id: str) -> dict:
        return self.get(f"/users/{user_id}")
