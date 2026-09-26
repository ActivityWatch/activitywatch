"""Normalize query results from both servers and diff them.

Normalization drops server-assigned event ids, parses timestamps (``Z`` vs
``+00:00``, offsets, fractional digits) into UTC epoch seconds, and compares
times and durations with a small tolerance (float round-trips differ between
Python and Rust). Unordered results are compared as multisets.
"""

import json
from typing import Any, List, Tuple

import iso8601

TOL = 2e-6  # seconds

Ev = Tuple[float, float, str]  # (start, duration, canonical data json)


def is_event(x: Any) -> bool:
    return isinstance(x, dict) and {"timestamp", "duration", "data"} <= set(x)


def event(x: dict) -> Ev:
    start = iso8601.parse_date(x["timestamp"]).timestamp()
    return (
        start,
        float(x["duration"]),
        json.dumps(x["data"], sort_keys=True, ensure_ascii=False),
    )


def normalize(x: Any, ordered: bool) -> Any:
    if isinstance(x, dict):
        if "__error__" in x:
            return ("ERROR",)
        if is_event(x):
            return event(x)
        return {k: normalize(v, ordered) for k, v in x.items()}
    if isinstance(x, list):
        items = [normalize(v, ordered) for v in x]
        if not ordered and all(isinstance(i, tuple) and len(i) == 3 for i in items):
            items.sort(key=lambda e: (round(e[0], 3), round(e[1], 3), e[2]))
        return items
    if isinstance(x, (int, float)) and not isinstance(x, bool):
        return float(x)
    return x


def _close(a: float, b: float) -> bool:
    # Absolute only: timestamps are epoch seconds (~1.8e9), where any relative
    # term would dwarf TOL. f64 still resolves them to well under 1 µs.
    return abs(a - b) <= TOL


def fmt_event(e: Ev) -> str:
    from datetime import datetime, timezone

    ts = datetime.fromtimestamp(e[0], tz=timezone.utc).isoformat()
    return f"{ts} dur={e[1]:.6f} {e[2]}"


def diff(py: Any, rs: Any, path: str = "$") -> List[str]:
    """Human readable differences between normalized results (empty if equal)."""
    if isinstance(py, dict) and isinstance(rs, dict):
        out = []
        for k in sorted(set(py) | set(rs)):
            if k not in py or k not in rs:
                out.append(f"{path}.{k}: only in {'python' if k in py else 'rust'}")
            else:
                out += diff(py[k], rs[k], f"{path}.{k}")
        return out
    if isinstance(py, list) and isinstance(rs, list):
        bad = [
            i
            for i in range(max(len(py), len(rs)))
            if i >= len(py) or i >= len(rs) or diff(py[i], rs[i])
        ]
        if not bad:
            return []
        lines = [
            f"{path}: {len(py)} (python) vs {len(rs)} (rust) items, first difference at [{bad[0]}]"
        ]
        lo = max(0, bad[0] - 2)
        for i in range(lo, min(max(len(py), len(rs)), lo + 12)):
            p = _show(py[i]) if i < len(py) else "-"
            r = _show(rs[i]) if i < len(rs) else "-"
            mark = "!=" if i in bad else "  "
            lines.append(f"  [{i}] {mark} python: {p}\n  [{i}] {mark} rust:   {r}")
        return ["\n".join(lines)]
    if isinstance(py, tuple) and isinstance(rs, tuple) and len(py) == len(rs) == 3:
        if _close(py[0], rs[0]) and _close(py[1], rs[1]) and py[2] == rs[2]:
            return []
        return [f"{path}: python {fmt_event(py)} != rust {fmt_event(rs)}"]
    if isinstance(py, float) and isinstance(rs, float):
        return [] if _close(py, rs) else [f"{path}: python {py!r} != rust {rs!r}"]
    return [] if py == rs else [f"{path}: python {_show(py)} != rust {_show(rs)}"]


def _show(x: Any) -> str:
    if isinstance(x, tuple) and len(x) == 3:
        return fmt_event(x)
    return repr(x)[:200]
