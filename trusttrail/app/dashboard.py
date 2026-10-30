"""Student dashboard: every release about the logged-in student, with receipts and checks.

This is the only code that reads the student <-> pseudonym mapping, and only
for the student who is logged in.
"""
import json
import os
from pathlib import Path

import jwt
from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from . import db, declarations, ledger, receipts, settings
from .errors import Refusal

PUBLIC_URL = os.environ.get("TT_PUBLIC_URL", "http://localhost:8000")
PAGE = Path(__file__).parent / "static" / "dashboard.html"


def router(kc, pmap) -> APIRouter:
    r = APIRouter(prefix="/dashboard")
    oauth = OAuth()
    oauth.register(
        "keycloak", client_id="dashboard", client_secret=os.environ.get("DASHBOARD_CLIENT_SECRET", ""),
        server_metadata_url=f"{settings.KC_INTERNAL_URL}/realms/{settings.REALM}/.well-known/openid-configuration",
        client_kwargs={"scope": "openid profile"})

    def student(request: Request) -> dict:
        s = request.session.get("student")
        if not s:
            raise Refusal(401, "not_logged_in", "log in at /dashboard/login")
        return s

    def my_pseudonyms(user_id: str) -> dict[str, str]:
        found = pmap.pseudonyms_for(user_id)
        for service_id in settings.services():
            if service_id not in found:      # mapping not built yet for this service
                pmap.rebuild(service_id)
        return pmap.pseudonyms_for(user_id)

    def my_entry(request: Request, conn, entry_id: int) -> dict:
        entry = ledger.get(conn, entry_id)
        mine = my_pseudonyms(student(request)["user_id"])
        if entry is None or mine.get(entry["service_id"]) != entry["student_pseudonym"]:
            raise Refusal(404, "not_found", "no such release for you")
        return entry

    @r.get("", response_class=HTMLResponse)
    def page():
        return PAGE.read_text()

    @r.get("/login")
    async def login(request: Request):
        return await oauth.keycloak.authorize_redirect(request, f"{PUBLIC_URL}/dashboard/callback")

    @r.get("/callback")
    async def callback(request: Request):
        token = await oauth.keycloak.authorize_access_token(request)
        info = token["userinfo"]
        request.session["student"] = {"user_id": info["sub"],
                                      "name": info.get("name") or info.get("preferred_username")}
        return RedirectResponse("/dashboard")

    @r.get("/logout")
    def logout(request: Request):
        request.session.clear()
        return RedirectResponse("/dashboard")

    @r.get("/api/releases")
    def releases(request: Request):
        s = student(request)
        names = {sid: svc["name"] for sid, svc in settings.services().items()}
        with db.tx() as conn:
            entries = ledger.entries_for(conn, my_pseudonyms(s["user_id"]))
        # Violations about this student are shown too: requests TrustTrail refused.
        return {"student": s["name"], "releases": [{
            "entry_id": e["entry_id"], "kind": e["kind"], "rule": e["rule"], "time": e["time"],
            "service": names.get(e["service_id"], e["service_id"]), "service_id": e["service_id"],
            "profile": e["profile"], "attributes": e["attributes_released"],
            "requested": e["attributes_requested"], "purpose": e["purpose"],
            "delete_by": e["retention_until"]} for e in entries]}

    @r.get("/api/verify/{entry_id}")
    def verify(entry_id: int, request: Request):
        with db.tx() as conn:
            entry = my_entry(request, conn, entry_id)
            chain = ledger.verify(ledger.all_entries(conn))
            receipt_jws = ledger.receipt(conn, entry_id)

        content_ok = ledger.compute_hash(entry) == entry["entry_hash"]
        # This entry is provably intact if the chain is unbroken from genesis up to it.
        linked = chain.ok or chain.first_bad_entry > entry_id
        try:
            receipt = receipts.verify(receipt_jws)
            receipt_sig, receipt_match = True, (receipt["entry_id"] == entry_id and
                                                receipt["entry_hash"] == ledger.compute_hash(entry))
        except (jwt.PyJWTError, TypeError):
            receipt_sig = receipt_match = False
        checks = {
            "entry content matches its hash": content_ok,
            "chain intact from the first entry up to this one": linked,
        }
        if entry["kind"] == "release":   # refused requests have no receipt
            checks["receipt signed by TrustTrail"] = receipt_sig
            checks["receipt matches this ledger entry"] = receipt_match
        return {"entry_id": entry_id, "ok": all(checks.values()), "checks": checks,
                "whole_ledger": chain.as_dict(), "anchor": "not available yet (Phase 5)"}

    def bundle(entry: dict, jws: str | None) -> dict:
        # Called outside db.tx(): declarations.get() takes the same (non-reentrant) lock.
        decl = declarations.get(entry["declaration_id"])
        return {
            "about": "TrustTrail release receipt. Verify receipt_jws with trusttrail_jwks (ES256); "
                     "its entry_hash must equal SHA-256 of the canonical JSON of ledger_entry "
                     "(all fields except entry_hash, sorted keys, no spaces).",
            "receipt_jws": jws, "receipt_payload": receipts.verify(jws) if jws else None,
            "trusttrail_jwks": receipts.jwks(), "ledger_entry": entry,
            "service_declaration_jws": decl.jws if decl else None}

    @r.get("/receipts/{entry_id}")
    def download_receipt(entry_id: int, request: Request):
        with db.tx() as conn:
            entry = my_entry(request, conn, entry_id)
            jws = ledger.receipt(conn, entry_id)
        return JSONResponse(bundle(entry, jws), headers={
            "Content-Disposition": f'attachment; filename="trusttrail-receipt-{entry_id}.json"'})

    @r.get("/receipts")
    def download_all(request: Request):
        s = student(request)
        with db.tx() as conn:
            pairs = [(e, ledger.receipt(conn, e["entry_id"]))
                     for e in ledger.entries_for(conn, my_pseudonyms(s["user_id"]))]
        return JSONResponse([bundle(e, jws) for e, jws in pairs], headers={
            "Content-Disposition": 'attachment; filename="trusttrail-receipts.json"'})

    return r
