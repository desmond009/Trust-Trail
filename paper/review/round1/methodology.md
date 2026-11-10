# Peer Reviewer 1 (Methodology): TrustTrail manuscript

## 1. Summary of what was evaluated and how

The paper reports five experiments on one Apple-silicon laptop with all components in local Docker containers:
(i) a scripted functional check of what three honest services receive (Sec. 9.2);
(ii) a login-latency benchmark, 200 interleaved runs per variant after 10 warm-ups, comparing a plain Keycloak client with TrustTrail (token plus `/release`), using the OAuth password grant;
(iii) a tamper experiment with six attacks (A-F), five repetitions, and three detectors (hash chain, held receipts, on-chain anchors);
(iv) a violation experiment with three scripted bad services, three repetitions of five attempts, plus 90 honest releases for false positives;
(v) an anchoring run on a local Hardhat chain (3 batches, 12 s interval, 19 entries) plus contract-test gas figures, extrapolated by arithmetic to a public chain.
Results are in `eval/results/*.md` and `*_raw.csv`. Each experiment is followed by a short interpretation, RQ answers, and a threats-to-validity paragraph.

I recomputed the latency table from `latency_raw.csv` (400 rows). I read `bench_latency.py`, `run_all.sh`, the tamper and violation results, and `anchoring_run_2026-11-10.md`.

## 2. Genuine strengths

- S-1. Latency design is better than typical for a student project (09-evaluation, "Latency overhead").
  - Warm-up, random interleaving of the two variants, `perf_counter`, and 200 runs per variant.
  - The overhead is decomposed into a Keycloak-token part and a `/release` part.
  - Raw per-run CSV is kept.
  - Medians are reported, so the 49.4 ms baseline outlier does not distort the headline.
  - The paper discloses that the TrustTrail token request is not identical to the baseline's.
- S-2. The tamper experiment is more than a happy-path demo (Sec. 9.4).
  - It tries attacks the hash chain cannot see (D, E, F) and reports where each detector fails: chain 0/5 on D/E/F, anchor 0/5 on F.
  - Showing the anchoring window (F) as a real negative result is honest.
  - Each repetition uses a randomly chosen target (not first, not newest) on a fresh copy of the DB (seeded in `tamper_test.py`).
- S-3. The violation experiment separates three outcomes: missed, wrong rule, false positive (Sec. 9.5). It runs honest traffic alongside, and the base tier is reset every repetition.
- S-4. The paper itself says that the 100% detection rate is a property of scripted clients and is not a prevalence estimate (Sec. 9.5 interpretation).
- S-5. The gas explanation is correct: constant cost per batch, with the first-anchor and deploy figures separated.
- S-6. Honest labelling of what was not done: no Sepolia run, no concurrency test, the taxonomy self-assessment is not independent.

## 3. Weaknesses

### M-1 (MAJOR): Tamper experiment is partly circular, and "any check 5/5" is close to a tautology
- Location: 09-evaluation, "Tamper detection", Method and Table `tab:tamper`; the threats paragraph.
- What is wrong:
  - The attacker, the detectors and the "as designed" oracle are written by the same team.
  - `tamper.md` has an "As designed" column, so the pass criterion is the author's own prediction. The result is "design predicts X, X happened", which verifies the implementation of the design rather than the design's security.
  - The "receipts 5/5 on all six attacks" result is nearly guaranteed by construction. The harness records the hash of every stored receipt (in `tamper_raw.csv`, `receipts_failed` was 439 for attack D), so any modification of any entry fails some receipt.
  - The receipt column therefore assumes every student holds a receipt for every entry, including the target. This is the best case. The paper flags it in one sentence but still counts it toward "Any check 5/5" and toward the RQ3 answer "yes, for all six attacks".
  - Under a realistic assumption (a fraction p of releases have an independently held receipt), D and E on unanchored or un-receipted entries would not be caught by the chain, and F would be undetected. The "100%" in the Any-check column hides this.
