
from __future__ import annotations
from typing import Dict, Callable, Any

_REGISTRY: Dict[str, Callable[..., Any]] = {}

def register(name: str):
    def _decorator(fn: Callable[..., Any]):
        _REGISTRY[name] = fn
        return fn
    return _decorator

def get(name: str) -> Callable[..., Any]:
    if name not in _REGISTRY:
        raise KeyError(f"No plugin registered under '{name}'")
    return _REGISTRY[name]
