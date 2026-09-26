"""Why the cases in known_failures.txt fail.

known_failures.txt has one line per currently failing case: the case id and the
issues it fails for, as keys of ISSUES below:

    identical-p0-flood          CORE_163,RUST_746
    identical-p0-union_no_overlap_rev   CORE_163 | CORE_161,RUST_744

``,`` means every listed issue has to be fixed before the case passes, ``|``
separates alternatives (either fix is enough). The cases are strict xfails, so
the suite is green today and a fix that lands in the pinned submodules turns
them into XPASS failures.

The keys are measured, not guessed: attribute.py derives them from runs of the
suite with each open fix alone, with all of them, and with all but one (see the
README). A case that still fails with every available fix keeps the keys of the
issues that have no fix yet. Its other causes, if any, are masked until then.

KNOWN_ISSUES only suggests keys for failures that are new to the list (by id
glob, every matching pattern counts). Those suggestions over-attribute, for
example a period-clipping scenario run through ``flood`` matches both
``period-clip-*`` and ``*-flood``, so confirm them with attribute.py.
"""

import fnmatch
from pathlib import Path
from typing import Dict, List, Tuple

ISSUES: Dict[str, str] = {
    "CORE_161": "union_no_overlap: contained events overlap (ActivityWatch/aw-core#161)",
    "CORE_162": "aw-core clips events 1 ms past the period end (ActivityWatch/aw-core#162)",
    "CORE_163": "equal-timestamp order differs between servers (ActivityWatch/aw-core#163)",
    "CORE_164": "aw-core parser mis-splits args after a nested call (ActivityWatch/aw-core#164)",
    "CORE_165": "aw-core flood() doesn't merge adjacent equal events (ActivityWatch/aw-core#165)",
    "CORE_166": "aw-core filter_period_intersect double-counts overlapping filters (ActivityWatch/aw-core#166)",
    "RUST_744": "union_no_overlap: zero-duration events (ActivityWatch/aw-server-rust#744)",
    "RUST_745": "Rust truncates durations to ns and sum_durations to ms (ActivityWatch/aw-server-rust#745)",
    "RUST_746": "flood() diverges (ActivityWatch/aw-server-rust#746)",
    "RUST_747": "filter_period_intersect drops zero-duration events in Rust (ActivityWatch/aw-server-rust#747)",
    "SHAPE": "output data shape differs (ActivityWatch/activitywatch#1466)",
    "PRECISION": "aw-core stores event timestamps at 1 ms resolution, Rust at 1 ns (by design)",
}

# (kind, pattern, key): suggestions for failures not yet in known_failures.txt
KNOWN_ISSUES: List[Tuple[str, str, str]] = [
    # --- invariants: bugs in one server ---
    ("invariant", "python:*-union_no_overlap*", "CORE_161"),
    ("invariant", "python:*-multidevice:md_no_overlap", "CORE_161"),
    ("invariant", "rust:zero-*-union_no_overlap*", "RUST_744"),
    ("invariant", "rust:*-flood:no_overlap_positive", "RUST_746"),
    ("invariant", "rust:*-sum_durations:sum_matches_a", "RUST_745"),
    ("invariant", "python:*-merge_events_by_keys_app:merge_conserves_app", "SHAPE"),
    # --- parity: whole scenarios whose input already differs ---
    ("parity", "identical-*", "CORE_163"),
    ("parity", "same-start-*", "CORE_163"),
    ("parity", "period-clip-p*", "CORE_162"),
    ("parity", "period-clip-us-*", "PRECISION"),
    ("parity", "dst-p1-*", "CORE_162"),
    ("parity", "fractional*", "PRECISION"),
    # --- parity: per transform ---
    ("parity", "*-flood", "RUST_746"),
    ("parity", "*-flood_pulsetime", "RUST_746"),
    ("parity", "*-union_no_overlap_flooded", "RUST_746"),
    ("parity", "*-union_no_overlap*", "CORE_161"),
    ("parity", "*-union_no_overlap*", "RUST_744"),
    ("parity", "*-filter_period_intersect*", "RUST_747"),
    ("parity", "*-period_union", "RUST_745"),
    ("parity", "*-sum_durations", "RUST_745"),
    ("parity", "*-merge_events_by_keys_*", "SHAPE"),
    ("parity", "*-chunk_events_by_key", "SHAPE"),
    ("parity", "*-split_url_events", "SHAPE"),
    ("parity", "*-tag", "SHAPE"),
    ("parity", "*-tag_list_names", "SHAPE"),
    ("parity", "*-nested_call_args", "CORE_164"),
    ("parity", "*-aw-client:*", "RUST_746"),
    ("parity", "*-aw-client:*", "SHAPE"),
    ("parity", "*-multidevice*", "RUST_746"),
    ("parity", "*-multidevice*", "SHAPE"),
]


def case_kind(case_id: str) -> str:
    return "invariant" if case_id.split(":")[0] in ("python", "rust") else "parity"


def suggest_spec(case_id: str) -> str:
    """Keys of every KNOWN_ISSUES pattern that matches, as a spec ("" if none)."""
    keys: List[str] = []
    for kind, pattern, key in KNOWN_ISSUES:
        if (
            kind == case_kind(case_id)
            and fnmatch.fnmatchcase(case_id, pattern)
            and key not in keys
        ):
            keys.append(key)
    return ",".join(keys)


def spec_keys(spec: str) -> List[str]:
    return [k for alt in spec.split("|") for k in alt.split(",") if k.strip()]


def spec_reason(spec: str) -> str:
    """Human-readable xfail reason for a spec like "A,B | C"."""
    alts = [
        " + ".join(
            ISSUES.get(k.strip(), f"unknown issue key {k.strip()!r}")
            for k in alt.split(",")
        )
        for alt in spec.split("|")
        if alt.strip()
    ]
    return " OR ".join(alts) if alts else "unclassified, see known_issues.py"


def read_known_failures(path: Path) -> Dict[str, str]:
    """case id -> spec. Lines are "<case id> <spec>"; the spec may be empty."""
    out: Dict[str, str] = {}
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.split("#", 1)[0].strip()
            if line:
                case_id, _, spec = line.partition(" ")
                out[case_id] = "".join(spec.split())
    return out


def write_known_failures(path: Path, cases: Dict[str, str]) -> None:
    width = max((len(c) for c in cases), default=0)
    path.write_text(
        "".join(
            f"{c.ljust(width)}  {cases[c].replace('|', ' | ')}".rstrip() + "\n"
            for c in sorted(cases)
        )
    )
