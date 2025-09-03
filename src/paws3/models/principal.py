from __future__ import annotations
from typing import Dict, Tuple, Any
import pyomo.environ as pyo
from loguru import logger

from ..core.config import PawsConfig
from ..core.datatypes import ProblemData
from .types import PrincipalResult


_CANDIDATE_UL_VARS = ("commit", "flow", "ship", "deliveries", "harvest", "x", "X", "H", "harvest_area", "Sell", "sell")


def _extract_first_period_commitments_from_model(m, data: ProblemData, t0: int) -> Dict[Tuple[str, str], float]:
    # Try typical cut variables with (stratum, t) indexing
    for cand in ("cut", "x", "harvest", "h", "c"):
        if hasattr(m, cand):
            var = getattr(m, cand)
            try:
                idx = var.index_set()
            except Exception:
                idx = None
            if idx is not None:
                out: Dict[Tuple[str, str], float] = {}
                for s in data.strata:
                    key = (s, t0)
                    if key in idx:
                        v = pyo.value(var[key])
                        if abs(v) > 1e-9:
                            # Interpret v as area fraction/ha; convert to volume using absolute-time yields:
                            vol = v * data.yields.get((s, t0), 0.0) * data.strata[s].area
                            out[(s, "sawlog")] = vol
                if out:
                    return out
    # Fallback: if only an aggregate vol[t] exists, return one pooled “ALL” entry
    if hasattr(m, "vol") and (t0 in m.vol):
        vt = float(pyo.value(m.vol[t0]))
        if vt > 1e-9:
            return {("ALL", "sawlog"): vt}
    return {}


def build_principal_model(data: ProblemData, cfg: PawsConfig, t0: int, T: int) -> PrincipalResult:
    """
    Principal (UL) model over a T-period window starting at absolute period t0.

    Decisions:
      - X[s,t] = harvested area (ha) in stratum s at absolute period t.

    Volume (m³) in period t:
      - vol[t] = sum_s X[s,t] * yield[(s, t)]   # yields are absolute-time after preprocessing

    Constraints:
      - Area conservation: sum_t X[s,t] <= area[s]
      - Physical cap: vol[t] <= sum_s area[s] * yield[(s, t)]
      - Demand bounds if demand exists for t
      - Optional even_flow: enforce min_vol only at first step t0

    Objective:
      - Maximize total volume over the window (simple, robust stub).
    """
    m = pyo.ConcreteModel(name="principal_upper_level")

    # Index sets
    m.S = pyo.Set(initialize=list(data.strata.keys()))
    m.T = pyo.Set(initialize=list(range(t0, t0 + T)))

    # Absolute-time yield lookup (yields already expanded by loaders.py)
    def yld(s: str, t_abs: int) -> float:
        return float(data.yields.get((s, t_abs), 0.0))

    # ---------- Decisions ----------
    m.X = pyo.Var(m.S, m.T, domain=pyo.NonNegativeReals)  # harvested area (ha)

    # ---------- Constraints ----------
    # Area conservation per stratum
    def _area_cap(_m, s):
        return sum(_m.X[s, t] for t in _m.T) <= data.strata[s].area
    m.AreaCap = pyo.Constraint(m.S, rule=_area_cap)

    # Period volume expression (m3)
    def _vol_rule(_m, t):
        return sum(_m.X[s, t] * yld(s, t) for s in _m.S)
    m.vol = pyo.Expression(m.T, rule=_vol_rule)

    # Physical cap per period (safety; useful for debugging)
    cap: Dict[int, float] = {t: sum(data.strata[s].area * yld(s, t) for s in m.S) for t in m.T}

    def _cap_con(_m, t):
        return _m.vol[t] <= cap[t] + 1e-9
    m.Cap = pyo.Constraint(m.T, rule=_cap_con)

    # Demand constraints (if any fall inside this absolute window)
    m.DemandLo = pyo.ConstraintList()
    m.DemandHi = pyo.ConstraintList()
    for d in data.demand:
        if d.period in m.T:
            m.DemandLo.add(m.vol[d.period] >= d.min_vol)
            m.DemandHi.add(m.vol[d.period] <= d.max_vol)

    # Even-flow minimum on the first step only
    if cfg.principal_policy.name == "even_flow":
        min_vol = float(cfg.principal_policy.params.get("min_vol", 0.0))
        if cap.get(t0, 0.0) > 1e-6 and min_vol > 0.0:
            m.MinFirst = pyo.Constraint(expr=m.vol[t0] >= min_vol)

        # Feasibility heads-up (based on one-cut-per-stand best-bin stock over this window)
        total_stock = sum(
            max(float(data.yields.get((s, k_abs), 0.0)) for k_abs in range(t0, t0 + T)) * data.strata[s].area
            for s in data.strata
        )
        if min_vol * T > total_stock + 1e-6:
            logger.warning(
                "even_flow may be infeasible on window starting t0={} : need {:.1f} (= {:.1f} × {}) vs stock ≤ {:.1f} m3. "
                "Lower min_vol, shorten T, or enforce only at first step.",
                t0, min_vol * T, min_vol, T, total_stock
            )

    # ---------- Objective ----------
    m.obj = pyo.Objective(expr=sum(m.vol[t] for t in m.T), sense=pyo.maximize)

    # ---------- Solve ----------
    from .solvers import solve_model
    res = solve_model(m, cfg.solver)

    # ---------- Build first-period commitments (UL -> LL) ----------
    def _first_period_commitments() -> Dict[Tuple[str, str], float]:
        out: Dict[Tuple[str, str], float] = {}
        if t0 not in m.T:
            return out
        for s in m.S:
            if (s, t0) in m.X:
                x_ha = pyo.value(m.X[s, t0]) or 0.0
            else:
                x_ha = 0.0
            if x_ha > 1e-9:
                vol_m3 = x_ha * yld(s, t0)  # m3/ha * ha = m3
                if vol_m3 > 1e-6:
                    out[(s, "sawlog")] = out.get((s, "sawlog"), 0.0) + float(vol_m3)
        if not out:
            v0 = float(pyo.value(m.vol[t0]))
            if v0 > 1e-6:
                out[("ALL", "sawlog")] = v0
        return out

    first_period_commitments = _first_period_commitments()

    # Safe objective value extraction
    try:
        _obj_val = float(pyo.value(m.obj))
    except Exception:
        _obj_val = None

    # Useful debug
    logger.debug(
        "UL cap[t0]={:.1f} m3, vol[t0]={:.1f} m3, commitments={} entries",
        cap.get(t0, 0.0),
        float(pyo.value(m.vol[t0])) if t0 in m.T else 0.0,
        len(first_period_commitments),
    )

    return PrincipalResult(
        model=m,
        solver_status=res.get("status", "unknown"),
        t0=t0,
        T=T,
        objective_value=_obj_val,
        first_period_commitments=first_period_commitments,
    )