"""Phase 1 demo: per-service pseudonyms, profile filtering and the tier cap.

    docker compose exec trusttrail python -m scripts.demo_phase1
"""
from app import settings
from app.demo_login import PERSONAL_CLAIMS, claims, login, release
from app.demo_service import DemoService
from app.keycloak import KeycloakAdmin

SERVICES = {k: v for k, v in settings.services().items() if not v.get("scripted")}  # the 3 test services
STUDENTS = [s["username"] for s in settings.load("students")["students"]]


def section(title):
    print(f"\n== {title} ==")


def main():
    section("1. Same student, different pseudonymous ID per service (pairwise sub)")
    print(f"{'student':8} " + " ".join(f"{sid:38}" for sid in SERVICES))
    for student in STUDENTS:
        subs = [claims(login(sid, student, svc["wants"]).json()["id_token"])["sub"]
                for sid, svc in SERVICES.items()]
        print(f"{student:8} " + " ".join(f"{s:38}" for s in subs),
              "all different" if len(set(subs)) == len(subs) else "COLLISION")

    section("2. What each service receives for asha (Keycloak token vs TrustTrail /release)")
    for sid, svc in SERVICES.items():
        tok = login(sid, "asha", svc["wants"]).json()
        leaked = PERSONAL_CLAIMS & (claims(tok["id_token"]).keys() | claims(tok["access_token"]).keys())
        decl = DemoService(sid).declare()   # Phase 2: releases need a signed declaration
        body = release(tok["access_token"], decl["declaration_id"]).json()
        print(f"{sid:8} profile={body['profile']:9} personal claims in Keycloak tokens: {sorted(leaked) or 'none'}")
        print(f"{'':8} released by TrustTrail: {body['released']}")

    section("3. Tier cap: profiles each service may request (assigned scopes in Keycloak)")
    # Read, not probed: since Phase 4, asking for a profile above the cap is a
    # recorded violation. scripts.bad_services tiercap shows Keycloak refusing it.
    kc = KeycloakAdmin()
    order = settings.profiles()["order"]
    print(f"{'service':8} {'tier':14} " + " ".join(f"{p:14}" for p in order))
    for sid, svc in SERVICES.items():
        assigned = kc.optional_scopes(kc.client(sid)["id"])
        cells = ["assigned" if f"profile-{p}" in assigned else "not assigned" for p in order]
        print(f"{sid:8} {svc['tier']:14} " + " ".join(f"{c:14}" for c in cells))

if __name__ == "__main__":
    main()
