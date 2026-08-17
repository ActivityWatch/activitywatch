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


def test_regex_metacharacters_in_category_names_are_escaped():
    """Names carry '&', '/' and '-'; an unescaped name would be a broken rule."""
    by_name = {c["name"][0]: c for c in emitter.build_preset()["categories"]}

    assert by_name["Sensitive / Excluded"]["rule"]["regex"] == r"^Sensitive\ /\ Excluded$"
    assert re.search(by_name["Shopping - Goods"]["rule"]["regex"], "Shopping - Goods")


def test_output_is_stable_across_runs():
    """CI reruns must not produce a different preset from the same map."""
    assert emitter.build_preset() == emitter.build_preset()


def test_serialises_without_newlines_for_github_env():
    """The value is written straight into $GITHUB_ENV, which ends at a newline."""
    payload = json.dumps([emitter.build_preset()], separators=(",", ":"))

    assert "\n" not in payload
    assert json.loads(payload)[0]["id"] == "research-study"
