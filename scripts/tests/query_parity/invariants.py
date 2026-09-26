"""Properties a single server's query output must satisfy on its own.

Each check gets the normalized output and that server's own normalized
``{"a": ..., "b": ...}`` inputs (as returned by query_bucket for the same
period), and returns a list of violations.
"""

from typing import Callable, Dict, List

from normalize import TOL, Ev


def _end(e: Ev) -> float:
    return e[0] + e[1]


def _self_overlapping(evs: List[Ev]) -> bool:
    evs = sorted(evs)
    return any(evs[i + 1][0] < _end(evs[i]) - TOL for i in range(len(evs) - 1))


def _measure(evs: List[Ev]) -> float:
    """Total length of the union of the events' intervals."""
    total, cur_s, cur_e = 0.0, None, None
    for s, d, _ in sorted(evs):
        e = s + d
        if cur_e is None or s > cur_e:
            if cur_e is not None:
                total += cur_e - cur_s
            cur_s, cur_e = s, e
        else:
            cur_e = max(cur_e, e)
    if cur_e is not None:
        total += cur_e - cur_s
    return total


def _overlaps(evs: List[Ev]) -> List[str]:
    out = []
    for i in range(len(evs) - 1):
        a, b = evs[i], evs[i + 1]
        if b[0] < a[0] - TOL:
            out.append(f"not sorted at [{i + 1}]: {b[0]} < {a[0]}")
        elif b[0] < _end(a) - TOL:
            out.append(
                f"[{i}] and [{i + 1}] overlap by {_end(a) - b[0]:.6f}s: {a} / {b}"
            )
    return out[:5]


def sorted_ts(out, inp):
    return [
        f"not sorted by timestamp at [{i + 1}]"
        for i in range(len(out) - 1)
        if out[i + 1][0] < out[i][0] - TOL
    ][:3]


def sorted_dur(out, inp):
    return [
        f"not sorted by duration at [{i + 1}]"
        for i in range(len(out) - 1)
        if out[i + 1][1] > out[i][1] + TOL
    ][:3]


def no_overlap(out, inp):
    # union_no_overlap only promises no overlap when neither input overlaps itself.
    if _self_overlapping(inp["a"]) or _self_overlapping(inp["b"]):
        return []
    return _overlaps(out)


def no_overlap_positive(out, inp):
    """flood() output: events with a duration never overlap (ActivityWatch/activitywatch#1369)."""
    return _overlaps(sorted(e for e in out if e[1] > TOL))


def measure_ab(out, inp):
    if _self_overlapping(inp["a"]) or _self_overlapping(inp["b"]):
        return []
    got, want = sum(e[1] for e in out), _measure(inp["a"] + inp["b"])
    return (
        []
        if abs(got - want) <= TOL * (len(out) + 1)
        else [
            f"total duration {got:.6f}s != covered time of a∪b {want:.6f}s (diff {got - want:+.6f}s)"
        ]
    )


def sum_matches_a(out, inp):
    want = sum(e[1] for e in inp["a"])
    return [] if abs(out - want) <= TOL * (len(inp["a"]) + 1) else [f"{out} != {want}"]


def merge_conserves_app(out, inp):
    import json

    want = sum(e[1] for e in inp["a"] if "app" in json.loads(e[2]))
    got = sum(e[1] for e in out)
    return (
        []
        if abs(got - want) <= TOL * (len(inp["a"]) + 1)
        else [f"merged {got:.6f}s != input {want:.6f}s"]
    )


def same_durations(out, inp):
    a = sorted(round(e[1], 5) for e in inp["a"])
    b = sorted(round(e[1], 5) for e in out)
    return [] if a == b else ["event durations changed"]


def within_b(out, inp):
    bad = []
    for e in out:
        if e[1] <= TOL:
            continue
        if not any(b[0] - TOL <= e[0] and _end(e) <= _end(b) + TOL for b in inp["b"]):
            bad.append(f"{e} not inside any filter event")
    return bad[:3]


def md_no_overlap(out, inp):
    return _overlaps(out["events"])


CHECKS: Dict[str, Callable] = {
    f.__name__: f
    for f in [
        sorted_ts,
        sorted_dur,
        no_overlap,
        no_overlap_positive,
        measure_ab,
        sum_matches_a,
        merge_conserves_app,
        same_durations,
        within_b,
        md_no_overlap,
    ]
}
