const CACHE_KEY = "iconha_flood_status_v2";
const utf8Decoder = new TextDecoder("utf-8");

export const DEMO_FALLBACK = {
  version: "2.0.0",
  updated_at_iso: "2026-11-16T00:00:00-03:00",
  updated_at_br: "16/11/2026 às 00:00",
  risk_tier: "VERDE",
  banner: {
    color_hex: "#2E7D32",
    title: "NÍVEL VERDE: NORMALIDADE",
    headline: "Bacia do Rio Iconha em condições normais.",
    advice: "Infiltração segura no solo. Sem previsão de escoamento superficial crítico."
  },
  summary: {
    trend_state: "STABLE",
    trend_label: "→ Tendência Estável",
    peak_6h_window: "15:00 às 21:00",
    api_t_mm: 18.4,
    soil_status: "AMC I (Solo Seco)",
    cn_effective: 62.1,
    effective_runoff_24h_mm: 0.0,
    effective_runoff_6h_mm: 0.0,
    joint_return_period_years: 0.4,
    upstream_forecast_24h_mm: 5.2,
    upstream_tc_6h_mm: 3.1,
    upstream_past_6h_mm: 0.8,
    upstream_past_72h_mm: 3.5,
    local_iconha_24h_mm: 3.8,
    local_iconha_tc_6h_mm: 2.0,
    local_iconha_past_6h_mm: 0.3,
    local_iconha_past_72h_mm: 1.5,
    rain_past_72h_mm: 3.3
  },
  points: [
    { id: "P1_CRUBIXA", zone: "upper", weight: 0.35, rain_past_72h_mm: 4.0 },
    { id: "P2_MONTE_ALEGRE", zone: "upper", weight: 0.30, rain_past_72h_mm: 3.5 },
    { id: "P3_DUAS_BARRAS", zone: "middle", weight: 0.25, rain_past_72h_mm: 2.8 },
    { id: "P4_ICONHA_SEDE", zone: "lower", weight: 0.10, rain_past_72h_mm: 1.5 }
  ],
  chart_12h_upstream: [
    { hour: "11:00", mm: 0.0, kind: "observed", is_now: false },
    { hour: "12:00", mm: 0.3, kind: "observed", is_now: false },
    { hour: "13:00", mm: 0.5, kind: "observed", is_now: false },
    { hour: "14:00", mm: 0.0, kind: "forecast", is_now: true },
    { hour: "15:00", mm: 0.5, kind: "forecast", is_now: false },
    { hour: "16:00", mm: 1.4, kind: "forecast", is_now: false },
    { hour: "17:00", mm: 1.2, kind: "forecast", is_now: false },
    { hour: "18:00", mm: 0.4, kind: "forecast", is_now: false },
    { hour: "19:00", mm: 0.0, kind: "forecast", is_now: false },
    { hour: "20:00", mm: 0.0, kind: "forecast", is_now: false },
    { hour: "21:00", mm: 0.0, kind: "forecast", is_now: false },
    { hour: "22:00", mm: 0.3, kind: "forecast", is_now: false }
  ]
};

export function getEdgeCacheSlot() {
  // [PERF-03] 5-minute epoch slot matching GCS `Cache-Control: public, max-age=300`
  // Protects the 50,000 Class B reads/month Always-Free Tier limit under storm traffic spikes
  return Math.floor(Date.now() / 300000);
}

export async function fetchBasinStatus() {
  if (typeof navigator !== "undefined" && navigator.onLine === false) {
    return readLocalFallback();
  }

  try {
    const slot = getEdgeCacheSlot();
    const res = await fetch(`./status.json?v=${slot}`, { cache: "default" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const buffer = await res.arrayBuffer();
    const data = JSON.parse(utf8Decoder.decode(buffer));
    localStorage.setItem(CACHE_KEY, JSON.stringify(data));
    return { data, isCached: false, isDemo: false };
  } catch (_) {
    return readLocalFallback();
  }
}

function readLocalFallback() {
  const cached = localStorage.getItem(CACHE_KEY);
  if (cached) {
    try {
      return { data: JSON.parse(cached), isCached: true, isDemo: false };
    } catch (_) {
      // Ignore corrupted local cache and fall back to demo baseline
    }
  }
  return { data: DEMO_FALLBACK, isCached: true, isDemo: true };
}
