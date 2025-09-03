
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, Tuple
from loguru import logger

from ..core.config import PawsConfig
from ..core.datatypes import ProblemData
from .principal import PrincipalResult
from ..core.interfaces import AgentRequest, AgentResponse
from ..plugins.registry import get as get_plugin

import pyomo.environ as pyo

@dataclass
class DecompOptions:
    max_iters: int = 1
    tol: float = 1e-6

def _extract_first_period_commitments(pr: PrincipalResult, data: ProblemData, t: int) -> Dict[Tuple[str, str], float]:
    """Map UL first-period decisions to volumes by (stratum, product='sawlog').
    If m.X(s,t) exists, use it; else split total m.vol[t] by area*yield weights."""
    m = pr.model
    commitments: Dict[Tuple[str, str], float] = {}

    # Case 1: we have per-stratum decisions m.X[s,t]
    if hasattr(m, "X"):
        X = m.X
        for key in X:
            if not (isinstance(key, tuple) and len(key) == 2):
                continue
            s_idx, tau = key
            if tau != t:
                continue
            area = pyo.value(X[key])
            if area is None or area <= 0:
                continue
            yld = float(data.yields.get((s_idx, t), 0.0))
            vol = area * yld
            if vol > 0:
                commitments[(s_idx, "sawlog")] = vol
        return commitments

    # Case 2: only total volume m.vol[t] is available → allocate by weights
    total = None
    if hasattr(m, "vol"):
        try:
            total = float(pyo.value(m.vol[t]))
        except Exception:
            total = None
    if not total or total <= 0:
        return commitments  # nothing to allocate

    # weights: area * yield(s,t)
    weights = {}
    wsum = 0.0
    for s, info in data.strata.items():
        w = float(info.area) * float(data.yields.get((s, t), 0.0))
        if w > 0:
            weights[s] = w
            wsum += w
    if wsum <= 0:
        return commitments

    for s, w in weights.items():
        share = w / wsum
        v = total * share
        if v > 0:
            commitments[(s, "sawlog")] = v
    return commitments

def _call_fhops_if_configured(cfg: PawsConfig, t: int, commitments: Dict[Tuple[str,str], float]) -> AgentResponse | None:
    if cfg.agent_behavior.name != "fhops_exec":
        return None
    fhops_fn = get_plugin("fhops_exec")
    areq = AgentRequest(
        period=t,
        blocks=[{"stratum": s, "product": p, "ub_vol": v} for (s, p), v in commitments.items()],
        commitments=commitments,
    )
    try:
        aresp = fhops_fn(areq, **cfg.agent_behavior.params)
        return aresp
    except Exception as e:
        logger.warning("FHOPS adapter error: {}", e)
        return None

def solve_bilevel_if_enabled(data: ProblemData, cfg: PawsConfig, pr: PrincipalResult, current_period: int) -> None:
    if not cfg.bilevel.enabled:
        return
    logger.info("Bilevel mode: {} (reformulation={})", cfg.bilevel.enabled, cfg.bilevel.reformulation)

    if cfg.bilevel.reformulation != "decomposition":
        # Placeholders for 'kkt' or 'bigm' can be inserted later
        return

    opts = DecompOptions()  # could be pulled from cfg later
    # Decomposition skeleton (single-window, first-period focus)
    for it in range(opts.max_iters):
        # 1) Map UL first-period decision -> LL request
        commitments = _extract_first_period_commitments(pr, data, current_period)
        logger.debug("Iter {}: UL->LL commitments (t={}): {} entries", it, current_period, len(commitments))
        tot_v = sum(commitments.values())
        logger.info(
            "Iter {}: committed UL volume at t={} ≈ {:.1f} ({} entries)",
            it, current_period, tot_v, len(commitments)
        )
        # Optional: top-3 breakdown for quick eyeballing
        for (s, p), v in sorted(commitments.items(), key=lambda kv: kv[1], reverse=True)[:3]:
            logger.debug("  - {}:{} {:.1f}", s, p, v)

        # Physical cap check for the current period
        Vcap_t = sum(
            data.yields.get((s, current_period), 0.0) * data.strata[s].area
            for s in data.strata
        )
        logger.debug("UL physical cap at t={} ≈ {:.1f} m3", current_period, Vcap_t)
        if tot_v > Vcap_t + 1e-6:
            logger.warning(
                "UL commitments ({:.1f}) exceed cap ({:.1f}) at t={} — check AreaCap.",
                tot_v, Vcap_t, current_period
        )
        # 2) Solve LL (FHOPS if configured; else stub)
        aresp = _call_fhops_if_configured(cfg, current_period, commitments)
        if aresp is None:
            # No FHOPS configured; use stub LL.
            logger.debug("Iter {}: No FHOPS configured; using stub LL.", it)
            break

        # 3) Evaluate response (record cost/feasibility) and generate a cut (TODO)
        summary = aresp.summary or {}
        logger.info("Iter {}: LL summary @t={}: {}", it, current_period, summary)

        # TODO: add feasibility/optimality cuts back to the UL model and re-solve within the same window.
        # For now, we accept the LL response and end.
        break
