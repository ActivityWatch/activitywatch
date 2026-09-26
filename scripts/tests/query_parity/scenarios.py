"""Event fixtures inserted identically into both servers.

A scenario is a set of buckets, keyed by role:

- ``a``, ``b``: generic buckets for single-transform queries. Events carry
  ``app``, ``title``, ``url``, ``status`` and ``audible`` so every transform
  has something to work on.
- ``window``, ``afk``, ``browser``, ``android``: realistic watcher buckets for
  the canonical aw-client/aw-webui queries (``browser`` holds a chrome bucket).
- ``window2``, ``afk2``: a second desktop host, for the multidevice query.

Deterministic edge cases are hand written; random scenarios are generated
from fixed seeds so every run (and every server) sees the same events.
"""

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

UTC = timezone.utc
T0 = datetime(2026, 1, 5, 9, 0, tzinfo=UTC)

APPS = ["Firefox", "Code", "Terminal", "Slack", "Google Chrome"]
TITLES = ["main.py - Code", "Inbox", "ActivityWatch", "", "Übersicht ✓"]
URLS = [
    "https://github.com/ActivityWatch/aw-core/pull/161",
    "https://activitywatch.net/",
    "http://localhost:5600/#/timeline?x=1",
    "https://docs.activitywatch.net/en/latest/",
    "about:blank",
]

BUCKET_TYPES = {
    "a": "test",
    "b": "test",
    "window": "currentwindow",
    "window2": "currentwindow",
    "afk": "afkstatus",
    "afk2": "afkstatus",
    "browser": "web.tab.current",
    "android": "currentwindow",
}

# Bucket id prefixes, chosen so the aw-client/aw-webui queries find them
# (e.g. browser buckets must contain "chrome").
BUCKET_PREFIX = {
    "a": "parity-a",
    "b": "parity-b",
    "window": "aw-watcher-window",
    "window2": "aw-watcher-window",
    "afk": "aw-watcher-afk",
    "afk2": "aw-watcher-afk",
    "browser": "aw-watcher-web-chrome",
    "android": "aw-watcher-android",
}


def ev(start, duration: float, **data) -> dict:
    """Event dict. ``start`` is seconds after T0, or a datetime/ISO string."""
    if isinstance(start, (int, float)):
        ts = (T0 + timedelta(seconds=start)).isoformat()
    elif isinstance(start, datetime):
        ts = start.isoformat()
    else:
        ts = start
    return {"timestamp": ts, "duration": duration, "data": data}


def app(start, duration, a="Code", title="main.py - Code", **extra) -> dict:
    return ev(start, duration, app=a, title=title, **extra)


@dataclass
class Scenario:
    name: str
    buckets: Dict[str, List[dict]]
    # Query periods as (start, end); defaults to one wide period.
    periods: List[Tuple[str, str]] = field(default_factory=list)

    def __post_init__(self):
        if not self.periods:
            self.periods = [
                (
                    (T0 - timedelta(days=2)).isoformat(),
                    (T0 + timedelta(days=5)).isoformat(),
                )
            ]

    def host(self, role: str) -> str:
        return f"{self.name}{'-2' if role.endswith('2') else ''}.parity"

    def bucket_id(self, role: str) -> str:
        # The trailing ".parity" keeps ids from being prefixes of each other,
        # since find_bucket() matches by prefix.
        return f"{BUCKET_PREFIX[role]}_{self.host(role)}"


def _generic(i: int, rng: Optional[random.Random] = None, **override) -> dict:
    r = rng or random.Random(i)
    data = {
        "app": r.choice(APPS),
        "title": r.choice(TITLES),
        "url": r.choice(URLS),
        "status": r.choice(["afk", "not-afk"]),
        "audible": r.choice([True, False]),
    }
    data.update(override)
    return data


