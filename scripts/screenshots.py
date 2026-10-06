#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "playwright==1.49.1",
# ]
# ///
"""Take marketing screenshots of the ActivityWatch web UI with realistic demo data.

Starts a throwaway aw-server-rust (own port, temp database, temp HOME), seeds it
with a deterministic year of demo data for three devices (a macOS work laptop,
a Linux home desktop, and an Android phone synced via aw-sync), configures the
UI for clean screenshots, and captures a set of views in light and dark themes
with headless Chromium.

Your own ActivityWatch (port 5600/5666) is never touched: the script refuses
those ports and only ever writes to the server it started itself.

Usage:

    uv run scripts/screenshots.py --build      # build aw-webui + aw-server-rust first (if needed)
    uv run scripts/screenshots.py              # use existing builds in the submodules
    uv run scripts/screenshots.py --theme dark --size 1920x1080 --only activity
    uv run scripts/screenshots.py --keep-running   # browse the seeded server afterwards

Output: dist/screenshots/<theme>/<NN-name>.png

By default the server binary is aw-server-rust/target/release/aw-server and the
web UI is aw-server-rust/aw-webui/dist (the pinned submodule checkouts);
override with --server-bin and --webpath.
"""

from __future__ import annotations

import argparse
import colorsys
import contextlib
import hashlib
import json
import math
import os
import random
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Dict, Iterator, List, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
SERVER_DIR = REPO_ROOT / "aw-server-rust"
WEBUI_DIR = SERVER_DIR / "aw-webui"
DEFAULT_SERVER_BIN = SERVER_DIR / "target" / "release" / "aw-server"
DEFAULT_WEBPATH = WEBUI_DIR / "dist"
DEFAULT_OUT = REPO_ROOT / "dist" / "screenshots"

# Ports of real ActivityWatch instances (production / testing). Never use them.
FORBIDDEN_PORTS = {5600, 5666}

LAPTOP = "work-macbook"
DESKTOP = "home-desktop"
PHONE = "pixel-8"

Interval = Tuple[datetime, datetime]

# =============================================================================
# Categories
# =============================================================================
# The aw-webui default categories (src/util/classes.ts, defaultCategories),
# with a few rules extended/added the way a typical user would, so that apps
# like VS Code, Zoom and Figma are categorized too.
CATEGORIES: List[dict] = [
    {
        "name": ["Work"],
        "rule": {
            "type": "regex",
            "regex": "Google Docs|libreoffice|ReText|Notion|Linear",
        },
        "data": {"score": 10},
    },
    {
        "name": ["Work", "Programming"],
        "rule": {
            "type": "regex",
            "regex": "GitHub|Stack Overflow|BitBucket|Gitlab|vim|Spyder|kate|Ghidra|Scite"
            "|Code|iTerm2|kitty|MDN",
        },
    },
    {
        "name": ["Work", "Programming", "ActivityWatch"],
        "rule": {"type": "regex", "regex": "ActivityWatch|aw-", "ignore_case": True},
    },
    {"name": ["Work", "Design"], "rule": {"type": "regex", "regex": "Figma"}},
    {"name": ["Work", "Image"], "rule": {"type": "regex", "regex": "GIMP|Inkscape"}},
    {"name": ["Work", "Video"], "rule": {"type": "regex", "regex": "Kdenlive"}},
    {"name": ["Work", "Audio"], "rule": {"type": "regex", "regex": "Audacity"}},
    {"name": ["Work", "3D"], "rule": {"type": "regex", "regex": "Blender"}},
    {"name": ["Media"], "rule": {"type": "none"}},
    {
        "name": ["Media", "Games"],
        "rule": {"type": "regex", "regex": "Minecraft|RimWorld|Steam"},
    },
    {
        "name": ["Media", "Video"],
        "rule": {"type": "regex", "regex": "YouTube|Plex|VLC"},
    },
    {
        "name": ["Media", "Social Media"],
        "rule": {
            "type": "regex",
            "regex": "reddit|Facebook|Twitter|Instagram|devRant",
            "ignore_case": True,
        },
    },
    {
        "name": ["Media", "Music"],
        "rule": {"type": "regex", "regex": "Spotify|Deezer", "ignore_case": True},
    },
    {"name": ["Comms"], "rule": {"type": "none"}},
    {
        "name": ["Comms", "IM"],
        "rule": {
            "type": "regex",
            "regex": "Messenger|Telegram|Signal|WhatsApp|Rambox|Slack|Riot|Element|Discord"
            "|Nheko|NeoChat|Mattermost",
        },
    },
    {
        "name": ["Comms", "Email"],
        "rule": {"type": "regex", "regex": "Gmail|Thunderbird|mutt|alpine"},
    },
    {
        "name": ["Comms", "Video Conferencing"],
        "rule": {"type": "regex", "regex": "zoom\\.us|Zoom Meeting|Google Meet"},
    },
    # Keep #CCC: dark.css restyles exactly this grey in the summary bars
    {"name": ["Uncategorized"], "rule": {"type": "none"}, "data": {"color": "#CCC"}},
]

# A calmer palette than the neon defaults. Base hues per category; the actual
# colors are derived per theme (see themed_categories) so that bar labels stay
# readable: #333 text on light, white text on dark (contrast >= ~4.9:1).
PALETTE: Dict[Tuple[str, ...], str] = {
    ("Work",): "#3FA27A",
    ("Work", "Programming"): "#2E9E9A",
    ("Work", "Programming", "ActivityWatch"): "#3BAE8C",
    ("Work", "Design"): "#D4AA3A",
    ("Work", "Image"): "#C58BD6",
    ("Work", "Video"): "#7FA6D9",
    ("Work", "Audio"): "#8FB8C9",
    ("Work", "3D"): "#B0A57A",
    ("Media",): "#E8915A",
    ("Media", "Games"): "#E06666",
    ("Media", "Video"): "#E8915A",
    ("Media", "Social Media"): "#E07AA8",
    ("Media", "Music"): "#8DB64A",
    ("Comms",): "#5B8FD0",
    ("Comms", "IM"): "#5E9BE0",
    ("Comms", "Email"): "#7D8FE8",
    ("Comms", "Video Conferencing"): "#9A7FE0",
}


def _luminance(rgb: Tuple[float, float, float]) -> float:
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in rgb]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def _tone(hex_color: str, target_luminance: float, saturation: float) -> str:
    """Same hue, lightness adjusted to a target relative luminance."""
    r, g, b = (int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5))
    h, _l, s = colorsys.rgb_to_hls(r, g, b)
    lo, hi = 0.0, 1.0
    for _ in range(30):
        mid = (lo + hi) / 2
        if _luminance(colorsys.hls_to_rgb(h, mid, s * saturation)) < target_luminance:
            lo = mid
        else:
            hi = mid
    rgb = colorsys.hls_to_rgb(h, (lo + hi) / 2, s * saturation)
    return "#%02X%02X%02X" % tuple(round(v * 255) for v in rgb)


