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
document.getElementById("symbolInput").addEventListener("keydown", (e) => {
  if (e.key === "Enter") runAnalysis();
});
document.getElementById("profileInput").addEventListener("change", () => {
  // Changing the risk profile re-weights the same signals, so if a
  // report is already on screen, just re-run the analysis with the
  // new profile rather than making the user click Analyze again.
  if (report) runAnalysis();
});
document.getElementById("starBtn").addEventListener("click", toggleWatchlist);

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
  const ul = document.getElementById("watchlistList");
  ul.innerHTML = "";
  if (data.watchlist.length === 0) {
    ul.innerHTML = `<li style="color: var(--muted);">Nothing starred yet -- analyze a company and click "Add to Watchlist".</li>`;
    return;
  }
  data.watchlist.forEach((r) => {
    const li = document.createElement("li");
    li.style.cursor = "pointer";
    const scoreHtml = r.overall_score === null || r.overall_score === undefined
      ? `<span class="score-chip chip-neutral">not yet scored</span>`
      : `<span class="score-chip ${labelClass(r.label)}">${signed(r.overall_score)} &middot; ${r.label}</span>`;
    li.innerHTML = `
      <div><span class="tkr">${r.symbol}</span> &middot; <span class="co">${r.company_name || ""} (${r.exchange})</span></div>
      ${scoreHtml}
    `;
    li.addEventListener("click", () => {
      document.getElementById("symbolInput").value = r.symbol;
      document.getElementById("exchangeInput").value = r.exchange;
      runAnalysis();
    });
    ul.appendChild(li);
  });
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
