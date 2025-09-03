
from __future__ import annotations
from ..core.config import PawsConfig
from ..core.datatypes import ProblemData
from .principal import PrincipalResult
from loguru import logger

from .types import AgentResponse
from typing import Optional

def emulate_agent_behavior(data, cfg, pr, current_period):
    consume_on = cfg.agent_behavior.params.get("consume_on_period", None)
    if consume_on is not None and current_period != int(consume_on):
        logger.debug("Skipping agent consumption at t={} (consume_on={}).", current_period, consume_on)
        return AgentResponse(summary={"consumed": 0.0})  # stub: nothing consumed now

    # ... existing stub acceptance of commitments for this period ...
    return AgentResponse(summary={"consumed": float(sum(pr.first_period_commitments.values()))})
