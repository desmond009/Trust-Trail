# Login latency with and without the privacy layer

_Generated 2026-11-10 10:54 UTC by `latency`; fake data, local machine._

| Variant | Runs | Median (ms) | p95 (ms) | Mean (ms) | Min (ms) | Max (ms) |
|---|---|---|---|---|---|---|
| Plain OIDC login (no privacy layer) | 200 | 15.5 | 20.6 | 16.4 | 14.7 | 31.2 |
| TrustTrail login + release (total) | 200 | 18.6 | 24.0 | 19.5 | 17.4 | 41.2 |
|   of which: Keycloak token | 200 | 15.3 | 18.8 | 15.9 | 14.5 | 37.5 |
|   of which: TrustTrail /release | 200 | 3.5 | 4.9 | 3.6 | 2.7 | 6.4 |

Overhead of the privacy layer: median **+3.2 ms** (+21%), p95 **+3.4 ms**.

Password grant on one laptop, all containers local; a browser login adds the same redirects to both variants. TrustTrail's token request is itself slightly different (pairwise ID, sid stripped, no claim mappers). Anchoring is asynchronous and not included.

Raw runs: `latency_raw.csv`.
