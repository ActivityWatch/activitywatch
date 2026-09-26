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
- fixed only by all fixes: the keys whose removal makes it fail again (``A,B``)
- still failing with all fixes: the keys it had (or the pattern suggestion),
  minus the measured fixes, i.e. the causes that have no fix yet

Only the first column of the result files is read, so they can be in either
the old (id only) or the new (id + spec) format.
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Set

from known_issues import (
    ISSUES,
    read_known_failures,
    spec_keys,
    suggest_spec,
    write_known_failures,
)

KNOWN_FAILURES = Path(__file__).with_name("known_failures.txt")


def failing(path: Path) -> Set[str]:
    return set(read_known_failures(path))


def attribute(results: Path, current: Dict[str, str]) -> Dict[str, str]:
    base = failing(results / "base.txt")
    fixes = sorted(p.stem for p in results.glob("*.txt") if p.stem in ISSUES)
    unknown = [
        p.name
        for p in results.glob("*.txt")
        if p.stem not in ISSUES
        and p.stem not in ("base", "all")
        and not (p.stem.startswith("all-") and p.stem[4:] in ISSUES)
    ]
    if unknown:
        sys.exit(f"unrecognised result files (not an ISSUES key): {unknown}")
    single = {k: failing(results / f"{k}.txt") for k in fixes}
    all_ = failing(results / "all.txt")
    all_but = {
        k: failing(results / f"all-{k}.txt")
        for k in fixes
        if (results / f"all-{k}.txt").exists()
    }

    new_failures = set().union(all_, *single.values(), *all_but.values()) - base
    if new_failures:
        print(f"note: {len(new_failures)} cases fail with a fix but not in base:")
        for c in sorted(new_failures):
            print("  ", c)

    out: Dict[str, str] = {}
    for c in sorted(base):
        alone = [k for k in fixes if c not in single[k]]
        needed = [k for k in fixes if k in all_but and c in all_but[k]]
        if c in all_:
            old = current.get(c) or suggest_spec(c)
            remaining = [k for k in spec_keys(old) if k not in fixes]
            if not remaining:
                print(f"unexplained: {c} still fails with every fix ({old!r})")
                remaining = spec_keys(old)
            out[c] = ",".join(dict.fromkeys(remaining))
        elif alone:
            alts: List[str] = list(alone)
            if needed and set(needed) != set(alone):
                alts.append(",".join(needed))
            out[c] = "|".join(dict.fromkeys(alts))
        elif needed:
            out[c] = ",".join(needed)
        else:
            print(
                f"ambiguous: {c} is fixed by all fixes, but by no single one or subset tested"
            )
            out[c] = ",".join(fixes)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("results", type=Path)
    parser.add_argument(
        "--write", action="store_true", help="update known_failures.txt"
    )
    args = parser.parse_args()

    current = read_known_failures(KNOWN_FAILURES)
    cases = attribute(args.results, current)
    counts: Dict[str, int] = {}
    for spec in cases.values():
        counts[spec] = counts.get(spec, 0) + 1
    for spec, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"{n:5}  {spec}")
    if args.write:
        write_known_failures(KNOWN_FAILURES, cases)
        print(f"wrote {len(cases)} cases to {KNOWN_FAILURES}")


if __name__ == "__main__":
    main()
