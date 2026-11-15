def fetch_official_brazilian_telemetry() -> dict:
    """
    Adapter for official Brazilian ground-truth sensors (CEMADEN / ANA / INMET).
    [VERIFY_PARAMETER]: Insert verified station codes from ANA HidroWeb / CEMADEN.
    Fails gracefully so the forecast pipeline never crashes if public sensors go offline.
    """
    return {
        "cemaden_active": False,
        "ana_river_level_m": None,
        "official_inmet_warning": None,
    }