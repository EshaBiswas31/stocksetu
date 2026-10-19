// dashboard.js

let report = null;
let activePillar = "fundamental";
let activeHorizon = { fundamental: "short_term", technical: "intraday", quant: "intraday" };
let chartInstance = null;

const PILLAR_CONFIG = {
  fundamental: {
    label: "Fundamental",
    horizons: [
      ["short_term", "Short (0-3mo)"],
      ["medium_term", "Medium (3-12mo)"],
      ["long_term", "Long (1-3y+)"],
    ],
  },
  technical: {
    label: "Technical",
    horizons: [
      ["intraday", "Intraday"],
      ["weekly", "Weekly"],
      ["monthly", "Monthly"],
    ],
  },
  quant: {
    label: "Quantitative",
    horizons: [
      ["intraday", "Intraday"],
      ["weekly", "Weekly"],
      ["monthly", "Monthly"],
    ],
  },
};

const PROFILE_LABELS = {
  trader: "Trader (short-term)",
  balanced: "Balanced",
  investor: "Investor (long-term)",
};

(async function init() {
  const user = await requireLogin();
  if (!user) return;
  document.getElementById("userName").textContent = user.name;
  if (user.role === "admin") document.getElementById("adminLink").classList.remove("hidden");
  loadRecent();
  loadWatchlist();
})();

document.getElementById("logoutBtn").addEventListener("click", doLogout);
document.getElementById("analyzeBtn").addEventListener("click", runAnalysis);
// Nothing calls Yahoo Finance / runs the analysis on its own -- not
// autocomplete, not clicking a watchlist row, not changing the risk
// profile. Those only ever fill in the search box; analysis runs only
// when the user explicitly clicks "Analyze" (or presses Enter in the
// search box, which is the same thing).
document.getElementById("starBtn").addEventListener("click", toggleWatchlist);

// ---------------------------------------------------------------------
// Autocomplete: as the user types a company name, show matching
// symbols in a dropdown (core/symbols.py's friendly-name list, served
// by /api/symbols/search). Picking one only fills the box -- it does
// NOT run the analysis; the user still clicks Analyze (or presses
// Enter) themselves.
// ---------------------------------------------------------------------
const symbolInput = document.getElementById("symbolInput");
const suggestBox = document.getElementById("symbolSuggestions");
let suggestTimer = null;
let suggestIndex = -1;

symbolInput.addEventListener("input", () => {
  clearTimeout(suggestTimer);
  const q = symbolInput.value.trim();
  if (!q) { hideSuggestions(); return; }
  suggestTimer = setTimeout(() => fetchSuggestions(q), 120);
});

symbolInput.addEventListener("keydown", (e) => {
  const items = suggestBox.querySelectorAll("li");
  if (e.key === "ArrowDown" && items.length) {
    e.preventDefault();
    suggestIndex = Math.min(suggestIndex + 1, items.length - 1);
    highlightSuggestion(items);
  } else if (e.key === "ArrowUp" && items.length) {
    e.preventDefault();
    suggestIndex = Math.max(suggestIndex - 1, 0);
    highlightSuggestion(items);
  } else if (e.key === "Enter") {
    if (suggestIndex >= 0 && items[suggestIndex]) {
      e.preventDefault();
      items[suggestIndex].click();
    } else {
      hideSuggestions();
      runAnalysis();
    }
  } else if (e.key === "Escape") {
    hideSuggestions();
  }
});

document.addEventListener("click", (e) => {
  if (!suggestBox.contains(e.target) && e.target !== symbolInput) hideSuggestions();
});

async function fetchSuggestions(query) {
  const { ok, data } = await apiGet(`/api/symbols/search?q=${encodeURIComponent(query)}`);
  if (!ok || symbolInput.value.trim() !== query) return;
  renderSuggestions(data.results);
}

