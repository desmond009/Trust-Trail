# Time per step inside POST /release

_Generated 2026-11-10 12:13 UTC by `release_steps`; fake data, local machine._

| Step | Median (ms) | p95 (ms) | Mean (ms) | Share of mean |
|---|---|---|---|---|
| verify token | 0.096 | 0.110 | 0.098 | 8% |
| find declaration | 0.016 | 0.022 | 0.017 | 1% |
| apply trust cap | 0.010 | 0.012 | 0.011 | 1% |
| rule checks (declaration, retention, attributes) | 0.005 | 0.007 | 0.005 | 0% |
| map pseudonym to student | 0.006 | 0.008 | 0.006 | 1% |
| fetch attributes from Keycloak | 0.503 | 0.657 | 0.534 | 43% |
| build release | 0.002 | 0.002 | 0.002 | 0% |
| append ledger entry | 0.047 | 0.070 | 0.051 | 4% |
| sign receipt (ES256) | 0.053 | 0.068 | 0.055 | 4% |
| store receipt and commit | 0.480 | 0.697 | 0.469 | 38% |
| **total (in process)** | 1.217 | 1.568 | 1.248 | 100% |

200 runs after 10 warm-up runs, LMS token (partial profile), on a copy of the data directory. Keycloak calls are real HTTP requests to the Keycloak container.

Raw: `release_steps_raw.csv`.
