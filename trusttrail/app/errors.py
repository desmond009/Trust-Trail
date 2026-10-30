class Refusal(Exception):
    """A request TrustTrail refuses, with a stable machine-readable code.

    The codes are part of the API (see README) and Phase 4 turns some of them
    into recorded violations, so don't rename them casually.
    """

    def __init__(self, status: int, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}")
        self.status, self.code, self.detail = status, code, detail
