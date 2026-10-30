"""Phase 2 demo: signed purpose declarations, refusals, and signed receipts.

    docker compose exec trusttrail python -m scripts.demo_phase2

Prints every request and response in full, then a table of refusal cases.
"""
import json
import time

import httpx
import jwt

from app import settings
from app.demo_login import login, release
from app.demo_service import TRUSTTRAIL, DemoService


def show(title, obj):
    print(f"\n--- {title} ---")
    print(json.dumps(obj, indent=2) if not isinstance(obj, str) else obj)


def short(jws: str) -> str:
    return jws[:40] + "..." + jws[-10:]


def main():
    lms = DemoService("lms")

    print("\n== 1. Service registers its public key ==")
    show("POST /services/keys  (Authorization: Bearer <lms client-credentials token>)", {"keys": [lms.jwk]})
    show("200 response", lms.register_key().json())

    print("\n== 2. Service signs and submits a purpose declaration ==")
    payload = lms.payload()
    jws = lms.sign(payload)
    show("JWS header", jwt.get_unverified_header(jws))
    show("JWS payload (signed with the service's private key)", payload)
    show("POST /declarations", {"declaration": short(jws)})
    decl = lms.submit(jws).json()
    show("201 response", {**decl, "jws": short(decl["jws"])})

    print("\n== 3. Student logs in to the LMS; the LMS asks TrustTrail for attributes ==")
    token = login("lms", "asha", "partial").json()["access_token"]
    show("POST /release  (Authorization: Bearer <asha's LMS access token>)",
         {"declaration_id": decl["declaration_id"]})
    body = release(token, decl["declaration_id"]).json()
    show("200 response", {**body, "receipt": short(body["receipt"])})

    jwks = httpx.get(f"{TRUSTTRAIL}/.well-known/jwks.json").json()
    key = jwt.PyJWKSet.from_dict(jwks)[jwt.get_unverified_header(body["receipt"])["kid"]].key
    show("receipt verified against GET /.well-known/jwks.json; payload",
         jwt.decode(body["receipt"], key, algorithms=["ES256"]))

    print("\n== 4. Refusals ==")
    now = int(time.time())
    short_lived = lms.submit(lms.sign(lms.payload(iat=now, exp=now + 2))).json()
    narrow = lms.declare(attributes=["sub", "affiliation"])
    exam_decl = DemoService("exam").declare()
    impostor = DemoService("lms")
    nonce = f"demo-{time.time_ns()}"
    lms.submit(lms.sign(lms.payload(nonce=nonce)))
    time.sleep(3)  # let short_lived expire

    cases = [
        ("signature by a key the service never registered",
         lambda: lms.submit(impostor.sign(lms.payload(), kid=lms.jwk["kid"]))),
        ("declaration already expired when submitted",
         lambda: lms.submit(lms.sign(lms.payload(iat=now - 7200, exp=now - 3600)))),
        ("release backed by a declaration that has since expired",
         lambda: release(login("lms", "asha", "partial").json()["access_token"], short_lived["declaration_id"])),
        ("release with no declaration",
         lambda: release(login("lms", "asha", "partial").json()["access_token"])),
        ("release using another service's declaration",
         lambda: release(login("lms", "asha", "partial").json()["access_token"], exam_decl["declaration_id"])),
        ("same nonce submitted twice",
         lambda: lms.submit(lms.sign(lms.payload(nonce=nonce)))),
        ("attribute outside the vocabulary",
         lambda: lms.submit(lms.sign(lms.payload(attributes=["sub", "blood_group"])))),
        ("retention date already over",
         lambda: lms.submit(lms.sign(lms.payload(retention_until="2020-01-01")))),
        # Last: since Phase 4 this is violation rule 1, which demotes the LMS.
        ("release asks for an attribute the purpose does not cover",
         lambda: release(login("lms", "asha", "partial").json()["access_token"],
                         narrow["declaration_id"], ["sub", "department"])),
    ]
    print(f"{'case':58} {'status':6} {'error':24} violation")
    for name, call in cases:
        r = call()
        violation = r.json().get("violation", {}).get("rule", "")
        print(f"{name:58} {r.status_code:<6} {r.json().get('error'):24} {violation}")

    # Undo the demotion so the LMS keeps working for the next demo (recorded in the ledger).
    httpx.post(f"{TRUSTTRAIL}/trust/lms/reset", json={"reason": "after Phase 2 demo"},
               headers={"Authorization": f"Bearer {settings.ADMIN_TOKEN}"}).raise_for_status()
    print("\n(The LMS was demoted by the last case; a recorded trust reset restored it.)")


if __name__ == "__main__":
    main()
