import fnmatch
import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path
from string import Template

import pytest

SCRIPT = Path(__file__).parents[1] / "patch_research_edition_profile.py"
SPEC = importlib.util.spec_from_file_location("patch_research_edition_profile", SCRIPT)
assert SPEC and SPEC.loader
patcher = importlib.util.module_from_spec(SPEC)
# dataclasses.dataclass() looks the defining module up in sys.modules (to
# resolve string type hints), so it must be registered before exec_module
# runs the class body -- otherwise the `Patch` dataclass fails to import.
sys.modules[SPEC.name] = patcher
SPEC.loader.exec_module(patcher)


def make_fixture_root(tmp_path: Path, target: str) -> Path:
    """Build a synthetic tree containing exactly one occurrence of every ``old``.

    Patches for the same path are concatenated in table order, each preceded
    by a filler line, so every target string appears exactly once per file --
    the precondition ``apply_patches`` requires to succeed.
    """
    by_path: "dict[str, list[patcher.Patch]]" = {}
    for patch in patcher.TARGETS[target]:
        by_path.setdefault(patch.path, []).append(patch)

    for rel_path, patches in by_path.items():
        file_path = tmp_path / rel_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        content = "".join(f"# filler\n{p.old}" for p in patches)
        file_path.write_text(content, encoding="utf-8")

    return tmp_path


@pytest.mark.parametrize("target", ["qt", "tauri"])
def test_applies_every_site(tmp_path: Path, target: str):
    root = make_fixture_root(tmp_path, target)
    patches = patcher.TARGETS[target]

    applied = patcher.apply_patches(root, patches, check=False)

    assert len(applied) == len(patches)

    by_path: "dict[str, list[patcher.Patch]]" = {}
    for patch in patches:
        by_path.setdefault(patch.path, []).append(patch)

    for rel_path, file_patches in by_path.items():
        text = (root / rel_path).read_text(encoding="utf-8")
        for patch in file_patches:
            assert patch.new in text
            if patch.old not in patch.new:
                assert patch.old not in text


@pytest.mark.parametrize("target", ["qt", "tauri"])
def test_check_mode_writes_nothing(tmp_path: Path, target: str):
    root = make_fixture_root(tmp_path, target)
    patches = patcher.TARGETS[target]

    before = {
        rel_path: (root / rel_path).read_bytes()
        for rel_path in {p.path for p in patches}
    }

    applied = patcher.apply_patches(root, patches, check=True)

    assert len(applied) == len(patches)
    for rel_path, contents in before.items():
        assert (root / rel_path).read_bytes() == contents


def test_missing_file_fails_closed(tmp_path: Path):
    root = make_fixture_root(tmp_path, "qt")
    patches = patcher.TARGETS["qt"]
    victim = patches[0].path
    (root / victim).unlink()

    with pytest.raises(patcher.PatchError, match="submodule") as exc_info:
        patcher.apply_patches(root, patches, check=False)
    assert victim in str(exc_info.value)


def test_missing_token_fails_closed(tmp_path: Path):
    root = make_fixture_root(tmp_path, "qt")
    patches = patcher.TARGETS["qt"]
    victim = patches[0]
    file_path = root / victim.path
    text = file_path.read_text(encoding="utf-8")
    file_path.write_text(text.replace(victim.old, "", 1), encoding="utf-8")

    with pytest.raises(patcher.PatchError) as exc_info:
        patcher.apply_patches(root, patches, check=False)

    message = str(exc_info.value)
    assert victim.path in message
    assert victim.why in message
    assert "found 0" in message


def test_ambiguous_token_fails_closed(tmp_path: Path):
    root = make_fixture_root(tmp_path, "qt")
    patches = patcher.TARGETS["qt"]
    victim = patches[0]
    file_path = root / victim.path
    text = file_path.read_text(encoding="utf-8")
    file_path.write_text(text + victim.old, encoding="utf-8")

    with pytest.raises(patcher.PatchError, match="found 2"):
        patcher.apply_patches(root, patches, check=False)


