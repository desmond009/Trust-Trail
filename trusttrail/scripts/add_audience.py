"""Add the TrustTrail audience mapper to the service clients of an existing realm.

    docker compose exec trusttrail python -m scripts.add_audience

For realms seeded before the audience check existed. Unlike scripts.seed it does
not reset the realm, so pairwise salts, pseudonyms and the ledger stay valid.
Idempotent: clients that already have the mapper are left alone.
"""
from app import settings
from scripts.seed import REALM, add_audience_mapper, call


def main():
    for sid in settings.services():
        found = call("GET", f"/{REALM}/clients?clientId={sid}")
        if not found:
            print(f"client {sid:10} not in realm, skipped")
            continue
        add_audience_mapper(found[0]["id"])
        print(f"client {sid:10} audience {settings.AUDIENCE!r} present")


if __name__ == "__main__":
    main()
