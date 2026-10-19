"""
indicators.py
-------------
Small, well-known technical indicators, each implemented directly in
pandas (no extra libraries) so the formulas are visible and easy to
explain line by line.
"""

from __future__ import annotations
import numpy as np
import pandas as pd


def sma(close: pd.Series, window: int) -> pd.Series:
    """Simple Moving Average: plain average of the last `window` closes."""
    return close.rolling(window=window, min_periods=window).mean()


def ema(close: pd.Series, span: int) -> pd.Series:
    """Exponential Moving Average: like SMA, but recent prices count more."""
    return close.ewm(span=span, adjust=False, min_periods=span).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index (0-100). Above 70 = overbought,
    below 30 = oversold, near 50 = neutral momentum."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    result = 100 - (100 / (1 + rs))
    return result.fillna(100)  # if avg_loss is 0, price only went up -> RSI 100


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """Moving Average Convergence Divergence. Returns (macd_line, signal_line, histogram).
    macd_line = EMA(fast) - EMA(slow). When macd_line crosses above signal_line,
    that's a classic bullish momentum signal (and vice versa)."""
    macd_line = ema(close, fast) - ema(close, slow)
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def annualized_volatility(close: pd.Series, bars_per_year: int) -> float | None:
    """Standard deviation of returns, scaled to a yearly figure so
    different timeframes (5-min bars, daily bars, weekly bars) are
    comparable. Higher = more erratic / risky price behaviour."""
    returns = close.pct_change().dropna()
    if len(returns) < 5:
        return None
    return float(returns.std() * np.sqrt(bars_per_year) * 100)


def pct_return(close: pd.Series, bars_back: int) -> float | None:
    """Percent change from `bars_back` bars ago to the most recent bar."""
    if len(close) <= bars_back:
        return None
    return float((close.iloc[-1] / close.iloc[-bars_back - 1] - 1) * 100)


def sharpe_like_ratio(close: pd.Series, bars_per_year: int) -> float | None:
    """A simplified Sharpe ratio: average return divided by volatility of
    return, annualized. Risk-free rate is treated as 0 to keep this
    simple and explainable -- higher means steadier gains per unit of
    risk taken."""
    returns = close.pct_change().dropna()
    if len(returns) < 10 or returns.std() == 0:
        return None
    return float((returns.mean() / returns.std()) * np.sqrt(bars_per_year))


def z_score_last_move(close: pd.Series, lookback: int = 20) -> float | None:
    """How unusual is the most recent price move, in standard deviations,
    compared to the recent past? Used as a simple momentum/mean-reversion
    signal."""
    returns = close.pct_change().dropna()
    if len(returns) < lookback:
        return None
    recent = returns.iloc[-lookback:]
    if recent.std() == 0:
        return None
    return float((returns.iloc[-1] - recent.mean()) / recent.std())
