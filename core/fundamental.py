"""
fundamental.py
--------------
Fundamental analysis: is the BUSINESS financially healthy? Scored across
three horizons, each using different metrics -- short-term reacts to
recent results and analyst sentiment, medium-term looks at valuation and
profitability, long-term looks at multi-year growth and balance-sheet
strength.

Every metric is converted into a score from -100 (very bearish signal)
to +100 (very bullish signal) using simple, commented thresholds from
standard equity analysis. If a metric isn't available for a company
(Yahoo Finance doesn't have everything for every stock), it's skipped --
the horizon score is the average of whatever metrics ARE available.
"""

from __future__ import annotations


def _band(value, thresholds):
    """thresholds: list of (minimum_value, score), sorted highest first.
    Returns the score for the first threshold the value meets or beats."""
    for minimum, score in thresholds:
        if value >= minimum:
            return score
    return thresholds[-1][1]


def _avg(scores: dict):
    """Average of whatever scores aren't None. Returns (score, count)."""
    available = [v for v in scores.values() if v is not None]
    if not available:
        return None, 0
    return round(sum(available) / len(available)), len(available)


# ---------------- individual metric scorers (-100 to +100) ----------------

def score_recommendation(mean_rating):
    # yfinance recommendationMean: 1.0 = Strong Buy ... 5.0 = Strong Sell
    if mean_rating is None:
        return None
    return _band(-mean_rating, [
        (-1.5, 90),   # rating <= 1.5 (Strong Buy / Buy)
        (-2.5, 50),   # rating <= 2.5 (Buy-ish)
        (-3.2, 0),    # rating <= 3.2 (Hold)
        (-4.0, -50),  # rating <= 4.0 (Underperform)
        (-999, -90),  # worse than that (Sell)
    ])


def score_target_upside(current_price, target_mean_price):
    if not current_price or not target_mean_price:
        return None
    upside_pct = (target_mean_price / current_price - 1) * 100
    return _band(upside_pct, [
        (25, 90), (12, 55), (3, 20), (-5, -10), (-15, -50), (-1e9, -90),
    ])


def score_earnings_growth(growth):
    # yfinance earningsGrowth is typically latest-quarter YoY.
    if growth is None:
        return None
    pct = growth * 100
    return _band(pct, [
        (25, 90), (10, 55), (0, 20), (-10, -20), (-25, -60), (-1e9, -90),
    ])


def score_pe_ratio(pe):
    if pe is None or pe <= 0:
        return None
    return _band(-pe, [
        (-15, 70), (-22, 40), (-30, 0), (-45, -40), (-1e9, -80),
    ])


def score_pb_ratio(pb):
    if pb is None or pb <= 0:
        return None
    return _band(-pb, [
        (-2, 60), (-4, 25), (-7, -10), (-1e9, -50),
    ])


def score_roe(roe):
    if roe is None:
        return None
    pct = roe * 100
    return _band(pct, [
        (22, 90), (16, 60), (10, 25), (5, -5), (0, -40), (-1e9, -80),
    ])


def score_profit_margin(margin):
    if margin is None:
        return None
    pct = margin * 100
    return _band(pct, [
        (20, 90), (12, 55), (6, 20), (2, -10), (0, -40), (-1e9, -80),
    ])


def score_revenue_growth(growth):
    if growth is None:
        return None
    pct = growth * 100
    return _band(pct, [
        (18, 90), (10, 55), (4, 20), (0, -10), (-10, -50), (-1e9, -85),
    ])


def score_debt_to_equity(de):
    if de is None:
        return None
    return _band(-de, [
        (-30, 70), (-70, 35), (-120, -10), (-200, -50), (-1e9, -85),
    ])


def score_dividend_yield(yield_pct):
    # A modest, healthy dividend is a mild positive; this is a small
    # signal, not a dominant one -- weighted implicitly by just being
    # one of several metrics averaged together.
    if yield_pct is None:
        return None
    pct = yield_pct * 100 if yield_pct < 1 else yield_pct
    return _band(pct, [(4, 40), (1.5, 25), (0.3, 10), (0, 0)])


def score_free_cash_flow(fcf):
    if fcf is None:
        return None
    return 60 if fcf > 0 else -60


def score_revenue_cagr(cagr_pct):
    if cagr_pct is None:
        return None
    return _band(cagr_pct, [
        (15, 90), (8, 55), (3, 20), (0, -15), (-1e9, -60),
    ])


