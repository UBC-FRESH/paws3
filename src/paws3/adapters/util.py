
from __future__ import annotations
import json, subprocess, shutil

def import_optional(name: str):
    try:
        return __import__(name)
    except Exception as e:
        raise RuntimeError(f"Optional dependency '{name}' not available: {e}")

def run_cli_json(cmd: list[str]) -> dict:
    if not shutil.which(cmd[0]):
        return {"warning": f"executable not found: {cmd[0]}"}
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        return {"error": p.stderr.strip()}
    try:
        return json.loads(p.stdout)
    except Exception:
        return {"stdout": p.stdout}
