// admin.js

let myUserId = null;

(async function init() {
  const user = await requireAdmin();
  if (!user) return;
  document.getElementById("userName").textContent = user.name;
  loadUsers();
})();

document.getElementById("logoutBtn").addEventListener("click", doLogout);

document.getElementById("addCustomerForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const msg = document.getElementById("addMsg");
  const btn = document.getElementById("addBtn");
  const name = document.getElementById("newName").value.trim();
  const email = document.getElementById("newEmail").value.trim();
  const password = document.getElementById("newPassword").value;
  const role = document.getElementById("newRole").value;

  btn.disabled = true;
  btn.textContent = "Creating...";
  const { ok, data } = await apiPost("/api/admin/add-customer", { name, email, password, role });
  btn.disabled = false;
  btn.textContent = "Create Account";

  showMsg(msg, data.message || data.error, !ok);
  if (ok) {
    document.getElementById("addCustomerForm").reset();
    loadUsers();
  }
});

async function loadUsers() {
  const { ok, data } = await apiGet("/api/admin/users");
  if (!ok) return;

  if (myUserId === null) {
    const me = await apiGet("/api/me");
    const myEmail = me.data.user.email;
    const mine = data.users.find(u => u.email === myEmail);
    myUserId = mine ? mine.id : null;
  }

  const tbody = document.getElementById("usersTableBody");
  tbody.innerHTML = "";

  data.users.forEach((u) => {
    const tr = document.createElement("tr");
    const isMe = u.id === myUserId;

    tr.innerHTML = `
      <td>${u.name}${isMe ? " <span style='color:var(--muted); font-size:11px;'>(you)</span>" : ""}</td>
      <td>${u.email}</td>
      <td><span class="badge ${u.role === "admin" ? "badge-admin" : "badge-user"}">${u.role}</span></td>
      <td><span class="badge ${u.is_active ? "badge-active" : "badge-disabled"}">${u.is_active ? "Active" : "Disabled"}</span></td>
      <td>${u.created_at}</td>
      <td>
        <button class="small-btn" data-action="toggle-role" data-id="${u.id}" ${isMe ? "disabled" : ""}>
          ${u.role === "admin" ? "Make Customer" : "Make Admin"}
        </button>
        <button class="small-btn" data-action="toggle-active" data-id="${u.id}" ${isMe ? "disabled" : ""}>
          ${u.is_active ? "Disable" : "Enable"}
        </button>
        <button class="small-btn" data-action="set-password" data-id="${u.id}">Reset Password</button>
      </td>
    `;
    tbody.appendChild(tr);
  });

  tbody.querySelectorAll("button[data-action='toggle-role'], button[data-action='toggle-active']").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const action = btn.dataset.action;
      const id = btn.dataset.id;
      btn.disabled = true;
      await apiPost(`/api/admin/users/${id}/${action}`);
      loadUsers();
    });
  });

  tbody.querySelectorAll("button[data-action='set-password']").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.dataset.id;
      const newPassword = prompt("Enter a new password for this user (at least 6 characters):");
      if (!newPassword) return;
      const { ok, data } = await apiPost(`/api/admin/users/${id}/set-password`, { new_password: newPassword });
      alert(data.message || data.error);
    });
  });
}
