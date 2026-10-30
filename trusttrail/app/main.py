import os

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

from . import dashboard, db, declarations, ledger, receipts, service_keys
from . import release as rel
from .errors import Refusal
from .keycloak import KeycloakAdmin
from .pseudonyms import PseudonymMap
from .tokens import TokenError, verify_access_token, verify_service_token

app = FastAPI(title="TrustTrail")
app.add_middleware(SessionMiddleware, secret_key=os.environ["SESSION_SECRET"],
                   session_cookie="tt_dashboard", same_site="lax")
kc = KeycloakAdmin()
pmap = PseudonymMap(kc)
app.include_router(dashboard.router(kc, pmap))


@app.exception_handler(Refusal)
def refusal_handler(request: Request, exc: Refusal):
    return JSONResponse(status_code=exc.status, content={"error": exc.code, "detail": exc.detail})


def _bearer(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise Refusal(401, "missing_token", "Authorization: Bearer <token> required")
    return authorization.removeprefix("Bearer ").strip()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/.well-known/jwks.json")
def jwks():
    """TrustTrail's public key, for verifying release receipts."""
    return receipts.jwks()


class JWKSIn(BaseModel):
    keys: list[dict]


@app.post("/services/keys")
def register_keys(body: JWKSIn, authorization: str | None = Header(None)):
    """A service registers the public key(s) it will sign declarations with."""
    try:
        claims = verify_service_token(_bearer(authorization))
    except TokenError as e:
        raise Refusal(401, "invalid_token", str(e))
    kids = service_keys.register(claims["azp"], body.keys)
    return {"client_id": claims["azp"], "kids": kids}


class DeclarationIn(BaseModel):
    declaration: str


@app.post("/declarations", status_code=201)
def submit_declaration(body: DeclarationIn):
    # No bearer token: the signature with a registered key is the authentication.
    decl = declarations.verify(body.declaration, service_keys.key_for)
    declarations.store(decl)
    return decl.public()


@app.get("/declarations/{declaration_id}")
def get_declaration(declaration_id: str):
    decl = declarations.get(declaration_id)
    if decl is None:
        raise Refusal(404, "not_found", "no such declaration")
    return decl.public()


class ReleaseIn(BaseModel):
    declaration_id: str | None = None
    attributes: list[str] | None = None   # default: everything declared and allowed


@app.post("/release")
def release(body: ReleaseIn, authorization: str | None = Header(None)):
    """The only path by which a service learns student attributes.

    Order of checks: valid student token -> the service's own, usable signed
    declaration -> requested attributes covered by that declaration -> and by
    the profile Keycloak granted. Phase 3 writes every release to the ledger.
    """
    try:
        claims = verify_access_token(_bearer(authorization))
    except TokenError as e:
        raise Refusal(401, "invalid_token", str(e))
    service = claims["azp"]

    decl = declarations.get(body.declaration_id) if body.declaration_id else None
    if decl is None or decl.client_id != service:
        raise Refusal(403, "no_declaration",
                      "a release needs a signed purpose declaration submitted by this service")
    declarations.check_usable(decl)

    profile = rel.granted_profile(claims.get("scope", ""))
    names = rel.choose_attributes(body.attributes, decl.attributes, rel.profile_attributes(profile))

    user_id = pmap.resolve(service, claims["sub"])
    if user_id is None:
        raise Refusal(403, "unknown_subject", "unknown pseudonym for this service")
    released = rel.build_release(names, rel.student_attributes(kc.user(user_id)), claims["sub"])

    # Ledger entry and receipt in one transaction: no release without a record.
    with db.tx() as conn:
        entry = ledger.append(conn, {
            "kind": "release", "service_id": service, "student_pseudonym": claims["sub"],
            "profile": profile, "attributes_released": names, "purpose": decl.purpose,
            "retention_until": decl.retention_until, "declaration_id": decl.declaration_id,
            "service_signature": decl.jws.rsplit(".", 1)[1]})
        receipt = receipts.sign({
            "service": service, "profile": profile, "attributes": names,
            # The pseudonym appears only if the service was given it anyway.
            **({"subject": claims["sub"]} if "sub" in names else {}),
            "purpose": decl.purpose, "retention_until": decl.retention_until,
            "declaration_id": decl.declaration_id, "declaration_sha256": decl.jws_sha256,
            "entry_id": entry["entry_id"], "entry_hash": entry["entry_hash"],
            "released_at": entry["time"]})
        ledger.store_receipt(conn, entry["entry_id"], receipt)
    return {"service": service, "profile": profile, "declaration_id": decl.declaration_id,
            "entry_id": entry["entry_id"], "released": released, "receipt": receipt}


@app.get("/ledger/verify")
def verify_ledger():
    """Public chain check. Returns only the result, never entry contents."""
    with db.tx() as conn:
        entries = ledger.all_entries(conn)
    return ledger.verify(entries).as_dict()