def test_nothing_written_when_one_site_fails(tmp_path: Path):
    root = make_fixture_root(tmp_path, "qt")
    patches = patcher.TARGETS["qt"]

    # Pick a path with multiple patches so breaking one leaves the others
    # unable to complete the file's all-or-nothing write.
    by_path: "dict[str, list[patcher.Patch]]" = {}
    for patch in patches:
        by_path.setdefault(patch.path, []).append(patch)
    multi_patch_path = next(p for p, ps in by_path.items() if len(ps) > 1)

    file_path = root / multi_patch_path
    broken_patch = by_path[multi_patch_path][-1]
    text = file_path.read_text(encoding="utf-8")
    file_path.write_text(text.replace(broken_patch.old, "", 1), encoding="utf-8")
    before = file_path.read_bytes()

    with pytest.raises(patcher.PatchError):
        patcher.apply_patches(root, patches, check=False)

    assert file_path.read_bytes() == before


def test_reapply_is_refused(tmp_path: Path):
    root = make_fixture_root(tmp_path, "qt")
    patches = patcher.TARGETS["qt"]

    patcher.apply_patches(root, patches, check=False)

    with pytest.raises(patcher.PatchError, match="already applied"):
        patcher.apply_patches(root, patches, check=False)


def test_main_exit_codes(tmp_path: Path, capsys):
    good_root = make_fixture_root(tmp_path / "good", "qt")
    assert patcher.main(["qt", "--root", str(good_root), "--check"]) == 0

    bad_root = tmp_path / "bad"
    bad_root.mkdir()
    code = patcher.main(["qt", "--root", str(bad_root), "--check"])
    assert code == 1
    captured = capsys.readouterr()
    assert "ERROR" in captured.err


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("target", ["qt", "tauri"])
def test_real_tree_check_passes_if_submodules_present(target: str):
    root = _repo_root()
    marker = root / "aw-qt" / "aw_qt" / "profile.py"
    if not marker.is_file():
        pytest.skip("submodules not checked out")

    applied = patcher.apply_patches(root, patcher.TARGETS[target], check=True)

    assert len(applied) == len(patcher.TARGETS[target])


def test_patched_python_profile_module_behaviour(tmp_path: Path, monkeypatch):
    repo_root = _repo_root()
    real_profile = repo_root / "aw-qt" / "aw_qt" / "profile.py"
    if not real_profile.is_file():
        pytest.skip("submodules not checked out")

    dest = tmp_path / "aw-qt" / "aw_qt" / "profile.py"
    dest.parent.mkdir(parents=True)
    dest.write_text(real_profile.read_text(encoding="utf-8"), encoding="utf-8")

    qt_python_patches = [
        p for p in patcher.TARGETS["qt"] if p.path == "aw-qt/aw_qt/profile.py"
    ]
    patcher.apply_patches(tmp_path, qt_python_patches, check=False)

    spec = importlib.util.spec_from_file_location("patched_profile", dest)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    monkeypatch.delenv("AW_PROFILE", raising=False)

    assert module.resolve_profile(None, False) == "research"
    assert module.resolve_profile(None, True) == "testing"
    assert module.DEFAULT_PROFILE == "default"
    assert module.profile_suffix("research") == "-research"

    module.export_profile(module.resolve_profile(None, False))
    assert os.environ["AW_PROFILE"] == "research"


@pytest.mark.parametrize("target", ["qt", "tauri"])
def test_macos_bundle_dir_is_distinct_from_standard(tmp_path: Path, target: str):
    """Research builds must not emit ActivityWatch.app next to a standard install."""
    root = make_fixture_root(tmp_path, target)
    patcher.apply_patches(root, patcher.TARGETS[target], check=False)

    stem = patcher.BUNDLE_DIR_STEM
    expected_app = f"{stem}.app"
    colliding = "ActivityWatch.app"

    if target == "qt":
        spec = (root / "aw.spec").read_text(encoding="utf-8")
        assert f'name="{expected_app}"' in spec
        assert f'name="{colliding}"' not in spec
    else:
        tauri = (root / "scripts/package/build_app_tauri.sh").read_text(
            encoding="utf-8"
        )
        assert f'APP_NAME="{stem}"' in tauri
        assert 'APP_NAME="ActivityWatch"\n' not in tauri

    makefile = (root / "Makefile").read_text(encoding="utf-8")
    assert f"APP_BUNDLE ?= {stem}\n" in makefile
    assert "APP_BUNDLE ?= ActivityWatch\n" not in makefile

    notarize = (root / "scripts/notarize.sh").read_text(encoding="utf-8")
    assert f"app=dist/{expected_app}" in notarize
    assert "app=dist/ActivityWatch.app" not in notarize


