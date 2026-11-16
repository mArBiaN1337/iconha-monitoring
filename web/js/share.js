import { formatTimestampBR } from "./components.js";

const SHARE_TITLE = "Monitoramento Hidrológico Independente - Rio Iconha";

function getCleanPanelUrl() {
  try {
    const u = new URL(window.location.href);
    u.search = "";
    u.hash = "";
    return u.toString();
  } catch (_) {
    return window.location.href.split("?")[0].split("#")[0];
  }
}

export function buildWhatsAppSummaryText(d) {
  const b = d?.banner || {};
  const s = d?.summary || {};
  const updatedStr = formatTimestampBR(d);
  const panelUrl = getCleanPanelUrl();

  return (
    `*${SHARE_TITLE}*\n` +
    `*Status:* ${b.title || "NÍVEL VERDE: NORMALIDADE"}\n` +
    `Atualizado em: ${updatedStr}\n\n` +
    `• *Cabeceira (Acima - 24h):* ${s.upstream_forecast_24h_mm} mm (Pico 6h: ${s.upstream_tc_6h_mm} mm)\n` +
    `• *Iconha Sede (24h):* ${s.local_iconha_24h_mm} mm (Pico 6h: ${s.local_iconha_tc_6h_mm} mm)\n` +
    `• *Escoamento Superficial (Q_eff):* ${s.effective_runoff_24h_mm} mm\n` +
    `• *Umidade do Solo (API):* ${s.api_t_mm} mm (${s.soil_status})\n` +
    `• *Tempo de Retorno Conjunto:* ${s.joint_return_period_years} anos\n\n` +
    `${b.headline ? `${b.headline} ` : ""}${b.advice || ""}\n\n` +
    `Painel ao vivo: ${panelUrl}`
  );
}

async function fetchCardImageFile() {
  const res = await fetch(`./card_whatsapp.png?t=${Date.now()}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const blob = await res.blob();
  return new File([blob], "card_whatsapp.png", { type: "image/png" });
}

export function setupWhatsAppShare(getStateFn) {
  const btn = document.getElementById("shareBtn");
  if (!btn) return;

  btn.addEventListener("click", async () => {
    const state = getStateFn();
    const shareText = buildWhatsAppSummaryText(state);

    // 1. Mobile Native Web Share API with PNG Card File + Single-URL Caption
    if (typeof navigator !== "undefined" && typeof navigator.share === "function") {
      try {
        const cardFile = await fetchCardImageFile();
        if (
          typeof navigator.canShare === "function" &&
          navigator.canShare({ files: [cardFile] })
        ) {
          // Do NOT pass a separate `url` property alongside `text` so the panel link is never duplicated
          await navigator.share({
            files: [cardFile],
            title: SHARE_TITLE,
            text: shareText
          });
          return;
        }
      } catch (err) {
        if (err && err.name === "AbortError") {
          return;
        }
        // Proceed to WhatsApp Web fallback if image fetch or file share is unsupported
      }
    }

    // 2. Desktop / Unsupported Browser Fallback via Official WhatsApp Web Intent
    const waUrl = `https://api.whatsapp.com/send?text=${encodeURIComponent(shareText)}`;
    window.open(waUrl, "_blank", "noopener,noreferrer");
  });
}
