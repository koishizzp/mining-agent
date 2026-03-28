const state = {
  chat: JSON.parse(window.localStorage.getItem("thermo-chat") || "[]"),
  latestPlan: null,
};

async function openFileBrowser(path) {
  const response = await fetch(`/api/fs/list?path=${encodeURIComponent(path)}`);
  const rows = await response.json();
  document.getElementById("file-browser-results").textContent = rows.map((row) => row.path).join("\n");
  document.getElementById("file-browser-modal").showModal();
}

async function refreshActiveRun() {
  const response = await fetch("/api/runs/active");
  const payload = await response.json();
  document.getElementById("run-monitor").textContent = payload.run_id
    ? `Active run: ${payload.run_id}`
    : "No active run";
}

window.addEventListener("load", () => {
  document.getElementById("close-browser").addEventListener("click", () => {
    document.getElementById("file-browser-modal").close();
  });
  refreshActiveRun();
  window.setInterval(refreshActiveRun, 2000);
});

window.thermoConsole = {
  openFileBrowser,
  state,
};
