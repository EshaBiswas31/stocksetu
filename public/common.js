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
