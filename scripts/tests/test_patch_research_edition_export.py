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


# Shape of BucketsExportRocket::new after aw-server-rust#677: the export is
# spooled to a tempfile by the datastore and rewound. Both export endpoints
# go through this one function, so it is the single insertion point.
UTIL_SRC = """impl BucketsExportRocket {
    pub fn new(
        datastore: &aw_datastore::Datastore,
        bucket_id: Option<&str>,
    ) -> Result<Self, HttpErrorJson> {
        let file = tempfile::tempfile().map_err(io_error)?;
        let (mut file, name) = datastore.export_to_file(bucket_id, file)?;
        file.seek(SeekFrom::Start(0)).map_err(io_error)?;
        let filename = match name {
            Some(id) => format!("attachment; filename=aw-bucket-export_{id}.json"),
            None => "attachment; filename=aw-buckets-export.json".into(),
        };
        Ok(Self { file, filename })
    }
}
"""

MOD_SRC = """mod util;
mod export;
mod hostcheck;
"""


def _util(root: Path) -> str:
    return (root / "aw-server-rust/aw-server/src/endpoints/util.rs").read_text(
        encoding="utf-8"
    )


def test_patch_inserts_module_and_call_site(tmp_path: Path):
    root = _write_tree(tmp_path, UTIL_SRC, MOD_SRC)

    patcher.patch_tree(root)

    util = _util(root)
    mod = (root / "aw-server-rust/aw-server/src/endpoints/mod.rs").read_text(
        encoding="utf-8"
    )
    copied = root / "aw-server-rust/aw-server/src/endpoints/export_sanitize.rs"

    assert copied.is_file()
    assert "mod export_sanitize;" in mod
    assert util.count(patcher.MARKER) == 1
    assert "sanitize_buckets_export" in util
    assert "Status::Conflict" in util
    # The sanitized spool replaces `file` before the filename is chosen and
    # the struct is built, so the response body is the sanitized JSON.
    assert util.index(patcher.MARKER) < util.index("let filename = match name")
    assert "sanitized.seek(SeekFrom::Start(0))" in util


def test_patch_is_idempotent(tmp_path: Path):
    root = _write_tree(tmp_path, UTIL_SRC, MOD_SRC)
    patcher.patch_tree(root)
    first = _util(root)
    patcher.patch_tree(root)
    second = _util(root)
    assert first == second
    mod = (root / "aw-server-rust/aw-server/src/endpoints/mod.rs").read_text(
        encoding="utf-8"
    )
    assert mod.count("mod export_sanitize;") == 1


def test_patch_fails_closed_without_export_marker(tmp_path: Path):
    root = _write_tree(tmp_path, "impl BucketsExportRocket {}\n", MOD_SRC)
    with pytest.raises(ValueError, match="insertion point"):
        patcher.patch_tree(root)


def test_patch_fails_closed_on_pre_677_endpoints(tmp_path: Path):
    # A tree where the endpoints still build `export.buckets` themselves has
    # no spooling call site; the patch must refuse rather than ship unsanitized.
    legacy_util = "impl BucketsExportRocket {\n    pub fn new() {}\n}\n"
    root = _write_tree(tmp_path, legacy_util, MOD_SRC)
    with pytest.raises(ValueError, match="found 0"):
        patcher.patch_tree(root)


def test_live_tree_is_patchable_or_already_patched():
    root = Path(__file__).resolve().parents[2]
    util = root / "aw-server-rust/aw-server/src/endpoints/util.rs"
    if not util.is_file():
        pytest.skip("aw-server-rust not checked out")
    util_text = util.read_text(encoding="utf-8")
    assert (
        patcher.MARKER in util_text
        or util_text.count(patcher.EXPORT_INSERT_NEEDLE) == 1
    ), "BucketsExportRocket::new no longer matches the research export patch; update EXPORT_INSERT_NEEDLE"


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
