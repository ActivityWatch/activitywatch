"""Tests for scripts/package/host-abi-gate.sh on fake bundle trees."""

import os
import subprocess
from pathlib import Path
from typing import Optional

import pytest

GATE = Path(__file__).parents[1] / "package" / "host-abi-gate.sh"
WAYLAND_ONLY = "libwayland-client libwayland-cursor libwayland-egl libwayland-server"


def run_gate(bundle: Path, libs_list: Optional[str] = None) -> int:
    env = {k: v for k, v in os.environ.items() if k != "HOST_ABI_LIBS_LIST"}
    if libs_list is not None:
        env["HOST_ABI_LIBS_LIST"] = libs_list
    return subprocess.run(
        ["bash", str(GATE), str(bundle)], env=env, capture_output=True
    ).returncode


def make_bundle(tmp_path: Path, *libs: str) -> Path:
    lib_dir = tmp_path / "bundle" / "usr" / "lib"
    lib_dir.mkdir(parents=True)
    (lib_dir / "libgtk-3.so.0").touch()  # never flagged
    for name in libs:
        (lib_dir / name).touch()
    return tmp_path / "bundle"


def test_clean_bundle_passes(tmp_path: Path):
    assert run_gate(make_bundle(tmp_path)) == 0


@pytest.mark.parametrize("lib", ["libglib-2.0.so.0", "libgio-2.0.so.0", "libwayland-client.so.0"])
def test_default_list_rejects_host_abi_libs(tmp_path: Path, lib: str):
    assert run_gate(make_bundle(tmp_path, lib)) == 1


def test_override_rejects_wayland(tmp_path: Path):
    bundle = make_bundle(tmp_path, "libglib-2.0.so.0", "libwayland-egl.so.1")
    assert run_gate(bundle, WAYLAND_ONLY) == 1


def test_override_replaces_rather_than_extends_default(tmp_path: Path):
    # The Tauri AppImage keeps glib on purpose: with the wayland-only list,
    # glib must pass, while the default list still rejects it.
    bundle = make_bundle(tmp_path, "libglib-2.0.so.0", "libgobject-2.0.so.0")
    assert run_gate(bundle, WAYLAND_ONLY) == 0
    assert run_gate(bundle) == 1


def test_empty_override_keeps_default(tmp_path: Path):
    assert run_gate(make_bundle(tmp_path, "libglib-2.0.so.0"), "") == 1


def test_symlinked_name_is_flagged(tmp_path: Path):
    bundle = make_bundle(tmp_path, "libwayland-client.so.0.22.0")
    (bundle / "usr" / "lib" / "libwayland-client.so.0").symlink_to("libwayland-client.so.0.22.0")
    assert run_gate(bundle, WAYLAND_ONLY) == 1
