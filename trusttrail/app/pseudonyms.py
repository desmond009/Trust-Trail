"""Per-service pseudonyms and the student <-> pseudonym mapping table.

Keycloak hands each service a pairwise `sub`. TrustTrail needs the reverse
direction (which student is behind this sub?) to fetch attributes and, later,
to show a student their own releases. Rather than leaking the real user ID to
services, we recompute the pairwise sub ourselves from the mapper's salt.

The mapping lives in its own SQLite file (identity_map.db), separate from the
ledger, so the ledger can be inspected without exposing who is who.
"""
import hashlib
import sqlite3
import threading
import uuid
from urllib.parse import urlparse

from . import settings
from .keycloak import KeycloakAdmin


def pairwise_sub(sector: str, local_sub: str, salt: str) -> str:
    # Port of Keycloak's SHA256PairwiseSubMapper.generateSub (26.x):
    #   sha256.update(sector); sha256.update(localSub); hash = sha256.digest(salt)
    #   return UUID.nameUUIDFromBytes(hash)   -> MD5-based, version 3 UUID
    digest = hashlib.sha256((sector + local_sub + salt).encode("utf-8")).digest()
    return str(uuid.UUID(bytes=hashlib.md5(digest).digest(), version=3))


def sector_identifier(client: dict) -> str:
    # Without a sectorIdentifierUri, Keycloak uses the single host shared by
    # all redirect URIs; it refuses clients whose redirect URIs span hosts.
    hosts = {urlparse(u).hostname for u in client.get("redirectUris", [])}
    if len(hosts) != 1:
        raise ValueError(f"client {client['clientId']} redirect URIs span hosts: {hosts}")
    return hosts.pop()


class PseudonymMap:
    def __init__(self, kc: KeycloakAdmin, path=None):
        self.kc = kc
        self.lock = threading.RLock()   # one connection shared by FastAPI's worker threads
        self.db = sqlite3.connect(path or settings.DATA_DIR / "identity_map.db",
                                  check_same_thread=False)
        self.db.execute("""CREATE TABLE IF NOT EXISTS pseudonyms (
            client_id TEXT NOT NULL, pseudonym TEXT NOT NULL, user_id TEXT NOT NULL,
            PRIMARY KEY (client_id, pseudonym))""")

    def rebuild(self, client_id: str) -> int:
        client = self.kc.client(client_id)
        mapper = self.kc.pairwise_mapper(client["id"])
        if mapper is None:
            raise LookupError(f"client {client_id} has no pairwise mapper")
        sector = sector_identifier(client)
        salt = mapper["config"]["pairwiseSubAlgorithmSalt"]
        rows = [(client_id, pairwise_sub(sector, u["id"], salt), u["id"]) for u in self.kc.users()]
        with self.lock, self.db:
            self.db.execute("DELETE FROM pseudonyms WHERE client_id = ?", (client_id,))
            self.db.executemany("INSERT INTO pseudonyms VALUES (?, ?, ?)", rows)
        return len(rows)

    def _lookup(self, client_id: str, pseudonym: str) -> str | None:
        with self.lock:
            row = self.db.execute("SELECT user_id FROM pseudonyms WHERE client_id = ? AND pseudonym = ?",
                                  (client_id, pseudonym)).fetchone()
        return row[0] if row else None

    def resolve(self, client_id: str, pseudonym: str) -> str | None:
        # A miss usually means a new student or a re-seeded realm, so refresh once.
        user_id = self._lookup(client_id, pseudonym)
        if user_id is None:
            self.rebuild(client_id)
            user_id = self._lookup(client_id, pseudonym)
        return user_id

    def pseudonyms_for(self, user_id: str) -> dict[str, str]:
        with self.lock:
            rows = self.db.execute("SELECT client_id, pseudonym FROM pseudonyms WHERE user_id = ?", (user_id,))
            return dict(rows.fetchall())