- Evidence: `results/tamper_raw.csv` (receipts_failed counts); the Method sentence "records the entry hashes contained in all stored receipts".
- Missing attacks:
  - tampering with the receipt table or the anchor contract state (the paper says only the dashboard check is not independent);
  - anchor-aware attacks (insert after the last anchor then wait for the next anchor, so the forged entry gets anchored);
  - deleting or reordering entries within an unanchored batch that has no receipts;
  - attacks on the signing key or the anchoring key;
  - a replay or fork of the chain.
- Fix:
  - Report the Any-check column as a conditional table. Add a parameter p (fraction of entries with a held receipt, e.g. 0%, 10%, 50%, 100%) and report detection per attack at each p. This is a small amount of harness work, about half a day.
  - Add at least two adversarial cases that the authors did not pre-label (anchor-after-forgery; edit within the last unanchored batch with no receipt) and report them as undetected where that is true.
  - Rename "5/5 detected" to "matched the designed outcome" throughout.
  - Needs new experiments, small.

### M-2 (MAJOR): Sample sizes of 5 and 3 repetitions make "x/5" and "15/15" statistically thin, and no uncertainty is given
- Location: tamper and violation tables; the RQ3 and RQ4 answers.
- What is wrong:
  - The rule is deterministic, so repetition adds little. Each of the 5 tamper repetitions differs only in which row is hit.
  - The three repetitions of the violation test replay one script (15 attempts per rule are 3 independent runs of 5 sequential attempts). After the second attempt the service is `blocked`, so attempts 3-5 mostly test a blocked service. Counting them as 15/15 "detections" inflates n. The independent trials are 3 per service (start from base tier), not 15.
  - No confidence interval is given. For 15/15 the 95% Clopper-Pearson lower bound is about 78%, and for 3 true independent trials about 37%.
- Evidence: `violations.md` tier column "semi_trusted → untrusted → blocked → blocked → blocked → blocked".
- Fix:
  - Report the effective n and a lower bound (rule of three), or drop the percentage language.
  - Vary the attack parameters (which attribute is overasked, how far past deletion, different students, timing relative to the sync interval), and randomise the order of misbehaviour. This is a medium amount of work.
  - Needs new experiments, small to medium.

### M-3 (MAJOR): Latency statistics are incomplete and the headline "stable to within half a millisecond" is not backed by reported data
- Location: "Latency overhead", Results paragraph and Table `tab:latency`.
- What is wrong:
  - There is no variance, standard deviation or confidence interval for the overhead. The paper gives only medians, p95 and mean/min/max. From the raw data, baseline sd is about 3.0 ms (inflated by one 49 ms outlier) and TrustTrail sd about 2.1 ms. A bootstrap CI on the median difference would be easy and is not given. The difference (3.6 ms) is a few times the typical spread, so it is probably real, but the paper should show this.
  - "Two earlier runs gave median overheads of 4.0 ms and 3.4 ms" cites runs whose data is not in the repo: only the 2026-11-10 raw CSV exists in the working tree. The 4.0 ms figure comes from the committed 2026-10-30 README and results, and `system_facts.md` says the README numbers (17.1/21.2/+4.0) differ from the 16.0/19.6/+3.6 of the paper. The 3.4 ms run I could not locate. Describing three runs as "stable to within about half a millisecond" hides that the three runs were the same procedure, same machine, and consecutive.
  - The overhead is reported as a difference of medians, and the p95 overhead as a difference of two separate p95s. That is not the p95 of paired differences; the runs are interleaved, not paired. The statement "at the 95th percentile the overhead was 5.5 ms" is a difference of marginal quantiles and is easily misread.
  - Percentile definition: `summarise` gives p95 20.2 / 25.6; a nearest-rank or numpy-linear computation on the raw CSV gives about 20.6 / 25.7. The table values are therefore a rounded interpolation and the definition is not stated.
  - Drift: the first 50 runs of each variant are about 0.5-0.9 ms slower than the last 50 (baseline median 16.5 to 15.7; TrustTrail 19.9 to 19.0). That is on the order of 5% of the effect size. It cancels in the difference, but "no drift" is not shown and no time series or autocorrelation is reported.
  - The ECDF figure omits the 49 ms outlier (disclosed in the caption).
