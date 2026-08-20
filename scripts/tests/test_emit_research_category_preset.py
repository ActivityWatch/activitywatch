import importlib.util
import json
import re
from pathlib import Path


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
    expected = {c for _, c in patcher.CATEGORY_MAP} | set(patcher.APP_CATEGORY_MAP.values())

    names = {c["name"][0] for c in emitter.build_preset()["categories"]}

    assert names == expected


def test_rules_match_their_own_category_and_nothing_else():
    """By the time aw-webui sees the event, `app` IS the category name."""
    for category in emitter.build_preset()["categories"]:
        name = category["name"][0]
        pattern = category["rule"]["regex"]

        assert re.search(pattern, name), f"{pattern!r} does not match {name!r}"
        assert not re.search(pattern, "Some Unrelated App")
        assert not re.search(pattern, f"{name} extra")


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


def test_output_is_stable_across_runs():
    """CI reruns must not produce a different preset from the same map."""
    assert emitter.build_preset() == emitter.build_preset()


def test_serialises_without_newlines_for_github_env():
    """The value is written straight into $GITHUB_ENV, which ends at a newline."""
    payload = json.dumps([emitter.build_preset()], separators=(",", ":"))

    assert "\n" not in payload
    assert json.loads(payload)[0]["id"] == "research-study"