def themed_categories(theme: str) -> List[dict]:
    # light: luminance 0.36 vs #333 text ~4.9:1; dark: 0.15 vs white text ~5.2:1
    target, sat = (0.15, 0.75) if theme == "dark" else (0.36, 0.85)
    out = []
    for cat in CATEGORIES:
        cat = json.loads(json.dumps(cat))
        base = PALETTE.get(tuple(cat["name"]))
        if base:
            cat.setdefault("data", {})["color"] = _tone(base, target, sat)
        out.append(cat)
    return out


# =============================================================================
# Demo data
# =============================================================================
# Building blocks: an "activity" is (app, title) for a window, optionally with
# a web page (url, title) when the app is a browser.


class Page:
    def __init__(self, url: str, title: str, audible: bool = False):
        self.url = url
        self.title = title
        self.audible = audible


def _pages(domain: str, items: Sequence[Tuple[str, str]], audible: bool = False) -> List[Page]:
    return [Page(f"https://{domain}{path}", title, audible) for path, title in items]


GITHUB_WORK = _pages(
    "github.com",
    [
        ("/acme/storefront/pull/1423", "Add retry logic to checkout · Pull Request #1423 · acme/storefront · GitHub"),
        ("/acme/storefront/pull/1431", "Migrate cart state to signals · Pull Request #1431 · acme/storefront · GitHub"),
        ("/acme/storefront/pulls", "Pull requests · acme/storefront · GitHub"),
        ("/acme/storefront/issues/987", "Safari: coupon field loses focus · Issue #987 · acme/storefront · GitHub"),
        ("/acme/billing-api/pull/312", "Idempotency keys for refunds · Pull Request #312 · acme/billing-api · GitHub"),
        ("/acme/billing-api/actions", "Actions · acme/billing-api · GitHub"),
        ("/acme/design-system", "acme/design-system: Shared UI components · GitHub"),
        ("/notifications", "Notifications · GitHub"),
    ],
)
GITHUB_HOME = _pages(
    "github.com",
    [
        ("/ActivityWatch/activitywatch", "ActivityWatch/activitywatch: The best free and open-source automated time tracker · GitHub"),
        ("/home-lab/weather-station", "home-lab/weather-station: ESP32 sensors + dashboard · GitHub"),
        ("/home-lab/weather-station/issues/14", "Graph humidity per room · Issue #14 · home-lab/weather-station · GitHub"),
        ("/home-lab/dotfiles", "home-lab/dotfiles · GitHub"),
        ("/trending", "Trending repositories on GitHub today · GitHub"),
    ],
)
STACKOVERFLOW = _pages(
    "stackoverflow.com",
    [
        ("/questions/43007/react-useeffect-cleanup", "reactjs - How to clean up an async useEffect? - Stack Overflow"),
        ("/questions/51012/postgres-upsert", "postgresql - Upsert with a unique partial index - Stack Overflow"),
        ("/questions/39210/python-asyncio-timeout", "python - asyncio.wait_for vs timeout context manager - Stack Overflow"),
        ("/questions/1123/css-grid-auto-fill", "css - auto-fill vs auto-fit in CSS grid - Stack Overflow"),
    ],
)
MDN = _pages(
    "developer.mozilla.org",
    [
        ("/en-US/docs/Web/API/Fetch_API", "Fetch API - Web APIs | MDN"),
        ("/en-US/docs/Web/CSS/CSS_grid_layout", "CSS grid layout - CSS | MDN"),
        ("/en-US/docs/Web/JavaScript/Reference/Global_Objects/Intl", "Intl - JavaScript | MDN"),
    ],
)
GDOCS = _pages(
    "docs.google.com",
    [
        ("/document/d/1a/edit", "Checkout v2 - design doc - Google Docs"),
        ("/document/d/1b/edit", "Q4 planning - Google Docs"),
        ("/spreadsheets/d/1c/edit", "Sprint capacity - Google Docs"),
        ("/document/d/1d/edit", "Incident review: payment timeouts - Google Docs"),
    ],
)
LINEAR = _pages(
    "linear.app",
    [
        ("/acme/team/WEB/active", "Active issues › Web › Linear"),
        ("/acme/issue/WEB-412", "WEB-412 Checkout retry banner › Linear"),
        ("/acme/view/my-issues", "My issues › Linear"),
    ],
)
NOTION = _pages(
    "www.notion.so",
    [
        ("/acme/Engineering-handbook", "Engineering handbook | Notion"),
        ("/acme/Weekly-notes", "Weekly notes | Notion"),
    ],
)
GMAIL = _pages(
    "mail.google.com",
    [
        ("/mail/u/0/#inbox", "Inbox (4) - Gmail"),
        ("/mail/u/0/#inbox", "Inbox (1) - Gmail"),
        ("/mail/u/0/#sent", "Sent Mail - Gmail"),
    ],
)
GCAL = _pages("calendar.google.com", [("/calendar/u/0/r/week", "Google Calendar - This week")])
LOCALHOST = [Page("http://localhost:3000/checkout", "Checkout · Storefront (dev)")]
YOUTUBE_WORK = _pages(
    "www.youtube.com",
    [
        ("/watch?v=demo1", "Conference talk: Designing for resilience - YouTube"),
        ("/watch?v=demo2", "Rust in 100 seconds - YouTube"),
    ],
    audible=True,
)
YOUTUBE_HOME = _pages(
    "www.youtube.com",
    [
        ("/watch?v=h1", "Building a mechanical keyboard from scratch - YouTube"),
        ("/watch?v=h2", "Minecraft redstone computer tutorial - YouTube"),
        ("/watch?v=h3", "Big Buck Bunny (Blender open movie) - YouTube"),
        ("/watch?v=h4", "Sourdough for beginners - YouTube"),
        ("/watch?v=h5", "The physics of black holes, explained - YouTube"),
        ("/watch?v=h6", "Lofi beats to code to - YouTube"),
        ("/", "YouTube"),
    ],
    audible=True,
)
REDDIT = _pages(
    "www.reddit.com",
    [
        ("/r/programming/", "r/programming - reddit"),
        ("/r/buildapc/", "r/buildapc - reddit"),
        ("/r/Minecraft/", "r/Minecraft - reddit"),
        ("/r/selfhosted/", "r/selfhosted - reddit"),
        ("/r/AskScience/", "r/AskScience - reddit"),
    ],
)
WIKIPEDIA = _pages(
    "en.wikipedia.org",
    [
        ("/wiki/Pomodoro_Technique", "Pomodoro Technique - Wikipedia"),
        ("/wiki/Black_hole", "Black hole - Wikipedia"),
        ("/wiki/Sourdough", "Sourdough - Wikipedia"),
    ],
)
HN = _pages("news.ycombinator.com", [("/", "Hacker News")])

# macOS laptop: (weight, app, titles-or-pages, median duration in seconds)
FILES_STOREFRONT = ["CheckoutForm.tsx", "useCart.ts", "retry.ts", "Checkout.test.tsx", "api.ts", "README.md"]
FILES_BILLING = ["refunds.py", "models.py", "test_refunds.py", "settings.py", "idempotency.py"]
FILES_DS = ["Button.tsx", "tokens.css", "Modal.tsx", "Button.stories.tsx"]
TERMINAL_TITLES = [
    "storefront — npm run dev",
    "storefront — zsh",
    "billing-api — pytest",
    "billing-api — zsh",
    "~ — ssh staging",
    "design-system — npm test",
]
SLACK_TITLES = [
    "#eng-web - Acme - Slack",
    "#general - Acme - Slack",
    "#design-review - Acme - Slack",
    "#incidents - Acme - Slack",
    "#random - Acme - Slack",
    "Threads - Acme - Slack",
]