- Fix:
  - Add a bootstrap 95% CI for the median difference and the sd/IQR in the table.
  - Say how p95 is computed.
  - Commit the raw files of the earlier runs, or delete the "two earlier runs" sentence.
  - No new experiment needed for the CI; about 30 minutes of analysis.

### M-4 (MAJOR): Latency baseline and workload do not represent the real login the system replaces; the 22% figure will be quoted and is misleading
- Location: Latency method, Interpretation.
- What is wrong:
  - Both variants are measured at about 16 ms, a localhost token endpoint. In a real flow (redirects, user agent, TLS, a remote Keycloak) a login takes hundreds of ms, so +3.6 ms relative to 16 ms is not a meaningful percentage. The paper reports the 22% prominently in `latency.md`, and the paper text uses it once. The absolute cost is the useful number.
  - The measured path does not include the services' own work. In the real design the extra cost includes one network hop from service to TrustTrail (acknowledged), but also the declaration fetch, JWKS fetching on first use, and the Keycloak Admin API call to cap profiles when the trust tier changes, none of which is measured.
  - Only one service (LMS), one declaration and one profile are used. The `/release` cost for the examination portal (all four attributes, more ledger work) and for a ledger that has grown is not measured. Note that each TrustTrail run appends to the ledger, so the ledger grows during the benchmark (about 200+ entries); the hash-chain append may be O(1) but this is never checked, and receipt/ledger verification cost with size is not reported.
  - Password grant is the Resource Owner flow, which is deprecated in OAuth 2.1; it skips authentication-session creation and consent, and in Keycloak it takes a different code path from the authorization-code flow. The sentence "a browser login adds the same redirects to both variants" is an assumption, not a measured result.
  - No baseline for the "no Keycloak" cost, i.e. a plain pairwise-pseudonym Keycloak setup without TrustTrail's `/release` hop, which is the fairer comparison for the privacy layer's own cost.
  - Single-threaded, sequential client, so no throughput or contention data, even though the paper itself notes a global DB lock (Sec. 9.3 Interpretation).
- Fix:
  - Foreground the absolute overhead and drop or caveat the percentage.
  - Run one authorisation-code flow benchmark with a headless browser (Playwright) with e.g. 30-50 runs, to validate the "same redirects" assumption.
  - Add a small concurrency sweep (1, 4, 16 clients) to support or soften the "throughput is an open question" statement, using `hey`/`locust`.
  - Add a breakdown by step (verify, DB, Keycloak fetch, ledger, sign), which the paper says was not timed. Instrumentation is cheap.
  - Needs new experiments, medium (1-2 days).

