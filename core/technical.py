"""
technical.py
------------
THE CENTERPIECE OF THIS PROJECT. Technical analysis is scored across
three horizons (Intraday, Weekly, Monthly), and at every horizon the
actual crossover signals -- price crossing a moving average, a fast
average crossing a slow average -- are found using the Line Segment
Intersection sweep-line algorithm in sweep_line.py, NOT a simple day-by-
day comparison loop.

Each horizon uses a different pair of moving averages, appropriate to
that timeframe:
  Intraday (5-min bars) -> EMA9 / EMA21   (fast, reacts quickly)
  Weekly   (daily bars) -> SMA20 / SMA50
  Monthly  (weekly bars) -> SMA10 / SMA40  (roughly 10 weeks / 40 weeks,
                                            the weekly-bar equivalent of
                                            the classic 50/200-day cross)

For each horizon we report:
  - "algorithm_stats": how many line segments were built and how many
    crossings the sweep-line algorithm found -- shown on the frontend so
    the algorithm's work is visible, not hidden inside a black box.
  - the most recent crossover and how many bars ago it happened
  - RSI and MACD as supporting indicators
  - a combined score from -100 to +100
"""

from __future__ import annotations
import pandas as pd

from core import indicators as ind
from core.sweep_line import detect_crossovers, segments_from_series


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

def score_price_vs_ma(close_last, ma_last):
    if ma_last is None or pd.isna(ma_last):
        return None
    return 55 if close_last > ma_last else -55


def score_ma_cross_state(fast_last, slow_last):
    """Is the fast average currently above the slow average (bullish
    "golden cross" state) or below (bearish "death cross" state)?"""
    if fast_last is None or slow_last is None or pd.isna(fast_last) or pd.isna(slow_last):
        return None
    return 70 if fast_last > slow_last else -70


def score_crossover_recency(events, total_bars, recent_window_frac=0.08):
    """If the most recent crossover happened recently (within the last
    ~8% of the available bars), its direction is a strong signal -- a
    crossover from weeks ago matters less than one from yesterday."""
    if not events:
        return 0
    last_event = events[-1]
    bars_ago = total_bars - last_event["x"]
    window = max(2, total_bars * recent_window_frac)
    if bars_ago > window:
        return 0
    closeness = 1 - (bars_ago / window)  # 1.0 = just happened, 0.0 = at the edge of the window
    magnitude = 60 * closeness
    return magnitude if last_event["direction"] == "bullish" else -magnitude


def score_rsi(rsi_value):
    if rsi_value is None or pd.isna(rsi_value):
        return None
    if 45 <= rsi_value <= 60:
        return 30       # healthy upward bias
    if 60 < rsi_value <= 70:
        return 55       # strong momentum, not yet overbought
    if rsi_value > 70:
        return -20       # overbought -- risk of pullback
    if 40 <= rsi_value < 45:
        return -5
    if 30 <= rsi_value < 40:
        return -45
    return -70            # < 30, oversold / weak


def score_macd(histogram_last):
    if histogram_last is None or pd.isna(histogram_last):
        return None
    return 50 if histogram_last > 0 else -50


# ---------------- horizon builder (shared by all three horizons) ----------------

def _analyze_horizon(df: pd.DataFrame, fast_window, slow_window, ma_kind: str, bars_per_year: int, label: str):
    if df is None or len(df) < slow_window + 5:
        return {
            "score": None, "available": False,
            "reason": f"Not enough {label.lower()} data available for this symbol.",
        }

    close = df["Close"]
    if ma_kind == "ema":
        fast_ma = ind.ema(close, fast_window)
        slow_ma = ind.ema(close, slow_window)
    else:
        fast_ma = ind.sma(close, fast_window)
        slow_ma = ind.sma(close, slow_window)

    rsi_series = ind.rsi(close)
    macd_line, signal_line, hist = ind.macd(close)

    # ---- THE ALGORITHM: find every crossing using the sweep-line method ----
    price_fast_events = detect_crossovers(close.tolist(), "Price", fast_ma.tolist(), "FastMA")
    fast_slow_events = detect_crossovers(fast_ma.tolist(), "FastMA", slow_ma.tolist(), "SlowMA")

    n_segments = (len(segments_from_series(close.tolist(), "Price"))
                  + len(segments_from_series(fast_ma.tolist(), "FastMA"))
                  + len(segments_from_series(slow_ma.tolist(), "SlowMA")))
    n_crossings = len(price_fast_events) + len(fast_slow_events)

    metrics = {
        "Price vs Fast Average": score_price_vs_ma(close.iloc[-1], fast_ma.iloc[-1]),
        "Fast vs Slow Average": score_ma_cross_state(fast_ma.iloc[-1], slow_ma.iloc[-1]),
        "Recent Crossover": score_crossover_recency(price_fast_events + fast_slow_events, len(close)),
        "RSI": score_rsi(rsi_series.iloc[-1]),
        "MACD": score_macd(hist.iloc[-1]),
    }
    score, coverage = _avg(metrics)

    last_price_fast = price_fast_events[-1] if price_fast_events else None
    last_fast_slow = fast_slow_events[-1] if fast_slow_events else None

    return {
        "score": score,
        "available": True,
        "metrics": metrics,
        "raw": {
            "Last Price": round(float(close.iloc[-1]), 2),
            "Fast Average": round(float(fast_ma.iloc[-1]), 2) if not pd.isna(fast_ma.iloc[-1]) else None,
            "Slow Average": round(float(slow_ma.iloc[-1]), 2) if not pd.isna(slow_ma.iloc[-1]) else None,
            "RSI": round(float(rsi_series.iloc[-1]), 1) if not pd.isna(rsi_series.iloc[-1]) else None,
            "MACD Histogram": round(float(hist.iloc[-1]), 3) if not pd.isna(hist.iloc[-1]) else None,
        },
        "algorithm_stats": {
            "segments_built": n_segments,
            "crossings_found": n_crossings,
        },
        "last_price_vs_fast_crossover": last_price_fast,
        "last_fast_vs_slow_crossover": last_fast_slow,
        "coverage": coverage,
    }


def intraday(intraday_df):
    """EMA9 / EMA21 on 5-minute bars."""
    return _analyze_horizon(intraday_df, 9, 21, "ema", bars_per_year=252 * 75, label="intraday")


def weekly(daily_df):
    """SMA20 / SMA50 on daily bars -- the 'weekly outlook' horizon."""
    return _analyze_horizon(daily_df, 20, 50, "sma", bars_per_year=252, label="daily")


def monthly(weekly_df):
    """SMA10 / SMA40 on weekly bars -- the 'monthly outlook' horizon,
    the weekly-bar equivalent of the classic 50/200-day cross."""
    return _analyze_horizon(weekly_df, 10, 40, "sma", bars_per_year=52, label="weekly")


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
