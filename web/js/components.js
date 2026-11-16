const TIER_STYLES = {
  VERDE: { bg: "#2E7D32", light: false },
  AMARELO: { bg: "#F9A825", light: true },
  LARANJA: { bg: "#EF6C00", light: false },
  VERMELHO: { bg: "#C62828", light: false }
};

export function formatTimestampBR(data) {
  if (
    typeof data?.updated_at_br === "string" &&
    /^\d{2}\/\d{2}\/\d{4} às \d{2}:\d{2}$/.test(data.updated_at_br.trim())
  ) {
    return data.updated_at_br.trim();
  }

  if (data?.updated_at_iso) {
    const parsed = new Date(data.updated_at_iso);
    if (!Number.isNaN(parsed.getTime())) {
      const parts = new Intl.DateTimeFormat("pt-BR", {
        timeZone: "America/Sao_Paulo",
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false
      }).formatToParts(parsed);
      const get = (type) => parts.find((p) => p.type === type)?.value || "00";
      return `${get("day")}/${get("month")}/${get("year")} às ${get("hour")}:${get("minute")}`;
    }
  }

  return "--/--/---- às --:--";
}

function formatNum(value, decimals = 1) {
  const num = Number(value);
  return Number.isFinite(num) ? num.toFixed(decimals) : "--";
}

function computeWeighted72hRain(data) {
  if (Array.isArray(data?.points) && data.points.length > 0) {
    const total = data.points.reduce((acc, pt) => {
      const rain = Number(pt.rain_past_72h_mm);
      const weight = Number(pt.weight);
      if (!Number.isFinite(rain) || !Number.isFinite(weight)) return acc;
      return acc + rain * weight;
    }, 0);
    return total.toFixed(1);
  }
  return formatNum(data?.summary?.rain_past_72h_mm, 1);
}

export function renderDashboard(data, isCached = false, isDemo = false) {
  const b = data.banner || {};
  const s = data.summary || {};
  const tierKey = String(data.risk_tier || "VERDE").toUpperCase();
  const tierStyle = TIER_STYLES[tierKey] || {
    bg: b.color_hex || "#2E7D32",
    light: false
  };

  const bannerEl = document.getElementById("riskBanner");
  bannerEl.style.background = tierStyle.bg;
  bannerEl.classList.toggle("banner--light", tierStyle.light);

  const formattedTime = formatTimestampBR(data);
  const connBadge = document.getElementById("connBadge");
  const offlineNotice = document.getElementById("offlineNotice");
  const offlineTime = document.getElementById("offlineTime");
  const isOfflineState = isCached || (typeof navigator !== "undefined" && navigator.onLine === false);

  if (isOfflineState) {
    connBadge.textContent = isDemo ? "Offline (Demo)" : "Offline (Cache)";
    connBadge.classList.add("is-offline");
    offlineNotice.hidden = false;
    offlineTime.textContent = formattedTime;
  } else {
    connBadge.textContent = "Ao vivo";
    connBadge.classList.remove("is-offline");
    offlineNotice.hidden = true;
  }

  document.getElementById("updatedAt").textContent = formattedTime;
  document.getElementById("riskTitle").textContent = b.title || "NÍVEL VERDE: NORMALIDADE";
  document.getElementById("riskAdvice").textContent = `${b.headline || ""} ${b.advice || ""}`.trim();

  document.getElementById("up24h").textContent = formatNum(s.upstream_forecast_24h_mm, 1);
  document.getElementById("upTc6h").textContent = formatNum(s.upstream_tc_6h_mm, 1);
  document.getElementById("loc24h").textContent = formatNum(s.local_iconha_24h_mm, 1);
  document.getElementById("locTc6h").textContent = formatNum(s.local_iconha_tc_6h_mm, 1);

  document.getElementById("qEff24h").textContent = formatNum(s.effective_runoff_24h_mm, 1);
  document.getElementById("soilStatus").textContent = s.soil_status || "AMC I";
  document.getElementById("apiT").textContent = formatNum(s.api_t_mm, 1);
  document.getElementById("rain72h").textContent = computeWeighted72hRain(data);
  document.getElementById("returnPeriod").textContent = formatNum(s.joint_return_period_years, 1);

  if (data.version) {
    document.getElementById("appVersion").textContent = `v${data.version}`;
  }

  const apiNum = Number(s.api_t_mm) || 0;
  const pct = Math.round(Math.min(100, Math.max(6, (apiNum / 90.0) * 100)));
  document.getElementById("soilBar").style.width = `${pct}%`;
  document.getElementById("soilProgress").setAttribute("aria-valuenow", String(pct));

  renderUpstreamChart(data.chart_12h_upstream || []);
}

function renderUpstreamChart(series) {
  const chartEl = document.getElementById("chartBars");
  const hintEl = document.getElementById("chartHint");
  chartEl.innerHTML = "";

  const maxMm = Math.max(15, ...series.map((d) => Number(d.mm) || 0));

  series.forEach((item) => {
    const mm = Number(item.mm) || 0;
    const heightPct = Math.max(6, Math.round((mm / maxMm) * 100));
    const intensityLabel = mm >= 20 ? "Forte" : mm >= 10 ? "Moderada" : mm > 0 ? "Fraca" : "Sem chuva";
    const barColor =
      mm >= 20 ? "#C62828" : mm >= 10 ? "#F9A825" : "#38bdf8";

    const col = document.createElement("div");
    col.className = `bar-col${mm <= 0 ? " is-dry" : ""}`;
    col.tabIndex = 0;
    col.title = `${item.hour}: ${mm.toFixed(1)} mm/h (${intensityLabel})`;
    col.setAttribute("aria-label", `${item.hour}, ${mm.toFixed(1)} milímetros por hora, ${intensityLabel}`);

    col.innerHTML = `
      <div class="bar-val">${mm > 0 ? mm.toFixed(1) : ""}</div>
      <div class="bar-stick" style="height:${heightPct}%; background:${barColor};"></div>
      <div class="bar-hr">${String(item.hour || "").slice(0, 2)}h</div>
    `;

    const selectBar = () => {
      chartEl.querySelectorAll(".bar-col.is-selected").forEach((el) => el.classList.remove("is-selected"));
      col.classList.add("is-selected");
      hintEl.textContent = `${item.hour} nas cabeceiras: ${mm.toFixed(1)} mm/h (${intensityLabel}).`;
    };

    col.addEventListener("click", selectBar);
    col.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        selectBar();
      }
    });

    chartEl.appendChild(col);
  });
}
