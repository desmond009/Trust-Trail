# Sepolia run, 2026-11-10

Contract `TrustTrailAnchor` on Sepolia (chain 11155111):
- address: 0x3415e1C6B20E184EA493007A56589Cebf2074BC8
- owner (anchoring account): 0x3872e690A3f511161BC2d9A3213bf14D31071EF6
- deploy tx: 0x311098914e8657aecef540b48f2d7205cf635ca83cfc6861da5f2cf6930d857e (block 12104082)
- explorer: https://sepolia.etherscan.io/address/0x3415e1C6B20E184EA493007A56589Cebf2074BC8

## Gas and fees (receipts read from Sepolia)

| Transaction | Entries | Block | Gas used | Effective gas price | Fee |
|---|---|---|---|---|---|
| deploy | – | 12104082 | 2,411,192 | 1.0 gwei | 0.00241 ETH |
| batch 0 (first anchor) | 1–943 | 12104085 | 349,631 | ~0 gwei | ~0 |
| batch 1 | 944–956 (13) | 12104090 | 254,408 | ~0 gwei | ~0 |
| batch 2 | 957–970 (14) | 12104093 | 254,408 | ~0 gwei | ~0 |
| batch 3 | 971–986 (16) | 12104096 | 254,408 | ~0 gwei | ~0 |

Same contract on the local Hardhat chain: deploy 361,072; first anchor 91,659; later 77,268.
The gas used differs between Hardhat's local chain and Sepolia's current gas schedule; on both, gas per
anchor is constant regardless of batch size.

Tx hashes: batch 0 0xc98e8ff632a4aa7bcae7782b2cdc83a823f6b43f3af009e2f7f5a081b5af5591,
batch 1 0xfed8cc01bb86af083319a2a353f7aaf145ba84a72d698056618639289bc119bb,
batch 2 0xf41f2600a8212d379451d5d0b477c933e8074428f05e2744d237e3bc2663f800,
batch 3 0x168f9bffa117994a768f063e54c22d19d96cb4c0700258797fba2bd251826601.

Total spent: 0.002411 SepoliaETH (balance 0.05 -> 0.04759).

## Delay (demo_phase5 --batches 3 --interval 30, release every ~2 s)

| Batch | Entries | Delay min (s) | Delay median (s) | Delay max (s) | Tx confirmed in (s) |
|---|---|---|---|---|---|
| 1 | 13 | 12.4 | 26.7 | 40.7 | 9.65 |
| 2 | 14 | 8.8 | 21.7 | 36.4 | 5.77 |
| 3 | 16 | 8.3 | 25.3 | 38.0 | 6.34 |

Over 43 entries: median 25.1 s, p95 38.0 s, max 40.7 s (interval 30 s).
Confirmation = time from sending the transaction to its receipt (inclusion in one block; not finality).

## Tamper test against Sepolia (eval.tamper_test --repeat 5)
Same table as on the local chain: A, B, C detected by all three checks; D and E missed by the chain alone,
caught by receipts and the Sepolia anchor; F caught only by receipts. Every repetition matched the design.
Raw: tamper_sepolia.md, tamper_sepolia_raw.csv (local results files restored to the committed run).

## Other checks
- verify_anchors: every anchored batch matches the chain (batches 0–7 after the tamper test).
- check_dashboard.sh: 6/6 PASS, including "downloaded receipt verifies against the chain without TrustTrail"
  (verify_receipt with CHAIN_RPC_URL = Sepolia).