class Activity:
    """A weighted kind of thing to do in an app."""

    def __init__(
        self,
        weight: float,
        app: str,
        titles: Optional[Sequence[str]] = None,
        pages: Optional[Sequence[Page]] = None,
        median: float = 180,
        title_suffix: str = "",
    ):
        self.weight = weight
        self.app = app
        self.titles = list(titles or [])
        self.pages = list(pages or [])
        self.median = median
        self.title_suffix = title_suffix


def laptop_focus(project: str) -> List[Activity]:
    files = {"storefront": FILES_STOREFRONT, "billing-api": FILES_BILLING, "design-system": FILES_DS}[project]
    chrome = "Google Chrome"
    return [
        Activity(34, "Code", titles=[f"{f} — {project}" for f in files], median=420),
        Activity(10, "iTerm2", titles=TERMINAL_TITLES, median=150),
        Activity(10, chrome, pages=GITHUB_WORK, median=240),
        Activity(5, chrome, pages=STACKOVERFLOW, median=150),
        Activity(4, chrome, pages=MDN, median=150),
        Activity(3, chrome, pages=LOCALHOST, median=90),
        Activity(9, "Slack", titles=SLACK_TITLES, median=100),
        Activity(3, chrome, pages=LINEAR, median=120),
        Activity(1.5, "Spotify", titles=["Spotify Premium"], median=40),
        Activity(1, "Finder", titles=["Downloads", "storefront"], median=30),
    ]


def laptop_admin() -> List[Activity]:
    chrome = "Google Chrome"
    return [
        Activity(12, chrome, pages=GMAIL, median=200),
        Activity(12, "Slack", titles=SLACK_TITLES, median=150),
        Activity(10, chrome, pages=GDOCS, median=500),
        Activity(5, chrome, pages=NOTION, median=240),
        Activity(5, chrome, pages=LINEAR, median=180),
        Activity(5, chrome, pages=GITHUB_WORK, median=240),
        Activity(5, "Figma", titles=["Checkout redesign – Figma", "Design system – Figma"], median=500),
        Activity(3, chrome, pages=GCAL, median=60),
        Activity(1, "Calendar", titles=["Calendar"], median=40),
        Activity(1, "System Settings", titles=["Displays", "Bluetooth"], median=40),
        Activity(1, chrome, pages=YOUTUBE_WORK, median=300),
    ]


def laptop_lunch() -> List[Activity]:
    chrome = "Google Chrome"
    return [
        Activity(5, chrome, pages=REDDIT, median=200),
        Activity(4, chrome, pages=YOUTUBE_WORK, median=400),
        Activity(3, chrome, pages=HN, median=200),
        Activity(3, "Slack", titles=SLACK_TITLES, median=90),
    ]


def desktop_evening(gaming_bias: float) -> List[Activity]:
    ff = "firefox"
    sfx = " — Mozilla Firefox"
    return [
        Activity(14, ff, pages=YOUTUBE_HOME, median=600, title_suffix=sfx),
        Activity(8, ff, pages=REDDIT, median=300, title_suffix=sfx),
        Activity(4, ff, pages=GITHUB_HOME, median=240, title_suffix=sfx),
        Activity(2, ff, pages=WIKIPEDIA, median=180, title_suffix=sfx),
        Activity(2, ff, pages=HN, median=180, title_suffix=sfx),
        Activity(10 * gaming_bias, "Minecraft* 1.21.4", titles=["Minecraft* 1.21.4 - Singleplayer", "Minecraft* 1.21.4 - Multiplayer (3rd-party Server)"], median=1500),
        Activity(5 * gaming_bias, "RimWorldLinux", titles=["RimWorld by Ludeon Studios"], median=1500),
        Activity(2 * gaming_bias, "steam", titles=["Steam", "Friends List - Steam"], median=120),
        Activity(6, "discord", titles=["#general | Board Game Night - Discord", "#builds | Minecraft Crew - Discord", "Friends - Discord"], median=240),
        Activity(5, "Code", titles=["main.py - weather-station - Visual Studio Code", "dashboard.vue - weather-station - Visual Studio Code", ".zshrc - dotfiles - Visual Studio Code"], median=900),
        Activity(2, "kitty", titles=["~/src/weather-station", "htop", "~/dotfiles"], median=200),
        Activity(3, "Spotify", titles=["Spotify Premium", "Evening Chill - Spotify"], median=60),
        Activity(1.5, "blender", titles=["Blender [~/3d/desk-lamp.blend]"], median=1500),
        Activity(1, "gimp-2.10", titles=["[Untitled]-1.0 (RGB color 8-bit gamma integer) – GIMP", "lamp-render.png – GIMP"], median=600),
        Activity(2, "thunderbird", titles=["Inbox - Mozilla Thunderbird"], median=200),
        Activity(1.5, "vlc", titles=["Big Buck Bunny - VLC media player", "Sintel - VLC media player"], median=2400),
        Activity(1, "org.gnome.Nautilus", titles=["Downloads", "Pictures"], median=40),
    ]


# Android: (weight, app name, package, median seconds)
PHONE_APPS: List[Tuple[float, str, str, float]] = [
    (14, "WhatsApp", "com.whatsapp", 70),
    (6, "Signal", "org.thoughtcrime.securesms", 50),
    (8, "Instagram", "com.instagram.android", 150),
    (7, "Reddit", "com.reddit.frontpage", 200),
    (6, "YouTube", "com.google.android.youtube", 300),
    (6, "Spotify", "com.spotify.music", 40),
    (6, "Gmail", "com.google.android.gm", 50),
    (6, "Chrome", "com.android.chrome", 120),
    (4, "Slack", "com.Slack", 60),
    (3, "Maps", "com.google.android.apps.maps", 90),
    (3, "Duolingo", "com.duolingo", 240),
    (2, "Camera", "com.google.android.GoogleCamera", 30),
    (2, "Telegram", "org.telegram.messenger", 60),
    (1.5, "Clock", "com.google.android.deskclock", 15),
]


class DayPlan:
    """Per-day knobs, deterministic from (seed, date)."""

    def __init__(self, d: date, seed: int):
        self.date = d
        self.rng = random.Random(_seed_for(seed, d.isoformat(), "day"))
        wd = d.weekday()
        self.weekend = wd >= 5
        self.vacation = _is_vacation(d)
        self.holiday = _is_holiday(d)
        self.sick = (not self.weekend) and self.rng.random() < 0.015
        self.workday = not (self.weekend or self.vacation or self.holiday or self.sick)
        # Winter evenings are more for gaming, summer evenings less screen time.
        month_angle = 2 * math.pi * (d.timetuple().tm_yday - 15) / 365.0
        self.winter = 0.5 + 0.5 * math.cos(month_angle)  # 1 in mid-Jan, 0 in mid-July
        self.energy = self.rng.uniform(0.75, 1.2)


def _seed_for(seed: int, *parts: str) -> int:
    h = hashlib.sha256(("|".join([str(seed), *parts])).encode()).hexdigest()
    return int(h[:16], 16)


