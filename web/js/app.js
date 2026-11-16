import { fetchBasinStatus, DEMO_FALLBACK } from "./api.js";
import { renderDashboard } from "./components.js";
import { setupWhatsAppShare } from "./share.js";

let latestState = { data: DEMO_FALLBACK, isCached: true, isDemo: true };

async function refreshStatus() {
  const result = await fetchBasinStatus();
  latestState = result;
  renderDashboard(result.data, result.isCached, result.isDemo);
}

async function init() {
  setupWhatsAppShare(() => latestState.data);
  await refreshStatus();

  window.addEventListener("online", () => {
    refreshStatus();
  });

  window.addEventListener("offline", () => {
    renderDashboard(latestState.data, true, latestState.isDemo);
  });
}

init();
