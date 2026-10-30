"""Create (or reset) the `trusttrail` realm with fake students, the four profile
scopes, the TrustTrail service account and the three test services.

    docker compose run --rm trusttrail python -m scripts.seed

Destructive: an existing `trusttrail` realm is deleted first.
"""
import os
import sys

import httpx

from app import settings

KC = settings.KC_INTERNAL_URL
REALM = settings.REALM
http = httpx.Client(timeout=30)


def admin_token() -> str:
    r = http.post(f"{KC}/realms/master/protocol/openid-connect/token",
                  data={"grant_type": "password", "client_id": "admin-cli",
                        "username": os.environ["KC_ADMIN_USER"],
                        "password": os.environ["KC_ADMIN_PASSWORD"]})
    r.raise_for_status()
    return r.json()["access_token"]


H = {"Authorization": f"Bearer {admin_token()}"}


def call(method: str, path: str, json=None, ok=(200, 201, 204)):
    r = http.request(method, f"{KC}/admin/realms{path}", json=json, headers=H)
    if r.status_code not in ok:
        sys.exit(f"{method} {path} -> {r.status_code}: {r.text}")
    return r.json() if r.content else None


def created_id(path: str, body: dict) -> str:
    r = http.post(f"{KC}/admin/realms{path}", json=body, headers=H)
    if r.status_code != 201:
        sys.exit(f"POST {path} -> {r.status_code}: {r.text}")
    return r.headers["Location"].rsplit("/", 1)[1]


def reset_realm():
    if http.get(f"{KC}/admin/realms/{REALM}", headers=H).status_code == 200:
        print(f"deleting existing realm {REALM}")
        call("DELETE", f"/{REALM}")
    call("POST", "", {"realm": REALM, "enabled": True,
                      "displayName": "TrustTrail Demo University (fake data)",
                      "registrationAllowed": False})
    # Keycloak 24+ drops attributes not declared in the user profile. Our extra
    # student attributes (roll_no, department, ...) stay admin-only.
    up = call("GET", f"/{REALM}/users/profile")
    up["unmanagedAttributePolicy"] = "ADMIN_EDIT"
    call("PUT", f"/{REALM}/users/profile", up)


def create_profile_scopes() -> dict[str, str]:
    """One empty client scope per profile. They carry no claim mappers on purpose:
    Keycloak only records WHICH profile was granted (in the token's `scope`);
    the attribute values are released by TrustTrail."""
    ids = {}
    for profile in settings.profiles()["order"]:
        ids[profile] = created_id(f"/{REALM}/client-scopes", {
            "name": f"profile-{profile}", "protocol": "openid-connect",
            "description": f"TrustTrail {profile} profile",
            "attributes": {"include.in.token.scope": "true",
                           "display.on.consent.screen": "true",
                           "consent.screen.text": f"Share your {profile} profile"}})
    return ids


def scope_id(name: str) -> str:
    return next(s["id"] for s in call("GET", f"/{REALM}/client-scopes") if s["name"] == name)


def trim_basic_scope(basic_id: str):
    # auth_time is identical for every service in one SSO session, so two
    # services could use it to link their pseudonyms. Our services don't need it.
    # (`sid` has the same problem; the strip-sid mapper on each client removes it.)
    for m in call("GET", f"/{REALM}/client-scopes/{basic_id}/protocol-mappers/models"):
        if m["name"] == "auth_time":
            call("DELETE", f"/{REALM}/client-scopes/{basic_id}/protocol-mappers/models/{m['id']}")


def create_trusttrail_client():
    cid = created_id(f"/{REALM}/clients", {
        "clientId": settings.TT_CLIENT_ID, "name": "TrustTrail disclosure layer",
        "publicClient": False, "secret": os.environ["TRUSTTRAIL_CLIENT_SECRET"],
        "serviceAccountsEnabled": True, "standardFlowEnabled": False,
        "directAccessGrantsEnabled": False})
    sa = call("GET", f"/{REALM}/clients/{cid}/service-account-user")
    rm = call("GET", f"/{REALM}/clients", None)
    rm_id = next(c["id"] for c in rm if c["clientId"] == "realm-management")
    roles = [call("GET", f"/{REALM}/clients/{rm_id}/roles/{r}") for r in ("view-users", "view-clients")]
    call("POST", f"/{REALM}/users/{sa['id']}/role-mappings/clients/{rm_id}", roles)


