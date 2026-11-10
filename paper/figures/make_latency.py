"""Latency ECDF figure for the paper, from trusttrail/eval/results/latency_raw.csv."""
import csv, statistics, pathlib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

root = pathlib.Path(__file__).resolve().parents[2]
rows = list(csv.DictReader(open(root / "trusttrail/eval/results/latency_raw.csv")))
data = {v: sorted(float(r["total_ms"]) for r in rows if r["variant"] == v) for v in ("baseline", "trusttrail")}
style = {
    "baseline":   dict(color="#eb6834", ls="--", label="Plain OIDC login (no privacy layer)"),
    "trusttrail": dict(color="#2a78d6", ls="-",  label="TrustTrail login + release"),
}
plt.rcParams.update({"font.family": "serif", "font.size": 9})
fig, ax = plt.subplots(figsize=(6.0, 2.8))
for v, xs in data.items():
    n = len(xs)
    ax.step(xs, [(i + 1) / n for i in range(n)], where="post", lw=2, **style[v])
    m = statistics.median(xs)
    ax.plot([m], [0.5], marker="o", ms=6, color=style[v]["color"], mec="white", mew=1.5, zorder=3)
    ax.annotate(f"median {m:.1f} ms", (m, 0.5), xytext=(6, -14 if v == "baseline" else 6),
                textcoords="offset points", fontsize=8, color="#333333")
ax.set_xlim(12, 35)
ax.set_ylim(0, 1.02)
ax.set_xlabel("Login latency (ms), 200 runs per variant")
ax.set_ylabel("Fraction of runs")
ax.grid(True, color="#e6e6e6", lw=0.6)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
ax.legend(loc="lower right", frameon=False, fontsize=8)
fig.tight_layout()
out = pathlib.Path(__file__).with_name("latency_ecdf.pdf")
fig.savefig(out)
fig.savefig(out.with_suffix(".png"), dpi=150)
print({v: (len(x), round(statistics.median(x), 1), round(max(x), 1)) for v, x in data.items()})
