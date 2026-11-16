from io import BytesIO
from pathlib import Path
import textwrap
from PIL import Image, ImageDraw, ImageFont


def _resolve_unicode_font_path() -> str | None:
    """Finds a TrueType font supporting Portuguese diacritics across OSes."""
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ]
    try:
        import matplotlib

        candidates.append(
            str(Path(matplotlib.get_data_path()) / "fonts" / "ttf" / "DejaVuSans-Bold.ttf")
        )
    except ImportError:
        pass

    for path_str in candidates:
        if Path(path_str).is_file():
            return path_str
    return None


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
        if font_path:
            try:
                return ImageFont.truetype(font_path, size)
            except OSError:
                pass
        return ImageFont.load_default(size=size)

    banner_rgb = tuple(payload["banner"]["color_rgb"])
    tier = str(payload.get("risk_tier", "VERDE")).upper()
    is_light_banner = tier == "AMARELO"
    banner_fg = (15, 23, 42) if is_light_banner else (255, 255, 255)
    banner_sub_fg = (30, 41, 59) if is_light_banner else (241, 245, 249)

    s = payload["summary"]

    # 1. Top Risk Banner (0 to 215)
    BANNER_MAX_W = W - 2 * PAD_X  # 984 px
    draw.rectangle([(0, 0), (W, 215)], fill=banner_rgb)

    header_tag = f"MONITORAMENTO HIDROLÓGICO INDEPENDENTE • RIO ICONHA - ES (v{payload['version']})"
    f_header = _fit_font_to_width(draw, header_tag, get_font, 24, BANNER_MAX_W)
    draw.text((PAD_X, 28), header_tag, fill=banner_sub_fg, font=f_header)

    title_text = payload["banner"]["title"]
    f_title = _fit_font_to_width(draw, title_text, get_font, 42, BANNER_MAX_W)
    draw.text((PAD_X, 74), title_text, fill=banner_fg, font=f_title)

    updated_text = f"Atualizado em: {payload['updated_at_br']}"
    f_updated = _fit_font_to_width(draw, updated_text, get_font, 23, BANNER_MAX_W)
    draw.text((PAD_X, 148), updated_text, fill=banner_sub_fg, font=f_updated)

    # 2. Side-by-Side Comparison Boxes (Upstream vs Local, y=240..545)
    BOX_W = 474
    LEFT_X1, LEFT_X2 = PAD_X, PAD_X + BOX_W  # 48..522
    RIGHT_X1, RIGHT_X2 = W - PAD_X - BOX_W, W - PAD_X  # 558..1032
    HALF_TEXT_MAX_W = BOX_W - 2 * CARD_INNER_PAD  # 410 px

    f_box_tag = get_font(25)
    f_box_sub = get_font(21)
    f_box_label = get_font(21)

    # Left Box: Upstream (Cabeceira)
    draw.rounded_rectangle(
        [(LEFT_X1, 240), (LEFT_X2, 545)],
        radius=20,
        fill=(30, 41, 59),
        outline=(51, 65, 85),
        width=2,
    )
    lx = LEFT_X1 + CARD_INNER_PAD
    draw.text((lx, 264), "CABECEIRA (ACIMA)", fill=(148, 163, 184), font=f_box_tag)
    up_sub = "Crubixá • Monte Alegre • Duas Barras"
    f_up_sub = _fit_font_to_width(draw, up_sub, get_font, 20, HALF_TEXT_MAX_W)
    draw.text((lx, 300), up_sub, fill=(203, 213, 225), font=f_up_sub)

    up_val_str = f"{s['upstream_forecast_24h_mm']} mm"
    f_up_big = _fit_font_to_width(draw, up_val_str, get_font, 58, HALF_TEXT_MAX_W)
    draw.text((lx, 344), up_val_str, fill=(255, 255, 255), font=f_up_big)
    draw.text((lx, 430), "Chuva Prevista (24h)", fill=(148, 163, 184), font=f_box_label)

    up_tc_str = f"Pico 6h (Tc): {s['upstream_tc_6h_mm']} mm"
    f_up_tc = _fit_font_to_width(draw, up_tc_str, get_font, 22, HALF_TEXT_MAX_W)
    draw.text((lx, 476), up_tc_str, fill=(56, 189, 248), font=f_up_tc)

    # Right Box: Local (Iconha Sede)
    draw.rounded_rectangle(
        [(RIGHT_X1, 240), (RIGHT_X2, 545)],
        radius=20,
        fill=(30, 41, 59),
        outline=(51, 65, 85),
        width=2,
    )
    rx = RIGHT_X1 + CARD_INNER_PAD
    draw.text((rx, 264), "ICONHA (SEDE)", fill=(148, 163, 184), font=f_box_tag)
    loc_sub = "Centro • Vale Urbano (Baixo Curso)"
    f_loc_sub = _fit_font_to_width(draw, loc_sub, get_font, 20, HALF_TEXT_MAX_W)
    draw.text((rx, 300), loc_sub, fill=(203, 213, 225), font=f_loc_sub)

    loc_val_str = f"{s['local_iconha_24h_mm']} mm"
    f_loc_big = _fit_font_to_width(draw, loc_val_str, get_font, 58, HALF_TEXT_MAX_W)
    draw.text((rx, 344), loc_val_str, fill=(255, 255, 255), font=f_loc_big)
    draw.text((rx, 430), "Chuva Prevista (24h)", fill=(148, 163, 184), font=f_box_label)

    loc_tc_str = f"Pico 6h (Tc): {s['local_iconha_tc_6h_mm']} mm"
    f_loc_tc = _fit_font_to_width(draw, loc_tc_str, get_font, 22, HALF_TEXT_MAX_W)
    draw.text((rx, 476), loc_tc_str, fill=(56, 189, 248), font=f_loc_tc)

    # 3. SCS-CN Runoff & Copula Box (y=570..770)
    draw.rounded_rectangle(
        [(PAD_X, 570), (W - PAD_X, 770)],
        radius=20,
        fill=(30, 41, 59),
        outline=(51, 65, 85),
        width=2,
    )
    cx = PAD_X + CARD_INNER_PAD

    runoff_line = f"ESCOAMENTO SUPERFICIAL (SCS-CN): {s['effective_runoff_24h_mm']} mm"
    f_runoff = _fit_font_to_width(draw, runoff_line, get_font, 30, FULL_TEXT_MAX_W)
    draw.text((cx, 594), runoff_line, fill=(255, 255, 255), font=f_runoff)

    soil_line = f"Índice de Umidade (API): {s['api_t_mm']} mm • {s['soil_status']}"
    f_soil = _fit_font_to_width(draw, soil_line, get_font, 25, FULL_TEXT_MAX_W)
    draw.text((cx, 650), soil_line, fill=(253, 224, 71), font=f_soil)

    copula_line = (
        f"Tempo de Retorno Conjunto (Cópula de Gumbel): {s['joint_return_period_years']} anos"
    )
    f_copula = _fit_font_to_width(draw, copula_line, get_font, 22, FULL_TEXT_MAX_W)
    draw.text((cx, 706), copula_line, fill=(148, 163, 184), font=f_copula)

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
