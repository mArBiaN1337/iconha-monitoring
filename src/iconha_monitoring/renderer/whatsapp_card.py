from io import BytesIO
from pathlib import Path
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


def generate_whatsapp_card(payload: dict) -> bytes:
    """Renders a 1080x1080 PNG status card with SCS-CN Runoff and Copula metrics."""
    W, H = 1080, 1080
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

    f_title = get_font(44)
    f_sub = get_font(28)
    f_big = get_font(64)
    f_med = get_font(32)
    f_small = get_font(23)

    banner_rgb = tuple(payload["banner"]["color_rgb"])
    s = payload["summary"]

    # 1. Top Risk Banner
    draw.rectangle([(0, 0), (W, 210)], fill=banner_rgb)
    draw.text(
        (50, 32),
        f"MONITORAMENTO RIO ICONHA - ES (v{payload['version']})",
        fill=(255, 255, 255),
        font=f_sub,
    )
    draw.text((50, 82), payload["banner"]["title"], fill=(255, 255, 255), font=f_title)
    draw.text(
        (50, 148),
        f"Atualizado em: {payload['updated_at_br']}",
        fill=(240, 240, 240),
        font=f_small,
    )

    # 2. Side-by-Side Comparison Boxes (Upstream vs Local)
    draw.rounded_rectangle([(45, 240), (520, 555)], radius=20, fill=(30, 41, 59))
    draw.text((75, 265), "CABECEIRA (ACIMA)", fill=(148, 163, 184), font=f_sub)
    draw.text((75, 305), "Crubixá / Duas Barras", fill=(203, 213, 225), font=f_small)
    draw.text((75, 355), f"{s['upstream_forecast_24h_mm']} mm", fill=(255, 255, 255), font=f_big)
    draw.text((75, 445), "Chuva Prevista (24h)", fill=(148, 163, 184), font=f_small)
    draw.text(
        (75, 490),
        f"Acumulado 6h (Tc): {s['upstream_tc_6h_mm']} mm",
        fill=(56, 189, 248),
        font=f_small,
    )

    draw.rounded_rectangle([(560, 240), (1035, 555)], radius=20, fill=(30, 41, 59))
    draw.text((590, 265), "ICONHA (SEDE)", fill=(148, 163, 184), font=f_sub)
    draw.text((590, 305), "Centro / Vale Urbano", fill=(203, 213, 225), font=f_small)
    draw.text((590, 355), f"{s['local_iconha_24h_mm']} mm", fill=(255, 255, 255), font=f_big)
    draw.text((590, 445), "Chuva Prevista (24h)", fill=(148, 163, 184), font=f_small)
    draw.text(
        (590, 490),
        f"Acumulado 6h (Tc): {s['local_iconha_tc_6h_mm']} mm",
        fill=(56, 189, 248),
        font=f_small,
    )

    # 3. SCS-CN Runoff & Copula Box
    draw.rounded_rectangle([(45, 585), (1035, 775)], radius=20, fill=(30, 41, 59))
    draw.text(
        (75, 610),
        f"ESCOAMENTO SUPERFICIAL (SCS-CN): {s['effective_runoff_24h_mm']} mm",
        fill=(255, 255, 255),
        font=f_med,
    )
    draw.text(
        (75, 665),
        f"Índice de Umidade (API): {s['api_t_mm']} mm • {s['soil_status']}",
        fill=(253, 224, 71),
        font=f_sub,
    )
    draw.text(
        (75, 715),
        f"Tempo de Retorno Conjunto (Cópula de Gumbel): {s['joint_return_period_years']} anos",
        fill=(148, 163, 184),
        font=f_small,
    )

    # 4. Guidance Box
    draw.rounded_rectangle([(45, 800), (1035, 960)], radius=20, fill=(39, 50, 68))
    draw.text((75, 825), payload["banner"]["headline"], fill=(255, 255, 255), font=f_med)
    draw.text((75, 885), payload["banner"]["advice"], fill=(203, 213, 225), font=f_small)

    # 5. Footer
    draw.text(
        (45, 990),
        "Emergência: Defesa Civil 199 | Bombeiros 193 • Modelos: SCS-CN + GPD/Gumbel",
        fill=(148, 163, 184),
        font=f_small,
    )

    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()