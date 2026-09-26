"""Measure which issues each known failure is caused by, and rewrite known_failures.txt.

Run the suite with ``--update-known-failures`` once per configuration and copy
the resulting known_failures.txt into a results directory, named:

    base.txt        pinned submodules, no fixes
    <KEY>.txt       only the fix for issue KEY applied (KEY from known_issues.ISSUES)
    all.txt         every fix applied
    all-<KEY>.txt   every fix except KEY's

Then ``python attribute.py RESULTS_DIR`` prints the attribution and
``--write`` updates known_failures.txt. For each case that fails in base:

- fixed by one fix alone: that key (``A | B`` if several each suffice)
- fixed only by all fixes: the keys whose removal makes it fail again (``A,B``).
  Optional ``<KEY>+<KEY>.txt`` runs (exactly those fixes) verify such
  combinations; without them they are inferred, which the script reports
- still failing with all fixes: the keys it had (or the pattern suggestion),
  minus the measured fixes within each alternative, i.e. the causes that have
  no fix yet

``--write`` refuses to write when a case can't be attributed from the runs.

Only the first column of the result files is read, so they can be in either
the old (id only) or the new (id + spec) format.
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from known_issues import (
    ISSUES,
    read_known_failures,
    suggest_spec,
    write_known_failures,
)

KNOWN_FAILURES = Path(__file__).with_name("known_failures.txt")


def failing(path: Path) -> Set[str]:
    if not path.is_file():
        sys.exit(f"missing result file: {path}")
    return set(read_known_failures(path))


def _combo_keys(stem: str) -> List[str]:
    parts = stem.split("+")
    return parts if len(parts) > 1 and all(k in ISSUES for k in parts) else []


def attribute(
    results: Path, current: Dict[str, str]
) -> Tuple[Dict[str, str], List[str]]:
    """Returns (case id -> spec, problems that make the result unsafe to write)."""
    base = failing(results / "base.txt")
    if not base:
        sys.exit(f"{results / 'base.txt'} lists no failures, refusing to attribute")
    stems = [p.stem for p in results.glob("*.txt")]
    fixes = sorted(s for s in stems if s in ISSUES)
    if not fixes:
        sys.exit(f"no <KEY>.txt result files in {results}")
    unknown = [
        s
        for s in stems
        if s not in ("base", "all")
        and s not in ISSUES
        and not (s.startswith("all-") and s[4:] in fixes)
        and not _combo_keys(s)
    ]
    if unknown:
        sys.exit(
            f"unrecognised result files (not an ISSUES key, or all-<KEY> without <KEY>): {unknown}"
        )
    single = {k: failing(results / f"{k}.txt") for k in fixes}
    all_ = failing(results / "all.txt")
    # Every fix needs its leave-one-out run, or combinations would be misattributed
    all_but = {k: failing(results / f"all-{k}.txt") for k in fixes}
    combos = {
        frozenset(_combo_keys(s)): failing(results / f"{s}.txt")
        for s in stems
        if _combo_keys(s)
    }

    new_failures = (
        set().union(all_, *single.values(), *all_but.values(), *combos.values()) - base
    )
    if new_failures:
        print(f"note: {len(new_failures)} cases fail with a fix but not in base:")
        for c in sorted(new_failures):
            print("  ", c)

    out: Dict[str, str] = {}
    problems: List[str] = []
    unverified = 0

    def combination(c: str, keys: List[str]) -> Optional[str]:
        """Spec for "all of keys", or None if the runs show it isn't enough."""
        nonlocal unverified
        if len(keys) == 1:
            # keys[0] alone was run and didn't fix it, so something else is
            # needed too, and the leave-one-out runs can't tell what.
            return None
        run = combos.get(frozenset(keys))
        if run is None:
            unverified += 1
        elif c in run:
            return None
        return ",".join(keys)

    for c in sorted(base):
        alone = [k for k in fixes if c not in single[k]]
        needed = [k for k in fixes if c in all_but[k]]
        if c in all_:
            # Still failing: drop fixed keys within each alternative, and drop
            # alternatives that only consisted of fixed keys (disproven).
            old = current.get(c) or suggest_spec(c)
            alts = []
            for alt in old.split("|"):
                keys = [k.strip() for k in alt.split(",") if k.strip()]
                rest = [k for k in keys if k not in fixes]
                if rest:
                    alts.append(",".join(dict.fromkeys(rest)))
            if not alts:
                problems.append(
                    f"unexplained: {c} still fails with every fix ({old!r})"
                )
                alts = [old]
            out[c] = "|".join(dict.fromkeys(alts))
        elif alone:
            alts = list(alone)
            if needed and set(needed) != set(alone):
                combo = combination(c, needed)
                if combo is not None:
                    alts.append(combo)
            out[c] = "|".join(dict.fromkeys(alts))
        else:
            combo = combination(c, needed) if needed else None
            if combo is None:
                # Fall back to the supplied combination runs that fix it and
                # contain every needed key, keeping only the minimal ones.
                passing = [
                    keys
                    for keys, run in combos.items()
                    if c not in run and set(needed) <= keys
                ]
                minimal = sorted(
                    ",".join(k for k in fixes if k in keys)
                    for keys in passing
                    if not any(other < keys for other in passing)
                )
                combo = "|".join(minimal) or None
            if combo is None:
                problems.append(
                    f"underdetermined: {c} is fixed by all fixes but not by "
                    f"{','.join(needed) or 'any single one'}; add KEY+KEY.txt runs"
                )
                combo = ",".join(fixes)
            out[c] = combo
    if unverified:
        print(
            f"note: {unverified} combination specs are inferred from the leave-one-out "
            "runs; add KEY+KEY.txt runs to verify them"
        )
    return out, problems


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("results", type=Path)
    parser.add_argument(
        "--write", action="store_true", help="update known_failures.txt"
    )
    args = parser.parse_args()

    current = read_known_failures(KNOWN_FAILURES)
    cases, problems = attribute(args.results, current)
    counts: Dict[str, int] = {}
    for spec in cases.values():
        counts[spec] = counts.get(spec, 0) + 1
    for spec, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"{n:5}  {spec}")
    for p in problems:
        print(p)
    if args.write and problems:
        sys.exit("not writing known_failures.txt, see the problems above")
    if args.write:
        write_known_failures(KNOWN_FAILURES, cases)
        print(f"wrote {len(cases)} cases to {KNOWN_FAILURES}")


if __name__ == "__main__":
    main()