### M-5 (MAJOR): Anchoring measurement is tiny and the public-chain extrapolation is not validated
- Location: "Anchoring cost and delay" and the RQ5 answer.
- What is wrong:
  - The delay measurement covers 3 batches and 19 entries. The entry-to-anchor delay is set almost entirely by the chosen 12 s interval and 2 s release period: with a uniform arrival the expected delay is about interval/2, and the median of 7.6 s is just what arithmetic predicts. This is not a measurement of anything the system does; it confirms the timer. Presenting "median 7.6 s, max 12.8 s" as a result adds no information beyond the configuration.
  - Confirmation in "at most 0.05 s" is Hardhat automine; it says nothing about Ethereum, where the block time and finality (12 s slots, about 13 min to finality) dominate. The statement "roughly 150 s and 310 s on a public network" quietly assumes 12 s block inclusion and ignores finality, reorgs, mempool delays, fee-bumping and failed transactions. The anchoring window that matters for the security argument (attack F) is thus underestimated, probably by an order of magnitude if finality is required.
  - The gas figures are taken from the local EVM. Gas for the same code is deterministic across EVM chains, so 77,268 gas is credible, but the cost line "0.000077 ETH at 1 gwei" and "0.022 ETH per day" (288 x 77,268 x 1e-9 = 0.0223, arithmetic checks) depend on a gas price that the paper picks arbitrarily. No conversion to currency, no L2 comparison, no range (e.g. 5-50 gwei), and no account of the dominant public-chain cost (calldata is small, but each tx pays the 21,000 base). The cost of verifying (reads) is not discussed.
  - The "same cost for 6, 7 and 100,000 entries" claim rests on the contract storing one root. This is a design property; the real scaling cost is off-chain (Merkle tree build, proof size) and is not measured. The paper never reports proof generation or verification time or ledger-size scaling, even though verification (`/anchors/verify`) is the operation users do.
  - The first-anchor (91,659) versus later (77,268) difference is explained only as array initialisation; this is plausible but not verified.
- Fix:
  - Either run once on Sepolia (a few hours, free testnet ETH) with 10-20 anchors and report observed confirmation and finality times and the actual gas used, or label every public-chain number "model estimate" in the table and the RQ5 answer.
  - Report a gas-price range.
  - Add Merkle build and proof-verify time versus ledger size (1e2 to 1e5), which is easy and informative.
  - Needs new experiments, small (Sepolia) to medium.

### M-6 (MINOR to MAJOR): Violation experiment: sync latency, rule coverage, and a waiting-time design that can hide misses
- Location: "Violation detection and trust response", Method.
- What is wrong:
  - After each attempt the harness "waits until the violation count changes, at most 15 s". If detection takes longer than 15 s it counts as a miss, but the time-to-detect is not reported at all. The paper claims "within seconds" and "Rule 3 at login ... detected as reliably as the synchronous rules" without giving one latency number. Rule 3 depends on polling Keycloak's LOGIN_ERROR event log; its detection delay, sync interval, event expiry (86,400 s) and the possibility of lost events are exactly what a methodology reader wants to see.
  - Only three rules and only LOGIN_ERROR events; no near-miss or benign-but-odd behaviour (e.g. a service asking for a declared attribute at a high rate, an expired declaration with clock skew, a boundary request exactly at the deletion time). False-positive testing uses only honest, well-behaved clients, so the 0/90 false-positive figure is uninformative about boundary cases such as the 30 s clock skew.
  - 90 honest releases is small and all are identical profiles.
- Fix: log and report time-to-detect (median, max) per rule; add 3-5 boundary cases (just before/after deletion time, skewed clocks, a declared-but-unusual attribute set). Small new experiment.

### M-7 (MINOR): Results are mostly reported, not analysed; no sensitivity or ablation
- Location: all of Sec. 9.
- What is wrong:
  - Interpretations are largely restatements ("the three mechanisms cover each other's gaps"). There is no ablation of the trust score parameters (the weights are admitted to be heuristic), no sensitivity to the sync interval, anchoring interval or batch size, and no comparison with an alternative design (e.g. the ledger without anchors, a signed-log baseline, or a Trillian/transparency-log style approach).
  - There is no analysis of why the tamper outcomes and costs are what they are beyond the design table, and no discussion of an unexpected result. The one non-obvious item, the 49.4 ms baseline outlier, is mentioned only in a caption.
  - The ledger and trust-score formulae are never stress-tested (e.g. what does one false positive do to a service; how long to recover).
- Fix: add a short sensitivity sweep (anchoring interval 30/60/300 s against delay and cost; trust weights against demotion speed) and one comparison baseline. These reuse the existing harness, medium work.

