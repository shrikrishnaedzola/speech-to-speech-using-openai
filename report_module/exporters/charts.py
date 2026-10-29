"""matplotlib charts for the PDF (the web page draws the same charts with Recharts).

Colours (reference data-viz palette):
- status:  good #0ca30c, warning #fab219 (OK), critical #d03b3b (Poor) - always with a label
- series:  STT #2a78d6 (blue), LLM #eb6834 (orange), TTS #1baf7a (aqua) - validated order
- single-series bars: blue #2a78d6
"""
import base64
import io

import matplotlib

matplotlib.use("Agg")  # no screen needed
import matplotlib.pyplot as plt  # noqa: E402

STATUS = {"Good": "#0ca30c", "OK": "#fab219", "Poor": "#d03b3b"}
SERIES = {"STT": "#2a78d6", "LLM": "#eb6834", "TTS": "#1baf7a"}
BLUE = "#2a78d6"
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"


def _style(ax):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def _to_data_uri(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=160, bbox_inches="tight")
    plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def score_parts_chart(parts: dict, labels: dict) -> str:
    names = [labels[k] for k in parts]
    values = [v if v is not None else 0 for v in parts.values()]
    fig, ax = plt.subplots(figsize=(6.4, 2.4))
    bars = ax.barh(names, values, color=BLUE, height=0.55, edgecolor="white", linewidth=2)
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    _style(ax)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=GRID, linewidth=0.6)
    for bar, value in zip(bars, parts.values()):
        text = "not rated" if value is None else f"{value:.0f}"
        ax.text(bar.get_width() + 1.5, bar.get_y() + bar.get_height() / 2, text, va="center", fontsize=8, color=INK)
    return _to_data_uri(fig)


def latency_chart(per_turn: list, thresholds: dict) -> str:
    turns = [t["turn"] for t in per_turn]
    values = [t["latency_ms"] for t in per_turn]
    colors = [STATUS.get(t["rating"], BLUE) for t in per_turn]
    fig, ax = plt.subplots(figsize=(6.4, 2.6))
    ax.bar(turns, values, color=colors, width=0.6, edgecolor="white", linewidth=2)
    for limit, name in ((thresholds["good"], "Good limit"), (thresholds["ok"], "OK limit")):
        ax.axhline(limit, color=MUTED, linewidth=1, linestyle=(0, (4, 3)))
        # Label outside the plot on the right, so it never covers a bar.
        ax.text(1.01, limit, f"{name}\n{limit} ms", fontsize=7, color=MUTED, va="center", ha="left",
                transform=ax.get_yaxis_transform())
    ax.set_xlabel("Turn", fontsize=8, color=MUTED)
    ax.set_ylabel("Reply time (ms)", fontsize=8, color=MUTED)
    ax.set_xticks(turns)
    _style(ax)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in STATUS.values()]
    ax.legend(handles, [f"Good < {thresholds['good']} ms", f"OK ≤ {thresholds['ok']} ms", f"Poor > {thresholds['ok']} ms"],
              fontsize=7, frameon=False, loc="upper left", ncol=3, bbox_to_anchor=(0, 1.18))
    return _to_data_uri(fig)


def stage_split_chart(per_turn: list) -> str:
    turns = [t["turn"] for t in per_turn]
    fig, ax = plt.subplots(figsize=(6.4, 2.6))
    bottom = [0.0] * len(turns)
    for stage, key in (("STT", "stt_ms"), ("LLM", "llm_ms"), ("TTS", "tts_ms")):
        values = [t.get(key) or 0 for t in per_turn]
        ax.bar(turns, values, bottom=bottom, color=SERIES[stage], width=0.6, label=stage, edgecolor="white", linewidth=2)
        bottom = [b + v for b, v in zip(bottom, values)]
    ax.set_xlabel("Turn", fontsize=8, color=MUTED)
    ax.set_ylabel("Time (ms)", fontsize=8, color=MUTED)
    ax.set_xticks(turns)
    _style(ax)
    ax.legend(fontsize=7, frameon=False, loc="upper left", ncol=3, bbox_to_anchor=(0, 1.18))
    return _to_data_uri(fig)
