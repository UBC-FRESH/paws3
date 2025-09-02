
from __future__ import annotations
from typing import Dict, Any
from .registry import register
from ..adapters.fhops_adapter import FHOPSAgent
from ..core.interfaces import AgentRequest, AgentResponse

@register("fhops_exec")
def fhops_exec(req: AgentRequest, *, mode: str = "cli", cli: str | None = "fhops", profile: str | None = None) -> AgentResponse:
    return FHOPSAgent(mode=mode, cli=cli, profile=profile).schedule_first_period(req)
