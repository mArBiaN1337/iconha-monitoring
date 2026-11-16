import { formatTimestampBR } from "./components.js";

export function setupWhatsAppShare(getStateFn) {
  const btn = document.getElementById("shareBtn");
  btn.addEventListener("click", async () => {
    const d = getStateFn();
    const s = d.summary;
    const updatedStr = formatTimestampBR(d);
    const shareText =
      `*${d.banner.title} - Rio Iconha (ES)*\n` +
      `Atualizado em: ${updatedStr}\n\n` +
      `• *Cabeceira (Acima - 24h):* ${s.upstream_forecast_24h_mm} mm (Pico 6h: ${s.upstream_tc_6h_mm} mm)\n` +
      `• *Iconha Sede (24h):* ${s.local_iconha_24h_mm} mm (Pico 6h: ${s.local_iconha_tc_6h_mm} mm)\n` +
      `• *Escoamento Superficial (SCS-CN):* ${s.effective_runoff_24h_mm} mm\n` +
      `• *Solo (API):* ${s.api_t_mm} mm (${s.soil_status})\n` +
      `• *Tempo de Retorno Conjunto:* ${s.joint_return_period_years} anos\n\n` +
      `${d.banner.advice}\n` +
      `Painel ao vivo: ${window.location.href}`;

    if (navigator.share) {
      try {
        await navigator.share({
          title: "Monitor Hidrológico - Rio Iconha",
          text: shareText,
          url: window.location.href
        });
        return;
      } catch (_) {
        // Fallback to WhatsApp web URL when native share is dismissed or unavailable
      }
    }
    window.open(`https://wa.me/?text=${encodeURIComponent(shareText)}`, "_blank", "noopener,noreferrer");
  });
}
