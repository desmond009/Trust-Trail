import hmac
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

from . import anchoring, dashboard, db, declarations, ledger, receipts, service_keys, settings
from . import release as rel
from .errors import Refusal
from .keycloak import KeycloakAdmin
from .pseudonyms import PseudonymMap
from .tokens import TokenError, verify_access_token, verify_service_token
from .trust import Trust

logging.basicConfig(level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)   # the trust poller calls Keycloak every few seconds
kc = KeycloakAdmin()
pmap = PseudonymMap(kc)
trust = Trust(kc)
anchorer = anchoring.Anchorer()


@asynccontextmanager
async def lifespan(app: FastAPI):
    trust.start()      # background: read Keycloak login errors, re-apply scope caps
    anchorer.start()   # background: anchor a Merkle root of new entries every interval
    yield


app = FastAPI(title="TrustTrail", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=os.environ["SESSION_SECRET"],
                   session_cookie="tt_dashboard", same_site="lax")
app.include_router(dashboard.router(kc, pmap, anchorer))


@app.exception_handler(Refusal)
def refusal_handler(request: Request, exc: Refusal):
    body = {"error": exc.code, "detail": exc.detail}
    if getattr(exc, "violation_entry", None):
        body["violation"] = {"rule": exc.rule, "entry_id": exc.violation_entry}
    return JSONResponse(status_code=exc.status, content=body)


def _admin(authorization: str | None):
    token = (authorization or "").removeprefix("Bearer ").strip()
    if not settings.ADMIN_TOKEN or not hmac.compare_digest(token, settings.ADMIN_TOKEN):
        raise Refusal(401, "not_admin", "admin bearer token required")


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

    Order of checks: valid student token -> the service's own signed declaration
    -> still usable (rule 2) -> requested attributes covered by it (rule 1) ->
    within the tier cap (rule 3) and the granted profile. Rule breaks are
    recorded as violations; successful releases are recorded as releases.
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

    granted = rel.granted_profile(claims.get("scope", ""))
    # A token issued before a demotion still carries the old scope; apply today's cap.
    profile = rel.lower_profile(granted, trust.current_cap(service))
    try:
        declarations.check_usable(decl)
        names = rel.choose_attributes(body.attributes, decl.attributes, rel.profile_attributes(profile),
                                      rel.profile_attributes(trust.entitled_cap(service)))
    except Refusal as refusal:
        if refusal.rule:   # one of the three violation rules: record it, then refuse
            entry = trust.record_violation(service, refusal.rule, {
                "student_pseudonym": claims["sub"], "profile": granted,
                "attributes_requested": refusal.requested or body.attributes or decl.attributes,
                "purpose": decl.purpose, "retention_until": decl.retention_until,
                "declaration_id": decl.declaration_id, "service_signature": decl.jws.rsplit(".", 1)[1]})
            refusal.violation_entry = entry["entry_id"]
        raise

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


@app.get("/ledger/proof/{entry_id}")
def ledger_proof(entry_id: int):
    """Public Merkle proof for one entry: sibling hashes only, never other entries' content."""
    try:
        return anchorer.proof(entry_id)
    except anchoring.AnchorUnavailable as e:
        raise Refusal(503, "anchoring_unavailable", str(e))


@app.get("/anchors")
def anchors():
    """Public: the batches anchored on-chain (read from the contract) and where to find them."""
    try:
        dep = anchorer.deployment()
        batches = anchorer.on_chain_batches()
    except anchoring.AnchorUnavailable as e:
        raise Refusal(503, "anchoring_unavailable", str(e))
    with db.tx() as conn:
        local = {r["batch_id"]: dict(r) for r in conn.execute(
            "SELECT * FROM anchors WHERE deployment = ?", (dep["deployedAt"],))}
    return {"network": dep["network"], "chain_id": dep["chainId"], "contract": dep["address"],
            "interval_seconds": anchoring.rules()["interval_seconds"],
            "batches": [b | {k: local.get(b["batch_id"], {}).get(k) for k in ("tx_hash", "block_number", "gas_used")}
                        for b in batches]}


@app.post("/anchors/run")
def anchors_run(authorization: str | None = Header(None)):
    """Admin: anchor now instead of waiting for the interval (demos and tests)."""
    _admin(authorization)
    try:
        return {"batch": anchorer.run_once()}
    except anchoring.AnchorUnavailable as e:
        raise Refusal(503, "anchoring_unavailable", str(e))


@app.get("/anchors/verify")
def anchors_verify():
    """Public: recompute every anchored batch's root from the ledger content and compare with the chain."""
    try:
        batches = anchorer.on_chain_batches()
    except anchoring.AnchorUnavailable as e:
        raise Refusal(503, "anchoring_unavailable", str(e))
    with db.tx() as conn:
        entries = ledger.all_entries(conn)
    results = anchoring.verify_ledger_against_chain(entries, batches)
    last = batches[-1]["last_entry_id"] if batches else 0
    return {"ok": all(r["ok"] for r in results), "batches_checked": len(results),
            "anchored_up_to": last, "unanchored_entries": max(0, (entries[-1]["entry_id"] if entries else 0) - last),
            "failures": [{"batch_id": r["batch_id"], "reason": r["reason"]} for r in results if not r["ok"]]}


@app.get("/trust")
def trust_overview():
    """Public: every service's current score, tier and cap."""
    return {sid: trust.state(sid) for sid in settings.services()}


@app.post("/trust/sync")
def trust_sync(authorization: str | None = Header(None)):
    """Admin: read Keycloak events and re-apply caps now instead of waiting for the poller."""
    _admin(authorization)
    return trust.sync()


class ResetIn(BaseModel):
    reason: str


@app.post("/trust/{service_id}/reset")
def trust_reset(service_id: str, body: ResetIn, authorization: str | None = Header(None)):
    """Admin: restore a service after review. Earlier violations stop counting; the reset is in the ledger."""
    _admin(authorization)
    if service_id not in settings.services():
        raise Refusal(404, "not_found", "unknown service")
    entry = trust.reset(service_id, body.reason)
    return {"entry_id": entry["entry_id"], "state": trust.state(service_id)}