def create_service_client(sid: str, svc: dict, profile_ids: dict, basic_id: str):
    order = settings.profiles()["order"]
    cap = settings.tier_cap(svc["tier"])
    allowed = order[: order.index(cap) + 1]
    cid = created_id(f"/{REALM}/clients", {
        "clientId": sid, "name": svc["name"], "publicClient": False,
        "secret": os.environ[f"{sid.upper()}_CLIENT_SECRET"],
        "rootUrl": svc["url"], "redirectUris": [f"{svc['url']}/callback"],
        "standardFlowEnabled": True, "fullScopeAllowed": False,
        # Service account (no roles): lets the service authenticate as itself
        # to TrustTrail when it registers its declaration-signing key.
        "serviceAccountsEnabled": True,
        # TEST ONLY: lets scripts log students in without a browser.
        "directAccessGrantsEnabled": True,
        "attributes": {"post.logout.redirect.uris": svc["url"],
                       # session_state in the login redirect is the same SSO
                       # session ID as `sid`, so hide it too.
                       "exclude.session.state.from.auth.response": "true",
                       # Refresh tokens need the session ID we strip below.
                       "use.refresh.tokens": "false"}})

    # Strip the realm's default scopes (profile, email, roles, ...): a service
    # must get nothing from Keycloak except the pairwise sub ("basic").
    # "service_account" stays: it only adds client_id to client-credentials tokens.
    for kind in ("default-client-scopes", "optional-client-scopes"):
        for s in call("GET", f"/{REALM}/clients/{cid}/{kind}"):
            if s["id"] != basic_id and s["name"] != "service_account":
                call("DELETE", f"/{REALM}/clients/{cid}/{kind}/{s['id']}")
    if basic_id not in {s["id"] for s in call("GET", f"/{REALM}/clients/{cid}/default-client-scopes")}:
        call("PUT", f"/{REALM}/clients/{cid}/default-client-scopes/{basic_id}")

    # The tier cap: only profiles up to the cap are assignable, so Keycloak
    # itself refuses anything more revealing.
    for p in allowed:
        call("PUT", f"/{REALM}/clients/{cid}/optional-client-scopes/{profile_ids[p]}")

    # Empty salt -> Keycloak generates a random one per client.
    call("POST", f"/{REALM}/clients/{cid}/protocol-mappers/models", {
        "name": "pairwise subject identifier", "protocol": "openid-connect",
        "protocolMapper": "oidc-sha256-pairwise-sub-mapper",
        "config": {"sectorIdentifierUri": "", "pairwiseSubAlgorithmSalt": ""}})
    # Our SPI (keycloak/strip-sid-mapper): without it every service in one
    # SSO session receives the same `sid`, which links the pairwise IDs.
    call("POST", f"/{REALM}/clients/{cid}/protocol-mappers/models", {
        "name": "strip session id", "protocol": "openid-connect",
        "protocolMapper": "trusttrail-strip-sid-mapper", "config": {}})
    print(f"client {sid:8} tier={svc['tier']:14} assignable profiles={allowed}")


def create_students():
    password = os.environ["STUDENT_DEMO_PASSWORD"]
    for s in settings.load("students")["students"]:
        created_id(f"/{REALM}/users", {
            "username": s["username"], "enabled": True, "emailVerified": True,
            "firstName": s["first"], "lastName": s["last"], "email": s["email"],
            "attributes": {"affiliation": ["student"], "roll_no": [s["roll_no"]],
                           "department": [s["department"]], "program": [s["program"]],
                           "year": [s["year"]]},
            "credentials": [{"type": "password", "value": password, "temporary": False}]})
    print(f"created {len(settings.load('students')['students'])} fake students")


def main():
    reset_realm()
    profile_ids = create_profile_scopes()
    basic_id = scope_id("basic")
    trim_basic_scope(basic_id)
    create_trusttrail_client()
    for sid, svc in settings.services().items():
        create_service_client(sid, svc, profile_ids, basic_id)
    create_students()
    print("seed complete")


if __name__ == "__main__":
    main()
