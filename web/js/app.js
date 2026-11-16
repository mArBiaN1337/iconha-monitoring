import { fetchBasinStatus, DEMO_FALLBACK } from "./api.js";
import { renderDashboard } from "./components.js";
import { setupWhatsAppShare } from "./share.js";

let latestState = DEMO_FALLBACK;

async function init() {
  setupWhatsAppShare(() => latestState);
  const { data, isCached } = await fetchBasinStatus();
  latestState = data;
  renderDashboard(data, isCached);
}

init();