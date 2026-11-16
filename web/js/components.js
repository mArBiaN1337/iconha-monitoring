export function renderDashboard(data, isCached = false) {
  const b = data.banner;
  const s = data.summary;

  document.getElementById("riskBanner").style.background = b.color_hex;
  document.getElementById("updatedAt").textContent = isCached
    ? `Offline (${data.updated_at_br})`
    : data.updated_at_br;
  document.getElementById("riskTitle").textContent = b.title;
  document.getElementById("riskAdvice").textContent = `${b.headline} ${b.advice}`;

  document.getElementById("up24h").textContent = s.upstream_forecast_24h_mm;
  document.getElementById("upTc6h").textContent = s.upstream_tc_6h_mm;
  document.getElementById("loc24h").textContent = s.local_iconha_24h_mm;
  document.getElementById("locTc6h").textContent = s.local_iconha_tc_6h_mm;

  document.getElementById("qEff24h").textContent = s.effective_runoff_24h_mm;
  document.getElementById("soilStatus").textContent = s.soil_status;
  document.getElementById("apiT").textContent = s.api_t_mm;
  document.getElementById("returnPeriod").textContent = s.joint_return_period_years;

  if (data.version) {
    document.getElementById("appVersion").textContent = `v${data.version}`;
  }

  const pct = Math.min(100, Math.max(6, (s.api_t_mm / 90.0) * 100));
  document.getElementById("soilBar").style.width = `${pct}%`;

  const chartEl = document.getElementById("chartBars");
  chartEl.innerHTML = "";
  const maxMm = Math.max(15, ...data.chart_12h_upstream.map((d) => d.mm));

  data.chart_12h_upstream.forEach((item) => {
    const heightPct = Math.max(6, Math.round((item.mm / maxMm) * 100));
    const barColor =
      item.mm >= 20 ? "#ef4444" : item.mm >= 10 ? "#f59e0b" : "#38bdf8";
    const col = document.createElement("div");
    col.className = "bar-col";
    col.innerHTML = `
      <div class="bar-val">${item.mm > 0 ? item.mm : ""}</div>
      <div class="bar-stick" style="height:${heightPct}%; background:${barColor};"></div>
      <div class="bar-hr">${item.hour.slice(0, 2)}h</div>
    `;
    chartEl.appendChild(col);
  });
}