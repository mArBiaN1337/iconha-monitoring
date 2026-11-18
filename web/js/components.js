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
  if (Number.isFinite(Number(data?.summary?.rain_past_72h_mm))) {
    return Number(data.summary.rain_past_72h_mm).toFixed(1);
  }
  if (Array.isArray(data?.points) && data.points.length > 0) {
    const total = data.points.reduce((acc, pt) => {
      const rain = Number(pt.rain_past_72h_mm);
      const weight = Number(pt.weight);
      if (!Number.isFinite(rain) || !Number.isFinite(weight)) return acc;
      return acc + rain * weight;
    }, 0);
    return total.toFixed(1);
  }
  return "--";
}

function computeUpstream72hRain(data) {
  if (Number.isFinite(Number(data?.summary?.upstream_past_72h_mm))) {
    return Number(data.summary.upstream_past_72h_mm).toFixed(1);
  }
  if (Array.isArray(data?.points) && data.points.length > 0) {
    const total = data.points.reduce((acc, pt) => {
      if (pt.zone !== "upper" && pt.zone !== "middle") return acc;
      const rain = Number(pt.rain_past_72h_mm);
      const weight = Number(pt.weight);
      if (!Number.isFinite(rain) || !Number.isFinite(weight)) return acc;
      return acc + rain * (weight / 0.9);
    }, 0);
    return total.toFixed(1);
  }
  return "--";
}

function computeLocal72hRain(data) {
  if (Number.isFinite(Number(data?.summary?.local_iconha_past_72h_mm))) {
    return Number(data.summary.local_iconha_past_72h_mm).toFixed(1);
  }
  if (Array.isArray(data?.points)) {
    const loc = data.points.find((pt) => pt.zone === "lower");
    if (loc && Number.isFinite(Number(loc.rain_past_72h_mm))) {
      return Number(loc.rain_past_72h_mm).toFixed(1);
    }
  }
  return "--";
}

function computeDataAgeInfo(data) {
  if (!data?.updated_at_iso) {
    return { ageHours: 0, relativeLabel: "" };
  }
  const parsed = new Date(data.updated_at_iso);
  if (Number.isNaN(parsed.getTime())) {
    return { ageHours: 0, relativeLabel: "" };
  }
  const diffMs = Math.max(0, Date.now() - parsed.getTime());
  const ageMin = Math.round(diffMs / 60000);
  const ageHours = diffMs / 3600000;

  if (ageMin < 2) {
    return { ageHours, relativeLabel: "agora" };
  }
  if (ageMin < 60) {
    return { ageHours, relativeLabel: `há ${ageMin} min` };
  }
  const hrs = Math.floor(ageHours);
  return { ageHours, relativeLabel: `há ${hrs}h` };
}

function formatReturnPeriodDisplay(val) {
  const num = Number(val);
  if (!Number.isFinite(num)) return "--";
  if (num < 1.0) {
    return `< 1 ano (${Math.max(0.1, num).toFixed(1)}a)`;
  }
  return `${num.toFixed(1)} anos`;
}

