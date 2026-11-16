const CACHE_KEY = "iconha_flood_status_v2";
const utf8Decoder = new TextDecoder("utf-8");

export const DEMO_FALLBACK = {
  version: "0.1.0",
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
    api_t_mm: 18.4,
    soil_status: "AMC I (Solo Seco)",
    cn_effective: 62.1,
    effective_runoff_24h_mm: 0.0,
    effective_runoff_6h_mm: 0.0,
    joint_return_period_years: 0.4,
    upstream_forecast_24h_mm: 5.2,
    upstream_tc_6h_mm: 3.1,
    local_iconha_24h_mm: 3.8,
    local_iconha_tc_6h_mm: 2.0
  },
  points: [
    { id: "P1_CRUBIXA", zone: "upper", weight: 0.35, rain_past_72h_mm: 4.0 },
    { id: "P2_MONTE_ALEGRE", zone: "upper", weight: 0.30, rain_past_72h_mm: 3.5 },
    { id: "P3_DUAS_BARRAS", zone: "middle", weight: 0.25, rain_past_72h_mm: 2.8 },
    { id: "P4_ICONHA_SEDE", zone: "lower", weight: 0.10, rain_past_72h_mm: 1.5 }
  ],
  chart_12h_upstream: [
    { hour: "14:00", mm: 0.0 }, { hour: "15:00", mm: 0.5 }, { hour: "16:00", mm: 1.4 },
    { hour: "17:00", mm: 1.2 }, { hour: "18:00", mm: 0.4 }, { hour: "19:00", mm: 0.0 },
    { hour: "20:00", mm: 0.0 }, { hour: "21:00", mm: 0.0 }, { hour: "22:00", mm: 0.3 },
    { hour: "23:00", mm: 0.6 }, { hour: "00:00", mm: 0.5 }, { hour: "01:00", mm: 0.3 }
  ]
};

export async function fetchBasinStatus() {
  if (typeof navigator !== "undefined" && navigator.onLine === false) {
    return readLocalFallback();
  }

  try {
    const res = await fetch(`./status.json?t=${Date.now()}`, { cache: "no-store" });
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