def _device_uuid(hostname: str) -> str:
    h = hashlib.sha256(f"{SEED}|device|{hostname}".encode()).hexdigest()
    return str(uuid.UUID(h[:32], version=4))


def _is_vacation(d: date) -> bool:
    # Three weeks of summer vacation from the first Monday of July, and the
    # Christmas break.
    july1 = date(d.year, 7, 1)
    start = july1 + timedelta(days=(7 - july1.weekday()) % 7)
    if start <= d < start + timedelta(days=19):
        return True
    if (d.month == 12 and d.day >= 23) or (d.month == 1 and d.day <= 2):
        return True
    return False


def _is_holiday(d: date) -> bool:
    return (d.month, d.day) in {(1, 6), (5, 1), (6, 6)}


def project_for(d: date) -> str:
    # The work project changes every couple of months.
    idx = ((d.year * 12 + d.month) // 2) % 3
    return ["storefront", "billing-api", "design-system"][idx]


def lognormal(rng: random.Random, median: float, sigma: float = 0.8) -> float:
    return median * math.exp(rng.gauss(0, sigma))


def at(d: date, hours: float) -> datetime:
    """Local wall-clock time on day d (hours may exceed 24), as an aware datetime."""
    naive = datetime(d.year, d.month, d.day) + timedelta(hours=hours)
    return naive.astimezone()  # system local timezone, DST-aware


def subtract(intervals: List[Interval], holes: List[Interval]) -> List[Interval]:
    out = []
    for s, e in intervals:
        cur = [(s, e)]
        for hs, he in holes:
            nxt = []
            for cs, ce in cur:
                if he <= cs or hs >= ce:
                    nxt.append((cs, ce))
                    continue
                if hs > cs:
                    nxt.append((cs, hs))
                if he < ce:
                    nxt.append((he, ce))
            cur = nxt
        out.extend(cur)
    return [(s, e) for s, e in out if (e - s).total_seconds() >= 30]


class Device:
    def __init__(self, hostname: str, device_id: str):
        self.hostname = hostname
        self.device_id = device_id
        self.afk: List[dict] = []
        self.window: List[dict] = []
        self.web: List[dict] = []
        self.active: List[Interval] = []  # not-afk periods, for the phone to avoid


def ev(start: datetime, end: datetime, data: dict) -> dict:
    return {
        "timestamp": start.astimezone(timezone.utc).isoformat(),
        "duration": round((end - start).total_seconds(), 3),
        "data": data,
    }


def fill_session(
    dev: Device,
    rng: random.Random,
    start: datetime,
    end: datetime,
    activities: List[Activity],
    browser_bucket: bool = True,
) -> None:
    """Fill a not-afk session with window events (and web events for browsers)."""
    weights = [a.weight for a in activities]
    t = start
    last_app = None
    while t < end:
        act = rng.choices(activities, weights=weights)[0]
        if act.app == last_app and rng.random() < 0.7:
            continue  # avoid lots of same-app repeats
        dur = max(8.0, lognormal(rng, act.median))
        seg_end = min(end, t + timedelta(seconds=dur))
        if act.pages:
            # Spread the time over 1-3 pages (tab switches)
            n = rng.choice([1, 1, 1, 2, 2, 3])
            cuts = sorted(rng.uniform(0, 1) for _ in range(n - 1))
            bounds = [0.0, *cuts, 1.0]
            span = (seg_end - t).total_seconds()
            for i in range(n):
                ps = t + timedelta(seconds=span * bounds[i])
                pe = t + timedelta(seconds=span * bounds[i + 1])
                if (pe - ps).total_seconds() < 3:
                    continue
                page = rng.choice(act.pages)
                dev.window.append(ev(ps, pe, {"app": act.app, "title": page.title + act.title_suffix}))
                if browser_bucket:
                    dev.web.append(
                        ev(
                            ps,
                            pe,
                            {
                                "url": page.url,
                                "title": page.title,
                                "audible": page.audible,
                                "incognito": False,
                                "tabCount": rng.randint(4, 18),
                            },
                        )
                    )
        else:
            dev.window.append(ev(t, seg_end, {"app": act.app, "title": rng.choice(act.titles)}))
        last_app = act.app
        t = seg_end


def afk_events(dev: Device, on: Interval, active: List[Interval]) -> None:
    """Alternating afk/not-afk events covering the 'computer on' interval."""
    s, e = on
    t = s
    for a_s, a_e in sorted(active):
        a_s, a_e = max(a_s, s), min(a_e, e)
        if a_e <= a_s:
            continue
        if a_s > t:
            dev.afk.append(ev(t, a_s, {"status": "afk"}))
        dev.afk.append(ev(a_s, a_e, {"status": "not-afk"}))
        t = a_e
    if t < e:
        dev.afk.append(ev(t, e, {"status": "afk"}))


def random_breaks(rng: random.Random, s: datetime, e: datetime, every_min: float, len_min: Tuple[float, float]) -> List[Interval]:
    out = []
    t = s + timedelta(minutes=rng.uniform(0.5, 1.2) * every_min)
    while t < e:
        dur = timedelta(minutes=rng.uniform(*len_min))
        out.append((t, t + dur))
        t = t + dur + timedelta(minutes=rng.uniform(0.6, 1.4) * every_min)
    return out


def gen_laptop(dev: Device, plan: DayPlan) -> None:
    rng = random.Random(_seed_for(SEED, plan.date.isoformat(), dev.hostname))
    d = plan.date
    sessions: List[Tuple[Interval, str]] = []  # (on-interval, mode)
    if plan.workday:
        start = 8.5 + rng.gauss(0.25, 0.3)
        end = 17.0 + rng.gauss(0.3, 0.45) + (0.5 if rng.random() < 0.15 else 0)
        on = (at(d, start), at(d, end))
        lunch_s = at(d, 11.75 + rng.uniform(0, 0.6))
        lunch = (lunch_s, lunch_s + timedelta(minutes=rng.uniform(35, 55)))
        breaks = [lunch] + random_breaks(rng, on[0], on[1], every_min=80, len_min=(3, 12))
        active = subtract([on], breaks)
        # A short lunch-time browse on some days
        lunch_browse: List[Interval] = []
        if rng.random() < 0.35:
            lb_s = lunch[0] + timedelta(minutes=rng.uniform(15, 25))
            lunch_browse = [(lb_s, lb_s + timedelta(minutes=rng.uniform(6, 14)))]
        # Meetings: daily standup + a few others
        meetings = [(at(d, 9.5), at(d, 9.75))]
        n_meet = rng.choices([0, 1, 2, 3], weights=[3, 4, 2, 0.5])[0]
        if d.weekday() == 0 and rng.random() < 0.5:
            n_meet += 1  # Monday planning
        slots = [10.0, 10.5, 11.0, 13.0, 13.5, 14.0, 14.5, 15.0, 15.5, 16.0]
        for h in sorted(rng.sample(slots, min(n_meet, len(slots)))):
            meetings.append((at(d, h), at(d, h + rng.choice([0.5, 0.5, 0.5, 1.0]))))
        # Focus in the morning, admin-ish in the afternoon (with variation)
        project = project_for(d)
        afternoon_admin = rng.uniform(0.2, 0.6)
        for a_s, a_e in active:
            pieces = [(a_s, a_e, None)]
            for m in meetings + lunch_browse:
                nxt = []
                for ps, pe, kind in pieces:
                    if kind is not None or m[1] <= ps or m[0] >= pe:
                        nxt.append((ps, pe, kind))
                        continue
                    if m[0] > ps:
                        nxt.append((ps, m[0], None))
                    nxt.append((max(ps, m[0]), min(pe, m[1]), "meeting" if m not in lunch_browse else "lunch"))
                    if m[1] < pe:
                        nxt.append((m[1], pe, None))
                pieces = nxt
            for ps, pe, kind in pieces:
                if (pe - ps).total_seconds() < 5:
                    continue
                if kind == "meeting":
                    dev.window.append(ev(ps, pe, {"app": "zoom.us", "title": "Zoom Meeting"}))
                elif kind == "lunch":
                    fill_session(dev, rng, ps, pe, laptop_lunch())
                else:
                    hour = ps.hour + ps.minute / 60
                    admin_share = 0.25 if hour < 12 else afternoon_admin
                    # Alternate focus / admin blocks of ~20-60 min
                    t = ps
                    while t < pe:
                        blk = min(pe, t + timedelta(minutes=rng.uniform(20, 60)))
                        acts = laptop_admin() if rng.random() < admin_share else laptop_focus(project)
                        fill_session(dev, rng, t, blk, acts)
                        t = blk
        sessions.append((on, "work"))
        dev.active.extend(active)
        afk_events(dev, on, active + lunch_browse)
        # Lunch browse happens during the lunch "afk" break but is active
        dev.active.extend(lunch_browse)
        # Occasional evening check-in
        if rng.random() < 0.18:
            es = at(d, 20.5 + rng.uniform(0, 1))
            on2 = (es, es + timedelta(minutes=rng.uniform(10, 30)))
            fill_session(dev, rng, on2[0], on2[1], laptop_admin())
            dev.active.append(on2)
            afk_events(dev, on2, [on2])
    elif plan.weekend and not plan.vacation and rng.random() < 0.1:
        # Rare weekend hour of work
        es = at(d, 14 + rng.uniform(0, 3))
        on = (es, es + timedelta(minutes=rng.uniform(30, 80)))
        fill_session(dev, rng, on[0], on[1], laptop_focus(project_for(d)))
        dev.active.append(on)
        afk_events(dev, on, [on])


def gen_desktop(dev: Device, plan: DayPlan) -> None:
    rng = random.Random(_seed_for(SEED, plan.date.isoformat(), dev.hostname))
    d = plan.date
    free_day = not plan.workday
    on_intervals: List[Interval] = []
    if free_day:
        if rng.random() < (0.55 if plan.vacation else 0.8):
            on_intervals.append((at(d, 10 + rng.uniform(0, 1.5)), at(d, 12.5 + rng.uniform(0, 1))))
        if rng.random() < 0.85:
            on_intervals.append((at(d, 15 + rng.uniform(0, 3)), at(d, 21.5 + rng.uniform(0, 2))))
    else:
        if rng.random() < 0.45 + 0.25 * plan.winter:
            s = 19.0 + rng.uniform(0, 1.5)
            on_intervals.append((at(d, s), at(d, s + rng.uniform(1.0, 3.5) * plan.energy)))
    gaming = 0.25 + 0.7 * plan.winter + (0.4 if plan.weekend else 0)
    for on in on_intervals:
        breaks = random_breaks(rng, on[0], on[1], every_min=55, len_min=(4, 25))
        active = subtract([on], breaks)
        for a_s, a_e in active:
            fill_session(dev, rng, a_s, a_e, desktop_evening(gaming))
        dev.active.extend(active)
        afk_events(dev, on, active)


def gen_phone(dev: Device, plan: DayPlan, busy: List[Interval]) -> None:
    rng = random.Random(_seed_for(SEED, plan.date.isoformat(), dev.hostname))
    d = plan.date
    n = int(rng.uniform(20, 34) * (1.3 if plan.vacation else 1.0))
    # Hours with more phone use: morning, commute, lunch, evening, bedtime
    peaks = [(7.4, 0.4, 2), (8.3, 0.3, 1.5), (12.2, 0.4, 3), (17.6, 0.5, 2.5), (20.5, 1.2, 3), (22.6, 0.4, 2.5)]
    weights = [p[2] for p in peaks]
    starts = []
    for _ in range(n):
        if rng.random() < 0.25:
            h = rng.uniform(7.0, 23.0)
        else:
            mu, sd, _w = rng.choices(peaks, weights=weights)[0]
            h = rng.gauss(mu, sd)
        h = min(max(h, 6.8), 23.7)
        t = at(d, h)
        in_busy = any(s <= t < e for s, e in busy)
        if in_busy and rng.random() > 0.12:
            continue
        starts.append(t)
    starts.sort()
    weights_app = [a[0] for a in PHONE_APPS]
    last_end = None
    for t in starts:
        if last_end and t < last_end + timedelta(seconds=30):
            t = last_end + timedelta(seconds=rng.uniform(30, 120))
        n_apps = rng.choice([1, 1, 2, 2, 3, 4])
        for _ in range(n_apps):
            w, app, package, median = rng.choices(PHONE_APPS, weights=weights_app)[0]
            if plan.vacation and app in ("Slack", "Gmail") and rng.random() < 0.8:
                continue
            dur = max(4.0, lognormal(rng, median, 0.7))
            e = t + timedelta(seconds=dur)
            dev.window.append(ev(t, e, {"app": app, "package": package, "classname": f"{package}.MainActivity"}))
            t = e + timedelta(seconds=rng.uniform(0.5, 3))
        last_end = t


SEED = 42  # overridden by --seed


def generate(days: int, end: datetime) -> Dict[str, Device]:
    devices = {
        LAPTOP: Device(LAPTOP, _device_uuid(LAPTOP)),
        DESKTOP: Device(DESKTOP, _device_uuid(DESKTOP)),
        PHONE: Device(PHONE, _device_uuid(PHONE)),
    }
    today = end.date()
    for i in range(days - 1, -1, -1):
        d = today - timedelta(days=i)
        plan = DayPlan(d, SEED)
        gen_laptop(devices[LAPTOP], plan)
        gen_desktop(devices[DESKTOP], plan)
        day_start, day_end = at(d, 0), at(d, 24)
        busy = [
            (s, e)
            for dev in (devices[LAPTOP], devices[DESKTOP])
            for s, e in dev.active
            if e > day_start and s < day_end
        ]
        gen_phone(devices[PHONE], plan, busy)
    # Nothing in the future: truncate at `end`
    end_utc = end.astimezone(timezone.utc)
    for dev in devices.values():
        for name in ("afk", "window", "web"):
            setattr(dev, name, _truncate(getattr(dev, name), end_utc))
    return devices


def _truncate(events: List[dict], end_utc: datetime) -> List[dict]:
    out = []
    for e in events:
        ts = datetime.fromisoformat(e["timestamp"])
        if ts >= end_utc:
            continue
        stop = ts + timedelta(seconds=e["duration"])
        if stop > end_utc:
            e = dict(e, duration=round((end_utc - ts).total_seconds(), 3))
        out.append(e)
    return out


# =============================================================================
# Server
# =============================================================================


class Server:
    def __init__(self, url: str):
        self.url = url.rstrip("/")

    def request(self, method: str, path: str, body=None, timeout: float = 120):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            self.url + "/api/0" + path,
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else None

    def create_bucket(self, bucket_id: str, type_: str, client: str, hostname: str, data: dict) -> None:
        self.request(
            "POST",
            f"/buckets/{bucket_id}",
            {
                "id": bucket_id,
                "type": type_,
                "client": client,
                "hostname": hostname,
                "created": datetime.now(timezone.utc).isoformat(),
                "data": data,
            },
        )

    def insert(self, bucket_id: str, events: List[dict], chunk: int = 5000) -> None:
        events = sorted(events, key=lambda e: e["timestamp"])
        for i in range(0, len(events), chunk):
            self.request("POST", f"/buckets/{bucket_id}/events", events[i : i + chunk])


def free_port() -> int:
    for _ in range(50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        if port not in FORBIDDEN_PORTS:
            return port
    raise RuntimeError("could not find a free port")


def port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


@contextlib.contextmanager
def run_server(server_bin: Path, webpath: Path, port: int, tmp: Path, verbose: bool) -> Iterator[subprocess.Popen]:
    home = tmp / "home"
    for sub in ("config", "data", "cache", "Library"):
        (home / sub).mkdir(parents=True, exist_ok=True)
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(home / "config"),
        "XDG_DATA_HOME": str(home / "data"),
        "XDG_CACHE_HOME": str(home / "cache"),
        "TMPDIR": str(tmp),
        "RUST_BACKTRACE": "1",
    }
    cmd = [
        str(server_bin),
        "--port",
        str(port),
        "--host",
        "127.0.0.1",
        "--dbpath",
        str(tmp / "screenshots.db"),
        "--webpath",
        str(webpath),
        "--device-id",
        _device_uuid(LAPTOP),
        "--no-legacy-import",
        "--profile",
        "screenshots",
    ]
    log = open(tmp / "aw-server.log", "wb")
    proc = subprocess.Popen(
        cmd,
        env=env,
        cwd=str(tmp),
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True,  # don't receive the terminal's Ctrl-C directly; we kill it ourselves
    )
    try:
        url = f"http://127.0.0.1:{port}"
        deadline = time.time() + 30
        while True:
            if proc.poll() is not None:
                raise RuntimeError(f"aw-server exited early, see {tmp / 'aw-server.log'}:\n{(tmp / 'aw-server.log').read_text()[-2000:]}")
            try:
                urllib.request.urlopen(url + "/api/0/info", timeout=1).read()
                break
            except (urllib.error.URLError, ConnectionError, OSError):
                if time.time() > deadline:
                    raise RuntimeError("aw-server did not come up within 30s")
                time.sleep(0.2)
        if verbose:
            print(f"aw-server running at {url} (pid {proc.pid}, log {tmp / 'aw-server.log'})")
        yield proc
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        log.close()


def seed_server(srv: Server, devices: Dict[str, Device], end: datetime) -> Dict[str, int]:
    info = srv.request("GET", "/info")
    if srv.request("GET", "/buckets/"):
        raise RuntimeError("refusing to seed a server that already has buckets")
    assert info is not None
    counts: Dict[str, int] = {}

    def bucket(bid, type_, client, dev: Device, events, synced: bool):
        data = {"device_id": dev.device_id}
        if synced:
            bid = f"{bid}-synced-from-{dev.hostname}"
            data["$aw.sync.origin"] = dev.hostname
        srv.create_bucket(bid, type_, client, dev.hostname, data)
        srv.insert(bid, events)
        counts[bid] = len(events)

    # The laptop is the device this server "runs on"; the others arrive via aw-sync.
    for host, browser, synced in ((LAPTOP, "chrome", False), (DESKTOP, "firefox", True)):
        dev = devices[host]
        bucket(f"aw-watcher-window_{host}", "currentwindow", "aw-watcher-window", dev, dev.window, synced)
        bucket(f"aw-watcher-afk_{host}", "afkstatus", "aw-watcher-afk", dev, dev.afk, synced)
        bucket(f"aw-watcher-web-{browser}_{host}", "web.tab.current", "aw-client-web", dev, dev.web, synced)
    phone = devices[PHONE]
    bucket("aw-watcher-android", "currentwindow", "aw-android", phone, phone.window, True)

    # A few stopwatch entries, so the Stopwatch view isn't empty
    laptop = devices[LAPTOP]
    sw = []
    rng = random.Random(_seed_for(SEED, "stopwatch"))
    labels = ["Code review", "Release notes", "Interview prep", "Deep work: checkout flow", "Expense report"]
    day = end.date()
    n = 0
    while n < 6:
        day -= timedelta(days=1)
        if day.weekday() >= 5 or _is_vacation(day):
            continue
        s = at(day, rng.choice([9.0, 10.0, 13.5, 14.0, 15.0]) + rng.uniform(0, 0.4))
        sw.append(ev(s, s + timedelta(minutes=rng.uniform(25, 95)), {"label": labels[n % len(labels)], "running": False}))
        n += 1
    running_start = end - timedelta(minutes=37)
    sw.append(ev(running_start, running_start, {"label": "Product launch checklist", "running": True}))
    srv.create_bucket("aw-stopwatch", "general.stopwatch", "aw-webui", LAPTOP, {"device_id": laptop.device_id})
    srv.insert("aw-stopwatch", sw)
    counts["aw-stopwatch"] = len(sw)
    return counts


def configure_settings(srv: Server, theme: str, end: datetime) -> None:
    far = (end + timedelta(days=3650)).astimezone(timezone.utc).isoformat()
    settings = {
        # Pretend the user has been around for a while: no first-run notices
        "initialTimestamp": (end - timedelta(days=500)).astimezone(timezone.utc).isoformat(),
        "startOfDay": "04:00",
        "startOfWeek": "Monday",
        "landingpage": "/home",
        "theme": theme,
        "locale": "en",
        "devmode": False,
        "hideUnsupportedVisualizations": True,
        "newReleaseCheckData": {
            "isEnabled": False,
            "nextCheckTime": far,
            "howOftenToCheck": 5 * 24 * 60 * 60,
            "timesChecked": 0,
        },
        "userSatisfactionPollData": {"isEnabled": False, "nextPollTime": far, "timesPollIsShown": 3},
        "uncategorizedNotificationData": {"isEnabled": False, "minTotalSeconds": 3600, "minRatio": 0.3},
        "classes": themed_categories(theme),
        "category_sets": [{"id": "default", "categories": themed_categories(theme)}],
        "active_set_ids": ["default"],
    }
    for key, value in settings.items():
        srv.request("POST", f"/settings/{key}", value)


# =============================================================================
# Capture
# =============================================================================

# localStorage set before the app loads (per-browser nudges that aren't server settings)
LOCAL_STORAGE = {
    "aw-supporter": "true",  # honor-system "I already support" flag: hides the supporter nudge
    "aw.timeline.editRefreshHintDismissed": "1",
    "landingpage": "/home",
}

WAIT_FOR_LOADED_JS = r"""
() => {
  const loadingRe = /Loading[.]{3}|Loading…|Computing trends/;
  const nodes = document.querySelectorAll('.aw-loading, text, .spinner-border, .b-skeleton');
  for (const n of nodes) {
    if (n.classList && (n.classList.contains('spinner-border') || n.classList.contains('b-skeleton'))) {
      if (n.offsetParent !== null) return false;
      continue;
    }
    if (loadingRe.test(n.textContent || '')) return false;
  }
  if (loadingRe.test(document.body.innerText || '')) return false;
  return !!document.querySelector('#wrapper');
}
"""

ERROR_JS = r"""
() => {
  const out = [];
  for (const el of document.querySelectorAll('div.alert')) {
    const t = (el.innerText || '').trim();
    if (/error|failed|exception/i.test(t)) out.push(t.slice(0, 300));
  }
  return out;
}
"""


class Shot:
    def __init__(self, name: str, path: str, setup: Optional[Callable] = None, full_page: bool = False):
        self.name = name
        self.path = path
        self.setup = setup
        self.full_page = full_page


def timeline_full_day(day: date) -> Callable:
    def setup(page):
        page.locator("#time-mode label", has_text="Date range").click()
        page.locator("input[aria-label='Start date']").fill(day.isoformat())
        page.locator("input[aria-label='End date (optional)']").fill(day.isoformat())
        page.get_by_role("button", name="Apply").click()
        page.wait_for_timeout(500)

    return setup


def work_report(page) -> None:
    page.get_by_role("button", name="Calculate Work Time").click()
    page.wait_for_timeout(500)


def search(pattern: str) -> Callable:
    def setup(page):
        page.get_by_placeholder("Regex pattern to search for").fill(pattern)
        page.get_by_role("button", name="Search").click()
        page.wait_for_timeout(500)

    return setup


EXAMPLE_QUERY = f"""
afk = query_bucket("aw-watcher-afk_{LAPTOP}");
events = query_bucket("aw-watcher-window_{LAPTOP}");
events = filter_period_intersect(events, filter_keyvals(afk, "status", ["not-afk"]));
events = categorize(events, __CATEGORIES__);
events = merge_events_by_keys(events, ["app", "title"]);
RETURN = sort_by_duration(events);
""".strip()


def query_explorer(day: date) -> Callable:
    def setup(page):
        dates = page.locator("input[type=date]")
        dates.nth(0).fill(day.isoformat())
        dates.nth(1).fill((day + timedelta(days=1)).isoformat())
        page.get_by_role("button", name="Query", exact=True).click()
        page.wait_for_timeout(500)
        # Show the query and (the top of) its results rather than the page header
        page.locator("textarea").evaluate("el => window.scrollTo(0, el.getBoundingClientRect().top + window.scrollY - 80)")

    return setup


def trends_30d(page) -> None:
    page.get_by_role("button", name="30 days").click()
    page.wait_for_timeout(500)


def build_shots(day: date, today: date) -> List[Shot]:
    # Week/month/year views take the *start* of the period in the URL (the UI
    # does not round a mid-period date down). Prefer complete periods.
    week = day - timedelta(days=day.weekday())
    if week + timedelta(days=7) > today:
        week -= timedelta(days=7)
    month = day.replace(day=1)
    if day.day < 20:
        month = (month - timedelta(days=1)).replace(day=1)
    year = date(day.year if day.month >= 4 else day.year - 1, 1, 1)
    d, w, m, y = day.isoformat(), week.isoformat(), month.isoformat(), year.isoformat()
    q = urllib.parse.quote(EXAMPLE_QUERY)
    return [
        Shot("activity-day", f"/#/activity/@all/day/{d}/view/summary"),
        Shot("activity-day-full", f"/#/activity/@all/day/{d}/view/summary", full_page=True),
        Shot("activity-week", f"/#/activity/@all/week/{w}/view/summary"),
        Shot("activity-month", f"/#/activity/@all/month/{m}/view/summary"),
        Shot("activity-year", f"/#/activity/@all/year/{y}/view/summary"),
        Shot("activity-browser", f"/#/activity/{LAPTOP}/day/{d}/view/browser"),
        Shot("timeline", "/#/timeline", setup=timeline_full_day(day)),
        Shot("search", "/#/search", setup=search("Pull Request")),
        Shot("query", f"/#/query?q={q}", setup=query_explorer(day)),
        Shot("stopwatch", "/#/stopwatch"),
        Shot("settings", "/#/settings/general"),
        Shot("categorization", "/#/settings/categorization"),
        Shot("buckets", "/#/buckets"),
        # Not included: Home (it is mostly a "Support us" page, not a product shot)
    ]


# Views with known web UI bugs (see PR); only captured when asked for with --only.
def extra_shots() -> List[Shot]:
    return [
        Shot("trends", f"/#/trends/{LAPTOP}", setup=trends_30d),
        Shot("work-report", "/#/work-report", setup=work_report),
    ]


def wait_until_loaded(page, timeout_s: float = 60) -> None:
    try:
        page.wait_for_load_state("networkidle", timeout=timeout_s * 1000)
    except Exception:
        pass
    page.wait_for_function(WAIT_FOR_LOADED_JS, timeout=timeout_s * 1000, polling=250)
    try:
        page.wait_for_load_state("networkidle", timeout=timeout_s * 1000)
    except Exception:
        pass
    # Charts animate in; give them a moment and re-check
    page.wait_for_timeout(1200)
    page.wait_for_function(WAIT_FOR_LOADED_JS, timeout=timeout_s * 1000, polling=250)


def capture(
    url: str,
    shots: List[Shot],
    themes: List[str],
    out_dir: Path,
    size: Tuple[int, int],
    scale: float,
    srv: Server,
    end: datetime,
) -> List[Path]:
    from playwright.sync_api import sync_playwright

    written: List[Path] = []
    real_info = srv.request("GET", "/info")
    fake_info = dict(real_info, hostname=LAPTOP)  # don't show this machine's hostname

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for theme in themes:
                configure_settings(srv, theme, end)
                ctx = browser.new_context(
                    viewport={"width": size[0], "height": size[1]},
                    device_scale_factor=scale,
                    color_scheme="dark" if theme == "dark" else "light",
                    locale="en-US",
                    timezone_id=_local_tz_name(),
                )
                ls = dict(LOCAL_STORAGE, theme=theme)
                ctx.add_init_script(
                    "(() => { const kv = %s; for (const k in kv) localStorage.setItem(k, kv[k]); })();" % json.dumps(ls)
                )

                def handle(route, request):
                    if not request.url.startswith(url):
                        return route.abort()  # no external requests (release checks, fonts, ...)
                    if request.url.split("?")[0].rstrip("/").endswith("/api/0/info"):
                        return route.fulfill(status=200, content_type="application/json", body=json.dumps(fake_info))
                    return route.continue_()

                ctx.route("**/*", handle)
                page = ctx.new_page()
                console_errors: List[str] = []
                page.on("pageerror", lambda exc: console_errors.append(str(exc)))
                theme_dir = out_dir / theme
                theme_dir.mkdir(parents=True, exist_ok=True)
                for i, shot in enumerate(shots, start=1):
                    t0 = time.time()
                    page.goto(url + shot.path)
                    page.reload()  # fresh app state per view (route changes keep stores around)
                    wait_until_loaded(page)
                    if shot.setup:
                        shot.setup(page)
                        wait_until_loaded(page)
                    errors = page.evaluate(ERROR_JS)
                    if errors:
                        raise RuntimeError(f"error shown in view {shot.name!r}: {errors}")
                    # Drop focus rings / hover states and park the mouse
                    page.evaluate("() => document.activeElement && document.activeElement.blur()")
                    page.mouse.move(size[0] - 2, size[1] - 2)
                    path = theme_dir / f"{i:02d}-{shot.name}.png"
                    page.screenshot(path=str(path), full_page=shot.full_page)
                    written.append(path)
                    print(f"  [{theme}] {path.relative_to(out_dir)}  ({time.time() - t0:.1f}s)")
                if console_errors:
                    print(f"  warning: page errors in {theme} run: {console_errors[:5]}", file=sys.stderr)
                ctx.close()
        finally:
            browser.close()
    return written


def _local_tz_name() -> Optional[str]:
    tz = os.environ.get("TZ")
    if tz:
        return tz
    with contextlib.suppress(OSError):
        link = os.readlink("/etc/localtime")
        if "zoneinfo/" in link:
            return link.split("zoneinfo/", 1)[1]
    with contextlib.suppress(OSError):
        return Path("/etc/timezone").read_text().strip() or None
    return None


def ensure_chromium() -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        exe = Path(p.chromium.executable_path)
    if not exe.exists():
        print("Installing Playwright Chromium...")
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)


