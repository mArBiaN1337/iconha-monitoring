from src.iconha_monitoring.config import SCS_IA_RATIO


def compute_scs_effective_runoff(
    precip_mm: float,
    api_mm: float,
    cn_ii_base: float = 78.0,  # Typical steep forested/rural mountain scarp in ES
    ia_ratio: float = SCS_IA_RATIO,
) -> dict:
    """
    Deterministic Path: Adjusts SCS Curve Number dynamically based on API_t
    using a smooth C^inf Hill saturation curve across AMC I, II, and III,
    and calculates Effective Surface Runoff (Q_eff in mm) with tropical
    escarpment initial abstraction ratio (lambda = Ia / S = 0.05).
    """
    precip_mm = max(0.0, float(precip_mm or 0.0))
    api_mm = max(0.0, float(api_mm or 0.0))
    cn_ii_base = min(max(float(cn_ii_base), 30.0), 99.5)
    lam = min(max(float(ia_ratio), 0.01), 0.30)

    # Classic Hawkins et al. (1985) AMC boundary conversions
    cn_i = (4.2 * cn_ii_base) / (10.0 - 0.058 * cn_ii_base)
    cn_iii = (23.0 * cn_ii_base) / (10.0 + 0.13 * cn_ii_base)

    # [HYDRO-01] Smooth Hill-function saturation curve (API_50 = 40.0 mm, gamma = 2.2)
    # Eliminates C1 derivative kinks and extends deep-soil saturation response above 75 mm
    api_50 = 40.0
    gamma = 2.2
    if api_mm <= 0.0:
        hill_weight = 0.0
    else:
        api_pow = api_mm ** gamma
        hill_weight = api_pow / ((api_50 ** gamma) + api_pow)

    cn_dynamic = cn_i + (cn_iii - cn_i) * hill_weight

    # Aligned physical AMC classification regimes
    if api_mm < 28.0:
        amc_class = "AMC I (Solo Seco)"
    elif api_mm < 58.0:
        amc_class = "AMC II (Solo Úmido)"
    elif api_mm < 85.0:
        amc_class = "AMC II-III (Transição Saturada)"
    else:
        amc_class = "AMC III (Solo Saturado)"

    # [HYDRO-02] Potential maximum soil retention S (in mm) and tropical initial abstraction Ia = lambda * S
    s_retention_mm = (25400.0 / cn_dynamic) - 254.0
    ia_mm = lam * s_retention_mm

    # SCS Curve Number Runoff Equation
    if precip_mm <= ia_mm:
        q_eff_mm = 0.0
    else:
        q_eff_mm = ((precip_mm - ia_mm) ** 2) / (precip_mm + (1.0 - lam) * s_retention_mm)

    return {
        "amc_class": amc_class,
        "cn_effective": round(cn_dynamic, 1),
        "soil_retention_capacity_mm": round(s_retention_mm, 1),
        "initial_abstraction_mm": round(ia_mm, 1),
        "effective_runoff_q_mm": round(q_eff_mm, 1),
    }