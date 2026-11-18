from functools import lru_cache
from io import BytesIO
from pathlib import Path
import textwrap
from PIL import Image, ImageDraw, ImageFont


@lru_cache(maxsize=1)
def _resolve_unicode_font_path() -> str | None:
    """
    [PERF-01] & [PERF-02] Finds a system TrueType font supporting Portuguese diacritics
    across Linux (GCP Buildpacks) and Windows without importing heavy matplotlib/numpy.
    """
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ]
    for path_str in candidates:
        if Path(path_str).is_file():
            return path_str
    return None


@lru_cache(maxsize=64)
def _get_cached_font(font_path: str | None, size: int):
    """[PERF-02] Caches FreeType font handles in memory across sizing steps and invocations."""
    if font_path:
        try:
            return ImageFont.truetype(font_path, size)
        except OSError:
            pass
    return ImageFont.load_default(size=size)


def _measure_text_width(draw: ImageDraw.ImageDraw, text: str, font) -> float:
    """Returns the rendered pixel width of a single line of text."""
    try:
        return float(draw.textlength(text, font=font))
    except Exception:
        bbox = draw.textbbox((0, 0), text, font=font)
        return float(bbox[2] - bbox[0])


def _fit_font_to_width(
    draw: ImageDraw.ImageDraw,
    text: str,
    get_font_fn,
    initial_size: int,
    max_width: int,
    min_size: int = 16,
):
    """Steps down font size until `text` fits within `max_width` pixels."""
    size = initial_size
    while size > min_size:
        font = get_font_fn(size)
        if _measure_text_width(draw, text, font) <= max_width:
            return font
        size -= 2
    return get_font_fn(min_size)


def _wrap_text_pixel_safe(
    draw: ImageDraw.ImageDraw,
    text: str,
    font,
    max_width: int,
    max_lines: int = 3,
) -> list[str]:
    """
    Wraps `text` using `textwrap` and verifies every line against `max_width` in pixels
    so text never clips or overflows card boundaries on high-DPI mobile screens.
    """
    cleaned = " ".join((text or "").split())
    if not cleaned:
        return []

    # Start from a conservative character width estimate and refine by actual pixel width
    avg_char_px = max(7.0, _measure_text_width(draw, "M" * 10, font) / 10.0)
    est_chars = max(20, int(max_width / (avg_char_px * 0.72)))

    for width_chars in range(est_chars + 12, 14, -3):
        candidate_lines = textwrap.wrap(cleaned, width=width_chars, break_long_words=False)
        if all(_measure_text_width(draw, ln, font) <= max_width for ln in candidate_lines):
            if len(candidate_lines) <= max_lines:
                return candidate_lines
            # Truncate cleanly on the last allowed line if text is unusually long
            kept = candidate_lines[: max_lines - 1]
            tail = " ".join(candidate_lines[max_lines - 1 :])
            while tail and _measure_text_width(draw, tail + "…", font) > max_width:
                tail = tail[:-1].rstrip()
            kept.append((tail + "…") if tail else "…")
            return kept

    # Word-by-word fallback guaranteed to respect max_width
    words = cleaned.split(" ")
    lines: list[str] = []
    current = ""
    for word in words:
        test_line = f"{current} {word}".strip()
        if _measure_text_width(draw, test_line, font) <= max_width or not current:
            current = test_line
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines[:max_lines]


