import ast
import importlib.util
import tomllib
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "patch_research_edition_config.py"
SPEC = importlib.util.spec_from_file_location("patch_research_edition_config", SCRIPT)
assert SPEC and SPEC.loader
patcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(patcher)


# Current config.py reads both maps. The Research Edition patch deliberately
# leaves the app map empty so approved application names survive capture.
RUNTIME_LOOKUPS = """

def parse_args():
    parsed_args.research_category_map = dict(config.get("research_category_map", {}))
    parsed_args.research_app_category_map = dict(config.get("research_app_category_map", {}))
"""

# Layout before aw-watcher-window#137: the research tables live in
# default_config, section-prefixed.
PRE_137 = (
    '''default_config = """
[aw-watcher-window]
poll_time = 1.0
research_enabled = false

[aw-watcher-window.research_category_map]

[aw-watcher-window.research_app_category_map]
""".strip()
'''
    + RUNTIME_LOOKUPS
)

# Layout since aw-watcher-window#137: research knobs moved to their own template
# so they are not persisted into every fresh install's config, and a comment
# documents the release-time rewrite -- including the literal flag text.
POST_137 = (
    '''default_config = """
[aw-watcher-window]
poll_time = 1.0
""".strip()

# The Research Edition release build rewrites the flag below with
#   sed -i 's/^research_enabled = false$/research_enabled = true/'
# Keep that line at column 0 and byte-identical.
research_defaults = """
research_enabled = false
""".strip()
'''
    + RUNTIME_LOOKUPS
)


def _string_constant(source: str, name: str) -> str:
    """Return the value of a module-level string assignment, unwrapping .strip()."""
    for node in ast.parse(source).body:
        if (
            isinstance(node, ast.Assign)
            and getattr(node.targets[0], "id", None) == name
        ):
            value = node.value
            if isinstance(value, ast.Call):  # `""" ... """.strip()`
                value = value.func.value
            return ast.literal_eval(value)
    raise AssertionError(f"{name} not found")


def test_pre_137_layout_injects_browser_map_and_preserves_app_names():
    result = patcher.patch_config(PRE_137)

    ast.parse(result)

    section = tomllib.loads(_string_constant(result, "default_config"))[
        "aw-watcher-window"
    ]
    assert section["research_enabled"] is True
    assert section["research_category_map"]["svenskaspel.se"] == "Sensitive / Excluded"
    assert section["research_app_category_map"] == {}


def test_post_137_layout_injects_only_browser_map_into_research_defaults():
    """The tables must land in research_defaults, with unprefixed headers.

    research_defaults is parsed standalone and merged into the
    [aw-watcher-window] section key by key, so a section-prefixed header there
    would produce a nested `aw-watcher-window` key that nothing reads.
    """
    result = patcher.patch_config(POST_137)

    ast.parse(result)

    defaults = tomllib.loads(_string_constant(result, "research_defaults"))
    assert "aw-watcher-window" not in defaults
    assert defaults["research_enabled"] is True
    assert defaults["research_category_map"]["svenskaspel.se"] == "Sensitive / Excluded"
    assert "research_app_category_map" not in defaults


def test_patched_config_matches_the_pinned_watcher_storage_contract():
    """Approved app names survive, while browser content and every URL do not."""
    root = Path(__file__).resolve().parents[2]
    config_path = root / "aw-watcher-window/aw_watcher_window/config.py"
    filter_path = root / "aw-watcher-window/aw_watcher_window/research_filter.py"
    if not config_path.is_file() or not filter_path.is_file():
        pytest.skip("aw-watcher-window not checked out")

    patched = patcher.patch_config(config_path.read_text(encoding="utf-8"))
    defaults = tomllib.loads(_string_constant(patched, "research_defaults"))

    spec = importlib.util.spec_from_file_location("research_filter", filter_path)
    assert spec and spec.loader
    research_filter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(research_filter)

    word = research_filter.transform(
        {
            "app": "Microsoft Word",
            "title": "confidential-draft.docx",
            "url": "file:///private/confidential-draft.docx",
        },
        defaults["research_category_map"],
        defaults.get("research_app_category_map"),
    )
    safari = research_filter.transform(
        {
            "app": "Safari",
            "title": "Confidential draft - Google Docs",
            "url": "https://docs.google.com/document/private-id",
        },
        defaults["research_category_map"],
        defaults.get("research_app_category_map"),
    )

    assert word == {"app": "Microsoft Word"}
    assert safari == {"app": "Safari", "title": "Work & Productivity"}


def test_flag_rewrite_is_line_anchored_and_spares_the_sed_comment():
    """The #137 comment contains the literal flag text, and precedes the real flag.

    An unanchored replace patches the comment and leaves research_enabled = false
    -- a green build shipping a Research Edition with research silently disabled.
    """
    result = patcher.patch_config(POST_137)

    assert "s/^research_enabled = false$/research_enabled = true/" in result
    assert (
        tomllib.loads(_string_constant(result, "research_defaults"))["research_enabled"]
        is True
    )


def test_app_map_runtime_support_is_not_required_for_name_preserving_build():
    without_lookup = POST_137.replace(
        'config.get("research_app_category_map"', 'config.get("something_else"'
    )

    result = patcher.patch_config(without_lookup)

    defaults = tomllib.loads(_string_constant(result, "research_defaults"))
    assert "research_app_category_map" not in defaults


def test_fails_closed_when_flag_is_missing():
    with pytest.raises(ValueError, match="research_enabled = false"):
        patcher.patch_config(
            f'default_config = """\n[aw-watcher-window]\n"""{RUNTIME_LOOKUPS}'
        )


def test_fails_closed_on_ambiguous_flag():
    """Two line-anchored flags mean an unknown layout -- refuse rather than guess."""
    ambiguous = POST_137.replace(
        "research_enabled = false\n",
        "research_enabled = false\nresearch_enabled = false\n",
        1,
    )

    with pytest.raises(ValueError, match="found 2"):
        patcher.patch_config(ambiguous)


def test_pre_137_layout_does_not_require_app_section():
    missing_app_table = PRE_137.replace(
        "\n[aw-watcher-window.research_app_category_map]\n", "\n"
    )

    result = patcher.patch_config(missing_app_table)

    section = tomllib.loads(_string_constant(result, "default_config"))[
        "aw-watcher-window"
    ]
    assert section["research_enabled"] is True
    assert "research_app_category_map" not in section
