import os
from functools import lru_cache
from pathlib import Path

import yaml

KC_INTERNAL_URL = os.environ.get("KC_INTERNAL_URL", "http://keycloak:8080")
KC_PUBLIC_URL = os.environ.get("KC_PUBLIC_URL", "http://localhost:8080")
REALM = os.environ.get("KC_REALM", "trusttrail")
ISSUER = f"{KC_PUBLIC_URL}/realms/{REALM}"
OIDC_BASE = f"{KC_INTERNAL_URL}/realms/{REALM}/protocol/openid-connect"

TT_CLIENT_ID = "trusttrail"
TT_CLIENT_SECRET = os.environ.get("TRUSTTRAIL_CLIENT_SECRET", "")
ADMIN_TOKEN = os.environ.get("TRUSTTRAIL_ADMIN_TOKEN", "")

CONFIG_DIR = Path(os.environ.get("CONFIG_DIR", "/config"))
DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))


@lru_cache
def load(name: str) -> dict:
    return yaml.safe_load((CONFIG_DIR / f"{name}.yaml").read_text())


def profiles() -> dict:
    return load("profiles")


def services() -> dict:
    return load("services")["services"]


def tier_cap(tier: str) -> str:
    return load("trust")["tiers"][tier]


def trust_rules() -> dict:
    return load("trust")


def declaration_rules() -> dict:
    return load("declarations")


def attribute_vocabulary() -> set[str]:
    """Every attribute name a declaration may mention: all profile attributes plus `sub`."""
    names = {"sub"}
    for spec in profiles()["profiles"].values():
        names.update(spec["attributes"])
    return names
