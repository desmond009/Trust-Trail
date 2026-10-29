import uuid

import pytest

from app.pseudonyms import pairwise_sub, sector_identifier


def test_pairwise_sub_is_deterministic_uuid_v3():
    a = pairwise_sub("library.localhost", "user-1", "salt")
    assert a == pairwise_sub("library.localhost", "user-1", "salt")
    assert uuid.UUID(a).version == 3


@pytest.mark.parametrize("change", [
    ("lms.localhost", "user-1", "salt"),       # other sector
    ("library.localhost", "user-2", "salt"),   # other student
    ("library.localhost", "user-1", "pepper"), # other salt
])
def test_pairwise_sub_changes_with_each_input(change):
    assert pairwise_sub(*change) != pairwise_sub("library.localhost", "user-1", "salt")


def test_sector_is_the_single_redirect_host():
    client = {"clientId": "lib", "redirectUris": ["http://library.localhost:8001/callback",
                                                  "http://library.localhost:8001/other"]}
    assert sector_identifier(client) == "library.localhost"


def test_sector_rejects_mixed_hosts():
    client = {"clientId": "x", "redirectUris": ["http://a.localhost/cb", "http://b.localhost/cb"]}
    with pytest.raises(ValueError):
        sector_identifier(client)
