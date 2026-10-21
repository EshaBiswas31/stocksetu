// common.js - shared helpers used by every page.

async function apiGet(url) {
  const res = await fetch(url);
  const data = await res.json();
  return { ok: res.ok, data };
}

async function apiPost(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  const data = await res.json();
  return { ok: res.ok, data };
}

function showMsg(el, text, isError) {
  if (!text) { el.className = "msg hidden"; el.textContent = ""; return; }
  el.className = "msg " + (isError ? "msg-error" : "msg-ok");
  el.textContent = text;
}

async function requireLogin() {
  const { data } = await apiGet("/api/me");
  if (!data.user) { window.location.href = "login.html"; return null; }
  return data.user;
}

async function requireAdmin() {
  const user = await requireLogin();
  if (user && user.role !== "admin") { window.location.href = "dashboard.html"; return null; }
  return user;
}

async function doLogout() {
  await apiPost("/api/logout");
  window.location.href = "login.html";
}

// Wires up every ".pw-toggle" button on the page: clicking it flips its
// sibling password <input> between hidden (dots) and plain text, and
// flips its own label between "Show" and "Hide". Call this once after
// the page's password fields exist.
function initPasswordToggles() {
  document.querySelectorAll(".pw-toggle").forEach((btn) => {
    const input = document.getElementById(btn.dataset.for);
    if (!input) return;
    btn.addEventListener("click", () => {
      const showing = input.type === "text";
      input.type = showing ? "password" : "text";
      btn.textContent = showing ? "Show" : "Hide";
      btn.setAttribute("aria-label", showing ? "Show password" : "Hide password");
    });
  });
}
