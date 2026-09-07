import importlib.util
import os
import sys
from pathlib import Path

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