function renderSuggestions(results) {
  suggestIndex = -1;
  if (!results || results.length === 0) { hideSuggestions(); return; }
  suggestBox.innerHTML = results.map((r) => `
    <li data-symbol="${r.symbol}">
      <span class="suggest-ticker">${r.symbol}</span>
      <span class="suggest-name">${r.name}</span>
      <span class="suggest-exchange">${document.getElementById("exchangeInput").value}</span>
    </li>
  `).join("");
  suggestBox.querySelectorAll("li").forEach((li) => {
    li.addEventListener("click", () => {
      symbolInput.value = li.dataset.symbol;
      hideSuggestions();
      symbolInput.focus();
      // Deliberately no runAnalysis() here -- picking a suggestion only
      // fills the box. The user clicks Analyze (or presses Enter) to
      // actually run it, same as if they'd typed the symbol themselves.
    });
  });
  suggestBox.classList.remove("hidden");
}

function highlightSuggestion(items) {
  items.forEach((li, i) => li.classList.toggle("active", i === suggestIndex));
}

function hideSuggestions() {
  suggestBox.classList.add("hidden");
  suggestBox.innerHTML = "";
  suggestIndex = -1;
}

async function runAnalysis() {
  const symbol = document.getElementById("symbolInput").value.trim();
  const exchange = document.getElementById("exchangeInput").value;
  const profile = document.getElementById("profileInput").value;
  const statusLine = document.getElementById("statusLine");
  const results = document.getElementById("results");
  const btn = document.getElementById("analyzeBtn");

  if (!symbol) {
    statusLine.textContent = "Please enter a company name or symbol.";
    statusLine.className = "status-line error";
    return;
  }

  btn.disabled = true;
  btn.textContent = "Analyzing...";
  statusLine.className = "status-line";
  statusLine.textContent = `Fetching ${symbol} from Yahoo Finance and running fundamental, technical and quantitative analysis...`;
  results.classList.add("hidden");

  const url = `/api/analyze?symbol=${encodeURIComponent(symbol)}&exchange=${exchange}&profile=${profile}`;
  const { ok, data } = await apiGet(url);

  btn.disabled = false;
  btn.textContent = "Analyze";

  if (!ok) {
    statusLine.className = "status-line error";
    statusLine.textContent = data.error;
    return;
  }

  statusLine.textContent = "";
  report = data;
  activePillar = "fundamental";
  activeHorizon = { fundamental: "short_term", technical: "intraday", quant: "intraday" };
  renderAll();
  results.classList.remove("hidden");
  loadRecent();
}

async function toggleWatchlist() {
  if (!report) return;
  const btn = document.getElementById("starBtn");
  btn.disabled = true;
  const { ok, data } = await apiPost("/api/watchlist/toggle", {
    symbol: report.symbol,
    exchange: report.exchange,
    company_name: report.company_name,
  });
  btn.disabled = false;
  if (!ok) return;
  report.in_watchlist = data.added;
  renderStarButton();
  loadWatchlist();
}

function renderStarButton() {
  const btn = document.getElementById("starBtn");
  if (report.in_watchlist) {
    btn.innerHTML = "&#9733; In Watchlist";
    btn.classList.add("active");
  } else {
    btn.innerHTML = "&#9734; Add to Watchlist";
    btn.classList.remove("active");
  }
}

