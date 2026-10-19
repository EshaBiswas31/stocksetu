"""
scoring.py
----------
Combines the three pillars (Fundamental, Technical, Quantitative) into
one final score from -100 (extremely bearish) to +100 (extremely
bullish), and explains WHY it landed there.

Two ideas live here, both kept deliberately simple so they're easy to
explain in a viva:

1. RISK PROFILES. Not every investor cares about the same horizon. A
   day trader barely cares about 3-year revenue growth; a long-term
   investor barely cares about today's RSI. Instead of always averaging
   fundamental/technical/quant equally, each profile gives its own
   weights to (a) the three pillars and (b) the three horizons inside
   each pillar. Changing the profile re-weights the SAME underlying
   signals -- nothing is re-invented, just re-emphasised.

2. DRIVERS ("why this score"). Every metric in fundamental.py,
   technical.py and quant.py already scores itself from -100 to +100
   (e.g. "RSI: -45", "P/E Ratio: +60"). To explain the final number, we
   simply collect every one of those individual metric scores across all
   three pillars and all horizons, and show the handful that pushed the
   score up the most and down the most. No hidden maths -- the "drivers"
   are literally the biggest numbers already computed elsewhere.
"""

from __future__ import annotations

# ---------------------------------------------------------------------
# Risk profiles: pillar weights, and horizon weights *within* each pillar.
# All weights in a group sum to 1.0 (they don't have to -- combine()
# re-normalises using whatever horizons/pillars actually have data --
# but keeping them summing to 1 makes the numbers easy to read).
# ---------------------------------------------------------------------
PROFILES = {
    "trader": {
        "label": "Trader (short-term)",
        "pillars": {"fundamental": 0.15, "technical": 0.50, "quant": 0.35},
        "fundamental": {"short_term": 0.50, "medium_term": 0.30, "long_term": 0.20},
        "technical": {"intraday": 0.45, "weekly": 0.35, "monthly": 0.20},
        "quant": {"intraday": 0.45, "weekly": 0.35, "monthly": 0.20},
    },
    "balanced": {
        "label": "Balanced",
        "pillars": {"fundamental": 0.35, "technical": 0.35, "quant": 0.30},
        "fundamental": {"short_term": 0.25, "medium_term": 0.35, "long_term": 0.40},
        "technical": {"intraday": 0.20, "weekly": 0.35, "monthly": 0.45},
        "quant": {"intraday": 0.20, "weekly": 0.35, "monthly": 0.45},
    },
    "investor": {
        "label": "Investor (long-term)",
        "pillars": {"fundamental": 0.60, "technical": 0.20, "quant": 0.20},
        "fundamental": {"short_term": 0.15, "medium_term": 0.35, "long_term": 0.50},
        "technical": {"intraday": 0.05, "weekly": 0.30, "monthly": 0.65},
        "quant": {"intraday": 0.05, "weekly": 0.30, "monthly": 0.65},
    },
}
DEFAULT_PROFILE = "balanced"


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


def _weighted_average(horizon_scores: dict, weights: dict):
    """Weighted average of whatever horizons actually have a score.
    A horizon with no data (score is None, e.g. intraday data wasn't
    available for this symbol) is simply left out and the remaining
    weights are re-normalised -- it does not drag the score toward
    zero."""
    num, den = 0.0, 0.0
    for horizon, weight in weights.items():
        score = horizon_scores.get(horizon)
        if score is None:
            continue
        num += score * weight
        den += weight
    if den == 0:
        return None
    return round(num / den)


def _pillar_score(pillar_result: dict, horizon_keys: list[str], weights: dict):
    horizon_scores = {h: pillar_result[h].get("score") for h in horizon_keys}
    return _weighted_average(horizon_scores, weights)


