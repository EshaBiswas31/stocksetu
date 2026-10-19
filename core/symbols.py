"""
symbols.py
----------
Input validation and a small helper lookup so a user can type a common
company name ("Tata Consultancy", "Infosys") instead of the exact ticker
symbol. This is intentionally a short, static list of well-known NSE/BSE
companies -- not a full instrument master -- which keeps this file simple
to read while still covering the companies most likely to be used in a
demo.

If the typed text isn't in this list, it's still accepted (as-is, upper-
cased) and tried directly against Yahoo Finance -- so any valid ticker
still works even if it's not one of the "friendly names" below.
"""

import re

COMMON_NAMES = {
    "tcs": "TCS", "tata consultancy": "TCS", "tata consultancy services": "TCS",
    "infosys": "INFY", "infy": "INFY",
    "reliance": "RELIANCE", "reliance industries": "RELIANCE",
    "hdfc bank": "HDFCBANK", "hdfcbank": "HDFCBANK",
    "icici bank": "ICICIBANK", "icicibank": "ICICIBANK",
    "sbi": "SBIN", "state bank of india": "SBIN", "sbin": "SBIN",
    "wipro": "WIPRO",
    "hcl tech": "HCLTECH", "hcl technologies": "HCLTECH", "hcltech": "HCLTECH",
    "itc": "ITC",
    "larsen": "LT", "l&t": "LT", "larsen and toubro": "LT", "lt": "LT",
    "bajaj finance": "BAJFINANCE",
    "maruti": "MARUTI", "maruti suzuki": "MARUTI",
    "asian paints": "ASIANPAINT",
    "kotak bank": "KOTAKBANK", "kotak mahindra bank": "KOTAKBANK",
    "axis bank": "AXISBANK",
    "sun pharma": "SUNPHARMA", "sun pharmaceutical": "SUNPHARMA",
    "titan": "TITAN",
    "tata motors": "TATAMOTORS",
    "tata steel": "TATASTEEL",
    "adani enterprises": "ADANIENT",
    "bharti airtel": "BHARTIARTL", "airtel": "BHARTIARTL",
    "ntpc": "NTPC",
    "ongc": "ONGC",
    "power grid": "POWERGRID",
    "ultratech cement": "ULTRACEMCO",
    "nestle india": "NESTLEIND",
    "hindustan unilever": "HINDUNILVR", "hul": "HINDUNILVR",
}

# A valid NSE/BSE ticker is letters, numbers, & and - only (e.g. "M&M",
# "BAJAJ-AUTO"), between 1 and 20 characters.
_SYMBOL_PATTERN = re.compile(r"^[A-Z0-9&\-]{1,20}$")


def resolve_and_validate(raw_input: str, exchange: str):
    """Returns (symbol, error). `symbol` is the cleaned-up ticker to send
    to Yahoo Finance (None if invalid); `error` is a human-readable
    message (None if valid)."""
    text = (raw_input or "").strip()
    if not text:
        return None, "Please enter a company name or ticker symbol."

    if exchange not in ("NSE", "BSE"):
        return None, "Exchange must be NSE or BSE."

    lowered = text.lower()
    if lowered in COMMON_NAMES:
        return COMMON_NAMES[lowered], None

    symbol = text.upper().replace(" ", "")
    if not _SYMBOL_PATTERN.match(symbol):
        return None, (f"'{text}' doesn't look like a valid ticker symbol. "
                       f"Use a symbol like TCS, RELIANCE or INFY.")

    return symbol, None
