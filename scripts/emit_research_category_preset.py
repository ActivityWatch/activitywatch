#!/usr/bin/env python3
"""Emit the Research Edition category preset consumed by aw-webui at build time.

The approved study contract keeps application names while the watcher replaces
browser titles with study categories and removes every URL. aw-webui categorises
client-side, so this preset matches both stored browser category labels and the
known raw application-name aliases. Top Applications can therefore show Word,
Spotify, and Teams while Top Categories still uses the study taxonomy.

aw-webui (ActivityWatch/aw-webui#936) reads a preset category set from the
`AW_PRESET_CATEGORY_SETS` env var at build time. This script derives that
preset from the same taxonomy source as the watcher build patch, so the two can
never drift:

    python3 scripts/emit_research_category_preset.py > preset.json

Rules are exact, case-insensitive matches. aw-webui applies every category rule
to `app` and `title`, and the oldest web UI pinned by the release carriers drops
unknown per-rule metadata, so the preset cannot rely on field or priority keys.
Each category carries a `data.color` so the Activity view is not unstyled
(ActivityWatch/activitywatch#1439). Explicitly excluded app aliases map to
`Excluded`; unknown applications remain `Uncategorized` instead of overlapping
every specific rule with a catch-all.
"""

import importlib.util
import json
import pathlib
import sys

# Characters that are special to BOTH Python's `re` and JavaScript's RegExp
# outside a character class. Escaping is deliberately restricted to these.
#
# `re.escape()` is not usable here: it escapes space as `\ ` and `&` as `\&`,
# which are *invalid identity escapes* in JavaScript unicode-mode regex. Names
# like "AI Chatbots & Assistants" then throw `Invalid escape` under `new
# RegExp(r, "u")` -- 14 of the 18 study categories do. They happen to compile
# today only because aw-webui builds the regex without the `u` flag, and the
# failure would present as "categories don't show", i.e. indistinguishable from
# the bug this preset exists to fix. Escape only what both engines agree on.
_REGEX_METACHARACTERS = set(r"\^$.|?*+()[]{}")

PRESET_ID = "research-study"
PRESET_NAME = "Research Edition study categories"

# Qualitative palette for the study taxonomy. aw-webui only colors a category
# when `data.color` is set — there is no name-hash fallback for categories —
# so omitting this is what made the research-study set render grey.
# Keys must stay in lockstep with CATEGORY_MAP ∪ APP_CATEGORY_MAP; build_preset
# raises if a category is missing.
CATEGORY_COLORS: dict[str, str] = {
    "AI Chatbots & Assistants": "#7B1FA2",
    "Banking & Finance": "#1B5E20",
    "Education & Learning": "#1565C0",
    "Email": "#00838F",
    "Excluded": "#BDBDBD",
    "Games": "#EF6C00",
    "Messaging": "#00897B",
    "Music & Audio": "#7CB342",
    "News & Current Affairs": "#C62828",
    "Public Services": "#455A64",
    "Search & Navigation": "#5C6BC0",
    "Sensitive / Excluded": "#757575",
    "Shopping - Goods": "#6D4C41",
    "Shopping - Groceries & Food": "#F9A825",
    "Social Networking": "#AD1457",
    "Travel & Mobility": "#0277BD",
    "Video Streaming": "#E53935",
    "Work & Productivity": "#2E7D32",
}

_PATCHER = pathlib.Path(__file__).with_name("patch_research_edition_config.py")


def _load_category_source():
    """Import the patch script without executing its CLI entry point."""
    spec = importlib.util.spec_from_file_location("_re_patcher", _PATCHER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {_PATCHER}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["_re_patcher"] = module
    spec.loader.exec_module(module)
    return module


def escape_portable(value: str) -> str:
    """Escape `value` so the result is a literal in both Python and JS regex.

    Portable across engines *and* across JS flag modes, unlike `re.escape()`.
    """
    return "".join(
        "\\" + char if char in _REGEX_METACHARACTERS else char for char in value
    )


def exact_alternation(values: set[str]) -> str:
    """Build a stable whole-value alternation portable across Python and JS."""
    escaped = [escape_portable(value) for value in sorted(values)]
    return f"^(?:{'|'.join(escaped)})$"


def color_for(category: str) -> str:
    """Look up the Activity-view color for a study category.

    Missing keys fail the build rather than ship an unstyled taxonomy.
    """
    try:
        return CATEGORY_COLORS[category]
    except KeyError as exc:
        raise RuntimeError(
            f"study category {category!r} has no color in CATEGORY_COLORS"
        ) from exc


def build_preset() -> dict:
    source = _load_category_source()

    categories = {category for _, category in source.CATEGORY_MAP}
    categories |= set(source.APP_CATEGORY_MAP.values())
    if not categories:
        raise RuntimeError("no categories found -- refusing to emit an empty preset")

    extra_colors = set(CATEGORY_COLORS) - categories
    if extra_colors:
        raise RuntimeError(
            "CATEGORY_COLORS has entries not in the study taxonomy: "
            + ", ".join(sorted(extra_colors))
        )

    return {
        "id": PRESET_ID,
        "name": PRESET_NAME,
        # Sorted so the same taxonomy always produces a byte-identical preset.
        "categories": [
            {
                "name": [category],
                "rule": {
                    "type": "regex",
                    "regex": exact_alternation(
                        {category}
                        | {
                            app
                            for app, app_category in source.APP_CATEGORY_MAP.items()
                            if app_category == category
                        }
                    ),
                    "ignore_case": True,
                },
                "data": {"color": color_for(category)},
            }
            for category in sorted(categories)
        ],
    }


def main() -> None:
    preset = build_preset()
    # Compact and newline-free: this is written straight into $GITHUB_ENV,
    # which treats a newline as the end of the value.
    print(json.dumps([preset], separators=(",", ":")))


if __name__ == "__main__":
    main()