# --- Windows install identity -------------------------------------------------
# These use the *real* .iss / tauri.conf.json rather than the synthetic fixture,
# because the thing under test is largely what the patch does NOT touch: the
# shortcut, uninstall and install-dir lines that derive from `#define MyAppName`.
# A synthetic file built from the `old` strings alone cannot catch upstream
# hardcoding a name that would then collide with a standard install.

WINDOWS_REAL_FILES = {
    "qt": "scripts/package/activitywatch-setup.iss",
    "tauri": "scripts/package/aw-tauri.iss",
}
STANDARD_APPID_QT = "F226B8F4-3244-46E6-901D-0CE8035423E4"
STANDARD_APPID_TAURI = "983D0855-08C8-46BD-AEFB-3924581C6703"


def _patch_real_file(tmp_path: Path, rel_path: str, patches) -> str:
    """Copy one real repo file into ``tmp_path``, patch it, return the result."""
    src = _repo_root() / rel_path
    if not src.is_file():
        pytest.skip(f"{rel_path} not present")
    dst = tmp_path / rel_path
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    relevant = [p for p in patches if p.path == rel_path]
    patcher.apply_patches(tmp_path, relevant, check=False)
    return dst.read_text(encoding="utf-8")


@pytest.mark.parametrize("target", ["qt", "tauri"])
def test_windows_installer_is_a_separate_product(tmp_path: Path, target: str):
    """Research setup must register its own product, not upgrade over standard."""
    rel = WINDOWS_REAL_FILES[target]
    patches = (
        patcher.WINDOWS_PATCHES_QT
        if target == "qt"
        else patcher.WINDOWS_PATCHES_TAURI
    )
    text = _patch_real_file(tmp_path, rel, patches)

    research_appid = (
        patcher.WINDOWS_APPID_QT if target == "qt" else patcher.WINDOWS_APPID_TAURI
    )
    standard_appid = STANDARD_APPID_QT if target == "qt" else STANDARD_APPID_TAURI

    # AppId is what Inno keys "same product" on — it must have changed.
    assert f"AppId={{{{{research_appid}}}" in text
    assert standard_appid not in text

    # Display name drives shortcuts, uninstall entry and (Qt) the install dir.
    assert patcher.BUNDLE_NAME in text
    assert '#define MyAppName "ActivityWatch"\n' not in text
    assert '#define MyAppName "ActivityWatch (Tauri)"\n' not in text

    # Setup .exe no longer collides with the standard artifact.
    assert "OutputBaseFilename=activitywatch-setup\n" not in text
    assert "OutputBaseFilename=activitywatch-research" in text

    # Shortcut / uninstall identity must still *derive* from MyAppName. If
    # upstream ever hardcodes the name here, the research build would install a
    # shortcut and uninstall entry indistinguishable from a standard install.
    for line in ("{autoprograms}", "{autodesktop}", "{userstartup}"):
        assert f'Name: "{line}\\{{#MyAppName}}"' in text
    assert "UninstallDisplayName={#MyAppName}\n" in text


