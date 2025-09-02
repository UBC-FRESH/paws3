
from __future__ import annotations
import typer, json
from pathlib import Path
from rich import print
from ..io.loaders import load_config
from ..core.config import PawsConfig
from ..core.sim import RollingHorizonSimulator

app = typer.Typer(no_args_is_help=True, help="PAWS3 — Principal-Agent Wood Supply Simulation System")

@app.command("init")
def init_cmd(target: str = typer.Argument("examples/minimal", help="Copy example files to target")):
    src = Path(__file__).resolve().parents[2] / "examples"
    dst = Path(target)
    dst.mkdir(parents=True, exist_ok=True)
    # Write minimal config and dataset
    cfg = {
        "data_path": str(dst / "data"),
        "bilevel": {"enabled": False},
        "horizon": {"period_length": 7, "horizon_periods": 12, "replanning_step": 1, "start_period": 0, "end_period": 24},
        "solver": {"driver": "auto", "time_limit": 30},
        "run": {"out_dir": str(dst / "runs")}
    }
    (dst / "configs").mkdir(parents=True, exist_ok=True)
    (dst / "configs" / "minimal.yaml").write_text(json.dumps(cfg, indent=2))
    (dst / "data").mkdir(parents=True, exist_ok=True)
    print(f"[green]Initialized example at {dst}[/green]")

@app.command("run-sim")
def run_sim(config: str = typer.Option(..., "--config", "-c", help="Path to YAML config")):
    cfg = load_config(config)
    sim = RollingHorizonSimulator(cfg)
    res = sim.run()
    print("[bold green]Simulation finished[/bold green]", res)

@app.command("solve-bilevel")
def solve_bilevel(config: str = typer.Option(..., "--config", "-c", help="Path to YAML config")):
    cfg = load_config(config)
    cfg.bilevel.enabled = True
    sim = RollingHorizonSimulator(cfg)
    res = sim.run()
    print("[bold green]Bilevel (stub) invocation complete[/bold green]", res)

# Back-compat synonyms with -cmd suffix to mirror FHOPS style
def run_sim_cmd():
    app(["run-sim"])

def solve_bilevel_cmd():
    app(["solve-bilevel"])
