"""
quant.py
--------
Quantitative analysis: statistical / risk-based view of recent price
behaviour, independent of "is this a good business" (that's fundamental)
and independent of chart patterns (that's technical). Same three
horizons: Intraday, Weekly, Monthly -- using the same three price series
as technical.py, just looked at through momentum, volatility, risk-
adjusted return and statistical unusualness instead of moving-average
crossovers.
"""

from __future__ import annotations
import pandas as pd

from core import indicators as ind


def _band(value, thresholds):
    for minimum, score in thresholds:
        if value >= minimum:
            return score
    return thresholds[-1][1]


def _avg(scores: dict):
    available = [v for v in scores.values() if v is not None]
    if not available:
        return None, 0
    return round(sum(available) / len(available)), len(available)


# ---------------- metric scorers ----------------

def score_momentum(pct_return):
    if pct_return is None:
        return None
    return _band(pct_return, [
        (15, 85), (6, 55), (1, 20), (-1, -10), (-6, -50), (-1e9, -85),
    ])


def score_volatility(annualized_vol_pct):
    # Lower volatility = steadier, lower-risk price behaviour -> mildly
    # positive; very high volatility is a risk flag, not outright bearish.
    if annualized_vol_pct is None:
        return None
    return _band(-annualized_vol_pct, [
        (-20, 30), (-40, 10), (-70, -15), (-1e9, -40),
    ])


def score_sharpe(sharpe):
    if sharpe is None:
        return None
    return _band(sharpe, [
        (1.5, 85), (0.8, 55), (0.2, 20), (-0.2, -10), (-0.8, -50), (-1e9, -85),
    ])


def score_zscore(z):
    """A big recent move (far from the recent average) in either
    direction gets flagged -- strongly positive z = strong recent
    outperformance (bullish momentum), strongly negative = sharp
    recent weakness."""
    if z is None:
        return None
    return _band(z, [
        (1.5, 60), (0.5, 25), (-0.5, -5), (-1.5, -40), (-1e9, -65),
    ])


# ---------------- horizon builder ----------------

def _analyze_horizon(df: pd.DataFrame, bars_back_for_momentum, bars_per_year, label: str):
    if df is None or len(df) < 15:
        return {
            "score": None, "available": False,
            "reason": f"Not enough {label.lower()} data available for this symbol.",
        }

    close = df["Close"]
    pct_ret = ind.pct_return(close, min(bars_back_for_momentum, len(close) - 1))
    vol = ind.annualized_volatility(close, bars_per_year)
    sharpe = ind.sharpe_like_ratio(close, bars_per_year)
    z = ind.z_score_last_move(close, lookback=min(20, len(close) - 2))

    metrics = {
        "Momentum": score_momentum(pct_ret),
        "Volatility": score_volatility(vol),
        "Risk-Adjusted Return (Sharpe-like)": score_sharpe(sharpe),
        "Recent Move Z-Score": score_zscore(z),
    }
    score, coverage = _avg(metrics)

    return {
        "score": score,
        "available": True,
        "metrics": metrics,
        "raw": {
            "Return over period": f"{pct_ret:.2f}%" if pct_ret is not None else "n/a",
            "Annualized Volatility": f"{vol:.1f}%" if vol is not None else "n/a",
            "Sharpe-like Ratio": f"{sharpe:.2f}" if sharpe is not None else "n/a",
            "Z-Score of Last Move": f"{z:.2f}" if z is not None else "n/a",
        },
        "coverage": coverage,
    }


def intraday(intraday_df):
    """Momentum/volatility over the last ~2 hours of 5-min bars (24 bars)."""
    return _analyze_horizon(intraday_df, bars_back_for_momentum=24, bars_per_year=252 * 75, label="intraday")


def weekly(daily_df):
    """Momentum/volatility over the last 20 trading days (~1 month) of daily bars."""
    return _analyze_horizon(daily_df, bars_back_for_momentum=20, bars_per_year=252, label="daily")


def monthly(weekly_df):
    """Momentum/volatility over the last 12 weeks (~3 months) of weekly bars."""
    return _analyze_horizon(weekly_df, bars_back_for_momentum=12, bars_per_year=52, label="weekly")


def analyze(intraday_df, daily_df, weekly_df):
    i = intraday(intraday_df)
    w = weekly(daily_df)
    m = monthly(weekly_df)

    horizon_scores = [h["score"] for h in (i, w, m) if h.get("score") is not None]
    overall = round(sum(horizon_scores) / len(horizon_scores)) if horizon_scores else 0

    return {
        "overall_score": overall,
        "intraday": i,
        "weekly": w,
        "monthly": m,
    }
