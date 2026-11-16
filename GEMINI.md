# Project Context: Iconha Flood & Severe Weather Monitoring System (`iconha-monitoring`)

## ABSOLUTE COST CONSTRAINT: $0.00 (ALWAYS FREE TIER ONLY)
- **Hard Rule:** Every architecture decision, code addition, and cloud configuration MUST operate 100% within Google Cloud's **Always Free Tier** limits. 
- **Prohibited:** Never propose paid Cloud SQL databases, paid Firestore instances, paid logging sinks, custom domains with billing, or multi-region storage. All hosting, compute, and storage must cost exactly **$0.00 USD/month**.

## 1. Mission & Architecture
- **Objective:** Open-source, low-cost flood and severe weather early warning system for **Iconha, Espírito Santo, Brazil**, monitoring the **Rio Iconha watershed** (headwaters in Alfredo Chaves/Crubixá/Monte Alegre down to Duas Barras and Iconha Sede).
- **Pattern:** "Compute-Once, Read-Many" Static Pipeline.
  - Backend (`src/iconha_monitoring/`): Python 3.12 managed by `uv`. Runs every 30 minutes on Google Cloud Run Functions (2nd Gen) to generate `status.json` and a 1080x1080 `card_whatsapp.png` (via Pillow).
  - Frontend (`web/`): Zero-typing single-screen mobile PWA (Vanilla HTML/CSS/ES Modules) hosted on Google Cloud Storage with `localStorage` offline fallback and 1-tap WhatsApp sharing.

## 2. Hydrological Engine Rules (`src/iconha_monitoring/hydrology/`)
- **Spatial Upstream Grid:** 4 coordinates (`P1_CRUBIXA` weight 0.35, `P2_MONTE_ALEGRE` weight 0.30, `P3_DUAS_BARRAS` weight 0.25, `P4_ICONHA_SEDE` weight 0.10). Headwaters carry 90% weight.
- **State Variable 1 (Slow Memory - `API_t`):** 14-day (336h) recursive Antecedent Precipitation Index using hourly decay derived from daily recession factor `k_daily = 0.88` (`k_hourly = 0.88 ** (1/24)`).
- **State Variable 2 (Fast Trigger - `Tc`):** Maximum rolling 6-hour accumulated precipitation matching the basin's time of concentration.
- **Dual Decision Engine:**
  1. **Deterministic Path (`scs_cn.py`):** Dynamic USDA SCS Curve Number adjusting continuously between AMC I, II, and III based on `API_t` to compute Effective Surface Runoff (`Q_eff` in mm).
  2. **Probabilistic Path (`copula_gpd.py`):** Peaks-Over-Threshold Generalized Pareto Distribution (GPD) coupled with an upper-tail Gumbel-Hougaard Copula to compute the Joint Return Period (`T_joint` in years). Pre-calibrated parameters live in `copula_params.json`.

## 3. Strict Google Cloud Free-Tier Parameters
- **Region:** MUST remain `us-east1` (required for Always Free 5 GB Cloud Storage, 5,000 Class A writes, 50,000 Class B reads).
- **Security:** Cloud Run Function (`iconha-monitoring-engine`) MUST remain private (`--no-allow-unauthenticated`), triggered only via OIDC by Cloud Scheduler (`*/30 * * * *`).
- **Artifact Registry:** Keep cleanup policy at `keepCount: 1` to stay well below the 0.5 GB Free Tier limit.
- **Local Commands:**
  - Run unit tests: `uv run pytest -v`
  - Run local dev pipeline & server: `uv run python scripts/dev.py`
  - Export requirements for GCP Buildpacks: `uv export --format requirements-txt --no-dev --no-hashes --no-emit-project > requirements.txt`