# =============================================================================
# Build
# =============================================================================


def build(server_bin: Path, webpath: Path) -> None:
    if webpath == DEFAULT_WEBPATH:
        if not (WEBUI_DIR / "package.json").exists():
            raise SystemExit("aw-webui submodule missing: git submodule update --init --recursive aw-server-rust")
        print("Building aw-webui...")
        if not (WEBUI_DIR / "node_modules").exists():
            subprocess.run(["npm", "ci"], cwd=WEBUI_DIR, check=True)
        subprocess.run(["make", "build"], cwd=WEBUI_DIR, check=True)
    if server_bin == DEFAULT_SERVER_BIN:
        print("Building aw-server-rust...")
        env = dict(os.environ, AW_WEBUI_DIR=str(webpath))
        subprocess.run(["cargo", "build", "--release", "--bin", "aw-server"], cwd=SERVER_DIR, env=env, check=True)


# =============================================================================
# Main
# =============================================================================


def parse_size(s: str) -> Tuple[int, int]:
    try:
        w, h = s.lower().split("x")
        return int(w), int(h)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid size {s!r}, expected WxH (e.g. 1270x760)")


def pick_day(devices: Dict[str, Device], today: date) -> date:
    """The most recent full workday (within two weeks) where all three devices
    were used, with an evening on the home desktop."""
    fallback = None
    for i in range(1, 15):
        d = today - timedelta(days=i)
        if d.weekday() >= 5 or _is_vacation(d) or _is_holiday(d):
            continue
        fallback = fallback or d
        evening = at(d, 18)
        desktop = sum((e - s).total_seconds() for s, e in devices[DESKTOP].active if s >= evening and s < at(d, 28))
        if desktop >= 1.5 * 3600:
            return d
    return fallback or today - timedelta(days=1)


