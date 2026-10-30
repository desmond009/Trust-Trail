#!/bin/sh
# Runs evaluation parts (a)-(c) and writes everything to eval/results/.
#   docker compose exec trusttrail sh eval/run_all.sh
# The usability study (d) needs real participants: see eval/usability/facilitator_guide.md.
set -e
export PYTHONWARNINGS=ignore   # Authlib's httpx deprecation notice
echo "== (a) latency";            python -m eval.bench_latency --runs 200
echo "== (b) tamper test";        python -m eval.tamper_test --repeat 5
echo "== (b) violation test";     python -m eval.violation_test --repeat 3 --attempts 5
echo "== (c) taxonomy chart";     python -m eval.plot_taxonomy
echo
echo "Results in eval/results/: latency.md, tamper.md, violations.md, taxonomy_chart.png (+ raw CSVs)"
