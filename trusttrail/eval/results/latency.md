# Login latency with and without the privacy layer

_Generated 2026-11-10 07:14 UTC by `latency`; fake data, local machine._

| Variant | Runs | Median (ms) | p95 (ms) | Mean (ms) | Min (ms) | Max (ms) |
|---|---|---|---|---|---|---|
| Plain OIDC login (no privacy layer) | 200 | 16.0 | 20.2 | 16.7 | 15.1 | 49.4 |
| TrustTrail login + release (total) | 200 | 19.6 | 25.6 | 20.1 | 17.9 | 31.0 |
|   of which: Keycloak token | 200 | 15.9 | 20.8 | 16.4 | 14.9 | 24.6 |
|   of which: TrustTrail /release | 200 | 3.6 | 5.1 | 3.8 | 2.8 | 6.4 |

Overhead of the privacy layer: median **+3.6 ms** (+22%), p95 **+5.5 ms**.

Password grant on one laptop, all containers local; a browser login adds the same redirects to both variants. TrustTrail's token request is itself slightly different (pairwise ID, sid stripped, no claim mappers). Anchoring is asynchronous and not included.

Raw runs: `latency_raw.csv`.
