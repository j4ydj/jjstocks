"""Append-only scan history for comparing chains and play outcomes over time."""
import json
import os
from datetime import datetime
from typing import Any, Dict, List

from dataclasses import asdict

HISTORY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
HISTORY_FILE = os.path.join(HISTORY_DIR, "momentum_history.jsonl")


def _serialize(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _serialize(v) for k, v in asdict(obj).items()}
    if isinstance(obj, list):
        return [_serialize(x) for x in obj]
    return obj


def append_scan(result, plays: List = None) -> str:
    os.makedirs(HISTORY_DIR, exist_ok=True)
    record: Dict[str, Any] = {
        "timestamp": datetime.now().isoformat(),
        "scan_time": result.scan_time,
        "universe_size": result.universe_size,
        "top_volatile": _serialize(result.top_volatile),
        "play_count": len(plays or []),
        "plays": _serialize(plays or []),
    }
    with open(HISTORY_FILE, "a") as f:
        f.write(json.dumps(record) + "\n")
    return HISTORY_FILE


def load_recent(n: int = 5) -> List[Dict]:
    if not os.path.exists(HISTORY_FILE):
        return []
    lines = []
    with open(HISTORY_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                lines.append(line)
    out = []
    for line in lines[-n:]:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out
