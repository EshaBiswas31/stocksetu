"""
yahoo.py
--------
Every call out to Yahoo Finance (via the `yfinance` library) lives here.

Ticker symbols need a suffix depending on exchange:
  NSE stocks  ->  "TCS.NS", "RELIANCE.NS", "INFY.NS"
  BSE stocks  ->  "TCS.BO", "RELIANCE.BO", "INFY.BO"
This module takes the plain symbol and exchange separately and builds the
correct suffix itself.

Three kinds of price history are fetched, one per analysis horizon:
  - intraday : 5-minute bars, last ~5 trading days (best-effort -- Yahoo
               Finance only keeps a short intraday history, and some
               symbols don't have intraday data at all; if it's
               unavailable we return None rather than failing the whole
               request, and the frontend shows "unavailable" for that
               section only)
  - daily    : daily bars, last 2 years (used for the "Weekly" horizon)
  - weekly   : weekly bars, last 5 years (used for the "Monthly" horizon,
               built by resampling daily bars)
"""

from __future__ import annotations
import pandas as pd
import yfinance as yf

EXCHANGE_SUFFIX = {"NSE": ".NS", "BSE": ".BO"}


def build_yahoo_symbol(symbol: str, exchange: str) -> str:
    symbol = symbol.strip().upper()
    suffix = EXCHANGE_SUFFIX.get(exchange.upper())
    if not suffix:
        raise ValueError("Exchange must be NSE or BSE")
    return symbol + suffix


def fetch_all_data(symbol: str, exchange: str) -> dict:
    """Fetches everything this project needs for one company in one go:
    company info/fundamentals, and price history at three granularities.

    Returns a dict:
      {
        "company_name": str,
        "info": dict,                  # yfinance's raw info dict
        "financials": {...},            # annual + quarterly statements
        "daily": DataFrame or None,      # ~2y of daily bars
        "weekly": DataFrame or None,      # ~5y of weekly bars
        "intraday": DataFrame or None,     # ~5d of 5-min bars (best-effort)
      }

    Raises ValueError if the symbol can't be resolved at all (i.e. no
    daily price history -- that's the one piece of data every section of
    this project depends on).
    """
    yahoo_symbol = build_yahoo_symbol(symbol, exchange)
    ticker = yf.Ticker(yahoo_symbol)

    daily = ticker.history(period="2y", interval="1d", auto_adjust=True)
    if daily is None or daily.empty:
        raise ValueError(f"No price data found for '{symbol}' on {exchange}. Check the symbol.")
    daily = daily.dropna(subset=["Close"])

    weekly = _resample_weekly(daily)

    intraday = None
    try:
        intraday = ticker.history(period="5d", interval="5m", auto_adjust=True)
        if intraday is not None and not intraday.empty:
            intraday = intraday.dropna(subset=["Close"])
        else:
            intraday = None
    except Exception:
        intraday = None

    try:
        info = ticker.info or {}
    except Exception:
        info = {}

    financials = _safe_financials(ticker)

    company_name = info.get("longName") or info.get("shortName") or symbol.upper()

    return {
        "company_name": company_name,
        "info": info,
        "financials": financials,
        "daily": daily,
        "weekly": weekly,
        "intraday": intraday,
    }


def _resample_weekly(daily: pd.DataFrame) -> pd.DataFrame:
    weekly = daily.resample("W").agg({
        "Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum",
    })
    return weekly.dropna(subset=["Close"])


def _safe_financials(ticker) -> dict:
    """Pulls annual and quarterly financial statements. Every call is
    wrapped individually -- yfinance doesn't have every statement for
    every company (especially smaller ones), and one missing statement
    shouldn't break the whole report."""
    out = {}
    for name, attr in [
        ("annual_financials", "financials"),
        ("quarterly_financials", "quarterly_financials"),
        ("annual_balance_sheet", "balance_sheet"),
        ("quarterly_balance_sheet", "quarterly_balance_sheet"),
        ("annual_cashflow", "cashflow"),
    ]:
        try:
            df = getattr(ticker, attr)
            out[name] = df if (df is not None and not df.empty) else None
        except Exception:
            out[name] = None
    return out
