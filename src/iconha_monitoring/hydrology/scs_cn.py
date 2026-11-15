def compute_scs_effective_runoff(
    precip_mm: float,
    api_mm: float,
    cn_ii_base: float = 78.0,  # Typical steep forested/rural mountain scarp in ES
) -> dict:
    """
    Deterministic Path: Adjusts SCS Curve Number dynamically based on API_t
    (AMC I, II, or III) and calculates Effective Surface Runoff (Q_eff in mm).
    """
    # Classic Hawkins et al. (1985) AMC conversion formulas
    cn_i = (4.2 * cn_ii_base) / (10.0 - 0.058 * cn_ii_base)
    cn_iii = (23.0 * cn_ii_base) / (10.0 + 0.13 * cn_ii_base)

    # Continuous piecewise interpolation of CN based on API_t (soil moisture)
    if api_mm <= 20.0:
        cn_dynamic = cn_i
        amc_class = "AMC I (Solo Seco)"
    elif api_mm < 45.0:
        ratio = (api_mm - 20.0) / 25.0
        cn_dynamic = cn_i + ratio * (cn_ii_base - cn_i)
        amc_class = "AMC II (Solo Úmido)"
    elif api_mm < 75.0:
        ratio = (api_mm - 45.0) / 30.0
        cn_dynamic = cn_ii_base + ratio * (cn_iii - cn_ii_base)
        amc_class = "AMC II-III (Transição Saturada)"
    else:
        cn_dynamic = cn_iii
        amc_class = "AMC III (Solo Saturado)"

    # Potential maximum soil retention S (in mm) and initial abstraction Ia = 0.2 * S
    s_retention_mm = (25400.0 / cn_dynamic) - 254.0
    ia_mm = 0.2 * s_retention_mm

    # SCS Curve Number Runoff Equation
    if precip_mm <= ia_mm:
        q_eff_mm = 0.0
    else:
        q_eff_mm = ((precip_mm - ia_mm) ** 2) / (precip_mm + 0.8 * s_retention_mm)

    return {
        "amc_class": amc_class,
        "cn_effective": round(cn_dynamic, 1),
        "soil_retention_capacity_mm": round(s_retention_mm, 1),
        "effective_runoff_q_mm": round(q_eff_mm, 1),
    }