import os
from pathlib import Path
from typing import Dict, List, Optional

import pytest

from known_issues import (
    ISSUES,
    read_known_failures,
    spec_keys,
    spec_reason,
    suggest_spec,
    write_known_failures,
)
from scenarios import BUCKET_TYPES, all_scenarios
from servers import Server, python_server_cmd, rust_server_cmd

SCENARIOS = all_scenarios()


KNOWN_FAILURES = Path(__file__).with_name("known_failures.txt")
_failed_ids: List[str] = []
_ran_ids: List[str] = []


def pytest_addoption(parser):
    parser.addoption(
        "--update-known-failures",
        action="store_true",
        help="run without xfail markers and rewrite known_failures.txt from the failures",
    )


def _case_id(item) -> Optional[str]:
    callspec = getattr(item, "callspec", None)
    return callspec.params.get("case_id") if callspec else None


def pytest_collection_modifyitems(config, items):
    if config.getoption("--update-known-failures"):
        return
    known = read_known_failures(KNOWN_FAILURES)
    for item in items:
        case_id = _case_id(item)
        if case_id in known:
            reason = spec_reason(known[case_id])
            # strict: a fix makes the case XPASS, which fails the run until
            # known_failures.txt is regenerated.
            item.add_marker(pytest.mark.xfail(reason=reason, strict=True))


def pytest_runtest_logreport(report):
    if report.when == "call" and "[" in report.nodeid:
        case_id = report.nodeid.split("[", 1)[1].rstrip("]")
        _ran_ids.append(case_id)
        if report.failed:
            _failed_ids.append(case_id)


def pytest_sessionfinish(session, exitstatus):
    if not session.config.getoption("--update-known-failures"):
        return
    # Only cases that actually ran are updated; entries for cases that were
    # deselected, skipped or never reached (interrupted run) are kept.
    # Cases that still fail keep their (measured) spec, new ones get the
    # pattern suggestion from known_issues.py, to be confirmed with attribute.py.
    old = read_known_failures(KNOWN_FAILURES)
    ids = (set(old) - set(_ran_ids)) | set(_failed_ids)
    cases = {i: old[i] if old.get(i) else suggest_spec(i) for i in ids}
    write_known_failures(KNOWN_FAILURES, cases)
    print(f"\nwrote {len(ids)} known failures to {KNOWN_FAILURES}")
    suggested = sorted(i for i in ids if not old.get(i) and cases[i])
    unclassified = sorted(i for i in ids if not cases[i])
    unknown = sorted(
        i for i in ids if any(k not in ISSUES for k in spec_keys(cases[i]))
    )
    if suggested:
        print(
            "new failures attributed by pattern only (confirm with attribute.py):\n  "
            + "\n  ".join(f"{i}  {cases[i]}" for i in suggested)
        )
    if unclassified:
        print(
            "not matched by any pattern in known_issues.py:\n  "
            + "\n  ".join(unclassified)
        )
    if unknown:
        print("unknown issue keys:\n  " + "\n  ".join(unknown))


def _missing(what: str):
    msg = f"{what} not found (see scripts/tests/query_parity/README.md)"
    if os.environ.get("AW_PARITY_REQUIRE"):
        pytest.fail(msg)
    pytest.skip(msg)


@pytest.fixture(scope="session")
def servers() -> Dict[str, Server]:
    py_cmd, rs_cmd = python_server_cmd(), rust_server_cmd()
    if not py_cmd:
        _missing("aw-server (Python)")
    if not rs_cmd:
        _missing("aw-server-rust binary")
    started = {
        "python": Server("python", py_cmd, []),
        "rust": Server(
            "rust", rs_cmd, ["--dbpath", "{tmp}/parity.db", "--no-legacy-import"]
        ),
    }
    try:
        for s in started.values():
            s.start()
        for scenario in SCENARIOS:
            for role, events in scenario.buckets.items():
                for s in started.values():
                    s.create_bucket(
                        scenario.bucket_id(role),
                        BUCKET_TYPES[role],
                        scenario.host(role),
                    )
                    s.insert_events(scenario.bucket_id(role), events)
        yield started
    finally:
        for name, s in started.items():
            if s.proc is not None and s.proc.poll() is not None:
                print(f"{name} server exited with {s.proc.returncode}:\n{s.logs()}")
            s.stop()
