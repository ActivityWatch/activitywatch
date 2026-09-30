import importlib.util
import json
import re
from pathlib import Path

import pytest


def _load(name: str):
    path = Path(__file__).parents[1] / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


emitter = _load("emit_research_category_preset")
patcher = _load("patch_research_edition_config")


def test_preset_covers_every_category_in_the_watcher_map():
    """Preset and watcher map must share one source, or the UI drifts from the data."""
    expected = {c for _, c in patcher.CATEGORY_MAP} | set(
        patcher.APP_CATEGORY_MAP.values()
    )

    names = {c["name"][0] for c in emitter.build_preset()["categories"]}

    assert names == expected


def _classify_event(data: dict[str, str]) -> str | None:
    """Mirror aw-webui's parsed-rule contract and equal-depth matching."""
    matches: list[str] = []
    for category in emitter.build_preset()["categories"]:
        rule = category["rule"]
        flags = re.IGNORECASE if rule["ignore_case"] else 0
        if any(
            key in data and re.search(rule["regex"], data[key], flags)
            for key in ("app", "title")
        ):
            matches.append(category["name"][0])
    assert len(matches) <= 1, (
        f"aw-webui cannot prioritize equal-depth matches: {matches}"
    )
    return matches[0] if matches else None


def test_rules_match_browser_categories_and_raw_app_aliases():
    """Browser titles and retained app names resolve to the same taxonomy."""
    assert _classify_event({"app": "Safari", "title": "Work & Productivity"}) == (
        "Work & Productivity"
    )
    assert _classify_event({"app": "Microsoft Word"}) == "Work & Productivity"
    assert _classify_event({"app": "SPOTIFY"}) == "Music & Audio"
    assert _classify_event({"app": "Terminal"}) == "Excluded"
    assert _classify_event({"app": "Some Unmapped Program"}) is None


def test_rules_are_exact_and_scoped_to_approved_fields():
    categories = {
        category["name"][0]: category
        for category in emitter.build_preset()["categories"]
    }
    work_rule = categories["Work & Productivity"]["rule"]

    assert re.search(work_rule["regex"], "Microsoft Word", re.IGNORECASE)
    assert not re.search(work_rule["regex"], "Microsoft Word extra", re.IGNORECASE)
    assert _classify_event({"hostname": "Microsoft Word"}) is None


def test_rules_use_only_fields_preserved_by_the_aw_webui_preset_parser():
    """The oldest pinned carrier strips unknown keys; behavior must survive that."""
    for category in emitter.build_preset()["categories"]:
        assert set(category["rule"]) <= {"type", "regex", "ignore_case"}


def test_excluded_rule_only_matches_explicitly_excluded_apps():
    categories = {
        category["name"][0]: category
        for category in emitter.build_preset()["categories"]
    }

    excluded = categories["Excluded"]["rule"]["regex"]
    assert re.search(excluded, "Terminal", re.IGNORECASE)
    assert not re.search(excluded, "Outlook", re.IGNORECASE)
    assert not re.search(excluded, "Some Unmapped Program", re.IGNORECASE)


def test_every_known_value_matches_exactly_one_rule_after_parser_projection():
    """Catch overlaps the production classifier cannot resolve at equal depth."""
    values = {category["name"][0] for category in emitter.build_preset()["categories"]}
    values |= set(patcher.APP_CATEGORY_MAP)

    for value in values:
        assert _classify_event({"app": value}) is not None


def test_escaping_is_portable_to_javascript_unicode_mode():
    """`re.escape` is unusable here: it emits `\\ ` and `\\&`.

    Those are valid in Python but are *invalid identity escapes* in JavaScript
    unicode-mode regex, so `new RegExp(r, "u")` throws on 14 of the 18 study
    categories. aw-webui compiles without the `u` flag today, which is the only
    reason `re.escape` would appear to work -- and the failure would present as
    "categories don't show", indistinguishable from the bug this preset fixes.
    """
    for category in emitter.build_preset()["categories"]:
        pattern = category["rule"]["regex"]
        escaped = {pattern[i + 1] for i, ch in enumerate(pattern[:-1]) if ch == "\\"}

        assert escaped <= emitter._REGEX_METACHARACTERS, (
            f"{pattern!r} escapes characters JavaScript rejects under the u flag"
        )


def test_escape_portable_still_escapes_real_metacharacters():
    """A future category name containing a metacharacter must not become a wildcard."""
    assert emitter.escape_portable("a.b") == r"a\.b"
    assert emitter.escape_portable("x(y)") == r"x\(y\)"
    assert emitter.escape_portable("Shopping - Goods") == "Shopping - Goods"
    assert re.fullmatch(emitter.escape_portable("a.b"), "a.b")
    assert not re.fullmatch(emitter.escape_portable("a.b"), "axb")


def test_exact_alternation_is_stable_and_whole_value():
    pattern = emitter.exact_alternation({"zoom.us", "Zoom"})

    assert pattern == r"^(?:Zoom|zoom\.us)$"
    assert re.fullmatch(pattern, "Zoom")
    assert re.fullmatch(pattern, "zoom.us")
    assert not re.fullmatch(pattern, "zoom.us meeting")


