"""Version resources must be applied to the assembled Windows bundle, before zip/setup."""

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/package/windows-version-info.py"


def test_windows_packaging_stamps_before_archiving():
    packaging = (ROOT / "scripts/package/package-all.sh").read_text()
    # Check the invocation, not a function definition or a macOS-only spec.
    stamp = 'python3 "$SCRIPT_DIR/windows-version-info.py" dist/activitywatch "$version_no_prefix"'
    assert stamp in packaging
    assert packaging.index(stamp) < packaging.index("\nbuild_zip\n")
    assert packaging.index(stamp) < packaging.index("\n    build_setup\n")


def load_module():
    spec = importlib.util.spec_from_file_location("windows_version_info", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "version, expected",
    [
        ("0.14.2", (0, 14, 2, 0)),
        ("v0.14.0b5", (0, 14, 0, 0)),
        ("0.14.0rc1", (0, 14, 0, 0)),
        ("0.14.2.dev-abc1234", (0, 14, 2, 0)),
        ("0.14.0b5-research", (0, 14, 0, 0)),
        ("1.0", (1, 0, 0, 0)),
    ],
)
def test_numeric_version(version, expected):
    assert load_module().numeric_version(version) == expected


@pytest.mark.parametrize("version", ["fatal: no tags", "", "65536.1.2"])
def test_invalid_version_fails(version):
    with pytest.raises(ValueError):
        load_module().numeric_version(version)


def test_targets_only_python_entrypoints(tmp_path):
    module = load_module()
    for filename in [
        "aw-qt.exe",
        "aw-watcher-afk/aw-watcher-afk.exe",
        "aw-server-rust/aw-sync.exe",
        "QtWebEngineProcess.exe",
    ]:
        path = tmp_path / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    assert {p.name for p in module.python_executables(tmp_path)} == {
        "aw-qt.exe",
        "aw-watcher-afk.exe",
    }


@pytest.mark.skipif(sys.platform != "win32", reason="requires Windows PE resource APIs")
def test_cli_writes_and_reads_real_pe_resource_preserving_overlay(tmp_path):
    import pefile
    from PyInstaller.utils.win32.versioninfo import read_version_info_from_executable

    bundle = tmp_path / "activitywatch"
    bundle.mkdir()
    exe = bundle / "aw-qt.exe"
    shutil.copy2(sys.executable, exe)
    marker = b"AW-test-overlay-preserved"
    with exe.open("ab") as stream:
        stream.write(marker)
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(bundle), "0.14.0b5"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    info = read_version_info_from_executable(str(exe))
    strings = {s.name: s.val for s in info.kids[0].kids[0].kids}
    assert strings["ProductName"] == "ActivityWatch"
    assert strings["FileVersion"] == "0.14.0b5"
    assert strings["OriginalFilename"] == "aw-qt.exe"
    assert info.ffi.fileVersionMS == 14
    assert info.ffi.fileVersionLS == 0
    with pefile.PE(str(exe), fast_load=True) as pe:
        assert pe.get_overlay().endswith(marker)


@pytest.mark.skipif(sys.platform != "win32", reason="requires Windows PE resource APIs")
def test_empty_bundle_fails(tmp_path):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(tmp_path), "0.14.2"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "No Python executables" in result.stderr
