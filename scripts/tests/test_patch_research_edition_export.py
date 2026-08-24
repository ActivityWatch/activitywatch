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


def _write_tree(tmp_path: Path, export: str, bucket: str, mod: str) -> Path:
    endpoints = tmp_path / "aw-server-rust" / "aw-server" / "src" / "endpoints"
    endpoints.mkdir(parents=True)
    (endpoints / "export.rs").write_text(export, encoding="utf-8")
    (endpoints / "bucket.rs").write_text(bucket, encoding="utf-8")
    (endpoints / "mod.rs").write_text(mod, encoding="utf-8")
    return tmp_path


EXPORT_SRC = """use std::collections::HashMap;

pub fn buckets_export() {
    for (bid, mut bucket) in buckets.drain() {
        export.buckets.insert(bid, bucket);
    }

    Ok(export.into())
}
"""

BUCKET_SRC = """pub fn bucket_export() {
    export.buckets.insert(bucket_id.into(), bucket);

    Ok(export.into())
}
"""

MOD_SRC = """mod util;
mod export;
mod hostcheck;
"""


def test_patch_inserts_module_and_both_call_sites(tmp_path: Path):
    root = _write_tree(tmp_path, EXPORT_SRC, BUCKET_SRC, MOD_SRC)

    patcher.patch_tree(root)

    export = (root / "aw-server-rust/aw-server/src/endpoints/export.rs").read_text(
        encoding="utf-8"
    )
    bucket = (root / "aw-server-rust/aw-server/src/endpoints/bucket.rs").read_text(
        encoding="utf-8"
    )
    mod = (root / "aw-server-rust/aw-server/src/endpoints/mod.rs").read_text(encoding="utf-8")
    copied = root / "aw-server-rust/aw-server/src/endpoints/export_sanitize.rs"

    assert copied.is_file()
    assert "mod export_sanitize;" in mod
    assert patcher.MARKER in export
    assert patcher.MARKER in bucket
    assert "sanitize_buckets_export" in export
    assert "sanitize_buckets_export" in bucket
    assert "Status::Conflict" in export
    assert "Status::Conflict" in bucket


def test_patch_is_idempotent(tmp_path: Path):
    root = _write_tree(tmp_path, EXPORT_SRC, BUCKET_SRC, MOD_SRC)
    patcher.patch_tree(root)
    first = (root / "aw-server-rust/aw-server/src/endpoints/export.rs").read_text(
        encoding="utf-8"
    )
    patcher.patch_tree(root)
    second = (root / "aw-server-rust/aw-server/src/endpoints/export.rs").read_text(
        encoding="utf-8"
    )
    assert first == second
    mod = (root / "aw-server-rust/aw-server/src/endpoints/mod.rs").read_text(encoding="utf-8")
    assert mod.count("mod export_sanitize;") == 1


def test_patch_fails_closed_without_export_marker(tmp_path: Path):
    root = _write_tree(tmp_path, "fn buckets_export() {}\n", BUCKET_SRC, MOD_SRC)
    with pytest.raises(ValueError, match="insertion point"):
        patcher.patch_tree(root)


def test_live_tree_is_patchable_or_already_patched():
    root = Path(__file__).resolve().parents[2]
    export = root / "aw-server-rust/aw-server/src/endpoints/export.rs"
    bucket = root / "aw-server-rust/aw-server/src/endpoints/bucket.rs"
    if not export.is_file() or not bucket.is_file():
        pytest.skip("aw-server-rust not checked out")
    export_text = export.read_text(encoding="utf-8")
    bucket_text = bucket.read_text(encoding="utf-8")
    assert patcher.MARKER in export_text or export_text.count(patcher.EXPORT_INSERT_NEEDLE) == 1
    assert patcher.MARKER in bucket_text or bucket_text.count(patcher.BUCKET_INSERT_NEEDLE) == 1


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
