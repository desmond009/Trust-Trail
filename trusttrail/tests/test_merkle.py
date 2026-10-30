import hashlib

import pytest

from app import merkle


def leaves(n: int) -> list[bytes]:
    return [merkle.leaf_hash(hashlib.sha256(str(i).encode()).hexdigest()) for i in range(n)]


def test_single_leaf_is_its_own_root():
    one = leaves(1)
    assert merkle.root(one) == one[0] and merkle.proof(one, 0) == []


def test_three_leaves_promote_the_odd_one():
    a, b, c = leaves(3)
    assert merkle.root([a, b, c]) == merkle.node_hash(merkle.node_hash(a, b), c)


@pytest.mark.parametrize("n", [1, 2, 3, 4, 5, 7, 8, 9, 16, 33])
def test_every_proof_verifies(n):
    ls = leaves(n)
    r = merkle.root(ls)
    for i, leaf in enumerate(ls):
        assert merkle.root_from_proof(leaf, merkle.proof(ls, i)) == r


def test_tampered_leaf_fails():
    ls = leaves(8)
    p = merkle.proof(ls, 3)
    assert merkle.root_from_proof(ls[4], p) != merkle.root(ls)


def test_tampered_sibling_fails():
    ls = leaves(8)
    p = merkle.proof(ls, 3)
    p[1]["hash"] = "00" * 32
    assert merkle.root_from_proof(ls[3], p) != merkle.root(ls)


def test_leaf_and_node_hashes_are_domain_separated():
    # An inner node presented as a leaf must not reproduce the root.
    ls = leaves(4)
    inner = merkle.node_hash(ls[0], ls[1])
    assert merkle.leaf_hash(inner.hex()) != inner


def test_duplicating_the_last_leaf_changes_the_root():
    # Guards against the duplicate-last-leaf ambiguity (CVE-2012-2459 style).
    ls = leaves(3)
    assert merkle.root(ls) != merkle.root(ls + [ls[-1]])


def test_empty_batch_is_rejected():
    with pytest.raises(ValueError):
        merkle.root([])
