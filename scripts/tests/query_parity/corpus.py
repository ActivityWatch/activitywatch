"""The query corpus run against both servers.

Each query is a template: ``{a}``, ``{window}`` etc. are replaced with the
scenario's bucket ids (plain token replacement, see ``render``). ``ordered=False`` means the result order is not part
of the contract (e.g. merge_events_by_keys groups, or ties in sort_by_duration)
and lists are compared as multisets. ``invariants`` name checks from
``invariants.py`` that each server's own output must satisfy.
"""

import json
import re
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple, Union

from aw_client.queries import (
    AndroidQueryParams,
    DesktopQueryParams,
    canonicalEvents,
    fullDesktopQuery,
)

CLASSES = [
    (["Work"], {"type": "regex", "regex": "Code|Terminal|GitHub|github"}),
    (
        ["Work", "Programming"],
        {"type": "regex", "regex": "main\\.py|aw-core", "ignore_case": True},
    ),
    (["Comms"], {"type": "regex", "regex": "Slack|Inbox"}),
    (["Media"], {"type": "regex", "regex": "^ActivityWatch$"}),
]
# Same un-escaping aw-client/aw-webui apply to regexes in category rules.
CLASSES_STR = json.dumps(CLASSES).replace("\\\\", "\\")
# tag() rules name tags with plain strings.
TAGS_STR = json.dumps([[".".join(c), r] for c, r in CLASSES]).replace("\\\\", "\\")


@dataclass
class Query:
    name: str
    code: Union[str, Callable[[Callable[[str], str]], str]]
    roles: Tuple[str, ...] = ("a", "b")
    ordered: bool = True
    invariants: List[str] = field(default_factory=list)
    # Both servers are expected to reject the query.
    expect_error: bool = False


LOAD = 'a = query_bucket("{a}"); b = query_bucket("{b}");'


# query_bucket returns events newest first; the interval transforms are meant
# for ascending input (as flood() produces), so most queries sort first.
LOAD_SORTED = 'a = sort_by_timestamp(query_bucket("{a}")); b = sort_by_timestamp(query_bucket("{b}"));'


def q(name, body, sort=False, **kw) -> Query:
    return Query(name, (LOAD_SORTED if sort else LOAD) + "\n" + body, **kw)


TRANSFORMS: List[Query] = [
    q("query_bucket", 'RETURN = {"a": a, "b": b};', ordered=True),
    q("find_bucket", 'RETURN = query_bucket(find_bucket("{a}"));'),
    q("flood", "RETURN = flood(a);", invariants=["sorted_ts", "no_overlap_positive"]),
    q("flood_pulsetime", "RETURN = flood(a, 10);"),
    q(
        "sort_by_timestamp",
        "RETURN = sort_by_timestamp(concat(b, a));",
        invariants=["sorted_ts"],
    ),
    q(
        "sort_by_duration",
        "RETURN = sort_by_duration(a);",
        ordered=False,
        invariants=["sorted_dur"],
    ),
    q("limit_events", "RETURN = limit_events(sort_by_timestamp(a), 3);"),
    q("limit_events_zero", "RETURN = limit_events(a, 0);"),
    q("concat", "RETURN = concat(a, b);"),
    q("sum_durations", "RETURN = sum_durations(a);", invariants=["sum_matches_a"]),
    q("filter_keyvals", 'RETURN = filter_keyvals(a, "app", ["Code", "A", "Firefox"]);'),
    q("filter_keyvals_bool", 'RETURN = filter_keyvals(a, "audible", [true]);'),
    q("exclude_keyvals", 'RETURN = exclude_keyvals(a, "app", ["Code", "A"]);'),
    q(
        "filter_keyvals_regex",
        'RETURN = filter_keyvals_regex(a, "title", "^(Inbox|main)|✓");',
    ),
    q(
        "merge_events_by_keys_app",
        'RETURN = merge_events_by_keys(a, ["app"]);',
        ordered=False,
        invariants=["merge_conserves_app"],
    ),
    q(
        "merge_events_by_keys_app_title",
        'RETURN = merge_events_by_keys(a, ["app", "title"]);',
        ordered=False,
    ),
    q(
        "merge_events_by_keys_missing",
        'RETURN = merge_events_by_keys(a, ["nonexistent"]);',
        ordered=False,
    ),
    q(
        "chunk_events_by_key",
        'RETURN = chunk_events_by_key(sort_by_timestamp(a), "app");',
    ),
    q("split_url_events", "RETURN = split_url_events(a);"),
    q(
        "categorize",
        "RETURN = categorize(a, " + CLASSES_STR + ");",
        invariants=["same_durations"],
    ),
    q("tag", "RETURN = tag(a, " + TAGS_STR + ");", invariants=["same_durations"]),
    q("tag_list_names", "RETURN = tag(a, " + CLASSES_STR + ");"),
    # Nested call followed by more arguments (no intermediate variable).
    Query(
        "nested_call_args",
        'RETURN = filter_keyvals(query_bucket("{a}"), "app", ["Code", "A"]);',
    ),
    q(
        "filter_period_intersect",
        "RETURN = filter_period_intersect(a, b);",
        sort=True,
        invariants=["within_b"],
    ),
    q(
        "filter_period_intersect_rev",
        "RETURN = filter_period_intersect(b, a);",
        sort=True,
    ),
    q("filter_period_intersect_unsorted", "RETURN = filter_period_intersect(a, b);"),
    q(
        "period_union",
        "RETURN = period_union(a, b);",
        sort=True,
        invariants=["no_overlap", "measure_ab"],
    ),
    q(
        "union_no_overlap",
        "RETURN = union_no_overlap(a, b);",
        sort=True,
        invariants=["no_overlap", "measure_ab"],
    ),
    q(
        "union_no_overlap_rev",
        "RETURN = union_no_overlap(b, a);",
        sort=True,
        invariants=["no_overlap", "measure_ab"],
    ),
    q("union_no_overlap_unsorted", "RETURN = union_no_overlap(a, b);"),
    q("union_no_overlap_empty", "RETURN = union_no_overlap([], a);", sort=True),
    q(
        "union_no_overlap_flooded",
        "RETURN = union_no_overlap(flood(a), flood(b));",
        invariants=["no_overlap"],
    ),
]


