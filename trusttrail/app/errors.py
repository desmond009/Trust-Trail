class Refusal(Exception):
    """A request TrustTrail refuses, with a stable machine-readable code.

    The codes are part of the API (see README). A refusal that breaks one of the
    three violation rules also carries `rule`; /release records those in the
    ledger before refusing, and they lower the service's trust score.
    """

    def __init__(self, status: int, code: str, detail: str = "", rule: str | None = None,
                 requested: list[str] | None = None):
        super().__init__(f"{code}: {detail}")
        self.status, self.code, self.detail = status, code, detail
        self.rule, self.requested = rule, requested


# The three violation rules: only what TrustTrail can actually observe.
UNDECLARED_ATTRIBUTE = "undeclared_attribute"   # rule 1: attribute not in the signed purpose
AFTER_RETENTION = "after_retention"             # rule 2: request after the promised deletion time
ABOVE_TIER_CAP = "above_tier_cap"               # rule 3: more than the service's tier cap allows