export function setupViewTabs() {
  const tabIntroBtn = document.getElementById("tabIntroBtn");
  const tabAnalysisBtn = document.getElementById("tabAnalysisBtn");
  const openAnalysisBtn = document.getElementById("openAnalysisBtn");
  const introView = document.getElementById("introView");
  const analysisView = document.getElementById("analysisView");

  if (!tabIntroBtn || !tabAnalysisBtn || !introView || !analysisView) return;

  const setView = (mode) => {
    const showIntro = mode === "intro";
    introView.hidden = !showIntro;
    analysisView.hidden = showIntro;
    tabIntroBtn.classList.toggle("is-active", showIntro);
    tabIntroBtn.setAttribute("aria-selected", String(showIntro));
    tabAnalysisBtn.classList.toggle("is-active", !showIntro);
    tabAnalysisBtn.setAttribute("aria-selected", String(!showIntro));
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  tabIntroBtn.addEventListener("click", () => setView("intro"));
  tabAnalysisBtn.addEventListener("click", () => setView("analysis"));
  if (openAnalysisBtn) {
    openAnalysisBtn.addEventListener("click", () => setView("analysis"));
  }
}

export function setupTapExplanations() {
  // [UI-04] Mobile touch accessibility: tapping any underlined metric shows its explanation
  const explainEl = document.getElementById("soilExplain");
  if (!explainEl) return;

  document.querySelectorAll(".tooltip-hint").forEach((el) => {
    const showHint = () => {
      const hint = el.getAttribute("title");
      if (hint) {
        explainEl.textContent = `ℹ ${hint}`;
      }
    };
    el.addEventListener("click", showHint);
    el.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        showHint();
      }
    });
  });
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

  // Sync live tier status pill on the Introductory Guide Card & Tab Indicator
  const introTierPill = document.getElementById("introTierPill");
  if (introTierPill) {
    introTierPill.textContent = `Agora: NÍVEL ${tierKey}`;
    introTierPill.style.background = tierStyle.bg;
    introTierPill.style.color = tierStyle.light ? "#0f172a" : "#ffffff";
  }
  const tabLiveDot = document.getElementById("tabLiveDot");
  if (tabLiveDot) {
    tabLiveDot.style.background = tierStyle.bg;
    tabLiveDot.title = b.title || `NÍVEL ${tierKey}`;
  }

  // [UI-01] Hydrological Trajectory & Trend Badge
  const trendBadge = document.getElementById("trendBadge");
  if (trendBadge) {
    const trendState = String(s.trend_state || "STABLE").toUpperCase();
    const shortTrend =
      trendState === "PEAKING"
        ? "⚠ Pico 6h"
        : trendState === "RISING"
          ? "↗ Subindo"
          : trendState === "RECEDING"
            ? "↘ Recuando"
            : "→ Estável";
    trendBadge.textContent = shortTrend;
    trendBadge.title = s.trend_label || "Tendência hidrológica para as próximas 6 horas";
    trendBadge.classList.toggle("is-rising", trendState === "RISING");
    trendBadge.classList.toggle("is-peaking", trendState === "PEAKING");
  }

  // [UI-03] Stale Data Warning (>2h) & Offline Resilience Strip
  const formattedTime = formatTimestampBR(data);
  const { ageHours, relativeLabel } = computeDataAgeInfo(data);
  const isStale = ageHours >= 2.0;
  const connBadge = document.getElementById("connBadge");
  const offlineNotice = document.getElementById("offlineNotice");
  const isOfflineState = isCached || (typeof navigator !== "undefined" && navigator.onLine === false);

  connBadge.classList.remove("is-offline", "is-stale");
  offlineNotice.classList.remove("is-critical-stale");

  if (isOfflineState) {
    connBadge.textContent = isDemo
      ? "Offline (Demo)"
      : isStale
        ? `Cache Antigo (${relativeLabel})`
        : "Offline (Cache)";
    connBadge.classList.add("is-offline");
    offlineNotice.hidden = false;
    if (isStale) {
      offlineNotice.classList.add("is-critical-stale");
      offlineNotice.textContent = `⚠ Atenção: Sem conexão. Exibindo boletim salvo ${relativeLabel} (${formattedTime}). O nível do rio pode ter mudado rapidamente.`;
    } else {
      offlineNotice.textContent = `Modo Offline (Cache Local) — exibindo último boletim salvo em ${formattedTime} (${relativeLabel || "recente"}).`;
    }
  } else if (isStale) {
    connBadge.textContent = `Desatualizado (${relativeLabel})`;
    connBadge.classList.add("is-stale");
    offlineNotice.hidden = false;
    offlineNotice.classList.add("is-critical-stale");
    offlineNotice.textContent = `⚠ Atenção: Este boletim foi gerado ${relativeLabel} (${formattedTime}). Verifique atualizações caso esteja chovendo forte nas cabeceiras.`;
  } else {
    connBadge.textContent = relativeLabel ? `Ao vivo • ${relativeLabel}` : "Ao vivo";
    offlineNotice.hidden = true;
  }

  document.getElementById("updatedAt").textContent = formattedTime;
  document.getElementById("riskTitle").textContent = b.title || "NÍVEL VERDE: NORMALIDADE";
  document.getElementById("riskAdvice").textContent = `${b.headline || ""} ${b.advice || ""}`.trim();

  document.getElementById("up24h").textContent = formatNum(s.upstream_forecast_24h_mm, 1);
  document.getElementById("upTc6h").textContent = formatNum(s.upstream_tc_6h_mm, 1);
  const upPeakEl = document.getElementById("upPeakWindow");
  if (upPeakEl) {
    const win = s.peak_6h_window;
    upPeakEl.textContent = win && win !== "--:-- às --:--" ? `(${win})` : "";
  }
  const upPastEl = document.getElementById("upPast72h");
  if (upPastEl) {
    upPastEl.textContent = computeUpstream72hRain(data);
  }

  document.getElementById("loc24h").textContent = formatNum(s.local_iconha_24h_mm, 1);
  document.getElementById("locTc6h").textContent = formatNum(s.local_iconha_tc_6h_mm, 1);
  const locPastEl = document.getElementById("locPast72h");
  if (locPastEl) {
    locPastEl.textContent = computeLocal72hRain(data);
  }

  document.getElementById("qEff24h").textContent = formatNum(s.effective_runoff_24h_mm, 1);
  document.getElementById("soilStatus").textContent = s.soil_status || "AMC I";
  document.getElementById("apiT").textContent = formatNum(s.api_t_mm, 1);
  document.getElementById("rain72h").textContent = computeWeighted72hRain(data);
  document.getElementById("returnPeriod").textContent = formatReturnPeriodDisplay(s.joint_return_period_years);

  if (data.version) {
    document.getElementById("appVersion").textContent = `v${data.version}`;
  }

  const apiNum = Number(s.api_t_mm) || 0;
  const pct = Math.round(Math.min(100, Math.max(6, (apiNum / 110.0) * 100)));
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
    const isObs = item.kind === "observed";
    const isNow = Boolean(item.is_now);
    const heightPct = Math.max(6, Math.round((mm / maxMm) * 100));
    const intensityLabel = mm >= 20 ? "Forte" : mm >= 10 ? "Moderada" : mm > 0 ? "Fraca" : "Sem chuva";
    const kindLabel = isObs ? "Já choveu (Observado)" : isNow ? "Agora (Previsão)" : "Previsto";
    const barColor =
      mm >= 20
        ? "#C62828"
        : mm >= 10
          ? "#F9A825"
          : isObs
            ? "#94a3b8"
            : "#38bdf8";

    const classes = ["bar-col"];
    if (mm <= 0) classes.push("is-dry");
    if (isObs) classes.push("is-observed");
    if (isNow) classes.push("is-now-boundary");

    const col = document.createElement("div");
    col.className = classes.join(" ");
    col.tabIndex = 0;
    col.title = `${item.hour} (${kindLabel}): ${mm.toFixed(1)} mm/h (${intensityLabel})`;
    col.setAttribute("aria-label", `${item.hour}, ${kindLabel}, ${mm.toFixed(1)} milímetros por hora, ${intensityLabel}`);

    col.innerHTML = `
      <div class="bar-val">${mm > 0 ? mm.toFixed(1) : ""}</div>
      <div class="bar-stick" style="height:${heightPct}%; background:${barColor};"></div>
      <div class="bar-hr">${String(item.hour || "").slice(0, 2)}h</div>
    `;

    const selectBar = () => {
      chartEl.querySelectorAll(".bar-col.is-selected").forEach((el) => el.classList.remove("is-selected"));
      col.classList.add("is-selected");
      hintEl.textContent = `${item.hour} • ${kindLabel} nas cabeceiras: ${mm.toFixed(1)} mm/h (${intensityLabel}).`;
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