def test_windows_research_installers_do_not_collide_with_each_other(tmp_path: Path):
    """Qt-research and Tauri-research are also distinct products from each other."""
    qt = _patch_real_file(
        tmp_path / "qt", WINDOWS_REAL_FILES["qt"], patcher.WINDOWS_PATCHES_QT
    )
    tauri = _patch_real_file(
        tmp_path / "tauri", WINDOWS_REAL_FILES["tauri"], patcher.WINDOWS_PATCHES_TAURI
    )

    appids = {
        patcher.WINDOWS_APPID_QT,
        patcher.WINDOWS_APPID_TAURI,
        STANDARD_APPID_QT,
        STANDARD_APPID_TAURI,
    }
    assert len(appids) == 4, "research AppIds must be unique GUIDs"

    def _output_name(text: str) -> str:
        for line in text.splitlines():
            if line.startswith("OutputBaseFilename="):
                return line.split("=", 1)[1]
        raise AssertionError("no OutputBaseFilename")

    # Both .iss files ship `activitywatch-setup` on master, so the research
    # names must be distinct from each other as well as from standard.
    assert _output_name(qt) != _output_name(tauri)

    # Install directories must differ (Qt derives its dir from MyAppName).
    assert "DefaultDirName={autopf}\\{#MyAppName}\n" in qt
    assert f"DefaultDirName={{autopf}}\\{patcher.BUNDLE_DIR_STEM}-Tauri\n" in tauri
    assert "DefaultDirName={autopf}\\ActivityWatch-Tauri\n" not in tauri


@pytest.fixture(
    params=[(target, research) for target in ("qt", "tauri") for research in (False, True)]
)
def windows_installer_names(tmp_path: Path, request):
    target, research = request.param
    rel = WINDOWS_REAL_FILES[target]
    # Packaging inputs are tracked root files, so a missing producer must fail.
    assert (_repo_root() / rel).is_file()
    patches = (
        patcher.WINDOWS_PATCHES_QT if target == "qt" else patcher.WINDOWS_PATCHES_TAURI
    )
    text = _patch_real_file(tmp_path, rel, patches if research else [])
    outputs = re.findall(r"^OutputBaseFilename=(\S+)$", text, re.MULTILINE)
    assert len(outputs) == 1, "expected one executable OutputBaseFilename assignment"

    package = (_repo_root() / "scripts/package/package-all.sh").read_text()
    calls = re.findall(
        r'^\s*"\$SCRIPT_DIR/collect-setup\.sh" "\$filename"\s*$', package, re.MULTILINE
    )
    assert len(calls) == 1, "build_setup must invoke the tested installer collector"
    templates = re.findall(
        r'^\s*filename="([^"\n]+-setup\.exe)"$', package, re.MULTILINE
    )
    assert len(templates) == 1, "expected one versioned installer filename assignment"
    suffix = "-tauri" if target == "tauri" else ""
    if research:
        suffix += "-research"
    final = Template(templates[0]).substitute(
        build_suffix=suffix, version="v0.14.0b5", platform="windows", arch="x86_64"
    )
    return target, outputs[0] + ".exe", final


def test_windows_installer_producer_matches_packaging_and_release(windows_installer_names):
    target, produced, final = windows_installer_names
    collector = (_repo_root() / "scripts/package/collect-setup.sh").read_text()
    inputs = re.findall(r"^\s*setup_src=\(([^)\n]+)\)$", collector, re.MULTILINE)
    assert len(inputs) == 1, "expected one executable setup_src assignment"
    assert fnmatch.fnmatchcase(f"dist/{produced}", inputs[0].strip())

    workflow = (_repo_root() / ".github/workflows/release.yml").read_text()
    jobs = dict(re.findall(
        r"^  ([\w-]+):\n(.*?)(?=^  [\w-]+:|\Z)", workflow, re.MULTILINE | re.DOTALL
    ))
    upload = re.search(
        r"^      - name: Upload packages\n(.*?)(?=^      - |\Z)",
        jobs[f"build-{target}"], re.MULTILINE | re.DOTALL,
    )
    assert upload, f"missing {target} package upload step"
    assert "uses: actions/upload-artifact@" in upload[1]
    path = re.search(r"^          path: (.+)$", upload[1], re.MULTILINE)
    assert path, f"missing {target} package upload path"
    globs = (
        re.findall(r"^            (\S+)$", upload[1], re.MULTILINE)
        if path[1] == "|" else [path[1]]
    )
    assert globs and any(fnmatch.fnmatchcase(f"dist/{final}", glob) for glob in globs)
    release = re.search(
        r"^      - name: Release\n(.*?)(?=^      - |\Z)",
        jobs["release"], re.MULTILINE | re.DOTALL,
    )
    assert release and "uses: softprops/action-gh-release@" in release[1]
    files = re.search(
        r"^          files: \|\n((?:^            \S.*\n)+)", release[1], re.MULTILINE
    )
    assert files, "missing release action's asset files block"
    release_globs = [line.strip() for line in files[1].splitlines()]
    assert release_globs and any(
        fnmatch.fnmatchcase(f"dist/builds-windows/{final}", glob) for glob in release_globs
    )


