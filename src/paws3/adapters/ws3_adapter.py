
from __future__ import annotations
from typing import Dict, Any, Tuple
from .util import import_optional, run_cli_json
from ..core.interfaces import PrincipalEmulator, PrincipalDecision

class WS3Principal(PrincipalEmulator):
    def __init__(self, mode: str = "import", cli: str | None = None, recipe: str | None = None):
        self.mode = mode
        self.cli = cli
        self.recipe = recipe

    def plan_first_period(self, state: Dict[str, Any]) -> PrincipalDecision:
        period = state.get("period", 0)
        if self.mode == "import":
            ws3 = import_optional("ws3")
            # Placeholder: call into ws3 API once available; here we synthesize even-flow-like commitments
            inv = state.get("inventory", {})
            commitments = {}
            for sid, info in inv.items():
                # allocate a small fraction to period 1 as a stub
                commitments[(sid, "sawlog")] = 0.01 * info.get("area", 0) * info.get("yield_p1", 1.0)
            return PrincipalDecision(period=period, commitments=commitments)
        elif self.mode == "cli":
            assert self.cli, "ws3 CLI path not provided"
            out = run_cli_json([self.cli, "run", "--recipe", self.recipe or "baseline.json"])
            # Map CLI JSON to commitments (placeholder)
            commitments = {(r["stratum"], r.get("product","sawlog")): r["vol"] for r in out.get("p1_commitments", [])}
            return PrincipalDecision(period=period, commitments=commitments)
        else:
            raise ValueError(f"Unknown ws3 adapter mode: {self.mode}")