### M-8 (MINOR): Reproducibility gaps
- Location: Setup paragraph; `eval/` scripts.
- What is wrong:
  - Hardware is described only as "one Apple-silicon laptop under macOS": no chip, RAM, Docker version or VM allocation, Python/JVM version, or Keycloak JVM settings (Keycloak in `start-dev` mode, with dev caches and H2 database, is not production-like and its absolute latency is unrepresentative).
  - The latency `random.shuffle` is not seeded (the tamper test is seeded with `--seed 1`; the latency and violation tests are not), so the exact interleaving cannot be reproduced.
  - No commit hash, no Docker image digests, and the results files in the git status are uncommitted modifications of the 2026-10-30 versions. A reader cannot tell which commit produced the tables. `system_facts.md` already notes that README numbers (+4.0 ms) differ from the paper (+3.6 ms).
  - The latency harness appends to the shared ledger; the paper does not say whether the database was reset before each experiment, though the tamper test shows a ledger with at least 439 entries, so the state varies.
  - No artefact statement (the repository URL/DOI and a one-command reproduce).
- Fix: add a hardware/software table, seed all RNGs, commit the results and cite the commit hash, add an artefact-availability sentence. 1-2 hours, no new experiments.

### M-9 (MINOR): Threats-to-validity section is generic and understates the circularity
- Location: "Threats to validity".
- What is wrong:
  - It does acknowledge that attacks and expected outcomes were fixed in advance by the same team, which is good, but then makes no attempt at mitigation (no external red-team, no mutation testing of the verifier). It omits the receipts-everywhere assumption (it is in the interpretation but not here), the interleaving/shared-ledger growth effect, the Keycloak dev-mode caveat, the self-reported taxonomy table (listed, but under construct validity only), the single seed, and the passage from local to public chain (finality) as a threat to the cost conclusions.
  - It lacks conclusion validity (statistics) altogether.
- Fix: add a "conclusion validity" paragraph and the omitted items; an external 2-hour attack session by a classmate and a verifier mutation test (flip each check off and see which attack goes undetected) would be a cheap and credible mitigation.

### M-10 (MINOR): Functional check (RQ1) is anecdotal
- Location: "What services receive".
- What is wrong: five students, three services, one run; results are "in every row, the three identifiers differed" with UUID prefixes shown. There is no statement of the number of checked tokens, and the browser-level check is described in one sentence with no artefact (screenshot, HAR, or test name). Claiming RQ1 "yes" is fine as a functional demonstration, but the pairwise-sub property is a property of the Keycloak mapper and is mostly Keycloak's, not TrustTrail's.
- Fix: cite the integration test names and numbers; add a collision/linkability check across all 5x3 identifiers and a test that two logins of the same student at one service give the same sub (stability). Trivial work.

## 4. Number-check table