def _desktop(bid, **kw) -> DesktopQueryParams:
    return DesktopQueryParams(
        bid_window=bid("window"), bid_afk=bid("afk"), classes=CLASSES, **kw
    )


def canonical_queries() -> List[Query]:
    """Real-world queries, generated with aw-client's query builders."""
    desktop = ("window", "afk")
    return [
        # fullDesktopQuery is the query behind aw-webui's Activity view.
        Query(
            "aw-client:fullDesktopQuery",
            lambda bid: fullDesktopQuery(_desktop(bid)),
            roles=desktop,
            ordered=False,
        ),
        Query(
            "aw-client:fullDesktopQuery+browser",
            lambda bid: fullDesktopQuery(_desktop(bid, bid_browsers=[bid("browser")])),
            roles=desktop + ("browser",),
            ordered=False,
        ),
        Query(
            "aw-client:fullDesktopQuery+always_active",
            lambda bid: fullDesktopQuery(
                _desktop(bid, always_active_pattern="Slack|Terminal")
            ),
            roles=desktop,
            ordered=False,
        ),
        # The ordered canonical event list, as used by the timeline.
        Query(
            "aw-client:canonicalEvents",
            lambda bid: canonicalEvents(_desktop(bid)) + "\nRETURN = events;",
            roles=desktop,
            invariants=["sorted_ts"],
        ),
        Query(
            "aw-client:canonicalEvents-android",
            lambda bid: canonicalEvents(
                AndroidQueryParams(bid_android=bid("android"), classes=CLASSES)
            )
            + "\nRETURN = events;",
            roles=("android",),
            ordered=False,
        ),
        Query(
            "multidevice",
            MULTIDEVICE,
            roles=MD_ROLES,
            ordered=False,
            invariants=["md_no_overlap"],
        ),
        Query(
            "multidevice-webui-android-merge",
            MULTIDEVICE_WEBUI,
            roles=MD_ROLES,
            ordered=False,
        ),
    ]


MD_ROLES = ("window", "afk", "window2", "afk2", "android")


def _host(
    n: str,
    window: str,
    afk: Optional[str],
    android: Optional[str] = None,
    merge_android: bool = False,
) -> str:
    """Per-host part of aw-webui's canonicalMultideviceEvents (src/queries.ts)."""
    if android:
        lines = [f'events = flood(query_bucket("{android}"));']
        if merge_android:
            lines.append('events = merge_events_by_keys(events, ["app"]);')
        lines.append("not_afk = events;")
    else:
        lines = [
            f'events = flood(query_bucket("{window}"));',
            f'not_afk = flood(query_bucket("{afk}"));',
            'not_afk = filter_keyvals(not_afk, "status", ["not-afk"]);',
            "events = filter_period_intersect(events, not_afk);",
        ]
    lines += [
        f"events = categorize(events, {CLASSES_STR});",
        f"events_{n} = events;",
        f"not_afk_{n} = not_afk;",
    ]
    return "\n".join(lines)


def _multidevice(merge_android: bool) -> str:
    hosts = [
        ("h1", "{window}", "{afk}", None),
        ("h2", "{window2}", "{afk2}", None),
        ("h3", None, None, "{android}"),
    ]
    parts = [_host(n, w, a, andr, merge_android) for n, w, a, andr in hosts]
    parts.append("events = []; not_afk = [];")
    for n, *_ in hosts:
        parts.append(f"events = union_no_overlap(events, events_{n});")
        parts.append(f"not_afk = union_no_overlap(not_afk, not_afk_{n});")
    parts.append(
        """
title_events = sort_by_duration(merge_events_by_keys(events, ["app", "title"]));
app_events = sort_by_duration(merge_events_by_keys(events, ["app"]));
cat_events = sort_by_duration(merge_events_by_keys(events, ["$category"]));
app_events = limit_events(app_events, 100);
title_events = limit_events(title_events, 100);
duration = sum_durations(events);
RETURN = {"events": events, "window": {"app_events": app_events, "title_events": title_events,
          "cat_events": cat_events, "active_events": not_afk, "duration": duration}};
"""
    )
    return "\n".join(parts)


# Multidevice query as aw-client#121 builds it (Android events not merged before the union).
MULTIDEVICE = _multidevice(merge_android=False)
# As aw-webui master builds it: Android merged by app before the union
# (ActivityWatch/aw-webui#1004). Both servers must still agree.
MULTIDEVICE_WEBUI = _multidevice(merge_android=True)


def all_queries() -> List[Query]:
    return TRANSFORMS + canonical_queries()


ROLE_TOKEN = re.compile(r"\{(a|b|window2?|afk2?|browser|android)\}")


def render(query: Query, bucket_id: Callable[[str], str]) -> str:
    """Query text for a scenario: ``{role}`` tokens become bucket ids."""
    if callable(query.code):
        return query.code(bucket_id)
    return ROLE_TOKEN.sub(lambda m: bucket_id(m.group(1)), query.code)
