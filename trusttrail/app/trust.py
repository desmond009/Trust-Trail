"""Trust score, tiers, and the scope cap that Keycloak enforces.

The loop: a violation is written to the ledger -> the service's score drops ->
its tier drops -> TrustTrail removes the more revealing profile scopes from the
client in Keycloak -> Keycloak itself refuses those profiles from then on.

The score is a heuristic with hand-picked weights (config/trust.yaml), tested
only against simulated services. It summarises behaviour TrustTrail can see;
it says nothing about what a service does with data afterwards.
"""
import json
import logging
import threading
import time
from datetime import datetime, timedelta, timezone

from . import db, ledger, settings
from .errors import ABOVE_TIER_CAP
from .release import profile_attributes

log = logging.getLogger("trusttrail.trust")


# --- pure scoring (unit-tested) ----------------------------------------------------

def score(client: dict, violations: int, rules: dict | None = None) -> dict:
    """Score from the three inputs: privacy policy, registration metadata, violations."""
    s = (rules or settings.trust_rules())["score"]
    attrs = client.get("attributes") or {}
    has_policy = bool(attrs.get("policyUri"))
    missing = [f for f in s["required_metadata"] if not (client.get(f) or attrs.get(f))]
    points = (s["start"]
              - (0 if has_policy else s["no_privacy_policy"])
              - (s["incomplete_metadata"] if missing else 0)
              - s["violation_step"] * violations)
    points = max(points, 0)
    return {"score": points, "privacy_policy_declared": has_policy, "missing_metadata": missing,
            "violations": violations, "demotions": int((s["start"] - points) // s["tier_band"])}


def tier_after(base_tier: str, demotions: int, rules: dict | None = None) -> str:
    """Move down from the base tier, one tier per demotion, never below the bottom."""
    order = (rules or settings.trust_rules())["tier_order"]
    return order[max(order.index(base_tier) - demotions, 0)]


def profiles_up_to(cap: str) -> list[str]:
    order = settings.profiles()["order"]
    return order[: order.index(cap) + 1]


# --- evaluation and enforcement --------------------------------------------------------

class Trust:
    def __init__(self, kc):
        self.kc = kc
        self._lock = threading.Lock()   # one enforcement at a time (poller vs request threads)

    def base_tier(self, service_id: str) -> str:
        return settings.services()[service_id]["tier"]

    def entitled_cap(self, service_id: str) -> str:
        """The cap from the service's agreement; the score can only lower it."""
        return settings.tier_cap(self.base_tier(service_id))

    def evaluate(self, service_id: str) -> dict:
        window = settings.trust_rules()["score"]["violation_window_days"]
        since = (datetime.now(timezone.utc) - timedelta(days=window)).isoformat().replace("+00:00", "Z")
        with db.tx() as conn:
            violations = ledger.violations_since(conn, service_id, since)
        result = score(self.kc.client(service_id), len(violations))
        tier = tier_after(self.base_tier(service_id), result["demotions"])
        return {"service_id": service_id, **result, "base_tier": self.base_tier(service_id),
                "tier": tier, "cap": settings.tier_cap(tier),
                "violations_by_rule": {r: sum(v["rule"] == r for v in violations)
                                       for r in sorted({v["rule"] for v in violations})}}

    def enforce(self, service_id: str) -> dict:
        """Re-evaluate, then make the client's assigned profile scopes match its cap."""
        with self._lock:
            state = self.evaluate(service_id)
            client = self.kc.client(service_id)
            wanted = {f"profile-{p}" for p in profiles_up_to(state["cap"])}
            current = {s for s in self.kc.optional_scopes(client["id"]) if s.startswith("profile-")}
            if wanted != current:
                ids = self.kc.client_scope_ids()
                for name in wanted - current:
                    self.kc.set_optional_scope(client["id"], ids[name], True)
                for name in current - wanted:
                    self.kc.set_optional_scope(client["id"], ids[name], False)
                log.info("%s: tier %s, Keycloak scopes now %s", service_id, state["tier"], sorted(wanted))
            with db.tx() as conn:
                conn.execute("INSERT OR REPLACE INTO trust_state VALUES (?, ?)", (service_id, json.dumps(state)))
            return state

    def state(self, service_id: str) -> dict:
        with db.tx() as conn:
            row = conn.execute("SELECT state FROM trust_state WHERE service_id = ?", (service_id,)).fetchone()
        return json.loads(row["state"]) if row else self.enforce(service_id)

    def current_cap(self, service_id: str) -> str:
        return self.state(service_id)["cap"]

    # --- writing to the ledger ---------------------------------------------------------

    def record_violation(self, service_id: str, rule: str, fields: dict) -> dict:
        with db.tx() as conn:
            entry = ledger.append(conn, {"kind": "violation", "rule": rule, "service_id": service_id,
                                         "attributes_released": [], **fields})
        self.enforce(service_id)
        log.warning("violation %s by %s (entry %s)", rule, service_id, entry["entry_id"])
        return entry

    def reset(self, service_id: str, reason: str) -> dict:
        """An administrator restores a service (e.g. after review). Recorded, so it's auditable."""
        with db.tx() as conn:
            entry = ledger.append(conn, {"kind": "trust_reset", "service_id": service_id,
                                         "purpose": reason, "attributes_requested": []})
        self.enforce(service_id)
        return entry

    # --- rule 3 at login: Keycloak refuses, TrustTrail reads the refusal ----------------

    def poll_events(self) -> int:
        """Turn Keycloak's 'Invalid scopes' login errors into rule-3 violations.

        Counted only when the requested profile is above the service's *agreement*
        (base tier). Requests above a lowered cap are refused by Keycloak but not
        counted again, so one violation can't snowball into automatic blocking.
        """
        order = settings.profiles()["order"]
        services = settings.services()
        found = 0
        for event in reversed(self.kc.login_errors()):      # oldest first
            with db.tx() as conn:
                if conn.execute("SELECT 1 FROM processed_events WHERE event_id = ?", (event["id"],)).fetchone():
                    continue
                conn.execute("INSERT INTO processed_events VALUES (?)", (event["id"],))
            reason = (event.get("details") or {}).get("reason", "")
            service_id = event.get("clientId")
            if not reason.startswith("Invalid scopes") or service_id not in services:
                continue
            asked = [w[len("profile-"):] for w in reason.split() if w.startswith("profile-")]
            asked = [p for p in asked if p in order]
            if not asked:
                continue
            requested = max(asked, key=order.index)
            if order.index(requested) > order.index(self.entitled_cap(service_id)):
                self.record_violation(service_id, ABOVE_TIER_CAP, {
                    "profile": requested, "attributes_requested": sorted(profile_attributes(requested))})
                found += 1
        return found

    def sync(self) -> dict:
        self.poll_events()
        return {sid: self.enforce(sid) for sid in settings.services()}

    def run_forever(self):
        interval = settings.trust_rules()["sync_seconds"]
        while True:
            try:
                self.sync()
            except Exception:  # Keycloak restarting, realm being re-seeded, ...
                log.exception("trust sync failed; retrying")
            time.sleep(interval)

    def start(self):
        threading.Thread(target=self.run_forever, name="trust-sync", daemon=True).start()