def generate_whatsapp_card(payload: dict) -> bytes:
    """Renders a 1080x1080 PNG status card with strict pixel bounds and text wrapping."""
    W, H = 1080, 1080
    PAD_X = 48
    CARD_INNER_PAD = 32
    FULL_TEXT_MAX_W = W - 2 * (PAD_X + CARD_INNER_PAD)  # 920 px

    img = Image.new("RGB", (W, H), color=(15, 23, 42))
    draw = ImageDraw.Draw(img)
    font_path = _resolve_unicode_font_path()

    def get_font(size: int):
        return _get_cached_font(font_path, size)

    banner_rgb = tuple(payload["banner"]["color_rgb"])
    tier = str(payload.get("risk_tier", "VERDE")).upper()
    is_light_banner = tier == "AMARELO"
    banner_fg = (15, 23, 42) if is_light_banner else (255, 255, 255)
    banner_sub_fg = (30, 41, 59) if is_light_banner else (241, 245, 249)

    s = payload["summary"]
    raw_trend = str(s.get("trend_label", "Tendência Estável"))
    clean_trend = raw_trend.lstrip("→↗↘⚠ ").strip()
    if not clean_trend.lower().startswith("tendência"):
        trend_display = f"Tendência: {clean_trend}"
    else:
        trend_display = clean_trend
    peak_window = s.get("peak_6h_window", "--:-- às --:--")

    # 1. Top Risk Banner (0 to 215)
    BANNER_MAX_W = W - 2 * PAD_X  # 984 px
    draw.rectangle([(0, 0), (W, 215)], fill=banner_rgb)

    header_tag = f"MONITORAMENTO HIDROLÓGICO INDEPENDENTE • RIO ICONHA - ES (v{payload['version']})"
    f_header = _fit_font_to_width(draw, header_tag, get_font, 23, BANNER_MAX_W)
    draw.text((PAD_X, 26), header_tag, fill=banner_sub_fg, font=f_header)

    title_text = payload["banner"]["title"]
    f_title = _fit_font_to_width(draw, title_text, get_font, 42, BANNER_MAX_W)
    draw.text((PAD_X, 72), title_text, fill=banner_fg, font=f_title)

    updated_text = f"Atualizado em: {payload['updated_at_br']}  •  {trend_display}"
    f_updated = _fit_font_to_width(draw, updated_text, get_font, 22, BANNER_MAX_W)
    draw.text((PAD_X, 148), updated_text, fill=banner_sub_fg, font=f_updated)

    # 2. Side-by-Side Comparison Boxes (Upstream vs Local, y=240..548)
    BOX_W = 474
    LEFT_X1, LEFT_X2 = PAD_X, PAD_X + BOX_W  # 48..522
    RIGHT_X1, RIGHT_X2 = W - PAD_X - BOX_W, W - PAD_X  # 558..1032
    HALF_TEXT_MAX_W = BOX_W - 2 * CARD_INNER_PAD  # 410 px

    f_box_label = get_font(20)

    # [UI-05] Highlight the 90% headwater box with an accented border so upstream danger stands out
    up_outline = banner_rgb if tier != "VERDE" else (56, 189, 248)

    # Left Box: Upstream (Cabeceira - 90% da Bacia)
    draw.rounded_rectangle(
        [(LEFT_X1, 238), (LEFT_X2, 550)],
        radius=20,
        fill=(30, 41, 59),
        outline=up_outline,
        width=3,
    )
    lx = LEFT_X1 + CARD_INNER_PAD
    up_tag = "CABECEIRA (ACIMA) • 90% BACIA"
    f_up_tag = _fit_font_to_width(draw, up_tag, get_font, 22, HALF_TEXT_MAX_W)
    draw.text((lx, 260), up_tag, fill=(56, 189, 248), font=f_up_tag)

    up_sub = "Crubixá • Monte Alegre • Duas Barras"
    f_up_sub = _fit_font_to_width(draw, up_sub, get_font, 19, HALF_TEXT_MAX_W)
    draw.text((lx, 292), up_sub, fill=(203, 213, 225), font=f_up_sub)

    up_val_str = f"{s['upstream_forecast_24h_mm']} mm"
    f_up_big = _fit_font_to_width(draw, up_val_str, get_font, 54, HALF_TEXT_MAX_W)
    draw.text((lx, 330), up_val_str, fill=(255, 255, 255), font=f_up_big)
    draw.text((lx, 408), "Chuva Prevista (Próx. 24h)", fill=(148, 163, 184), font=f_box_label)

    up_tc_str = f"Pico 6h (Tc): {s['upstream_tc_6h_mm']} mm"
    if peak_window and peak_window != "--:-- às --:--":
        up_tc_str += f" ({peak_window})"
    f_up_tc = _fit_font_to_width(draw, up_tc_str, get_font, 20, HALF_TEXT_MAX_W)
    draw.text((lx, 448), up_tc_str, fill=(56, 189, 248), font=f_up_tc)

    up_past72 = s.get("upstream_past_72h_mm", s.get("rain_past_72h_mm", 0.0))
    up_obs_str = f"Já Choveu (72h): {up_past72} mm"
    f_up_obs = _fit_font_to_width(draw, up_obs_str, get_font, 20, HALF_TEXT_MAX_W)
    draw.text((lx, 488), up_obs_str, fill=(203, 213, 225), font=f_up_obs)

    # Right Box: Local (Iconha Sede - 10% da Bacia)
    draw.rounded_rectangle(
        [(RIGHT_X1, 238), (RIGHT_X2, 550)],
        radius=20,
        fill=(30, 41, 59),
        outline=(51, 65, 85),
        width=2,
    )
    rx = RIGHT_X1 + CARD_INNER_PAD
    loc_tag = "ICONHA (SEDE) • 10% BACIA"
    f_loc_tag = _fit_font_to_width(draw, loc_tag, get_font, 22, HALF_TEXT_MAX_W)
    draw.text((rx, 260), loc_tag, fill=(148, 163, 184), font=f_loc_tag)

    loc_sub = "Centro • Vale Urbano (Baixo Curso)"
    f_loc_sub = _fit_font_to_width(draw, loc_sub, get_font, 19, HALF_TEXT_MAX_W)
    draw.text((rx, 292), loc_sub, fill=(203, 213, 225), font=f_loc_sub)

    loc_val_str = f"{s['local_iconha_24h_mm']} mm"
    f_loc_big = _fit_font_to_width(draw, loc_val_str, get_font, 54, HALF_TEXT_MAX_W)
    draw.text((rx, 330), loc_val_str, fill=(255, 255, 255), font=f_loc_big)
    draw.text((rx, 408), "Chuva Prevista (Próx. 24h)", fill=(148, 163, 184), font=f_box_label)

    loc_tc_str = f"Pico 6h (Tc): {s['local_iconha_tc_6h_mm']} mm"
    f_loc_tc = _fit_font_to_width(draw, loc_tc_str, get_font, 20, HALF_TEXT_MAX_W)
    draw.text((rx, 448), loc_tc_str, fill=(56, 189, 248), font=f_loc_tc)

    loc_past72 = s.get("local_iconha_past_72h_mm", s.get("rain_past_72h_mm", 0.0))
    loc_obs_str = f"Já Choveu (72h): {loc_past72} mm"
    f_loc_obs = _fit_font_to_width(draw, loc_obs_str, get_font, 20, HALF_TEXT_MAX_W)
    draw.text((rx, 488), loc_obs_str, fill=(203, 213, 225), font=f_loc_obs)

    # 3. SCS-CN Runoff & Copula Box (y=572..772)
    draw.rounded_rectangle(
        [(PAD_X, 572), (W - PAD_X, 772)],
        radius=20,
        fill=(30, 41, 59),
        outline=(51, 65, 85),
        width=2,
    )
    cx = PAD_X + CARD_INNER_PAD

    q6h_val = s.get("effective_runoff_6h_mm", 0.0)
    runoff_line = (
        f"ESCOAMENTO SUPERFICIAL (SCS-CN): {s['effective_runoff_24h_mm']} mm (Pico 6h: {q6h_val} mm)"
    )
    f_runoff = _fit_font_to_width(draw, runoff_line, get_font, 28, FULL_TEXT_MAX_W)
    draw.text((cx, 596), runoff_line, fill=(255, 255, 255), font=f_runoff)

    soil_line = f"Índice de Umidade (API 14d): {s['api_t_mm']} mm • {s['soil_status']}"
    f_soil = _fit_font_to_width(draw, soil_line, get_font, 24, FULL_TEXT_MAX_W)
    draw.text((cx, 652), soil_line, fill=(253, 224, 71), font=f_soil)

    t_ret = float(s.get("joint_return_period_years") or 0.0)
    if t_ret < 1.0:
        ret_str = f"< 1 ano ({max(0.1, t_ret):.1f} a • Rotineiro)"
    elif t_ret >= 9.0:
        ret_str = f"{t_ret:.1f} anos (Evento Extremo)"
    elif t_ret >= 2.0:
        ret_str = f"{t_ret:.1f} anos (Evento Severo)"
    else:
        ret_str = f"{t_ret:.1f} anos (Moderado)"

    copula_line = f"Tempo de Retorno Conjunto (Cópula de Gumbel): {ret_str}"
    f_copula = _fit_font_to_width(draw, copula_line, get_font, 22, FULL_TEXT_MAX_W)
    draw.text((cx, 708), copula_line, fill=(148, 163, 184), font=f_copula)

    # 4. Guidance Box with automatic pixel-bounded line wrapping (y=795..985)
    draw.rounded_rectangle(
        [(PAD_X, 795), (W - PAD_X, 985)],
        radius=20,
        fill=(36, 48, 68),
        outline=(51, 65, 85),
        width=2,
    )
    f_head_wrap = get_font(26)
    f_adv_wrap = get_font(22)

    headline_lines = _wrap_text_pixel_safe(
        draw, payload["banner"]["headline"], f_head_wrap, FULL_TEXT_MAX_W, max_lines=2
    )
    curr_y = 818
    for line in headline_lines:
        draw.text((cx, curr_y), line, fill=(255, 255, 255), font=f_head_wrap)
        curr_y += 34

    curr_y += 6
    remaining_lines = max(1, (968 - curr_y) // 30)
    advice_lines = _wrap_text_pixel_safe(
        draw, payload["banner"]["advice"], f_adv_wrap, FULL_TEXT_MAX_W, max_lines=remaining_lines
    )
    for line in advice_lines:
        draw.text((cx, curr_y), line, fill=(203, 213, 225), font=f_adv_wrap)
        curr_y += 30

    # 5. Independent Monitoring Footer (y=1014)
    footer_text = (
        "Monitoramento Hidrológico Independente - Rio Iconha • Modelos: SCS-CN + GPD/Gumbel"
    )
    f_footer = _fit_font_to_width(draw, footer_text, get_font, 21, BANNER_MAX_W)
    draw.text((PAD_X, 1016), footer_text, fill=(148, 163, 184), font=f_footer)

    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
