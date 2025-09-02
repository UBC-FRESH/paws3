
from __future__ import annotations
from typing import Dict, Any, Tuple
from .registry import register
from ..adapters.ws3_adapter import WS3Principal
from ..core.interfaces import PrincipalDecision

@register("ws3_emulator")
def ws3_emulator(state: Dict[str, Any], *, mode: str = "import", cli: str | None = None, recipe: str | None = None) -> PrincipalDecision:
    return WS3Principal(mode=mode, cli=cli, recipe=recipe).plan_first_period(state)
