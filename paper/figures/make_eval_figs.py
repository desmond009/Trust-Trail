"""Figures for the load and per-step experiments, from trusttrail/eval/results/*_raw.csv."""
import csv, statistics, pathlib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

root = pathlib.Path(__file__).resolve().parents[2] / "trusttrail/eval/results"
out = pathlib.Path(__file__).parent
plt.rcParams.update({"font.family": "serif", "font.size": 9})
BLUE, ORANGE, GRID = "#2a78d6", "#eb6834", "#e6e6e6"

def nearest(xs, p):
    s = sorted(xs); k = max(1, -(-len(s) * p // 100)); return s[int(k) - 1]

# Load: two panels, one measure each (no dual axis).
rows = list(csv.DictReader(open(root / "load_raw.csv")))
levels = sorted({int(r["concurrency"]) for r in rows})
lat = {l: [float(r["latency_ms"]) for r in rows if int(r["concurrency"]) == l and r["status"] == "200"] for l in levels}
md = [l.split("|") for l in open(root / "load.md").read().splitlines() if l.startswith("| ") and l[2].isdigit()]
thr = {int(c[1]): float(c[4]) for c in md}
fig, (a, b) = plt.subplots(1, 2, figsize=(6.4, 2.5))
a.plot(levels, [thr[l] for l in levels], marker="o", ms=6, lw=2, color=BLUE)
a.set_xlabel("Concurrent clients"); a.set_ylabel("Releases per second"); a.set_ylim(0, 600)
b.plot(levels, [statistics.median(lat[l]) for l in levels], marker="o", ms=6, lw=2, color=BLUE, label="median")
b.plot(levels, [nearest(lat[l], 95) for l in levels], marker="s", ms=6, lw=2, ls="--", color=ORANGE, label="p95")
b.set_xlabel("Concurrent clients"); b.set_ylabel("Latency per release (ms)"); b.legend(frameon=False, fontsize=8)
for ax in (a, b):
    ax.set_xticks(levels); ax.grid(True, color=GRID, lw=0.6)
    for s in ("top", "right"): ax.spines[s].set_visible(False)
fig.tight_layout(); fig.savefig(out / "load.pdf"); fig.savefig(out / "load.png", dpi=150)

# Steps: horizontal bars of median ms per step.
r = list(csv.DictReader(open(root / "release_steps_raw.csv")))
steps = [k for k in r[0] if k != "run"]
med = [statistics.median(float(x[k]) for x in r) for k in steps]
fig, ax = plt.subplots(figsize=(6.0, 2.9))
y = list(range(len(steps)))[::-1]
ax.barh(y, med, color=BLUE, height=0.6)
ax.set_yticks(y); ax.set_yticklabels(steps, fontsize=8)
for yi, m in zip(y, med):
    ax.text(m + 0.008, yi, f"{m:.3f}", va="center", fontsize=7.5, color="#333333")
ax.set_xlabel("Median time per release (ms), 200 runs"); ax.set_xlim(0, max(med) * 1.25)
ax.grid(True, axis="x", color=GRID, lw=0.6)
for s in ("top", "right"): ax.spines[s].set_visible(False)
fig.tight_layout(); fig.savefig(out / "release_steps.pdf"); fig.savefig(out / "release_steps.png", dpi=150)
print("ok", thr)
