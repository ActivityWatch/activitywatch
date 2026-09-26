"""Why the cases in known_failures.txt fail.

known_failures.txt lists the exact case ids that currently fail; they are
marked strict xfail, so the suite is green today and a fix that lands in the
pinned submodules turns them into XPASS failures. Then regenerate the list
with ``--update-known-failures`` (and drop entries here that no longer match).

The globs below attribute each listed case to an issue; the first match wins.
Parity ids look like ``<scenario>-p<period>-<query>``, invariant ids like
``<server>:<scenario>-p<period>-<query>:<check>``. ``--update-known-failures``
prints any failure no pattern explains, which is a new divergence to triage.
"""

from typing import List, Tuple

CORE_161 = "union_no_overlap: contained events overlap (ActivityWatch/aw-core#161)"
RUST_744 = "union_no_overlap: zero-duration events (ActivityWatch/aw-server-rust#744)"
UNION = "union_no_overlap: ActivityWatch/aw-core#161 (containment), ActivityWatch/aw-server-rust#744 (zero-duration)"
RUST_745 = "Rust truncates durations to ns and sum_durations to ms (ActivityWatch/aw-server-rust#745)"
RUST_746 = "flood() diverges (ActivityWatch/aw-server-rust#746)"
RUST_747 = "filter_period_intersect drops zero-duration events in Rust (ActivityWatch/aw-server-rust#747)"
CORE_162 = "aw-core clips events 1 ms past the period end (ActivityWatch/aw-core#162)"
CORE_163 = "equal-timestamp order differs between servers (ActivityWatch/aw-core#163)"
CORE_164 = (
    "aw-core parser mis-splits args after a nested call (ActivityWatch/aw-core#164)"
)
SHAPE = "output data shape differs (ActivityWatch/activitywatch#1466)"
PRECISION = (
    "aw-core stores event timestamps at 1 ms resolution, Rust at 1 ns (by design)"
)
CANONICAL = "canonical queries inherit flood()/merge_events_by_keys divergences (ActivityWatch/aw-server-rust#746, ActivityWatch/activitywatch#1466)"

# (kind, pattern, reason)
KNOWN_ISSUES: List[Tuple[str, str, str]] = [
    # --- invariants: bugs in one server ---
    ("invariant", "python:*-union_no_overlap*", CORE_161),
    ("invariant", "python:*-multidevice:md_no_overlap", CORE_161),
    ("invariant", "rust:zero-*-union_no_overlap*", RUST_744),
    ("invariant", "rust:*-flood:no_overlap_positive", RUST_746),
    ("invariant", "rust:*-sum_durations:sum_matches_a", RUST_745),
    ("invariant", "python:*-merge_events_by_keys_app:merge_conserves_app", SHAPE),
    # --- parity: whole scenarios whose input already differs ---
    ("parity", "identical-*", CORE_163),
    ("parity", "same-start-*", CORE_163),
    ("parity", "period-clip-p*", CORE_162),
    ("parity", "period-clip-us-*", CORE_162),
    ("parity", "dst-p1-*", CORE_162),
    ("parity", "fractional*", PRECISION),
    # --- parity: per transform ---
    ("parity", "*-flood", RUST_746),
    ("parity", "*-flood_pulsetime", RUST_746),
    ("parity", "*-union_no_overlap_flooded", RUST_746 + "; " + UNION),
    ("parity", "*-union_no_overlap*", UNION),
    ("parity", "*-filter_period_intersect*", RUST_747),
    ("parity", "*-period_union", RUST_745),
    ("parity", "*-sum_durations", RUST_745),
    ("parity", "*-merge_events_by_keys_*", SHAPE),
    ("parity", "*-chunk_events_by_key", SHAPE),
    ("parity", "*-split_url_events", SHAPE),
    ("parity", "*-tag", SHAPE),
    ("parity", "*-tag_list_names", SHAPE),
    ("parity", "*-nested_call_args", CORE_164),
    ("parity", "*-aw-client:*", CANONICAL),
    ("parity", "*-multidevice*", CANONICAL),
]
