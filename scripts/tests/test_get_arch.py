"""Tests for scripts/package/get-arch.sh.

Reproduces ActivityWatch/activitywatch#1519: Git Bash on windows-11-arm
reports uname -m as x86_64 under x64 emulation, so a Tauri ARM64 zip was
named windows-x86_64 and overwrote the genuine Intel/AMD asset.
"""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

GET_ARCH = Path(__file__).parents[1] / "package" / "get-arch.sh"


def _fake_uname(tmp_path: Path, kernel: str, machine: str) -> Path:
    """Install a uname stub that reports a Windows/Linux kernel + machine."""
    stub = tmp_path / "uname"
    stub.write_text(
        "#!/bin/bash\n"
        'if [[ "${1:-}" == "-m" ]]; then echo "' + machine + '"; exit 0; fi\n'
        'echo "' + kernel + '"\n'
    )
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    return stub


def run_get_arch(
    tmp_path: Path,
    *,
    kernel: str,
    machine: str,
    extra_env: dict[str, str] | None = None,
) -> str:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _fake_uname(bin_dir, kernel, machine)
    env = {k: v for k, v in os.environ.items() if k not in {
        "RUNNER_ARCH",
        "PROCESSOR_ARCHITECTURE",
        "PROCESSOR_ARCHITEW6432",
    }}
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
    if extra_env:
        env.update(extra_env)
    result = subprocess.run(
        ["bash", str(GET_ARCH)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def test_windows_git_bash_arm_runner_uses_runner_arch_not_uname(tmp_path: Path):
    # The v0.14.1 collision: Git Bash uname -m is x86_64, runner is ARM64.
    assert (
        run_get_arch(
            tmp_path,
            kernel="MINGW64_NT-10.0-26100",
            machine="x86_64",
            extra_env={"RUNNER_ARCH": "ARM64"},
        )
        == "aarch64"
    )


def test_windows_git_bash_x64_runner_stays_x86_64(tmp_path: Path):
    assert (
        run_get_arch(
            tmp_path,
            kernel="MINGW64_NT-10.0-26100",
            machine="x86_64",
            extra_env={"RUNNER_ARCH": "X64"},
        )
        == "x86_64"
    )


def test_windows_msys_processor_architecture_arm64_without_runner_arch(tmp_path: Path):
    assert (
        run_get_arch(
            tmp_path,
            kernel="MSYS_NT-10.0",
            machine="x86_64",
            extra_env={"PROCESSOR_ARCHITECTURE": "ARM64"},
        )
        == "aarch64"
    )


def test_windows_amd64_processor_architecture_maps_to_x86_64(tmp_path: Path):
    assert (
        run_get_arch(
            tmp_path,
            kernel="MINGW64_NT-10.0",
            machine="i686",
            extra_env={"PROCESSOR_ARCHITECTURE": "AMD64"},
        )
        == "x86_64"
    )


def test_linux_uname_m_passthrough(tmp_path: Path):
    assert run_get_arch(tmp_path, kernel="Linux", machine="x86_64") == "x86_64"


def test_linux_aarch64_passthrough(tmp_path: Path):
    assert run_get_arch(tmp_path, kernel="Linux", machine="aarch64") == "aarch64"


def test_macos_arm64_stays_arm64_not_aarch64(tmp_path: Path):
    # macOS artifact names already use arm64 (uname -m). Do not rename them.
    assert run_get_arch(tmp_path, kernel="Darwin", machine="arm64") == "arm64"


def test_linux_runner_arch_does_not_override_uname(tmp_path: Path):
    # RUNNER_ARCH is Windows-only for this helper. Linux/macOS keep uname -m
    # so existing activitywatch-*-linux-aarch64 / macos-arm64 names stay put.
    assert (
        run_get_arch(
            tmp_path,
            kernel="Linux",
            machine="x86_64",
            extra_env={"RUNNER_ARCH": "ARM64"},
        )
        == "x86_64"
    )


def test_package_all_calls_get_arch_helper():
    package = (Path(__file__).parents[1] / "package" / "package-all.sh").read_text()
    assert "get-arch.sh" in package
    assert 'function get_arch() {\n    _arch="$(uname -m)"' not in package