def combine(fundamental: dict, technical: dict, quant: dict, profile_name: str = DEFAULT_PROFILE) -> dict:
    profile = PROFILES.get(profile_name, PROFILES[DEFAULT_PROFILE])

    f_score = _pillar_score(fundamental, ["short_term", "medium_term", "long_term"], profile["fundamental"])
    t_score = _pillar_score(technical, ["intraday", "weekly", "monthly"], profile["technical"])
    q_score = _pillar_score(quant, ["intraday", "weekly", "monthly"], profile["quant"])

    overall = _weighted_average(
        {"fundamental": f_score, "technical": t_score, "quant": q_score},
        profile["pillars"],
    )
    overall = overall if overall is not None else 0
    label = overall_label(overall)

    pillar_scores = {"fundamental": f_score, "technical": t_score, "quant": q_score}
    drivers = _top_drivers(fundamental, technical, quant)
    rationale = _build_rationale(overall, label, pillar_scores, drivers)

    return {
        "overall_score": overall,
        "label": label,
        "rationale": rationale,
        "pillar_scores": pillar_scores,
        "drivers": drivers,
        "profile": profile_name,
        "profile_label": profile["label"],
    }


# ---------------------------------------------------------------------
# "Why this score": the strongest individual signals, good and bad,
# pulled from every horizon of every pillar.
# ---------------------------------------------------------------------

_PILLAR_LABEL = {"fundamental": "Fundamental", "technical": "Technical", "quant": "Quantitative"}
_HORIZON_LABEL = {
    "short_term": "Short-term", "medium_term": "Medium-term", "long_term": "Long-term",
    "intraday": "Intraday", "weekly": "Weekly", "monthly": "Monthly",
}


def _top_drivers(fundamental: dict, technical: dict, quant: dict, n: int = 4):
    """Flattens every scored metric from all three pillars into one list,
    then returns the n strongest positive (bullish) and n strongest
    negative (bearish) signals, sorted by how extreme they are."""
    all_metrics = []
    for pillar_name, pillar_result, horizon_keys in (
        ("fundamental", fundamental, ["short_term", "medium_term", "long_term"]),
        ("technical", technical, ["intraday", "weekly", "monthly"]),
        ("quant", quant, ["intraday", "weekly", "monthly"]),
    ):
        for horizon_key in horizon_keys:
            horizon = pillar_result.get(horizon_key) or {}
            for metric_name, score in (horizon.get("metrics") or {}).items():
                if score is None:
                    continue
                all_metrics.append({
                    "metric": metric_name,
                    "score": round(score),
                    "pillar": _PILLAR_LABEL[pillar_name],
                    "horizon": _HORIZON_LABEL[horizon_key],
                })

    positives = sorted([m for m in all_metrics if m["score"] > 0], key=lambda m: -m["score"])[:n]
    negatives = sorted([m for m in all_metrics if m["score"] < 0], key=lambda m: m["score"])[:n]
    return {"positive": positives, "negative": negatives}


def _build_rationale(overall, label, pillar_scores, drivers) -> str:
    def describe(name, val):
        if val is None:
            return f"no usable {name} data"
        if val >= 40:
            return f"strongly supportive {name}"
        if val >= 15:
            return f"mildly supportive {name}"
        if val > -15:
            return f"neutral {name}"
        if val > -40:
            return f"mildly negative {name}"
        return f"strongly negative {name}"

    f, t, q = pillar_scores["fundamental"], pillar_scores["technical"], pillar_scores["quant"]
    parts = [describe("fundamentals", f), describe("technical signals", t), describe("quantitative signals", q)]
    sentence1 = f"The overall outlook is {label.lower()} ({overall:+d}), built from {parts[0]}, {parts[1]}, and {parts[2]}."

    top_pos = drivers["positive"][0]["metric"] if drivers["positive"] else None
    top_neg = drivers["negative"][0]["metric"] if drivers["negative"] else None
    if top_pos and top_neg:
        sentence2 = f"The strongest bullish signal is {top_pos}; the strongest bearish signal is {top_neg}."
    elif top_pos:
        sentence2 = f"The strongest signal overall is {top_pos}, and it is bullish."
    elif top_neg:
        sentence2 = f"The strongest signal overall is {top_neg}, and it is bearish."
    else:
        sentence2 = "No single signal dominates -- this score reflects many small, roughly balanced factors."

    return sentence1 + " " + sentence2
