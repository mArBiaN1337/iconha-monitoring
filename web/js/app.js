import { fetchBasinStatus, DEMO_FALLBACK } from "./api.js";
import { renderDashboard, setupTapExplanations, setupViewTabs } from "./components.js";
import { setupWhatsAppShare } from "./share.js";

let latestState = { data: DEMO_FALLBACK, isCached: true, isDemo: true };
const AUTO_REFRESH_MS = 5 * 60 * 1000; // 5-minute background refresh aligned with GCS edge cache

async function refreshStatus() {
  const result = await fetchBasinStatus();
  latestState = result;
  renderDashboard(result.data, result.isCached, result.isDemo);
}

async function init() {
  setupViewTabs();
  setupWhatsAppShare(() => latestState.data);
  setupTapExplanations();
  await refreshStatus();

  // [UI-03] Automatic background refresh and tab wake-up refresh during storms
  setInterval(() => {
    refreshStatus();
  }, AUTO_REFRESH_MS);

  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") {
      refreshStatus();
    }
  });

  window.addEventListener("online", () => {
    refreshStatus();
  });

  window.addEventListener("offline", () => {
    renderDashboard(latestState.data, true, latestState.isDemo);
  });
}

init();
