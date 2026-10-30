# Login latency with and without the privacy layer

_Generated 2026-10-30 10:00 UTC by `latency`; fake data, local machine._

| Variant | Runs | Median (ms) | p95 (ms) | Mean (ms) | Min (ms) | Max (ms) |
|---|---|---|---|---|---|---|
| Plain OIDC login (no privacy layer) | 200 | 17.1 | 19.1 | 17.4 | 15.7 | 27.7 |
| TrustTrail login + release (total) | 200 | 21.2 | 24.7 | 21.6 | 19.3 | 37.1 |
|   of which: Keycloak token | 200 | 16.9 | 19.5 | 17.3 | 15.6 | 33.1 |
|   of which: TrustTrail /release | 200 | 4.2 | 5.8 | 4.4 | 3.4 | 7.4 |

Overhead of the privacy layer: median **+4.0 ms** (+24%), p95 **+5.6 ms**.

Password grant on one laptop, all containers local; a browser login adds the same redirects to both variants. TrustTrail's token request is itself slightly different (pairwise ID, sid stripped, no claim mappers). Anchoring is asynchronous and not included.

Raw runs: `latency_raw.csv`.
