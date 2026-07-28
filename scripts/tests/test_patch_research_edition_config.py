import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "patch_research_edition_config.py"
SPEC = importlib.util.spec_from_file_location("patch_research_edition_config", SCRIPT)
assert SPEC and SPEC.loader
patcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(patcher)


def test_patch_config_matches_watcher_config_shape():
    source = '''default_config = """
[aw-watcher-window]
research_enabled = false

[aw-watcher-window.research_category_map]
""".strip()
'''

    result = patcher.patch_config(source)

    assert "research_enabled = true" in result
    assert "research_enabled = false" not in result
    assert '[aw-watcher-window.research_category_map]\n"svenskaspel.se" = "Sensitive / Excluded"' in result
    assert '"kagi" = "Search & Navigation"\n""".strip()' in result


def test_patch_config_fails_closed_without_category_section():
    with pytest.raises(ValueError, match="research_category_map"):
        patcher.patch_config("research_enabled = false\n")
