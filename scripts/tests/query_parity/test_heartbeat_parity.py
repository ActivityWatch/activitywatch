"""Sequential collection parity, reusing the direct-insert query harness.

No concurrent requests: that is a separate reproduction scope. Every case uses
fresh buckets so the previous case's last heartbeat cannot affect this one.
"""

import json

import pytest

from corpus import all_queries, render
from normalize import diff, normalize
from scenarios import Scenario, app


QUERY_BY_NAME = {q.name: q for q in all_queries()}

CASES = [
    ("steady", 10, [app(0, 0), app(5, 0), app(10, 0)]),
    ("beyond-pulsetime", 10, [app(0, 0), app(11, 0)]),
    ("data-change", 10, [app(0, 0, "A"), app(5, 0, "B"), app(10, 0, "B")]),
    ("boundary-before", 10, [app(0, 0), app(9.999, 0)]),
    ("boundary-exact", 10, [app(0, 0), app(10, 0)]),
    ("boundary-after", 10, [app(0, 0), app(10.001, 0)]),
    ("same-timestamp-longer", 10, [app(0, 5), app(0, 10)]),
    ("same-timestamp-shorter", 10, [app(0, 10), app(0, 5)]),
    ("containment", 10, [app(0, 30), app(10, 5)]),
    ("negative-gap", 10, [app(0, 20), app(10, 20), app(25, 0)]),
]


@pytest.mark.parametrize("name,pulsetime,events", CASES, ids=[c[0] for c in CASES])
def test_heartbeat_parity(servers, name, pulsetime, events):
    scenario = Scenario(f"heartbeat-{name}", {"a": [], "b": []})
    period = "/".join(scenario.periods[0])
    for server in servers.values():
        for role in ("a", "b"):
            server.create_bucket(scenario.bucket_id(role), "test", scenario.host(role))
        for event in events:
            server.heartbeat(scenario.bucket_id("a"), event, pulsetime)

    context = f"case={name}, pulsetime={pulsetime}, heartbeats={json.dumps(events)}"
    stored = {
        name: normalize(server.events(scenario.bucket_id("a")), ordered=False)
        for name, server in servers.items()
    }
    assert stored["python"] and stored["rust"], f"empty stored events: {context}"
    problems = diff(stored["python"], stored["rust"])
    assert not problems, context + "\nstored events:\n" + "\n".join(problems)

    for query_name in ("flood", "merge_events_by_keys_app"):
        query = QUERY_BY_NAME[query_name]
        program = render(query, scenario.bucket_id)
        results = {
            name: server.query(program, period) for name, server in servers.items()
        }
        for name, result in results.items():
            assert not (isinstance(result, dict) and "__error__" in result), (
                f"{name} query failed: {result}\n{context}\n{program}"
            )
        problems = diff(
            normalize(results["python"], query.ordered),
            normalize(results["rust"], query.ordered),
        )
        assert not problems, context + f"\n{program}\n" + "\n".join(problems)
