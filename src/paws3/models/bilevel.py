
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, Tuple
from loguru import logger

from ..core.config import PawsConfig
from ..core.datatypes import ProblemData
from .principal import PrincipalResult
from ..core.interfaces import AgentRequest, AgentResponse
from ..plugins.registry import get as get_plugin

@dataclass
class DecompOptions:
    max_iters: int = 1
    tol: float = 1e-6

def _extract_first_period_commitments(pr: PrincipalResult, data: ProblemData, t: int) -> Dict[Tuple[str, str], float]:
    """Map upper-level first-period area decisions to volumes by (stratum, product).
    Product is a placeholder 'sawlog' for now. Vol = area * yield[s,t]."""
    m = pr.model
    commitments: Dict[Tuple[str,str], float] = {}
    if not hasattr(m, "X"):
        return commitments
    for s in list(data.strata.keys()):
        x = m.X.get((s, t), None)
        try:
            area = float(x.value) if x is not None and x.value is not None else 0.0
        except Exception:
            area = 0.0
        vol = area * float(data.yields.get((s, t), 0.0))
        if vol > 0:
            commitments[(s, "sawlog")] = vol
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
