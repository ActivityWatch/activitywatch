import importlib.util
import json
from pathlib import Path

import pytest

GENERATOR = Path(__file__).parents[1] / "package" / "generate_latest_json.py"


def _load():
    spec = importlib.util.spec_from_file_location("generate_latest_json", GENERATOR)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gen = _load()


def _write_sig(root: Path, name: str, signature: str = "sig-bytes") -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(signature + "\n")
    # Matching binary next to the .sig, as the packaging step copies both.
    path.with_name(name[: -len(".sig")]).write_bytes(b"bundle")


def test_normalize_version_strips_v_and_research_suffix():
    assert gen.normalize_version("v0.14.0b4") == "0.14.0b4"
    assert gen.normalize_version("0.14.0b4") == "0.14.0b4"
    assert gen.normalize_version("v0.14.0b4-research") == "0.14.0b4"
    assert gen.normalize_version("0.14.0b4-research") == "0.14.0b4"


def test_infer_edition_from_tag_or_explicit_flag():
    assert gen.infer_edition("v0.14.0") == "standard"
    assert gen.infer_edition("v0.14.0b4") == "standard"
    assert gen.infer_edition("v0.14.0b4-research") == "research"
    assert gen.infer_edition("v0.14.0b4-research", "standard") == "standard"
    assert gen.infer_edition("v0.14.0", "research") == "research"


def test_asset_prefix_and_manifest_filename_partition_editions():
    assert gen.asset_prefix("standard") == "activitywatch-tauri"
    assert gen.asset_prefix("research") == "activitywatch-tauri-research"
    assert gen.manifest_filename("standard") == "latest.json"
    assert gen.manifest_filename("research") == "latest-research.json"


def test_standard_collect_ignores_research_artifacts(tmp_path):
    _write_sig(
        tmp_path,
        "activitywatch-tauri-0.14.0b4-darwin-aarch64.app.tar.gz.sig",
        "std-sig",
    )
    _write_sig(
        tmp_path,
        "activitywatch-tauri-research-0.14.0b4-darwin-aarch64.app.tar.gz.sig",
        "research-sig",
    )

    platforms = gen.collect_platforms(
        str(tmp_path),
        "0.14.0b4",
        "ActivityWatch/activitywatch",
        "v0.14.0b4",
        "standard",
    )

    assert list(platforms) == ["darwin-aarch64"]
    assert platforms["darwin-aarch64"]["signature"] == "std-sig"
    assert platforms["darwin-aarch64"]["url"].endswith(
        "/v0.14.0b4/activitywatch-tauri-0.14.0b4-darwin-aarch64.app.tar.gz"
    )


def test_research_collect_ignores_standard_artifacts(tmp_path):
    _write_sig(
        tmp_path,
        "activitywatch-tauri-0.14.0b4-linux-x86_64.AppImage.tar.gz.sig",
        "std-sig",
    )
    _write_sig(
        tmp_path,
        "activitywatch-tauri-research-0.14.0b4-linux-x86_64.AppImage.tar.gz.sig",
        "research-sig",
    )

    platforms = gen.collect_platforms(
        str(tmp_path),
        "0.14.0b4",
        "ActivityWatch/activitywatch",
        "v0.14.0b4-research",
        "research",
    )

    assert list(platforms) == ["linux-x86_64"]
    assert platforms["linux-x86_64"]["signature"] == "research-sig"
    assert platforms["linux-x86_64"]["url"].endswith(
        "/v0.14.0b4-research/"
        "activitywatch-tauri-research-0.14.0b4-linux-x86_64.AppImage.tar.gz"
    )


def test_windows_prefers_nsis_over_msi_regardless_of_walk_order(tmp_path):
    _write_sig(tmp_path, "activitywatch-tauri-0.14.0-windows-x86_64.msi.zip.sig", "msi-sig")
    _write_sig(tmp_path, "activitywatch-tauri-0.14.0-windows-x86_64.nsis.zip.sig", "nsis-sig")

    platforms = gen.collect_platforms(
        str(tmp_path),
        "0.14.0",
        "ActivityWatch/activitywatch",
        "v0.14.0",
        "standard",
    )

    assert list(platforms) == ["windows-x86_64"]
    assert platforms["windows-x86_64"]["signature"] == "nsis-sig"
    assert platforms["windows-x86_64"]["url"].endswith(
        "/v0.14.0/activitywatch-tauri-0.14.0-windows-x86_64.nsis.zip"
    )


def test_main_writes_manifest_and_refuses_empty(tmp_path):
    _write_sig(tmp_path, "activitywatch-tauri-0.14.0-windows-x86_64.nsis.zip.sig")
    out = tmp_path / "latest.json"

    gen.main(
        [
            "--version",
            "v0.14.0",
            "--notes",
            "ActivityWatch v0.14.0",
            "--repo",
            "ActivityWatch/activitywatch",
            "--tag",
            "v0.14.0",
            "--edition",
            "standard",
            "--dist",
            str(tmp_path),
            "--output",
            str(out),
        ]
    )

    manifest = json.loads(out.read_text())
    assert manifest["version"] == "0.14.0"
    assert "windows-x86_64" in manifest["platforms"]

    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(SystemExit, match="No standard updater artifacts"):
        gen.main(
            [
                "--version",
                "0.14.0",
                "--notes",
                "none",
                "--repo",
                "ActivityWatch/activitywatch",
                "--tag",
                "v0.14.0",
                "--dist",
                str(empty),
                "--output",
                str(tmp_path / "latest.json"),
            ]
        )
