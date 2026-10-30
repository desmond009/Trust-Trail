"""Shared helpers for the evaluation scripts: result files and Markdown tables."""
import csv
import statistics
from datetime import datetime, timezone
from pathlib import Path

RESULTS = Path(__file__).parent / "results"


def percentile(values: list[float], p: float) -> float:
    """Nearest-rank percentile (p in 0-100), the usual definition for latency reports."""
    s = sorted(values)
    rank = max(1, -(-len(s) * p // 100))   # ceil(n * p / 100)
    return s[int(rank) - 1]


def summarise(values: list[float]) -> dict:
    return {"n": len(values), "median": statistics.median(values), "p95": percentile(values, 95),
            "mean": statistics.mean(values), "min": min(values), "max": max(values)}


def markdown_table(header: list[str], rows: list[list]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join(lines)


def write_csv(name: str, header: list[str], rows: list[list]) -> Path:
    RESULTS.mkdir(exist_ok=True)
    path = RESULTS / name
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    return path


def write_markdown(name: str, title: str, body: str) -> Path:
    RESULTS.mkdir(exist_ok=True)
    path = RESULTS / name
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    path.write_text(f"# {title}\n\n_Generated {stamp} by `{Path(name).stem}`; fake data, local machine._\n\n{body}\n")
    return path