def deterministic() -> List[Scenario]:
    m = 60
    s: List[Scenario] = []

    def gen(name, a, b, **kw):
        s.append(Scenario(name, {"a": a, "b": b}, **kw))

    # union_no_overlap containment (ActivityWatch/aw-core#161,
    # ActivityWatch/aw-server-rust#674): several b events inside one a event.
    gen(
        "containment",
        [app(0, 10 * m, "A"), app(20 * m, 10 * m, "A")],
        [app(2 * m, 1 * m, "b"), app(5 * m, 1 * m, "b")],
    )
    # b event straddling a gap between two a events.
    gen(
        "straddle",
        [app(0, 10 * m, "A"), app(20 * m, 10 * m, "A")],
        [app(5 * m, 20 * m, "b"), app(35 * m, 1 * m, "b")],
    )
    # Adjacent events, touching exactly at the boundary.
    gen(
        "adjacent",
        [app(0, 10, "A"), app(10, 10, "A"), app(30, 10, "C")],
        [app(20, 10, "b"), app(40, 5, "b"), app(0, 10, "b")],
    )
    # Zero-duration events (ActivityWatch/aw-server-rust#744).
    gen(
        "zero-duration",
        [app(5, 0, "A"), app(7, 1, "A"), app(20, 0, "A")],
        [app(0, 10, "b"), app(20, 0, "b"), app(30, 0, "b")],
    )
    # Zero-duration point inside an earlier b event (review of aw-core#161).
    gen("zero-inside-b", [app(0, 1, "A")], [app(0, 3, "b"), app(0, 0, "b")])
    # Identical ranges in both buckets and within one bucket.
    gen(
        "identical",
        [app(0, 10, "A"), app(0, 10, "A2"), app(20, 5, "A")],
        [app(0, 10, "b"), app(20, 5, "b")],
    )
    # filter_period_intersect boundaries (ActivityWatch/aw-core#166): a
    # zero-duration filter at the end of another filter, or at the end of the
    # event, and two adjacent filters. Half-open [start, end) semantics keep the
    # zero-duration piece at 6 s, since 6 s isn't inside [0, 6).
    gen("fpi-zero-at-filter-end", [app(0, 10, "A")], [app(0, 6, "b"), app(6, 0, "z")])
    gen("fpi-zero-at-event-end", [app(0, 10, "A")], [app(0, 10, "b"), app(10, 0, "z")])
    gen("fpi-adjacent-filters", [app(0, 10, "A")], [app(0, 6, "b"), app(6, 4, "c")])
    # Equal start times. Storage order for ties differs between servers, and
    # order-sensitive transforms (flood, merge_events_by_keys, union) inherit it.
    gen(
        "same-start",
        [
            app(0, 5, "A"),
            app(0, 10, "B"),
            app(0, 0, "C"),
            app(20, 3, "D"),
            app(20, 3, "E"),
        ],
        [app(0, 2, "b"), app(0, 7, "c"), app(20, 3, "d")],
    )
    # Self-overlapping input (as produced by buggy watchers or merged buckets).
    gen(
        "self-overlap",
        [app(0, 30, "A"), app(10, 5, "B"), app(12, 30, "C")],
        [app(5, 10, "b"), app(40, 10, "b")],
    )
    # Inserted out of order; servers sort on read.
    gen(
        "unsorted",
        [app(50, 5, "C"), app(0, 5, "A"), app(20, 10, "B"), app(10, 3, "A")],
        [app(40, 3, "b"), app(3, 10, "b"), app(60, 1, "b")],
    )
    # Fractional seconds (µs precision timestamps and durations).
    gen(
        "fractional",
        [app(0.123456, 1.5, "A"), app(1.623457, 0.000001, "A"), app(2.5, 0.0005, "B")],
        [app(0.5, 0.25, "b"), app(1.623456, 0.1, "b"), app(2.4995, 0.001, "b")],
    )
    # Millisecond-precision fractional seconds.
    gen(
        "fractional-ms",
        [app(0.123, 1.5, "A"), app(1.623, 0.001, "A"), app(2.5, 0.25, "B")],
        [app(0.5, 0.25, "b"), app(1.624, 0.1, "b")],
    )
    # Timestamps with non-UTC offsets around the Europe DST switch
    # (2026-03-29 01:00 UTC): 01:59:30+01:00 and 03:00:00+02:00 are 60 s apart.
    cet, cest = timezone(timedelta(hours=1)), timezone(timedelta(hours=2))
    dst_a = [
        ev(datetime(2026, 3, 29, 1, 59, 0, tzinfo=cet), 30, app="A", title="x"),
        ev(datetime(2026, 3, 29, 1, 59, 30, tzinfo=cet), 60, app="A", title="x"),
        ev(datetime(2026, 3, 29, 3, 0, 30, tzinfo=cest), 30, app="B", title="y"),
    ]
    dst_b = [
        ev(datetime(2026, 3, 29, 3, 0, 0, tzinfo=cest), 45, app="b", title="z"),
        ev("2026-03-29T00:58:00Z", 30, app="b", title="z"),
    ]
    gen(
        "dst",
        dst_a,
        dst_b,
        periods=[
            ("2026-03-28T00:00:00+01:00", "2026-03-30T00:00:00+02:00"),
            # Period cut in the middle of events, in a non-UTC offset.
            ("2026-03-29T01:59:45+01:00", "2026-03-29T03:00:40+02:00"),
        ],
    )
    # Events cut by the query period boundaries.
    gen(
        "period-clip",
        [app(-30, 60, "A"), app(100, 50, "B"), app(170, 60, "C")],
        [app(-10, 20, "b"), app(190, 20, "b")],
        periods=[
            (T0.isoformat(), (T0 + timedelta(seconds=200)).isoformat()),
            (
                (T0 + timedelta(seconds=0.5)).isoformat(),
                (T0 + timedelta(seconds=199.5)).isoformat(),
            ),
        ],
    )
    # Period boundaries with sub-millisecond precision.
    gen(
        "period-clip-us",
        [app(-30, 60, "A"), app(100, 50, "B")],
        [app(-10, 20, "b")],
        periods=[
            (
                (T0 + timedelta(seconds=10.0004)).isoformat(),
                (T0 + timedelta(seconds=120.0004)).isoformat(),
            ),
        ],
    )
    # One bucket empty.
    gen("empty-b", [app(0, 10, "A"), app(20, 10, "B")], [])
    # Data edge cases: missing keys, non-string values, unicode.
    gen(
        "data-shapes",
        [
            ev(
                0,
                10,
                app="A",
                title="t",
                url="https://x.org/a?b=c#d",
                n=1,
                audible=True,
                status="not-afk",
            ),
            ev(
                10,
                10,
                app="A",
                url="https://x.org:8080/",
                n=1.5,
                audible=False,
                status="afk",
            ),
            ev(20, 10, title="no app", url="not a url", status="not-afk"),
            ev(
                30,
                10,
                app="Ä😀",
                title="Ä😀",
                url="",
                nested={"k": [1, 2]},
                audible=True,
            ),
            ev(40, 10, app=None, title="null app"),
        ],
        [ev(5, 30, app="b", title="t", status="not-afk")],
    )
    # Gaps just under/over the flood pulsetime (5 s).
    gen(
        "flood-gaps",
        [
            app(0, 10, "A"),
            app(14.9, 10, "A"),
            app(30, 10, "A"),
            app(45.1, 1, "B"),
            app(46, 10, "A"),
        ],
        [app(0, 1, "b"), app(5, 1, "b"), app(11.5, 1, "c")],
    )
    return s


