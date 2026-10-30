# Violation detection test

_Generated 2026-10-30 10:01 UTC by `violations`; fake data, local machine._

| Service | Misbehaviour | Rule | Attempts | Detected | Missed | Wrong rule | Detection rate | Tier after each attempt (every repetition) | Max profile |
|---|---|---|---|---|---|---|---|---|---|
| Campus Deals | asks for attributes its declaration doesn't cover | 1 · undeclared attribute | 15 | 15 | 0 | 0 | 100% | semi_trusted → untrusted → blocked → blocked → blocked → blocked | partial → anonymous |
| Alumni Tracker | requests again after its promised deletion time | 2 · after retention | 15 | 15 | 0 | 0 | 100% | semi_trusted → untrusted → blocked → blocked → blocked → blocked | partial → anonymous |
| Career Portal | asks Keycloak for a profile above its tier cap | 3 · above tier cap | 15 | 15 | 0 | 0 | 100% | untrusted → blocked → blocked → blocked → blocked → blocked | pseudonym → anonymous |

| Honest services | Releases | Violations (false positives) | Tier changes |
|---|---|---|---|
| Digital Library, Learning System, Examination Portal | 90 | 0 | 0 |

3 repetitions × 5 attempts per bad service, each repetition starting from base tiers. Scripted clients only: this shows that the rules fire as designed and that honest traffic is not flagged. It does not estimate how often real services misbehave, nor how often subtler misuse (anything after the data leaves TrustTrail) goes unseen.
