"""(c) Draw the taxonomy comparison chart from eval/taxonomy/*.csv.

    docker compose exec trusttrail python -m eval.plot_taxonomy

Scores are 0, partial or full. Empty cells are drawn as "not scored", never as 0.
Until a teammate fills `trusttrail_score`, the TrustTrail column shows the
builder's suggestion, hatched and marked with *, so a self-assessment can't pass
for an independent one.
"""
import csv
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch, Rectangle  # noqa: E402

from eval.common import RESULTS  # noqa: E402

HERE = Path(__file__).parent / "taxonomy"
VALUE = {"0": 0.0, "partial": 0.5, "full": 1.0}
LABEL = {"0": "none", "partial": "partial", "full": "full"}
# One-hue ordinal ramp (validated: monotone lightness, light end >= 2:1 on the surface);
# "none" is the neutral gray that reads as absence. Every cell also carries a text label.
FILL = {"full": "#2a78d6", "partial": "#86b6ef", "0": "#f0efec"}
INK = {"full": "#ffffff", "partial": "#0b0b0b", "0": "#52514e"}
SURFACE, TEXT, MUTED, EDGE = "#fcfcfb", "#0b0b0b", "#52514e", "#c3c2b7"


def load():
    features = list(csv.DictReader((HERE / "taxonomy.csv").open()))
    proposals = list(csv.DictReader((HERE / "proposals.csv").open()))
    problems = []
    for f in features:
        for col in ["trusttrail_suggested", "trusttrail_score"] + [f"P{i}_score" for i in range(1, 5)]:
            v = f[col].strip().lower()
            if v not in ("", *VALUE):
                problems.append(f"{f['feature_id']}.{col} = {f[col]!r} (use 0, partial or full)")
            f[col] = v
    if problems:
        sys.exit("Invalid scores:\n  " + "\n  ".join(problems))
    return features, proposals


def column(features, key, fallback=None):
    """[(score or '', is_suggestion)] for one system."""
    out = []
    for f in features:
        if f[key]:
            out.append((f[key], False))
        elif fallback and f[fallback]:
            out.append((f[fallback], True))
        else:
            out.append(("", False))
    return out


def main():
    features, proposals = load()
    systems = [("TrustTrail", column(features, "trusttrail_score", "trusttrail_suggested"))]
    systems += [(p["short_name"], column(features, f"{p['proposal_id']}_score")) for p in proposals]
    rows = [f["feature"].removeprefix("DRAFT: ") for f in features]
    draft = any(f["feature"].startswith("DRAFT") for f in features)

    n_rows, n_cols = len(rows), len(systems)
    fig, ax = plt.subplots(figsize=(2.2 + 1.45 * n_cols + 2.4, 1.6 + 0.5 * n_rows), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    gap = 0.04   # surface gap between cells
    for c, (_, scores) in enumerate(systems):
        for r, (score, suggested) in enumerate(scores):
            y = n_rows - 1 - r
            if score:
                ax.add_patch(Rectangle((c + gap, y + gap), 1 - 2 * gap, 1 - 2 * gap, facecolor=FILL[score],
                                       edgecolor=EDGE if suggested else "none", linewidth=0.6,
                                       hatch="///" if suggested else None))
                ax.text(c + 0.5, y + 0.5, LABEL[score] + ("*" if suggested else ""), ha="center", va="center",
                        fontsize=9, color=INK[score],
                        bbox=dict(boxstyle="round,pad=0.15", fc=FILL[score], ec="none") if suggested else None)
            else:
                ax.add_patch(Rectangle((c + gap, y + gap), 1 - 2 * gap, 1 - 2 * gap, facecolor=SURFACE,
                                       edgecolor=EDGE, linewidth=0.8, linestyle=(0, (3, 2))))
                ax.text(c + 0.5, y + 0.5, "not scored", ha="center", va="center", fontsize=8, color=MUTED)
        # Coverage per system: full = 1, partial = 0.5, out of the number of features.
        scored = [s for s, _ in scores if s]
        total = (f"{sum(VALUE[s] for s in scored):.1f} / {n_rows}" if len(scored) == n_rows
                 else f"{len(scored)}/{n_rows} scored")
        if any(sug for _, sug in scores):
            total += "*"
        ax.text(c + 0.5, -0.45, total, ha="center", va="center", fontsize=9, color=TEXT)

    ax.set_xlim(0, n_cols)
    ax.set_ylim(-0.8, n_rows)
    ax.set_xticks([c + 0.5 for c in range(n_cols)], [name for name, _ in systems], fontsize=9, color=TEXT)
    ax.xaxis.tick_top()
    ax.set_yticks([n_rows - 1 - r + 0.5 for r in range(n_rows)] + [-0.45], rows + ["Coverage"],
                  fontsize=9, color=TEXT)
    ax.tick_params(length=0)
    for side in ax.spines.values():
        side.set_visible(False)

    legend = [Patch(facecolor=FILL["full"], label="full"), Patch(facecolor=FILL["partial"], label="partial"),
              Patch(facecolor=FILL["0"], label="none"),
              Patch(facecolor=SURFACE, edgecolor=EDGE, linestyle="--", label="not scored")]
    ax.legend(handles=legend, loc="upper left", bbox_to_anchor=(1.01, 1.0), frameon=False, fontsize=9,
              labelcolor=TEXT, title="Score", title_fontsize=9)

    title = "Privacy features: TrustTrail vs. the authors' four proposals"
    fig.suptitle(title, x=0.02, ha="left", fontsize=12, color=TEXT, fontweight="bold")
    notes = []
    if any(s for _, scores in systems[:1] for _, s in scores):
        notes.append("* TrustTrail: builder's suggestion, not yet scored by a teammate who didn't build the feature.")
    if draft:
        notes.append("Feature names are a DRAFT; replace them with the paper's nine features.")
    notes.append("Coverage: full = 1, partial = 0.5.")
    fig.text(0.02, 0.01, "\n".join(notes), fontsize=8, color=MUTED, ha="left", va="bottom")
    fig.tight_layout(rect=(0, 0.03 + 0.025 * len(notes), 1, 0.95))

    RESULTS.mkdir(exist_ok=True)
    for ext in ("png", "svg"):
        fig.savefig(RESULTS / f"taxonomy_chart.{ext}", dpi=200, facecolor=SURFACE)
    print(f"Saved eval/results/taxonomy_chart.png and .svg")

    todo = [f"{f['feature_id']} {name}" for name, scores in systems for f, (s, sug) in zip(features, scores)
            if not s or sug]
    if draft or todo:
        print(f"\nStill to do: {len(todo)} cell(s) unscored or only suggested"
              + ("; feature list is still the draft" if draft else "") + ".")
    print("Reminder: each feature's TrustTrail score should come from a teammate who did NOT build it;\n"
          "record who in trusttrail_scored_by. Score the authors' proposals from the paper, with evidence.")


if __name__ == "__main__":
    main()