def test_output_is_stable_across_runs():
    """CI reruns must not produce a different preset from the same map."""
    assert emitter.build_preset() == emitter.build_preset()


def test_serialises_without_newlines_for_github_env():
    """The value is written straight into $GITHUB_ENV, which ends at a newline."""
    payload = json.dumps([emitter.build_preset()], separators=(",", ":"))

    assert "\n" not in payload
    assert json.loads(payload)[0]["id"] == "research-study"


def test_every_category_has_a_distinct_hex_color():
    """Activity view has no name-hash fallback; missing data.color renders grey."""
    categories = emitter.build_preset()["categories"]
    colors = [category["data"]["color"] for category in categories]

    assert len(colors) == len(categories)
    assert len(set(colors)) == len(colors)
    for color in colors:
        assert re.fullmatch(r"#[0-9A-F]{6}", color)


def test_color_table_matches_the_study_taxonomy():
    """A new map entry without a color must fail the build, not ship unstyled."""
    names = {category["name"][0] for category in emitter.build_preset()["categories"]}

    assert set(emitter.CATEGORY_COLORS) == names


# --- Optional geography-free preset -----------------------------------------
#
# The build ships a second, study-neutral preset. aw-webui activates only the
# first preset on a fresh install and offers the rest for manual activation
# (see aw-webui `loadCategories`), so emitting the default *after* the study
# preset is what makes it optional rather than a replacement.

EXPECTED_DEFAULT_CATEGORIES = {
    "Email",
    "Games",
    "Messaging",
    "Music & Audio",
    "News & Current Affairs",
    "Search & Navigation",
    "Shopping - Goods",
    "Shopping - Groceries & Food",
    "Social Networking",
    "Video Streaming",
    "Work & Productivity",
}


def _classify_event_in(preset, data: dict[str, str]) -> str | None:
    matches: list[str] = []
    for category in preset["categories"]:
        rule = category["rule"]
        flags = re.IGNORECASE if rule["ignore_case"] else 0
        if any(
            key in data and re.search(rule["regex"], data[key], flags)
            for key in ("app", "title")
        ):
            matches.append(category["name"][0])
    assert len(matches) <= 1, f"ambiguous match within one preset: {matches}"
    return matches[0] if matches else None


def test_build_presets_ships_study_first_then_optional_default():
    """Order is load-bearing: aw-webui's first preset is the install default."""
    presets = emitter.build_presets()

    assert [p["id"] for p in presets] == ["research-study", "research-default"]
    assert presets[0] == emitter.build_preset()
    assert presets[1] == emitter.build_default_preset()


def test_default_preset_categories_match_the_published_toml():
    """The TOML is the source of truth; a drift here is a silent taxonomy fork."""
    names = {c["name"][0] for c in emitter.build_default_preset()["categories"]}

    assert names == EXPECTED_DEFAULT_CATEGORIES


def test_stdlib_toml_reader_agrees_with_tomllib():
    """The 3.9-compatible reader must not diverge from a real TOML parser."""
    tomllib = pytest.importorskip("tomllib")

    with emitter.DEFAULT_MAP_TOML.open("rb") as fh:
        parsed = tomllib.load(fh)

    values = parsed["aw-watcher-window"]["research_category_map"].values()
    assert emitter._load_default_categories() == set(values)
    assert set(values) == EXPECTED_DEFAULT_CATEGORIES


def test_default_preset_reuses_the_shared_color_palette():
    """Every default category must be colored by the same palette as the study set."""
    names = {c["name"][0] for c in emitter.build_default_preset()["categories"]}

    assert names <= set(emitter.CATEGORY_COLORS)
    for category in emitter.build_default_preset()["categories"]:
        assert re.fullmatch(r"#[0-9A-F]{6}", category["data"]["color"])


def test_default_preset_keeps_app_names_and_has_no_app_aliases():
    """The default keeps app names, so its rules match only stored category labels."""
    preset = emitter.build_default_preset()
    categories = {c["name"][0]: c for c in preset["categories"]}

    work = categories["Work & Productivity"]["rule"]["regex"]
    assert re.fullmatch(work, "Work & Productivity", re.IGNORECASE)
    # No app aliases: a raw application name must not match the default preset.
    assert _classify_event_in(preset, {"app": "Microsoft Word"}) is None
    assert _classify_event_in(preset, {"app": "SPOTIFY"}) is None


def test_default_preset_labels_are_mutually_exclusive():
    """Equal-depth web-UI rules cannot be prioritized, so labels must not overlap."""
    preset = emitter.build_default_preset()
    for name in EXPECTED_DEFAULT_CATEGORIES:
        assert _classify_event_in(preset, {"title": name}) == name


def test_default_preset_avoids_the_bare_yahoo_collision():
    """The one Ghent/Lund collision: bare yahoo.com must not appear as a rule."""
    for category in emitter.build_default_preset()["categories"]:
        assert "yahoo\\.com" not in category["rule"]["regex"]


def test_full_payload_is_newline_free_for_github_env():
    """Both presets are serialized into a single $GITHUB_ENV value."""
    payload = json.dumps(emitter.build_presets(), separators=(",", ":"))

    assert "\n" not in payload
    assert json.loads(payload)[0]["id"] == "research-study"
    assert json.loads(payload)[1]["id"] == "research-default"
