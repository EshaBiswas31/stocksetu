"""
scoring.py
----------
Combines the three pillars (Fundamental, Technical, Quantitative) into
one final score from -100 (extremely bearish) to +100 (extremely
bullish), and writes a short plain-English rationale.

The three pillars are weighted equally and simply averaged -- this keeps
the combination step easy to explain and reproduce by hand, rather than
hiding behind an opaque weighting scheme.
"""

from __future__ import annotations


def overall_label(score: float) -> str:
    if score >= 60:
        return "Strong Bullish"
    if score >= 20:
        return "Bullish"
    if score > -20:
        return "Neutral"
    if score > -60:
        return "Bearish"
    return "Strong Bearish"


def combine(fundamental: dict, technical: dict, quant: dict) -> dict:
    scores = [fundamental["overall_score"], technical["overall_score"], quant["overall_score"]]
    overall = round(sum(scores) / len(scores))
    label = overall_label(overall)

    rationale = _build_rationale(overall, label, fundamental, technical, quant)

    return {
        "overall_score": overall,
        "label": label,
        "rationale": rationale,
        "pillar_scores": {
            "fundamental": fundamental["overall_score"],
            "technical": technical["overall_score"],
            "quant": quant["overall_score"],
        },
    }


def _build_rationale(overall, label, fundamental, technical, quant) -> str:
    f, t, q = fundamental["overall_score"], technical["overall_score"], quant["overall_score"]

    pillars_desc = []
    for name, val in [("fundamentals", f), ("technical signals", t), ("quantitative signals", q)]:
        if val >= 40:
            pillars_desc.append(f"strongly supportive {name}")
        elif val >= 15:
            pillars_desc.append(f"mildly supportive {name}")
        elif val > -15:
            pillars_desc.append(f"neutral {name}")
        elif val > -40:
            pillars_desc.append(f"mildly negative {name}")
        else:
            pillars_desc.append(f"strongly negative {name}")

    # Find the strongest driver and the weakest driver to call out by name.
    labelled = [("fundamentals", f), ("technical signals", t), ("quantitative signals", q)]
    best = max(labelled, key=lambda x: x[1])
    worst = min(labelled, key=lambda x: x[1])

    sentence1 = (
        f"The overall outlook is {label.lower()} ({overall:+d}), built from "
        f"{pillars_desc[0]}, {pillars_desc[1]}, and {pillars_desc[2]}."
    )

    if best[1] - worst[1] >= 25:
        sentence2 = (
            f"The strongest driver is {best[0]} ({best[1]:+d}), while {worst[0]} "
            f"({worst[1]:+d}) is the main drag on the score."
        )
    else:
        sentence2 = "All three pillars are broadly aligned, which adds confidence to this view."

    return sentence1 + " " + sentence2
