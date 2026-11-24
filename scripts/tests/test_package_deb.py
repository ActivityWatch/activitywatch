"""Tests for scripts/package/package-deb.sh, run against a fixture tree.

Packaging tools (sudo, apt-get, jdupes, dpkg-deb) are stubbed; the script's
own logic (version field, staging directory, output name) runs for real.
"""

from __future__ import annotations

import shutil
import stat
import subprocess
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).parents[1]
PACKAGE_DEB = SCRIPTS / "package" / "package-deb.sh"
CONTROL = SCRIPTS / "package" / "deb" / "control"

STUBS = {
    # chown to root needs real root; everything else runs as the test user.
    "sudo": '#!/bin/bash\n[[ "$1" == chown ]] && exit 0\nexec "$@"\n',
    "apt-get": "#!/bin/bash\nexit 0\n",
    "jdupes": "#!/bin/bash\nexit 0\n",
    # Record the staged control file and tree, then emit the .deb dpkg-deb
    # would produce (named after the staging directory).
    "dpkg-deb": (
        '#!/bin/bash\n[[ "$1" == --build ]] || exit 1\n'
        'cp "$2/DEBIAN/control" "$2.control"\n'
        '(cd "$2" && find . -type f | sort) > "$2.files"\n'
        'touch "$2.deb"\n'
    ),
}


def _exe(path: Path, content: str) -> None:
    path.write_text(content)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


def make_tree(tmp_path: Path, version: str) -> Path:
    root = tmp_path / "repo"
    pkg = root / "scripts" / "package"
    (pkg / "deb").mkdir(parents=True)
    shutil.copy(PACKAGE_DEB, pkg / "package-deb.sh")
    shutil.copy(CONTROL, pkg / "deb" / "control")
    _exe(pkg / "getversion.sh", f'#!/bin/bash\necho "{version}"\n')
    dist = root / "dist" / "activitywatch"
    dist.mkdir(parents=True)
    (dist / "aw-qt.desktop").write_text("[Desktop Entry]\nExec=aw-qt\n")
    (dist / "aw-qt").write_text("")
    bindir = tmp_path / "bin"
    bindir.mkdir()
    for name, content in STUBS.items():
        _exe(bindir / name, content)
    return root


def run_package_deb(tmp_path: Path, root: Path) -> subprocess.CompletedProcess[str]:
    env = {"PATH": f"{tmp_path / 'bin'}:/usr/bin:/bin", "HOME": str(tmp_path)}
    return subprocess.run(
        ["bash", "scripts/package/package-deb.sh"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def control_version(root: Path, pkgdir: str) -> str:
    for line in (root / f"{pkgdir}.control").read_text().splitlines():
        if line.startswith("Version: "):
            return line.split(": ", 1)[1]
    raise AssertionError("no Version field")


@pytest.mark.parametrize(
    ("tag", "expected"),
    [
        ("v0.14.0", "0.14.0"),
        ("v0.14.0b5", "0.14.0~b5"),
        ("v0.14.0rc1", "0.14.0~rc1"),
        ("v0.14.0a2", "0.14.0~a2"),
        ("v0.14.0b5.dev-abc1234", "0.14.0~b5.dev-abc1234"),
        # A dev build after a final tag is newer than that release: no tilde.
        ("v0.14.0.dev-abc1234", "0.14.0.dev-abc1234"),
        ("v0.14.0b5-research", "0.14.0~b5"),
    ],
)
def test_control_version(tmp_path: Path, tag: str, expected: str) -> None:
    root = make_tree(tmp_path, tag)
    result = run_package_deb(tmp_path, root)
    assert result.returncode == 0, result.stderr
    # The staging dir and published filename keep the plain version.
    plain = tag.removeprefix("v").removesuffix("-research")
    assert control_version(root, f"activitywatch_{plain}") == f"1:{expected}"
    name = tag.removesuffix("-research")
    assert (root / "dist" / f"activitywatch-{name}-linux-x86_64.deb").exists()


@pytest.mark.skipif(shutil.which("dpkg") is None, reason="needs dpkg")
@pytest.mark.parametrize(
    ("older", "newer"),
    [
        ("v0.14.0b5", "v0.14.0"),
        ("v0.14.0rc1", "v0.14.0"),
        ("v0.14.0b5", "v0.14.0b5.dev-abc1234"),
        ("v0.14.0b5.dev-abc1234", "v0.14.0"),
        ("v0.14.0", "v0.14.0.dev-abc1234"),
    ],
)
def test_upgrade_ordering(tmp_path: Path, older: str, newer: str) -> None:
    versions = []
    for i, tag in enumerate((older, newer)):
        root = make_tree(tmp_path / str(i), tag)
        assert run_package_deb(tmp_path / str(i), root).returncode == 0
        plain = tag.removeprefix("v")
        versions.append(control_version(root, f"activitywatch_{plain}"))
    cmp = subprocess.run(["dpkg", "--compare-versions", versions[0], "lt", versions[1]])
    assert cmp.returncode == 0, f"{versions[0]} should sort below {versions[1]}"


@pytest.mark.skipif(shutil.which("dpkg") is None, reason="needs dpkg")
@pytest.mark.parametrize("tag", ["v0.14.4b2", "v0.14.4rc1", "v0.14.4"])
def test_upgrade_from_legacy_beta(tmp_path: Path, tag: str) -> None:
    root = make_tree(tmp_path, tag)
    result = run_package_deb(tmp_path, root)
    assert result.returncode == 0, result.stderr
    version = control_version(root, f"activitywatch_{tag.removeprefix('v')}")
    cmp = subprocess.run(["dpkg", "--compare-versions", "0.14.4b1", "lt", version])
    assert cmp.returncode == 0, f"legacy 0.14.4b1 should upgrade to {version}"


@pytest.mark.parametrize(
    "tag",
    ["v0.14.0 *", "v0.14.0/../../victim", "v0.14.0\nother", "v0.14.0;other", "v"],
)
def test_unsafe_version_rejected_before_cleanup(tmp_path: Path, tag: str) -> None:
    root = make_tree(tmp_path, tag)
    # Even an existing tag-derived staging path must not be removed.
    staging = root / f"activitywatch_{tag.removeprefix('v')}"
    staging.mkdir(parents=True)
    marker = staging / "keep"
    marker.write_text("must survive")
    result = run_package_deb(tmp_path, root)
    assert result.returncode != 0
    assert "Unsafe or unsupported version" in result.stderr
    assert marker.read_text() == "must survive"
    assert not list(root.glob("*.control"))


def test_rebuild_drops_stale_files(tmp_path: Path) -> None:
    root = make_tree(tmp_path, "v0.14.0")
    stale = root / "activitywatch_0.14.0" / "opt" / "activitywatch" / "removed-module"
    stale.parent.mkdir(parents=True)
    stale.write_text("left over from an earlier build")
    result = run_package_deb(tmp_path, root)
    assert result.returncode == 0, result.stderr
    files = (root / "activitywatch_0.14.0.files").read_text()
    assert "removed-module" not in files
    assert "./opt/activitywatch/aw-qt" in files
