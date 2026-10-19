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

(async function init() {
  const user = await requireLogin();
  if (!user) return;
  document.getElementById("userName").textContent = user.name;
  if (user.role === "admin") document.getElementById("adminLink").classList.remove("hidden");
  loadRecent();
})();

document.getElementById("logoutBtn").addEventListener("click", doLogout);
document.getElementById("analyzeBtn").addEventListener("click", runAnalysis);
document.getElementById("symbolInput").addEventListener("keydown", (e) => {
  if (e.key === "Enter") runAnalysis();
});

async function runAnalysis() {
  const symbol = document.getElementById("symbolInput").value.trim();
  const exchange = document.getElementById("exchangeInput").value;
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

  const { ok, data } = await apiGet(`/api/analyze?symbol=${encodeURIComponent(symbol)}&exchange=${exchange}`);

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

function renderAll() {
  document.getElementById("companyTitle").textContent =
    `${report.company_name} (${report.symbol}.${report.exchange === "NSE" ? "NS" : "BO"})`;

  renderOverall();
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
  document.getElementById("miniFund").textContent = signed(o.pillar_scores.fundamental);
  document.getElementById("miniTech").textContent = signed(o.pillar_scores.technical);
  document.getElementById("miniQuant").textContent = signed(o.pillar_scores.quant);
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
    const pillarData = report[key];
    const btn = document.createElement("button");
    btn.className = "pillar-tab" + (key === activePillar ? " active" : "");
    btn.innerHTML = `${cfg.label} <span class="pillar-score-badge">${signed(pillarData.overall_score)}</span>`;
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

  chartInstance = new Chart(ctx, {
    type: "line",
    data: {
      labels: chart.dates,
      datasets: [
        { label: "Close Price", data: chart.close, borderColor: "#161a3d", borderWidth: 1.5, pointRadius: 0 },
        { label: "SMA20", data: chart.sma20, borderColor: "#f0a93c", borderWidth: 1.5, pointRadius: 0 },
        { label: "SMA50", data: chart.sma50, borderColor: "#8d92bd", borderWidth: 1.5, pointRadius: 0 },
      ],
    },
    options: {
      responsive: true,
      interaction: { mode: "index", intersect: false },
      scales: { x: { ticks: { maxTicksLimit: 10 } }, y: { title: { display: true, text: "Price (₹)" } } },
      plugins: { legend: { position: "top" } },
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
