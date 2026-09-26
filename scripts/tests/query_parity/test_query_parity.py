"""Query parity between aw-server (Python) and aw-server-rust.

Inserts identical events into both servers, runs the same queries through
``/api/0/query/`` and asserts the normalized results match. Also checks
invariants (sorting, no overlap after unions, duration conservation) on
each server's output separately. See README.md for how to run it.
"""

from functools import lru_cache
from typing import Any, List, Tuple

import pytest

from conftest import SCENARIOS
from corpus import all_queries, render
from invariants import CHECKS
from normalize import diff, normalize

QUERIES = all_queries()
SCENARIO_BY_NAME = {s.name: s for s in SCENARIOS}
QUERY_BY_NAME = {q.name: q for q in QUERIES}


def _cases() -> List[Tuple[str, str, int]]:
    out = []
    for s in SCENARIOS:
        for pi in range(len(s.periods)):
            for q in QUERIES:
                if set(q.roles) <= set(s.buckets):
                    out.append((s.name, q.name, pi))
    return out


CASES = _cases()


def case_id(scenario: str, query: str, period: int) -> str:
    return f"{scenario}-p{period}-{query}"


_servers: dict = {}


@lru_cache(maxsize=None)
def run(server: str, scenario: str, query: str, period: int) -> Any:
    s, q = SCENARIO_BY_NAME[scenario], QUERY_BY_NAME[query]
    start, end = s.periods[period]
    return _servers[server].query(render(q, s.bucket_id), f"{start}/{end}")


@lru_cache(maxsize=None)
def run_raw(server: str, scenario: str, period: int) -> Any:
    return normalize(run(server, scenario, "query_bucket", period), ordered=True)


@pytest.fixture(autouse=True)
def _bind_servers(servers):
    _servers.update(servers)


@pytest.mark.parametrize(
    "case_id,scenario,query,period",
    [(case_id(s, q, p), s, q, p) for s, q, p in CASES],
    ids=[case_id(s, q, p) for s, q, p in CASES],
)
def test_parity(case_id, scenario, query, period):
    q = QUERY_BY_NAME[query]
    py_raw, rs_raw = (
        run("python", scenario, query, period),
        run("rust", scenario, query, period),
    )
    py, rs = normalize(py_raw, q.ordered), normalize(rs_raw, q.ordered)
    problems = diff(py, rs)
    if not problems and not q.expect_error and py == ("ERROR",):
        problems = ["both servers returned an error"]
    if problems:
        errors = [
            f"{name} error {r['__error__']}: {r['__message__']}"
            for name, r in (("python", py_raw), ("rust", rs_raw))
            if isinstance(r, dict) and "__error__" in r
        ]
        text = render(q, SCENARIO_BY_NAME[scenario].bucket_id)
        pytest.fail(
            f"python and rust disagree on {query!r} ({scenario}, period {period}):\n"
            + "\n".join(errors + problems)
            + f"\n--- query ---\n{text[:1500]}",
            pytrace=False,
        )


INVARIANT_CASES = [
    (f"{server}:{case_id(s, q, p)}:{check}", server, s, q, p, check)
    for server in ("python", "rust")
    for s, q, p in CASES
    for check in QUERY_BY_NAME[q].invariants
]


@pytest.mark.parametrize(
    "case_id,server,scenario,query,period,check",
    INVARIANT_CASES,
    ids=[c[0] for c in INVARIANT_CASES],
)
def test_invariant(case_id, server, scenario, query, period, check):
    result = run(server, scenario, query, period)
    if isinstance(result, dict) and "__error__" in result:
        pytest.skip(f"{server} errored; covered by test_parity")
    raw = run_raw(server, scenario, period)
    violations = CHECKS[check](normalize(result, ordered=True), raw)
    if violations:
        pytest.fail(
            f"{server}: {query} violates {check} ({scenario}, period {period}):\n"
            + "\n".join(violations),
            pytrace=False,
        )
