# StockSetu

*Setu* means "bridge" — a bridge between raw NSE/BSE market data and a
clear, numeric verdict on a company: a **Fundamental Score**, a
**Technical Score**, a **Quantitative Score**, and one combined score
from **-100 (extremely bearish) to +100 (extremely bullish)**.

## What it does

1. Log in (or sign up, or have an admin create your account).
2. Type a company name or symbol (e.g. `TCS`, `Infosys`, `RELIANCE`) and
   pick NSE or BSE.
3. The backend fetches real data from Yahoo Finance and runs three
   independent analyses, **each across three time horizons**:

   | Pillar | Horizons | What it measures |
   |---|---|---|
   | **Fundamental** | Short (0-3mo) / Medium (3-12mo) / Long (1-3y+) | Is the business financially healthy? Valuation, profitability, debt, growth |
   | **Technical** | Intraday / Weekly / Monthly | Price action and moving-average crossovers, found with the **Line Segment Intersection (sweep-line) algorithm** |
   | **Quantitative** | Intraday / Weekly / Monthly | Statistical view: momentum, volatility, risk-adjusted return |

4. Pick a **Risk Profile** -- Trader, Balanced, or Investor. This changes
   how much weight the three pillars (and the three horizons inside each
   pillar) get when they're combined into one **Overall Score** from
   -100 to +100. A Trader profile leans heavily on Intraday Technical/
   Quant signals; an Investor profile leans heavily on Long-term
   Fundamentals. Same underlying signals, different emphasis -- nothing
   is re-computed, just re-weighted. See `core/scoring.py` -> `PROFILES`.
5. **"Why This Score"**: every individual metric (RSI, P/E ratio, a
   moving-average crossover, etc.) already scores itself from -100 to
   +100. The dashboard simply shows the four strongest bullish and four
   strongest bearish of those metric scores, across all three pillars --
   so the final number is never a black box.
6. **Autocomplete**: typing in the search box queries `/api/symbols/search`
   (backed by the friendly-name list in `core/symbols.py`) and shows a
   dropdown of matching tickers, arrow-key navigable, like a real
   trading-terminal search box.
7. **Watchlist**: logged-in users can star a company from the results
   page. "My Watchlist" is a terminal-style table -- Security, Bias,
   Overall/Fundamental/Technical/Quant scores side by side, and when the
   score was last refreshed -- with a Refresh button (re-runs the
   analysis for just that row) and a Remove button per row.
8. **Admins** get a cPanel-style panel: add a customer directly (name,
   email, password), see every admin and customer in one table, disable
   accounts, promote/demote, or reset anyone's password.

## Why the algorithm is the centerpiece

Every technical-analysis crossover in this project — price crossing its
moving average, a fast average crossing a slow average — is found using
the **same general-purpose algorithm**: Line Segment Intersection via a
plane sweep (the algorithm from the course slides), not a simple day-by-
day "is price above or below" loop.

The idea: every line on a price chart (the close price, a moving average)
is really a chain of tiny straight line segments. A crossover is exactly
two segments intersecting. `core/sweep_line.py`'s `find_intersections()`
sweeps a horizontal line down through all the segments and reports every
crossing in **O((n + k) log n)** time (n = segments, k = crossings found)
instead of the brute-force **O(n²)** of comparing every pair. Every
horizon of the Technical pillar calls this same function — only the
moving-average windows change (EMA9/21 for intraday, SMA20/50 for weekly,
SMA10/40 for monthly). The dashboard shows exactly how many segments were
built and how many crossings were found, so the algorithm's work is
visible, not hidden.

## Project structure

```
stocksetu_v2/
  public/                    Frontend - plain HTML/CSS/JS, no framework
    login.html, signup.html, forgot.html, reset.html
    dashboard.html, admin.html
    style.css, common.js, dashboard.js, admin.js
  api/
    app.py                   The ENTIRE backend - one Flask file, every route
  core/
    sweep_line.py             THE algorithm - line segment intersection
    indicators.py              RSI, MACD, SMA/EMA, volatility, Sharpe-like ratio
    yahoo.py                    Fetches data from Yahoo Finance (3 timeframes)
    symbols.py                   Input validation + friendly name lookup
    fundamental.py                 Fundamental pillar, 3 horizons
    technical.py                    Technical pillar, 3 horizons (uses sweep_line.py)
    quant.py                         Quantitative pillar, 3 horizons
    scoring.py                        Combines the 3 pillars into the final score
    db.py                              All SQL (Postgres) - users, score_cache, watchlist
    mailer.py                          Sends the password-reset email
  requirements.txt
  vercel.json
  push.bat                  One-click "commit + push" for quick redeploys
```

## How to explain the code (viva walkthrough order)