async function loadWatchlist() {
  const { ok, data } = await apiGet("/api/watchlist");
  if (!ok) return;
  const body = document.getElementById("watchlistBody");
  const empty = document.getElementById("watchlistEmpty");
  body.innerHTML = "";

  if (data.watchlist.length === 0) {
    empty.classList.remove("hidden");
    return;
  }
  empty.classList.add("hidden");

  data.watchlist.forEach((r) => {
    const tr = document.createElement("tr");
    const scored = r.overall_score !== null && r.overall_score !== undefined;
    tr.innerHTML = `
      <td>
        <div class="tkr">${r.symbol}</div>
        <div class="co">${r.company_name || ""} &middot; ${r.exchange}</div>
      </td>
      <td>${scored ? `<span class="badge-bias ${labelClass(r.label)}">${r.label}</span>` : `<span class="badge-bias chip-neutral">Not scored</span>`}</td>
      <td class="${numClass(r.overall_score)}">${scored ? signed(r.overall_score) : "--"}</td>
      <td class="${numClass(r.fundamental_score)}">${pillarSigned(r.fundamental_score)}</td>
      <td class="${numClass(r.technical_score)}">${pillarSigned(r.technical_score)}</td>
      <td class="${numClass(r.quant_score)}">${pillarSigned(r.quant_score)}</td>
      <td class="muted-cell">${formatRefreshed(r.fetched_at)}</td>
      <td class="watch-actions">
        <button class="small-btn" data-action="refresh">Refresh</button>
        <button class="small-btn small-btn-danger" data-action="remove">Remove</button>
      </td>
    `;
    tr.querySelector('[data-action="refresh"]').addEventListener("click", () => refreshWatchlistRow(r, tr));
    tr.querySelector('[data-action="remove"]').addEventListener("click", () => removeWatchlistRow(r));
    tr.querySelectorAll("td:not(.watch-actions)").forEach((td) => {
      td.style.cursor = "pointer";
      td.title = "Fill the search box with this symbol";
      td.addEventListener("click", () => {
        // Fills the search box only -- same rule as autocomplete: the
        // user still clicks Analyze to actually run it. Use the
        // row's own Refresh button to re-score this symbol directly.
        document.getElementById("symbolInput").value = r.symbol;
        document.getElementById("exchangeInput").value = r.exchange;
        document.getElementById("symbolInput").focus();
        window.scrollTo({ top: 0, behavior: "smooth" });
      });
    });
    body.appendChild(tr);
  });
}

function formatRefreshed(isoString) {
  if (!isoString) return "Never";
  const diffMs = Date.now() - new Date(isoString).getTime();
  const minutes = Math.round(diffMs / 60000);
  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return new Date(isoString).toLocaleDateString();
}

async function refreshWatchlistRow(r, tr) {
  const btn = tr.querySelector('[data-action="refresh"]');
  btn.disabled = true;
  btn.textContent = "...";
  const profile = document.getElementById("profileInput").value;
  await apiGet(`/api/analyze?symbol=${encodeURIComponent(r.symbol)}&exchange=${r.exchange}&profile=${profile}`);
  await loadWatchlist();
}

async function removeWatchlistRow(r) {
  await apiPost("/api/watchlist/toggle", { symbol: r.symbol, exchange: r.exchange, company_name: r.company_name });
  if (report && report.symbol === r.symbol && report.exchange === r.exchange) {
    report.in_watchlist = false;
    renderStarButton();
  }
  loadWatchlist();
}

function renderAll() {
  document.getElementById("companyTitle").textContent =
    `${report.company_name} (${report.symbol}.${report.exchange === "NSE" ? "NS" : "BO"})`;

  renderOverall();
  renderStarButton();
  renderDrivers();
  renderPillarTabs();
  renderHorizonTabs();
  renderHorizonContent();
  renderAlgoBanner();

  try {
    drawChart(report.chart);
  } catch (e) {
    console.error("Chart rendering failed:", e);
    const chartCard = document.querySelector(".chart-card");
    if (chartCard) {
      chartCard.innerHTML = `<h3>Price vs Moving Averages</h3>
        <p style="color: var(--muted);">Chart could not be loaded right now. Scores above are unaffected.</p>`;
    }
  }
}

function renderOverall() {
  const o = report.overall;
  document.getElementById("overallScore").textContent = (o.overall_score > 0 ? "+" : "") + o.overall_score;
  const labelEl = document.getElementById("overallLabel");
  labelEl.textContent = o.label;
  labelEl.className = "gauge-label " + labelClass(o.label);

  // needle: -100 -> -90deg, 0 -> 0deg, +100 -> +90deg
  const angle = (o.overall_score / 100) * 90;
  document.getElementById("needle").style.transform = `translateX(-50%) rotate(${angle}deg)`;

  document.getElementById("rationaleText").textContent = o.rationale;
  document.getElementById("profileBadge").textContent = `(${o.profile_label || PROFILE_LABELS[o.profile] || ""} profile)`;
  document.getElementById("miniFund").textContent = pillarSigned(o.pillar_scores.fundamental);
  document.getElementById("miniTech").textContent = pillarSigned(o.pillar_scores.technical);
  document.getElementById("miniQuant").textContent = pillarSigned(o.pillar_scores.quant);
}

