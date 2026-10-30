"""Merkle tree over a batch of ledger entry hashes.

Follows the RFC 6962 (Certificate Transparency) conventions:
  leaf = SHA-256(0x00 || entry_hash)      node = SHA-256(0x01 || left || right)
The different prefixes stop an inner node from being passed off as a leaf, and
an odd node at the end of a level is promoted unchanged rather than duplicated
(duplication lets two different batches share a root).

A proof lets a student check one entry against the on-chain root while seeing
only sibling hashes, never the other entries.
"""
import hashlib


def leaf_hash(entry_hash_hex: str) -> bytes:
    return hashlib.sha256(b"\x00" + bytes.fromhex(entry_hash_hex)).digest()


def node_hash(left: bytes, right: bytes) -> bytes:
    return hashlib.sha256(b"\x01" + left + right).digest()


def _next_level(level: list[bytes]) -> list[bytes]:
    parents = [node_hash(level[i], level[i + 1]) for i in range(0, len(level) - 1, 2)]
    if len(level) % 2:
        parents.append(level[-1])
    return parents


def root(leaves: list[bytes]) -> bytes:
    if not leaves:
        raise ValueError("a batch needs at least one entry")
    level = leaves
    while len(level) > 1:
        level = _next_level(level)
    return level[0]


def proof(leaves: list[bytes], index: int) -> list[dict]:
    """Sibling hashes from the leaf up to the root. `side` is where the sibling sits."""
    path, level = [], leaves
    while len(level) > 1:
        sibling = index ^ 1
        if sibling < len(level):     # no sibling = promoted, nothing to add at this level
            path.append({"hash": level[sibling].hex(), "side": "left" if sibling < index else "right"})
        index //= 2
        level = _next_level(level)
    return path


def root_from_proof(leaf: bytes, path: list[dict]) -> bytes:
    node = leaf
    for step in path:
        sibling = bytes.fromhex(step["hash"])
        node = node_hash(sibling, node) if step["side"] == "left" else node_hash(node, sibling)
    return node
