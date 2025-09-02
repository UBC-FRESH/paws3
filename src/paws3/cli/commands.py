
from __future__ import annotations
import typer
from pathlib import Path
from rich import print
from loguru import logger
from ..io.loaders import load_config
from ..core.sim import RollingHorizonSimulator

app = typer.Typer(no_args_is_help=True, help="PAWS3 — Principal-Agent Wood Supply Simulation System")

@app.command("init")
def init_cmd(target: str = typer.Argument("examples/minimal", help="Copy example files to target")):
    import yaml
    src = Path(__file__).resolve().parents[2] / "examples"
    dst = Path(target)
    dst.mkdir(parents=True, exist_ok=True)
    # Write minimal config and dataset
    cfg = {
        "data_path": str(dst / "data"),
        "bilevel": {"enabled": False},
        "horizon": {"period_length": 7, "horizon_periods": 12, "replanning_step": 1, "start_period": 0, "end_period": 24},
        "solver": {"driver": "auto", "time_limit": 30},
        "principal_policy": {"name": "even_flow", "params": {}},
        "agent_behavior": {"name": "profit_max_flow_stub", "params": {}},
        "run": {"out_dir": str(dst / "runs")},
    }
    (dst / "configs").mkdir(parents=True, exist_ok=True)
    (dst / "configs" / "minimal.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
    # Also create a bilevel stub config, as referenced by README
    bilevel_cfg = dict(cfg)
    bilevel_cfg.update({"bilevel": {"enabled": True, "reformulation": "decomposition"}, "run": {"out_dir": str(dst / "runs" / "bilevel_stub")}})
    (dst / "configs" / "bilevel_stub.yaml").write_text(yaml.safe_dump(bilevel_cfg, sort_keys=False))
    # Ensure data dir exists (the loader will synthesize if problem.json is absent)
    (dst / "data").mkdir(parents=True, exist_ok=True)
    print(f"[green]Initialized examples at {dst}[/green]")

@app.command("run-sim")
def run_sim(config: str = typer.Option(..., "--config", "-c", help="Path to YAML config"),
            verbose: bool = typer.Option(False, "--verbose", "-v", help="DEBUG logging"),
            quiet: bool = typer.Option(False, "--quiet", "-q", help="Only WARN+")):
    if verbose:
        logger.remove()
        logger.add(lambda m: print(m, end=""), level="DEBUG")
    elif quiet:
        logger.remove()
        logger.add(lambda m: print(m, end=""), level="WARNING")

    cfg = load_config(config)
    sim = RollingHorizonSimulator(cfg)
    res = sim.run()
    print("[bold green]Simulation finished[/bold green]", res)

@app.command("solve-bilevel")
def solve_bilevel(config: str = typer.Option(..., "--config", "-c", help="Path to YAML config"),
                  verbose: bool = typer.Option(False, "--verbose", "-v", help="DEBUG logging"),
                  quiet: bool = typer.Option(False, "--quiet", "-q", help="Only WARN+")):
    if verbose:
        logger.remove()
        logger.add(lambda m: print(m, end=""), level="DEBUG")
    elif quiet:
        logger.remove()
        logger.add(lambda m: print(m, end=""), level="WARNING")

    cfg = load_config(config)
    cfg.bilevel.enabled = True
    sim = RollingHorizonSimulator(cfg)
    res = sim.run()
    print("[bold green]Bilevel (stub) invocation complete[/bold green]", res)

# Back-compat synonyms with -cmd suffix to mirror FHOPS style
def run_sim_cmd():
    app(["run-sim"])

def solve_bilevel_cmd():
    app(["solve-bilevel"]
)