function pillarSigned(n) {
  return n === null || n === undefined ? "n/a" : signed(n);
}

function renderDrivers() {
  const drivers = report.overall.drivers || { positive: [], negative: [] };
  const posEl = document.getElementById("driversPositive");
  const negEl = document.getElementById("driversNegative");

  const row = (d) => `<li><span>${d.metric} <span class="driver-tag">${d.pillar} &middot; ${d.horizon}</span></span><span class="metric-score ${scoreClass(d.score)}">${signed(d.score)}</span></li>`;

  posEl.innerHTML = drivers.positive.length
    ? drivers.positive.map(row).join("")
    : `<li style="color: var(--muted);">No strong bullish signal found.</li>`;
  negEl.innerHTML = drivers.negative.length
    ? drivers.negative.map(row).join("")
    : `<li style="color: var(--muted);">No strong bearish signal found.</li>`;
}

function signed(n) {
  return (n > 0 ? "+" : "") + n;
}

function labelClass(label) {
  if (label === "Strong Bullish") return "chip-strong-good";
  if (label === "Bullish") return "chip-good";
  if (label === "Strong Bearish") return "chip-strong-bad";
  if (label === "Bearish") return "chip-bad";
  return "chip-neutral";
}

function scoreClass(score) {
  if (score === null || score === undefined) return "chip-neutral";
  if (score >= 40) return "chip-strong-good";
  if (score >= 10) return "chip-good";
  if (score > -10) return "chip-neutral";
  if (score > -40) return "chip-bad";
  return "chip-strong-bad";
}

// Same -100..+100 scale and the same +-20 "Neutral" band as
// scoring.py's overall_label(), but returns a plain text color (no chip
// background) -- used for dense table cells like the watchlist.
function numClass(score) {
  if (score === null || score === undefined) return "num-neutral";
  if (score >= 20) return "num-good";
  if (score <= -20) return "num-bad";
  return "num-neutral";
}

function renderPillarTabs() {
  const wrap = document.getElementById("pillarTabs");
  wrap.innerHTML = "";
  Object.entries(PILLAR_CONFIG).forEach(([key, cfg]) => {
    // Use the profile-weighted pillar score (same number shown at the
    // top), not each module's own equal-weight overall_score, so the
    // same pillar never shows two different numbers on screen.
    const badgeScore = report.overall.pillar_scores[key];
    const btn = document.createElement("button");
    btn.className = "pillar-tab" + (key === activePillar ? " active" : "");
    btn.innerHTML = `${cfg.label} <span class="pillar-score-badge">${pillarSigned(badgeScore)}</span>`;
    btn.addEventListener("click", () => {
      activePillar = key;
      renderPillarTabs();
      renderHorizonTabs();
      renderHorizonContent();
      renderAlgoBanner();
    });
    wrap.appendChild(btn);
  });
}

function renderHorizonTabs() {
  const wrap = document.getElementById("horizonTabs");
  wrap.innerHTML = "";
  PILLAR_CONFIG[activePillar].horizons.forEach(([key, label]) => {
    const btn = document.createElement("button");
    btn.className = "horizon-tab" + (key === activeHorizon[activePillar] ? " active" : "");
    btn.textContent = label;
    btn.addEventListener("click", () => {
      activeHorizon[activePillar] = key;
      renderHorizonTabs();
      renderHorizonContent();
    });
    wrap.appendChild(btn);
  });
}

function renderAlgoBanner() {
  const banner = document.getElementById("algoBanner");
  if (activePillar !== "technical") {
    banner.classList.add("hidden");
    return;
  }
  const horizonKey = activeHorizon.technical;
  const h = report.technical[horizonKey];
  if (!h.available) {
    banner.classList.add("hidden");
    return;
  }
  banner.classList.remove("hidden");
  document.getElementById("algoStats").textContent =
    `${h.algorithm_stats.segments_built} line segments built, ${h.algorithm_stats.crossings_found} crossings found.`;
}

