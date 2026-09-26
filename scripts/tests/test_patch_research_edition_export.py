import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "patch_research_edition_export.py"
SPEC = importlib.util.spec_from_file_location("patch_research_edition_export", SCRIPT)
assert SPEC and SPEC.loader
patcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(patcher)

CONFIG_PATCHER_PATH = Path(__file__).parents[1] / "patch_research_edition_config.py"
CONFIG_SPEC = importlib.util.spec_from_file_location(
    "patch_research_edition_config", CONFIG_PATCHER_PATH
)
assert CONFIG_SPEC and CONFIG_SPEC.loader
config_patcher = importlib.util.module_from_spec(CONFIG_SPEC)
CONFIG_SPEC.loader.exec_module(config_patcher)


def _write_tree(tmp_path: Path, util: str, mod: str) -> Path:
    endpoints = tmp_path / "aw-server-rust" / "aw-server" / "src" / "endpoints"
    endpoints.mkdir(parents=True)
    (endpoints / "util.rs").write_text(util, encoding="utf-8")
    (endpoints / "mod.rs").write_text(mod, encoding="utf-8")
    return tmp_path


# util.rs as of aw-server-rust#721/#722: the export struct, the streaming
# BucketsExportRocket, and the CSV export. Built from the patcher's own anchors
# so the fixture tracks them; test_live_tree_* checks them against the real tree.
UTIL_SRC = (
    "use std::fs::File;\n\n"
    + patcher.STRUCT_NEEDLE
    + "\nfn export_filename() {}\n\n"
    + patcher.EXPORT_INSERT_NEEDLE
    + "\n// ── CSV streaming export\n\n"
    + patcher.CSV_NEEDLE
    + "        datastore.get_bucket(bucket_id)?;\n    }\n}\n"
)

MOD_SRC = """mod util;
mod export;
mod hostcheck;
"""

ENDPOINTS = "aw-server-rust/aw-server/src/endpoints"


def _util(root: Path) -> str:
    return (root / ENDPOINTS / "util.rs").read_text(encoding="utf-8")


def _mod(root: Path) -> str:
    return (root / ENDPOINTS / "mod.rs").read_text(encoding="utf-8")


def _fn_body(text: str, signature: str) -> str:
    start = text.index(signature)
    end = text.index("\n}\n", start)
    return text[start:end]


def test_patch_inserts_module_and_all_anchors(tmp_path: Path):
    root = _write_tree(tmp_path, UTIL_SRC, MOD_SRC)

    patcher.patch_tree(root)

    util = _util(root)
    assert (root / ENDPOINTS / "export_sanitize.rs").is_file()
    assert "mod export_sanitize;" in _mod(root)
    for marker in (patcher.MARKER, patcher.STRUCT_MARKER, patcher.CSV_MARKER):
        assert util.count(marker) == 1, marker
    # None of the original streaming export code paths survive
    assert patcher.EXPORT_INSERT_NEEDLE not in util
    assert "spawn_export_stream(self.datastore" not in util


def test_json_export_is_sanitized_before_headers_with_409(tmp_path: Path):
    root = _write_tree(tmp_path, UTIL_SRC, MOD_SRC)
    patcher.patch_tree(root)
    util = _util(root)

    helper = _fn_body(util, "fn research_sanitized_export(")
    # The sanitizer's refusal is a 409, other failures are errors too.
    assert "sanitize_buckets_export(export)" in helper
    assert "Status::Conflict" in helper
    assert "Status::InternalServerError" in helper
    # Unnamed tempfiles only (removed when dropped, on every path)
    assert helper.count("tempfile::tempfile()") == 2
    assert "NamedTempFile" not in util

    # `new` runs it (before any response exists) and `?` returns its error
    new = _fn_body(util, "impl BucketsExportRocket {")
    assert "research_sanitized_export(datastore, bucket_id)?" in new
    assert new.index("research_sanitized_export") < new.index("Ok(Self {")

    # The responder only streams the sanitized spool
    responder = _fn_body(util, "impl<'r> Responder<'r, 'static> for BucketsExportRocket")
    assert "from_std(self.sanitized)" in responder
    assert "export_to_file" not in responder
    assert "spawn_export_stream" not in responder