| Claim in paper | Source checked | Matches? |
|---|---|---|
| Plain median 16.0, p95 20.2, mean 16.7, min 15.1, max 49.4 | `latency_raw.csv` (recomputed: median 16.015, mean 16.747, min 15.08, max 49.36; p95 20.63 by plain index) | Yes, except p95 differs by about 0.4 ms depending on percentile method (method not stated) |
| TrustTrail total median 19.6, p95 25.6, mean 20.1, min 17.9, max 31.0 | `latency_raw.csv` (19.57, p95 25.74, 20.12, 17.94, 31.02) | Yes (p95 method caveat) |
| Keycloak token 15.9/20.8/16.4; /release 3.6/5.1/3.8 | `latency.md` | Yes (matches `latency.md`; not recomputed per column) |
| Overhead +3.6 ms, 22%, p95 +5.5 | `latency.md`: +3.6 (+22%), +5.5 | Yes (3.55/16.0 = 22%) |
| "Two earlier runs gave +4.0 and +3.4 ms" | `system_facts.md` (4.0 from committed 2026-10-30 README); 3.4 not found | Partly: 4.0 traced; 3.4 not found; raw data for both not in the repo |
| 200 runs per variant, 10 warm-up, interleaved | `bench_latency.py` and CSV (400 rows) | Yes |
| Tamper table (A-F columns) | `tamper.md` | Yes, all cells |
| 5 repetitions, 6 attacks | `tamper.md`, `run_all.sh --repeat 5` | Yes |
| 45 violation attempts all detected, 0 wrong rule | `violations.md` (15+15+15) | Yes, but n effectively 3 independent starts per service (M-2) |
| 90 honest releases, 0 FP | `violations.md` | Yes (30 per repetition x 3) |
| Tier trajectories | `violations.md` | Yes |
| Alumni Tracker starts at 85 | `violations_raw.csv` (score_before 85) | Yes |
| Gas 77,268 per later anchor (6, 6, 7 entries) | `anchoring_run_2026-11-10.md` | Yes |
| First anchor 91,659; 100,000-entry anchor 77,268 | anchoring note (contract tests) | Yes (cited from note; tests not re-run) |
| Deploy gas 361,072 | not in the anchoring note | Could not verify |
| Delay median 7.6 s, max 12.8 s over 19 entries; confirmation at most 0.05 s | anchoring note | Yes |
| 0.000077 ETH at 1 gwei; 288 anchors = 0.022 ETH/day | arithmetic (77,268e-9 = 7.7e-5; x288 = 0.0223) | Yes |
| 150 s mean and 310 s max delay at 300 s interval | arithmetic from the interval plus an assumed 12 s block | Estimate, unvalidated (M-5) |
| "Raw data is stored with the results" | `eval/results/*_raw.csv` present, but uncommitted | Present, but not committed |

I found no outright mismatch between paper numbers and data. The issues are definitions (p95), provenance (earlier runs), and over-interpretation.

## 5. Criterion judgements

- Experimental design: PARTLY_MEETS. The latency protocol is sound; the baseline, workload (single service, password grant) and the attack set are narrow and author-defined (M-1, M-4).
- Statistical reporting: PARTLY_MEETS. Medians, p95 and raw data are given, but there are no CIs, no sd, and no paired analysis; n of 3 and 5 repetitions, with counts reported as "15/15" (M-2, M-3).
- Validity of conclusions: PARTLY_MEETS. The paper discloses most limitations itself. "100% detection", "yes for all six attacks" and the public-chain delay and cost conclusions are stronger than the evidence (M-1, M-5).
- Reproducibility: PARTLY_MEETS. Scripts, raw CSVs and a one-command runner exist, which is good. Hardware and version details, seeds, and the commit hash are missing (M-8).
- Result analysis depth: PARTLY_MEETS (leaning low). Interpretations are short and mostly restate results. There is no sensitivity or ablation, and the time-to-detect and the scaling of verification are not analysed (M-6, M-7).

For the 15-mark "Implementation, experimental evaluation and result analysis" criterion, the implementation and harness are a clear strength. The analysis and statistics are the weaker part; I would place this in the upper-middle band.

## 6. Recommendation: MAJOR REVISION

Rationale: the experiments are real, scripted, reproducible in principle, and reported honestly. No reported number conflicts with the data. But the strongest claims (RQ3 "yes for all six", RQ4 "100%", RQ5 public-chain cost and delay) rest on self-authored attacks with self-authored expected outcomes, a best-case receipt assumption, tiny repetition counts without uncertainty, and an anchoring-delay figure that mostly restates the configured timer.

Cheapest high-value fixes:
1. Make receipt coverage a parameter in the tamper results.
2. Add a bootstrap CI and a defined percentile method to the latency table.
3. Report time-to-detect.
4. Either run a Sepolia trial or label every public-chain number as a model estimate.
5. Add hardware/version/seed/commit details.

Items 1, 2, 3 and 5 need little or no new experimentation (about 1-2 days in total); items 4 and the concurrency and authorisation-code benchmarks add a few more days.