function renderHorizonContent() {
  const container = document.getElementById("horizonContent");
  const horizonKey = activeHorizon[activePillar];
  const h = report[activePillar][horizonKey];

  if (!h.available && h.score === null) {
    container.innerHTML = `<p class="unavailable-note">${h.reason || "Data unavailable for this horizon."}</p>`;
    return;
  }

  const metricsHtml = Object.entries(h.metrics).map(([name, score]) => {
    const shown = score === null || score === undefined ? "n/a" : signed(score);
    const cls = score === null ? "chip-neutral" : scoreClass(score);
    return `<li><span>${name}</span><span class="metric-score ${cls}">${shown}</span></li>`;
  }).join("");

  const rawHtml = Object.entries(h.raw).map(([name, value]) => {
    const shown = value === null || value === undefined ? "n/a" : value;
    return `<li><span>${name}</span><span>${shown}</span></li>`;
  }).join("");

  let crossoverHtml = "";
  if (activePillar === "technical") {
    crossoverHtml = buildCrossoverNote(h);
  }

  container.innerHTML = `
    <div class="horizon-body">
      <div>
        <h3>Signal Breakdown (score -100 to +100)</h3>
        <ul class="metric-list">${metricsHtml}</ul>
      </div>
      <div>
        <h3>Key Figures</h3>
        <ul class="raw-list">${rawHtml}</ul>
        ${crossoverHtml}
      </div>
    </div>
  `;
}

function buildCrossoverNote(h) {
  const pf = h.last_price_vs_fast_crossover;
  const fs = h.last_fast_vs_slow_crossover;
  const parts = [];
  if (pf) {
    parts.push(`Last Price/Average crossover: <b class="${pf.direction}">${pf.direction}</b> at bar ${Math.round(pf.x)}`);
  }
  if (fs) {
    parts.push(`Last Fast/Slow Average crossover: <b class="${fs.direction}">${fs.direction}</b> at bar ${Math.round(fs.x)}`);
  }
  if (parts.length === 0) {
    return `<div class="crossover-note">No moving-average crossover found in the available window.</div>`;
  }
  return `<div class="crossover-note">${parts.join("<br>")}</div>`;
}

function drawChart(chart) {
  const ctx = document.getElementById("priceChart").getContext("2d");
  if (chartInstance) chartInstance.destroy();

  // Pulled from the CSS theme so the chart always matches the page
  // (dark background, light text) instead of hardcoding colors that
  // would go invisible if the theme ever changes.
  const style = getComputedStyle(document.documentElement);
  const gridColor = style.getPropertyValue("--line").trim();
  const textColor = style.getPropertyValue("--ink-soft").trim();

  chartInstance = new Chart(ctx, {
    type: "line",
    data: {
      labels: chart.dates,
      datasets: [
        { label: "Close Price", data: chart.close, borderColor: "#f4f5fb", borderWidth: 1.5, pointRadius: 0 },
        { label: "SMA20", data: chart.sma20, borderColor: "#f0a93c", borderWidth: 1.5, pointRadius: 0 },
        { label: "SMA50", data: chart.sma50, borderColor: "#7d84ff", borderWidth: 1.5, pointRadius: 0 },
      ],
    },
    options: {
      responsive: true,
      interaction: { mode: "index", intersect: false },
      scales: {
        x: { ticks: { maxTicksLimit: 10, color: textColor }, grid: { color: gridColor } },
        y: { title: { display: true, text: "Price (₹)", color: textColor }, ticks: { color: textColor }, grid: { color: gridColor } },
      },
      plugins: { legend: { position: "top", labels: { color: textColor } } },
    },
  });
}

async function loadRecent() {
  const { ok, data } = await apiGet("/api/recent");
  if (!ok) return;
  const ul = document.getElementById("recentList");
  ul.innerHTML = "";
  if (data.recent.length === 0) {
    ul.innerHTML = `<li style="color: var(--muted);">Nothing analyzed yet -- search a company above.</li>`;
    return;
  }
  data.recent.forEach((r) => {
    const li = document.createElement("li");
    li.innerHTML = `
      <div><span class="tkr">${r.symbol}</span> &middot; <span class="co">${r.company_name || ""} (${r.exchange})</span></div>
      <span class="score-chip ${labelClass(r.label)}">${signed(r.overall_score)} &middot; ${r.label}</span>
    `;
    ul.appendChild(li);
  });
}
