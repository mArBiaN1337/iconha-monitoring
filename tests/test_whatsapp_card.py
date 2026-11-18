# tests/test_whatsapp_card.py
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from src.iconha_monitoring.config import TIER_CONFIG
from src.iconha_monitoring.renderer.whatsapp_card import (
    generate_whatsapp_card,
    _wrap_text_pixel_safe,
    _measure_text_width,
)


def test_whatsapp_card_dimensions_and_all_tiers():
    for tier, banner in TIER_CONFIG.items():
        payload = {
            "version": "2.0.1",
            "updated_at_br": "16/11/2026 às 19:00",
            "risk_tier": tier,
            "banner": banner,
            "summary": {
                "api_t_mm": 155.6,
                "soil_status": "AMC II-III (Transição Saturada)",
                "cn_effective": 89.4,
                "effective_runoff_24h_mm": 137.4,
                "effective_runoff_6h_mm": 69.0,
                "joint_return_period_years": 21.8,
                "upstream_forecast_24h_mm": 167.1,
                "upstream_tc_6h_mm": 96.1,
                "local_iconha_24h_mm": 112.4,
                "local_iconha_tc_6h_mm": 54.2,
            },
        }
        png_bytes = generate_whatsapp_card(payload)
        with Image.open(BytesIO(png_bytes)) as img:
            assert img.size == (1080, 1080)
            assert img.mode == "RGB"


def test_pixel_safe_wrapping_respects_max_width():
    img = Image.new("RGB", (1080, 1080))
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=24)
    long_text = (
        "Saturação crítica e chuva intensa nas cabeceiras com risco extremo de enxurrada "
        "no vale do Rio Iconha nas próximas horas."
    )
    lines = _wrap_text_pixel_safe(draw, long_text, font, max_width=400, max_lines=3)
    assert 1 <= len(lines) <= 3
    for ln in lines:
        assert _measure_text_width(draw, ln, font) <= 400