1. **`core/sweep_line.py`** — start here, read the big docstring at the
   top first. This is the actual algorithm: `find_intersections()` is a
   direct implementation of the slides' `FindIntersections` /
   `HandleEventPoint` / `FindNewEvent`, using Python's `heapq` for the
   event queue and a sorted list for the status structure. The
   `detect_crossovers()` function at the bottom is a thin wrapper every
   other file calls — it takes two price lines and returns every
   crossing, labelled "bullish" or "bearish".

2. **`core/indicators.py`** — small, individually testable functions:
   SMA, EMA, RSI, MACD, volatility, a simplified Sharpe ratio. Each is
   10-15 lines of plain pandas.

3. **`core/technical.py`** — THE pillar that uses the algorithm. Read
   `_analyze_horizon()`: it builds a fast/slow moving-average pair, calls
   `detect_crossovers()` (from sweep_line.py) to find every crossing,
   and combines that with RSI/MACD into a -100..+100 score. The same
   function runs for all three horizons — only the moving-average
   windows differ.

4. **`core/fundamental.py`** and **`core/quant.py`** — same pattern:
   each metric has its own small scoring function with commented
   thresholds, horizons average whatever metrics are available.

5. **`core/scoring.py`** — the final step. `PROFILES` holds the Trader/
   Balanced/Investor weight tables; `combine()` does a weighted average
   of each pillar's three horizon scores (skipping any horizon with no
   data), then a weighted average of the three pillars, picks a label
   (Strong Bullish/Bullish/Neutral/Bearish/Strong Bearish), and writes a
   one-paragraph rationale. `_top_drivers()` is the "Why This Score"
   logic -- it flattens every metric score from every horizon of every
   pillar into one list and returns the strongest positives/negatives.

6. **`core/yahoo.py`** — fetches daily (2y), weekly (resampled), and
   best-effort intraday (5-min, ~5 days) price history, plus the
   company's fundamentals, from Yahoo Finance via `yfinance`.

7. **`core/db.py`** — every SQL query in one place, plain readable SQL
   (no ORM). `init_db()` creates the three tables (`users`, `score_cache`,
   `watchlist`) and seeds the first admin account from environment
   variables.

8. **`api/app.py`** — the whole backend, organized into six labelled
   sections. Each route is short: validate input → call a `core/`
   function → return JSON.

9. **`public/dashboard.js`** — the main frontend logic: calls
   `/api/analyze`, then renders the gauge, the pillar tabs, the horizon
   tabs within each pillar, and the chart.

## Setting it up (do this once, before deploying)

### 1. Create a Vercel Postgres database
In your Vercel project → **Storage** tab → **Create Database** →
**Postgres** (powered by Neon). Vercel automatically adds a
`DATABASE_URL` environment variable — nothing to copy/paste.

### 2. Set the admin account and session secret
In Vercel → **Settings** → **Environment Variables**:

| Name | Value |
|---|---|
| `ADMIN_EMAIL` | the email you'll log in as admin with |
| `ADMIN_PASSWORD` | a password for that admin account |
| `ADMIN_NAME` | (optional) your name |
| `SECRET_KEY` | any long random string |

### 3. Set up email sending (for "Forgot Password")
You need a Gmail account and an **App Password**:
1. Google Account → **Security** → turn on **2-Step Verification**.
2. Go to **myaccount.google.com/apppasswords**, create one named "StockSetu".
3. In Vercel's Environment Variables:

| Name | Value |
|---|---|
| `SMTP_EMAIL` | your Gmail address |
| `SMTP_APP_PASSWORD` | the 16-character App Password (no spaces) |

### 4. Deploy
Push this project to GitHub, import it into Vercel, click Deploy.
`vercel.json` handles the rest.

### 5. Redeploying after changes
Run `push.bat` (double-click it). It commits and pushes to GitHub, and
Vercel auto-redeploys.

## Data sources — what's covered and what isn't

**Yahoo Finance covers everything this project uses**: price history at
three granularities, P/E, P/B, ROE, debt/equity, margins, growth rates,
analyst recommendations and target prices, and annual/quarterly financial
statements.

**What Yahoo Finance does *not* have**, and what a more advanced version
could add: promoter/FII/DII shareholding patterns, corporate announcement
feeds, and concall transcripts — these live on screener.in, NSE/BSE's own
sites, or specialized data vendors. Scraping them reliably is fragile and
outside this project's scope, so it's documented here as a known
limitation rather than something that silently breaks.

**Intraday data limitation**: Yahoo Finance only keeps ~5-60 days of
5-minute bars, and not every symbol has intraday data. The app handles
this gracefully — if intraday data isn't available for a symbol, that
one section shows "data unavailable" instead of breaking the rest of the
report.

## Future scope

- A fourth pillar: simple sentiment analysis from recent news headlines.
- Batch-score an entire index (e.g. NIFTY 50) on a schedule, instead of
  only on-demand per search.
- Let customers save a personal watchlist (one new table, same database).
- Compare two companies side-by-side.
- Swap the simplified status structure in `sweep_line.py` for a true
  self-balancing BST, for better worst-case performance at very large
  scale — a natural "what would you improve" answer for the viva.