def main() -> int:
    global SEED
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--build", action="store_true", help="build aw-webui and aw-server-rust before running")
    parser.add_argument("--server-bin", type=Path, default=DEFAULT_SERVER_BIN, help="aw-server (rust) binary")
    parser.add_argument("--webpath", type=Path, default=DEFAULT_WEBPATH, help="built aw-webui directory")
    parser.add_argument("--port", type=int, default=None, help="port for the throwaway server (default: a free one)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output directory")
    parser.add_argument("--theme", choices=["light", "dark", "both"], default="both")
    parser.add_argument("--size", type=parse_size, default=(1270, 760), help="viewport WxH (default 1270x760)")
    parser.add_argument("--scale", type=float, default=2, help="device scale factor (default 2)")
    parser.add_argument("--days", type=int, default=365, help="days of demo data, ending now")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--date", type=date.fromisoformat, default=None, help="day to show (default: last full workday)")
    parser.add_argument("--only", action="append", default=[], help="only views whose name contains this (repeatable or comma-separated; also enables trends, work-report)")
    parser.add_argument("--full-page", action="store_true", help="capture every view as a full-page (tall) screenshot")
    parser.add_argument("--keep-running", action="store_true", help="leave the seeded server up after capturing")
    parser.add_argument("--no-capture", action="store_true", help="only start and seed the server (implies --keep-running)")
    args = parser.parse_args()
    SEED = args.seed
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]

    if args.port is not None and args.port in FORBIDDEN_PORTS:
        parser.error(f"port {args.port} is reserved for a real ActivityWatch instance")
    if args.build:
        build(args.server_bin, args.webpath)
    if not args.server_bin.exists():
        parser.error(f"server binary not found: {args.server_bin} (run with --build)")
    if not (args.webpath / "index.html").exists():
        parser.error(f"web UI not built: {args.webpath} (run with --build)")
    port = args.port or free_port()
    if port_in_use(port):
        parser.error(f"port {port} is already in use")

    t_start = time.time()
    end = datetime.now().astimezone().replace(microsecond=0)
    print(f"Generating {args.days} days of demo data (seed {SEED})...")
    devices = generate(args.days, end)

    tmp = Path(tempfile.mkdtemp(prefix="aw-screenshots-"))
    # Turn SIGTERM/SIGHUP into an exception so the server gets cleaned up
    def _raise(signum, frame):
        raise KeyboardInterrupt
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, _raise)

    try:
        with run_server(args.server_bin, args.webpath, port, tmp, verbose=True):
            url = f"http://127.0.0.1:{port}"
            srv = Server(url)
            t0 = time.time()
            counts = seed_server(srv, devices, end)
            print(f"Inserted {sum(counts.values())} events into {len(counts)} buckets in {time.time() - t0:.1f}s")
            themes = ["light", "dark"] if args.theme == "both" else [args.theme]
            configure_settings(srv, themes[0], end)

            if not args.no_capture:
                ensure_chromium()
                day = args.date or pick_day(devices, end.date())
                shots = build_shots(day, end.date())
                if args.only:
                    only = [o for arg in args.only for o in arg.split(",") if o]
                    shots = [s for s in shots + extra_shots() if any(o in s.name for o in only)]
                if args.full_page:
                    for s in shots:
                        s.full_page = True
                print(f"Capturing {len(shots)} views x {len(themes)} theme(s) at {args.size[0]}x{args.size[1]}@{args.scale}x (day {day})...")
                written = capture(url, shots, themes, args.out, args.size, args.scale, srv, end)
                print(f"Wrote {len(written)} screenshots to {args.out} in {time.time() - t_start:.0f}s")

            if args.keep_running or args.no_capture:
                print(f"\nServer is running at {url}  (data in {tmp})\nPress Ctrl-C to stop.")
                while True:
                    time.sleep(3600)
    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
