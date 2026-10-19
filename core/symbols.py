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


def search_suggestions(query: str, limit: int = 8):
    """Powers the autocomplete dropdown: given whatever the user has typed
    so far, returns a list of {"symbol", "name"} matches from the
    friendly-name list above. Matches on either the ticker itself or any
    of its friendly names, and ranks a match at the START of a name
    higher than one in the middle (so "inf" lists Infosys before a name
    that merely contains "inf" somewhere else)."""
    query = (query or "").strip().lower()
    if not query:
        return []

    # Build one entry per ticker, collecting every friendly name that
    # maps to it (COMMON_NAMES has several spellings per company).
    by_symbol = {}
    for name, symbol in COMMON_NAMES.items():
        by_symbol.setdefault(symbol, set()).add(name)

    scored = []
    for symbol, names in by_symbol.items():
        # Prefer the longest/most complete name as the display name.
        display_name = max(names, key=len).title()
        best_rank = None
        for candidate in list(names) + [symbol.lower()]:
            words = candidate.split()
            if candidate.startswith(query):
                rank = 0
            elif any(word.startswith(query) for word in words):
                rank = 1  # matches the start of a later word, e.g. "bank" in "axis bank"
            else:
                continue
            if best_rank is None or rank < best_rank:
                best_rank = rank
        if best_rank is not None:
            scored.append((best_rank, symbol, display_name))

    scored.sort(key=lambda t: (t[0], t[1]))
    return [{"symbol": s, "name": n} for _, s, n in scored[:limit]]


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
