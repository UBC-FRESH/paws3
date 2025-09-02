
from __future__ import annotations
import yaml, json
from pathlib import Path
from . import readers as rdrs
from ..core.config import PawsConfig
from ..core.datatypes import ProblemData

def load_config(path: str | Path) -> PawsConfig:
    p = Path(path)
    data = yaml.safe_load(p.read_text())
    return PawsConfig(**data)

def load_problem_data(data_path: str | Path) -> ProblemData:
    dp = Path(data_path)
    # Minimal placeholder: load from JSON if present; else synthesize tiny dataset
    js = dp / "problem.json"
    if js.exists():
        return ProblemData(**json.loads(js.read_text()))
    return rdrs.synthesize_problem_data()