@pytest.mark.skipif(
    sys.platform != "linux", reason="Bash fixture runs in the Ubuntu packaging smoke job"
)
def test_windows_setup_collection(tmp_path: Path, windows_installer_names):
    _, produced, final = windows_installer_names
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / produced).write_bytes(b"fixture installer")
    (dist / "activitywatch-portable.zip").write_bytes(b"portable archive")

    result = subprocess.run(
        ["bash", str(_repo_root() / "scripts/package/collect-setup.sh"), final],
        cwd=tmp_path, capture_output=True, text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert {path.name for path in dist.iterdir()} == {final, "activitywatch-portable.zip"}
    assert (dist / final).read_bytes() == b"fixture installer"
    assert (dist / "activitywatch-portable.zip").read_bytes() == b"portable archive"


@pytest.mark.skipif(
    sys.platform != "linux", reason="Bash fixture runs in the Ubuntu packaging smoke job"
)
@pytest.mark.parametrize("case", ["missing", "multiple", "directory"])
def test_windows_setup_collection_refuses_invalid_inputs(tmp_path: Path, case: str):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "activitywatch-portable.zip").write_bytes(b"portable archive")
    if case == "multiple":
        for name in ("activitywatch-setup.exe", "activitywatch-research-setup.exe"):
            (dist / name).write_bytes(name.encode())
    elif case == "directory":
        (dist / "activitywatch-research-setup.exe").mkdir()

    def snapshot():
        return {
            path.name: path.read_bytes() if path.is_file() else None
            for path in dist.iterdir()
        }

    before = snapshot()
    result = subprocess.run(
        [
            "bash", str(_repo_root() / "scripts/package/collect-setup.sh"),
            "activitywatch-research-v0.14.0b5-windows-x86_64-setup.exe",
        ],
        cwd=tmp_path, capture_output=True, text=True,
    )

    assert result.returncode != 0
    assert "expected exactly one" in result.stdout + result.stderr
    assert snapshot() == before


def test_tauri_wix_upgrade_code_is_pinned_and_config_stays_valid_json(tmp_path: Path):
    """The MSI upgrade code defines the product family; pin it, don't derive it."""
    import json
    import uuid

    rel = "aw-tauri/src-tauri/tauri.conf.json"
    text = _patch_real_file(tmp_path, rel, patcher.WINDOWS_PATCHES_TAURI)

    config = json.loads(text)  # deny_unknown_fields upstream: must stay valid
    wix = config["bundle"]["windows"]["wix"]
    assert wix["upgradeCode"] == patcher.WINDOWS_WIX_UPGRADE_CODE_TAURI
    uuid.UUID(wix["upgradeCode"])  # tauri parses this as a uuid::Uuid


# --- Linux package identity ---------------------------------------------------
# Like the Windows tests above, these patch the *real* packaging scripts: the
# thing under test is mostly what the patch does NOT touch. A synthetic fixture
# built from the `old` strings alone would still pass if upstream added a fourth
# reference to /opt/activitywatch or copied the desktop entry somewhere else.


def test_linux_deb_is_a_separate_package(tmp_path: Path):
    """A research deb must be co-installable, not an upgrade of the standard one."""
    control = _patch_real_file(
        tmp_path, "scripts/package/deb/control", patcher.LINUX_PATCHES_QT
    )
    assert f"Package: {patcher.LINUX_PACKAGE}\n" in control
    # dpkg keys off the package name: same name == upgrade == standard removed.
    assert "Package: activitywatch\n" not in control