# ---------------- horizon builders ----------------

def short_term(info: dict, financials: dict):
    """0-3 months: analyst sentiment + target price + latest earnings momentum."""
    current_price = info.get("currentPrice") or info.get("regularMarketPrice")
    metrics = {
        "Analyst Recommendation": score_recommendation(info.get("recommendationMean")),
        "Target Price Upside": score_target_upside(current_price, info.get("targetMeanPrice")),
        "Latest Earnings Growth (YoY)": score_earnings_growth(info.get("earningsGrowth")),
    }
    score, n = _avg(metrics)
    raw = {
        "Recommendation": info.get("recommendationKey", "n/a"),
        "Target Mean Price": info.get("targetMeanPrice"),
        "Current Price": current_price,
        "Earnings Growth (YoY)": _pct(info.get("earningsGrowth")),
    }
    return {"score": score, "metrics": metrics, "raw": raw, "coverage": n}


def medium_term(info: dict, financials: dict):
    """3-12 months: valuation + profitability + revenue growth."""
    metrics = {
        "P/E Ratio": score_pe_ratio(info.get("trailingPE")),
        "P/B Ratio": score_pb_ratio(info.get("priceToBook")),
        "Return on Equity": score_roe(info.get("returnOnEquity")),
        "Profit Margin": score_profit_margin(info.get("profitMargins")),
        "Revenue Growth (YoY)": score_revenue_growth(info.get("revenueGrowth")),
    }
    score, n = _avg(metrics)
    raw = {
        "P/E Ratio": info.get("trailingPE"),
        "P/B Ratio": info.get("priceToBook"),
        "Return on Equity": _pct(info.get("returnOnEquity")),
        "Profit Margin": _pct(info.get("profitMargins")),
        "Revenue Growth": _pct(info.get("revenueGrowth")),
    }
    return {"score": score, "metrics": metrics, "raw": raw, "coverage": n}


def long_term(info: dict, financials: dict):
    """1-3+ years: balance sheet strength + multi-year growth + cash generation."""
    revenue_cagr = _compute_revenue_cagr(financials.get("annual_financials"))
    metrics = {
        "Debt to Equity": score_debt_to_equity(info.get("debtToEquity")),
        "3-4 Year Revenue CAGR": score_revenue_cagr(revenue_cagr),
        "Free Cash Flow": score_free_cash_flow(info.get("freeCashflow")),
        "Dividend Yield": score_dividend_yield(info.get("dividendYield")),
    }
    score, n = _avg(metrics)
    raw = {
        "Debt to Equity": info.get("debtToEquity"),
        "Revenue CAGR (multi-year)": f"{revenue_cagr:.1f}%" if revenue_cagr is not None else "n/a",
        "Free Cash Flow": info.get("freeCashflow"),
        "Dividend Yield": _pct(info.get("dividendYield")),
    }
    return {"score": score, "metrics": metrics, "raw": raw, "coverage": n}


def _compute_revenue_cagr(annual_financials):
    """Compound Annual Growth Rate of Total Revenue across however many
    years of annual statements Yahoo Finance provides (usually 3-4)."""
    if annual_financials is None:
        return None
    try:
        row = None
        for candidate in ("Total Revenue", "TotalRevenue"):
            if candidate in annual_financials.index:
                row = annual_financials.loc[candidate]
                break
        if row is None:
            return None
        values = row.dropna().values
        if len(values) < 2:
            return None
        oldest, newest = float(values[-1]), float(values[0])
        years = len(values) - 1
        if oldest <= 0 or years <= 0:
            return None
        cagr = ((newest / oldest) ** (1 / years) - 1) * 100
        return cagr
    except Exception:
        return None


def _pct(value):
    if value is None:
        return "n/a"
    v = value * 100 if abs(value) < 5 else value  # heuristic: yfinance ratios are usually fractions
    return f"{v:.1f}%"


def analyze(info: dict, financials: dict):
    """Runs all three horizons and returns the combined fundamental pillar."""
    short = short_term(info, financials)
    medium = medium_term(info, financials)
    long_ = long_term(info, financials)

    horizon_scores = [h["score"] for h in (short, medium, long_) if h["score"] is not None]
    overall = round(sum(horizon_scores) / len(horizon_scores)) if horizon_scores else 0

    return {
        "overall_score": overall,
        "short_term": short,
        "medium_term": medium,
        "long_term": long_,
    }