def q2ms(x: float) -> float:
    """Round to an even number of milliseconds.

    aw-core truncates event timestamps to milliseconds, so a gap split at its
    midpoint (flood) is only exact on both servers when every boundary is a
    multiple of 2 ms. Sub-millisecond behaviour has its own scenarios.
    """
    return round(x * 500) / 500


def _random_events(rng: random.Random, n: int) -> List[dict]:
    t = rng.uniform(0, 60)
    out = []
    for i in range(n):
        dur = q2ms(
            rng.choice(
                [
                    0.0,
                    rng.uniform(0, 5),
                    rng.uniform(0, 120),
                    float(rng.randint(1, 600)),
                ]
            )
        )
        t = q2ms(t)
        out.append(ev(t, dur, **_generic(i, rng)))
        step = rng.choice(
            [
                dur,  # adjacent
                dur + rng.uniform(0, 4),  # small gap (flood fills it)
                dur + rng.uniform(5, 300),  # large gap
                dur * rng.uniform(0, 1),  # overlap with previous
            ]
        )
        # Unique start times: the tie order of equal timestamps is covered
        # separately by the "same-start" scenario.
        t += max(step, 0.002)
    rng.shuffle(out)  # insertion order is random; servers sort on read
    return out


def _random_watchers(rng: random.Random, suffix: str = "") -> Dict[str, List[dict]]:
    """Heartbeat-like window/afk/browser/android buckets."""
    b: Dict[str, List[dict]] = {}
    t, window, afk, web = 0.0, [], [], []
    for _ in range(rng.randint(20, 80)):
        dur = q2ms(rng.choice([rng.uniform(1, 60), rng.uniform(60, 900)]))
        a = rng.choice(APPS)
        window.append(app(t, dur, a, rng.choice(TITLES)))
        if a == "Google Chrome":
            web.append(
                ev(
                    t + 0.5,
                    max(0.0, dur - 1),
                    url=rng.choice(URLS),
                    title=rng.choice(TITLES),
                    audible=rng.random() < 0.2,
                    incognito=False,
                )
            )
        t = q2ms(
            t + dur + rng.choice([0.0, 0.0, rng.uniform(0, 4), rng.uniform(5, 600)])
        )
    end = t
    t = 0.0
    status = "not-afk"
    while t < end:
        dur = q2ms(rng.uniform(60, 1800))
        afk.append(ev(t, dur, status=status))
        status = "afk" if status == "not-afk" else "not-afk"
        t = q2ms(t + dur + rng.choice([0.0, rng.uniform(0, 3)]))
    b["window" + suffix] = window
    b["afk" + suffix] = afk
    if not suffix:
        b["browser"] = web
        t = rng.uniform(0, 3600)
        android = []
        for _ in range(rng.randint(10, 40)):
            dur = q2ms(rng.uniform(1, 300))
            android.append(
                ev(
                    q2ms(t),
                    dur,
                    app=rng.choice(APPS),
                    package="org.example",
                    classname="Main",
                )
            )
            t += dur + rng.choice([0.0, rng.uniform(0, 600)])
        b["android"] = android
    return b


def random_scenarios(n: int = 12) -> List[Scenario]:
    out = []
    for seed in range(n):
        rng = random.Random(seed)
        buckets: Dict[str, List[dict]] = {
            "a": _random_events(rng, rng.randint(5, 60)),
            "b": _random_events(rng, rng.randint(5, 60)),
        }
        buckets.update(_random_watchers(rng))
        buckets.update(_random_watchers(rng, suffix="2"))
        # Cut events at the period start only, at millisecond precision:
        # cutting at the period end diverges on its own (aw-core rounds the
        # end up by 1 ms), which the period-clip* scenarios cover.
        clip = (
            (T0 + timedelta(seconds=q2ms(rng.uniform(100, 2000)))).isoformat(),
            (T0 + timedelta(days=3)).isoformat(),
        )
        wide = (
            (T0 - timedelta(days=1)).isoformat(),
            (T0 + timedelta(days=3)).isoformat(),
        )
        out.append(Scenario(f"seed{seed:02d}", buckets, periods=[wide, clip]))
    return out


def all_scenarios() -> List[Scenario]:
    return deterministic() + random_scenarios()