def test_linux_deb_installs_beside_a_standard_install(tmp_path: Path):
    """No /opt/activitywatch or shared desktop-entry filename may survive."""
    script = _patch_real_file(
        tmp_path, "scripts/package/package-deb.sh", patcher.LINUX_PATCHES_QT
    )

    # The staged install tree, the Exec= line and the .deb filename must all
    # move together; a leftover bare "/opt/activitywatch" would overwrite the
    # standard install's files even with a distinct package name.
    assert "/opt/activitywatch/" not in script
    assert f"{patcher.LINUX_OPT_DIR}/aw-qt" in script
    assert "activitywatch_${VERSION_NUM}.deb" not in script

    # Both copies out of the install tree must land under the research
    # filename: /etc/xdg/autostart and /usr/share/applications are shared
    # namespaces, so a same-named entry silently replaces the standard one.
    for dest in ("etc/xdg/autostart", "usr/share/applications"):
        assert f"$PKGDIR/{dest}/{patcher.LINUX_DESKTOP_FILENAME}\n" in script
        assert f"$PKGDIR/{dest}/\n" not in script


def test_linux_desktop_entry_is_rebranded(tmp_path: Path):
    """Menu/dock name and icon id must not read as a standard install."""
    entry = _patch_real_file(
        tmp_path, "aw-qt/resources/aw-qt.desktop", patcher.LINUX_PATCHES_QT
    )
    assert f"Name={patcher.BUNDLE_NAME}\n" in entry
    assert "Name=ActivityWatch\n" not in entry
    assert f"Icon={patcher.LINUX_ICON_ID}\n" in entry


def test_appimage_desktop_and_icon_ids_agree(tmp_path: Path):
    """linuxdeploy's --icon-filename must match the entry's Icon= key.

    Desktop integration resolves the icon by that id; a mismatch ships an
    AppImage with no icon, and a shared id would overwrite the standard
    install's icon in the user's hicolor theme.
    """
    script = _patch_real_file(
        tmp_path, "scripts/package/package-appimage.sh", patcher.LINUX_PATCHES_QT
    )
    entry = _patch_real_file(
        tmp_path, "aw-qt/resources/aw-qt.desktop", patcher.LINUX_PATCHES_QT
    )

    assert f"--icon-filename {patcher.LINUX_ICON_ID}\n" in script
    assert f"Icon={patcher.LINUX_ICON_ID}\n" in entry
    # The entry handed to linuxdeploy is the research-named copy, and the copy
    # is staged before it is used.
    assert f"--desktop-file ./activitywatch/{patcher.LINUX_DESKTOP_FILENAME} " in script
    stage = script.index(f"cp ./activitywatch/aw-qt.desktop ./activitywatch/{patcher.LINUX_DESKTOP_FILENAME}")
    assert stage < script.index("linuxdeploy-x86_64.AppImage --appdir")


def test_first_run_autostart_identity_is_distinct_on_every_platform(tmp_path: Path):
    """aw-qt writes its own autostart entry; those names are the installer's.

    Bundle id, package name and profile are all already split at this point --
    but if the login item / Startup shortcut / autostart .desktop keep their
    standard names, the two editions still overwrite each other's autostart.
    """
    rel = "aw-qt/aw_qt/autostart.py"
    src = _repo_root() / rel
    if not src.is_file():
        pytest.skip(f"{rel} not present")
    before = src.read_text(encoding="utf-8")
    after = _patch_real_file(tmp_path, rel, patcher.AUTOSTART_PATCHES_QT)

    # Linux: the written filename changes; the *shipped resource* name does not
    # (the patched build still reads resources/aw-qt.desktop out of the bundle).
    # Must not be aw-qt-research.desktop — that is the standard named-profile entry.
    assert f'_linux_autostart_dir() / "{patcher.LINUX_DESKTOP_FILENAME}"' in after
    assert "aw-qt-research.desktop" not in after
    assert 'DESKTOP_FILENAME = "aw-qt.desktop"' in after
    # macOS: plist path follows _macos_launch_agent_label(), which would otherwise
    # become net.activitywatch.aw-qt-research and collide with --profile research.
    assert f'return "{patcher.BUNDLE_ID}"' in after
    assert 'return f"{LAUNCH_AGENT_LABEL}{_profile_suffix()}"' not in after
    assert f'return "{patcher.LAUNCH_AGENT_LABEL}"' not in after
    # Windows: both the Run value name and the Startup .lnk derive from APP_NAME.
    # Named-profile suffixing then yields "ActivityWatch Research (research)".
    assert f'APP_NAME = "{patcher.BUNDLE_NAME}"' in after
    assert 'APP_NAME = "ActivityWatch"\n' not in after

    # Guard the runtime identity sources: if upstream stops suffixing these, the
    # research overrides above would be patching dead code.
    for derived in (
        'return _linux_autostart_dir() / f"{stem}{_profile_suffix()}{extension}"',
        'return f"{LAUNCH_AGENT_LABEL}{_profile_suffix()}"',
        'return APP_NAME if not suffix else f"{APP_NAME} ({_profile()})"',
    ):
        assert derived in before, f"upstream no longer derives: {derived}"


