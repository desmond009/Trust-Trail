import os

import httpx
import pytest

TRUSTTRAIL = os.environ.get("TRUSTTRAIL_URL", "http://localhost:8000")
ADMIN = {"Authorization": f"Bearer {os.environ.get('TRUSTTRAIL_ADMIN_TOKEN', '')}"}


def admin_sync() -> dict:
    r = httpx.post(f"{TRUSTTRAIL}/trust/sync", headers=ADMIN, timeout=30)
    r.raise_for_status()
    return r.json()


@pytest.fixture(autouse=True)
def services_start_at_base_tier(request):
    """Every integration test starts with every service at its base tier.

    Many tests break the rules on purpose, and since Phase 4 that demotes the
    service. First drain Keycloak's login errors (so a late rule-3 event can't
    land in the next test), then record a trust reset for any service that is
    not at its base tier. Resets are ledger entries, so this is auditable too.
    """
    if request.node.get_closest_marker("integration") is None:
        yield
        return
    for service_id, state in admin_sync().items():
        if state["violations"] or state["tier"] != state["base_tier"]:
            httpx.post(f"{TRUSTTRAIL}/trust/{service_id}/reset", json={"reason": "test isolation"},
                       headers=ADMIN, timeout=30).raise_for_status()
    yield
