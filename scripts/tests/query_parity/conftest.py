import fnmatch
import os
from pathlib import Path
from typing import Dict, List, Optional

import pytest

from known_issues import KNOWN_ISSUES
from scenarios import BUCKET_TYPES, all_scenarios
from servers import Server, python_server_cmd, rust_server_cmd

SCENARIOS = all_scenarios()


KNOWN_FAILURES = Path(__file__).with_name("known_failures.txt")
_failed_ids: List[str] = []


def pytest_addoption(parser):
    parser.addoption(
        "--update-known-failures",
        action="store_true",
        help="run without xfail markers and rewrite known_failures.txt from the failures",
    )


def known_reason(case_id: str) -> Optional[str]:
    kind = "invariant" if case_id.split(":")[0] in ("python", "rust") else "parity"
    for k, pattern, reason in KNOWN_ISSUES:
        if k == kind and fnmatch.fnmatchcase(case_id, pattern):
            return reason
    return None


def _case_id(item) -> Optional[str]:
    callspec = getattr(item, "callspec", None)
    return callspec.params.get("case_id") if callspec else None


def pytest_collection_modifyitems(config, items):
    if config.getoption("--update-known-failures"):
        return
    known = (
        set(KNOWN_FAILURES.read_text().split()) if KNOWN_FAILURES.exists() else set()
    )
    for item in items:
        case_id = _case_id(item)
        if case_id in known:
            reason = known_reason(case_id) or "unclassified, see known_issues.py"
            # strict: a fix makes the case XPASS, which fails the run until
            # known_failures.txt is regenerated.
            item.add_marker(pytest.mark.xfail(reason=reason, strict=True))


def pytest_runtest_logreport(report):
    if report.when == "call" and report.failed:
        _failed_ids.append(report.nodeid.split("[", 1)[1].rstrip("]"))


def pytest_sessionfinish(session, exitstatus):
    if not session.config.getoption("--update-known-failures"):
        return
    ids = sorted(set(_failed_ids))
    KNOWN_FAILURES.write_text("".join(i + "\n" for i in ids))
    unclassified = [i for i in ids if known_reason(i) is None]
    print(f"\nwrote {len(ids)} known failures to {KNOWN_FAILURES}")
    if unclassified:
        print(
            "not matched by any pattern in known_issues.py:\n  "
            + "\n  ".join(unclassified)
        )


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