def test_tauri_autostart_uses_distinct_app_name_for_research_build(tmp_path: Path):
    """tauri_plugin_autostart derives its entry name from productName by default.

    Both standard and research Tauri builds share productName "aw-tauri", so
    enabling autostart in one edition would overwrite the other's entry on
    Windows (registry key) and Linux (~/.config/autostart/*.desktop).

    The fix is entirely patcher-side: PROFILE_PATCHES_TAURI inserts BUILD_PROFILE
    into profile.rs; AUTOSTART_PATCHES_TAURI replaces the tauri_plugin_autostart::init()
    call in lib.rs with a Builder that sets an explicit app_name derived from
    BUILD_PROFILE when it differs from DEFAULT_PROFILE.

    This test asserts both patch sets produce the expected output on the real sources.
    """
    # --- half 1: PROFILE_PATCHES_TAURI inserts BUILD_PROFILE = "research" ---
    profile_rs_rel = "aw-tauri/src-tauri/src/profile.rs"
    profile_rs_src = _repo_root() / profile_rs_rel
    if not profile_rs_src.is_file():
        pytest.skip(f"{profile_rs_rel} not present")
    before_profile = profile_rs_src.read_text(encoding="utf-8")
    # Standard source has DEFAULT_PROFILE but NOT BUILD_PROFILE
    assert 'pub const DEFAULT_PROFILE: &str = "default";' in before_profile
    assert "BUILD_PROFILE" not in before_profile, (
        "BUILD_PROFILE must NOT exist in the unpatched source; the patcher inserts it"
    )
    after_profile = _patch_real_file(
        tmp_path,
        profile_rs_rel,
        patcher.PROFILE_PATCHES_TAURI,
    )
    assert f'pub const BUILD_PROFILE: &str = "{patcher.RESEARCH_PROFILE}";' in after_profile

    # --- half 2: AUTOSTART_PATCHES_TAURI overrides named-profile app_name ---
    lib_rs_rel = "aw-tauri/src-tauri/src/lib.rs"
    lib_rs_src = _repo_root() / lib_rs_rel
    if not lib_rs_src.is_file():
        pytest.skip(f"{lib_rs_rel} not present")
    before_lib = lib_rs_src.read_text(encoding="utf-8")
    # Standard source already uses Builder + named-profile identities.
    assert "tauri_plugin_autostart::Builder::new()" in before_lib
    assert "profile::autostart_app_name" in before_lib
    assert "BUILD_PROFILE" not in before_lib
    after_lib = _patch_real_file(
        tmp_path,
        lib_rs_rel,
        patcher.AUTOSTART_PATCHES_TAURI,
    )
    # Research build keeps named-profile wiring, then overrides the OS identity
    # so it does not collide with a standard `--profile research` login item.
    assert "profile::autostart_app_name" in after_lib
    assert "profile::BUILD_PROFILE != profile::DEFAULT_PROFILE" in after_lib
    assert '"aw-tauri-{}-edition"' in after_lib
    assert 'format!("aw-tauri-{}", profile::BUILD_PROFILE)' not in after_lib