def test_csv_export_returns_403(tmp_path: Path):
    root = _write_tree(tmp_path, UTIL_SRC, MOD_SRC)
    patcher.patch_tree(root)
    new = _fn_body(_util(root), "impl BucketEventsCsvRocket {")
    body = new.split(") -> Result<Self, HttpErrorJson> {", 1)[1]
    # The very first statement refuses; nothing touches the datastore before it
    first = body.strip().splitlines()
    assert first[0].startswith("// " + patcher.CSV_MARKER)
    assert first[1].strip() == "return Err(HttpErrorJson::new("
    assert "Status::Forbidden" in body.split("));", 1)[0]
    assert "CSV export is disabled in Research Edition" in body


def test_patch_is_idempotent(tmp_path: Path):
    root = _write_tree(tmp_path, UTIL_SRC, MOD_SRC)
    patcher.patch_tree(root)
    first = _util(root)
    patcher.patch_tree(root)
    assert _util(root) == first
    assert _mod(root).count("mod export_sanitize;") == 1


@pytest.mark.parametrize(
    "anchor,name",
    [
        ("STRUCT_NEEDLE", "export-struct"),
        ("EXPORT_INSERT_NEEDLE", "export-sanitizer"),
        ("CSV_NEEDLE", "csv-export"),
    ],
)
def test_patch_fails_closed_without_any_one_anchor(tmp_path: Path, anchor, name):
    util = UTIL_SRC.replace(getattr(patcher, anchor), "// changed upstream\n")
    root = _write_tree(tmp_path, util, MOD_SRC)
    with pytest.raises(ValueError, match=f"exactly one {name} insertion point, found 0"):
        patcher.patch_tree(root)
    # Nothing was written: no half-patched tree
    assert _util(root) == util
    assert _mod(root) == MOD_SRC
    assert not (root / ENDPOINTS / "export_sanitize.rs").exists()


def test_patch_fails_closed_on_duplicate_anchor(tmp_path: Path):
    util = UTIL_SRC + patcher.CSV_NEEDLE
    root = _write_tree(tmp_path, util, MOD_SRC)
    with pytest.raises(ValueError, match="csv-export insertion point, found 2"):
        patcher.patch_tree(root)


def test_patch_fails_closed_without_mod_anchor(tmp_path: Path):
    root = _write_tree(tmp_path, UTIL_SRC, "mod util;\n")
    with pytest.raises(ValueError, match="export-sanitize module insertion point"):
        patcher.patch_tree(root)
    assert _util(root) == UTIL_SRC


def test_patch_fails_closed_on_pre_721_endpoints(tmp_path: Path):
    # The #1449 shape (sanitizer spliced after export_to_file in `new`) is gone
    # upstream; a tree still shaped like that must not be half patched.
    legacy_util = (
        "impl BucketsExportRocket {\n    pub fn new() {\n"
        "        let (mut file, name) = datastore.export_to_file(bucket_id, file)?;\n"
        "    }\n}\n"
    )
    root = _write_tree(tmp_path, legacy_util, MOD_SRC)
    with pytest.raises(ValueError, match="found 0"):
        patcher.patch_tree(root)


def test_live_tree_is_patchable_or_already_patched():
    root = Path(__file__).resolve().parents[2]
    util = root / ENDPOINTS / "util.rs"
    if not util.is_file():
        pytest.skip("aw-server-rust not checked out")
    text = util.read_text(encoding="utf-8")
    for name, needle, _, marker in patcher.UTIL_EDITS:
        assert marker in text or text.count(needle) == 1, (
            f"aw-server-rust no longer matches the research export patch ({name}); "
            "update scripts/patch_research_edition_export.py"
        )


def test_sanitizer_allowlist_covers_config_categories():
    rust = (
        Path(__file__).parents[1] / "research_edition" / "export_sanitize.rs"
    ).read_text(encoding="utf-8")
    expected = {c for _, c in config_patcher.CATEGORY_MAP} | set(
        config_patcher.APP_CATEGORY_MAP.values()
    )
    expected.update({"Excluded", "excluded"})
    missing = [category for category in expected if f'"{category}"' not in rust]
    assert missing == []


def test_every_research_build_patches_the_export_sanitizer():
    workflow = (
        Path(__file__).resolve().parents[2] / ".github" / "workflows" / "release.yml"
    ).read_text(encoding="utf-8")

    assert workflow.count("python3 scripts/patch_research_edition_config.py") == 3
    assert workflow.count("python3 scripts/patch_research_edition_export.py") == 3
