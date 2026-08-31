import importlib.util
import subprocess
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "check_tauri_server.py"
SPEC = importlib.util.spec_from_file_location("check_tauri_server", SCRIPT)
assert SPEC and SPEC.loader
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)

major_minor = checker.major_minor
read_locked_server = checker.read_locked_server
read_package_version = checker.read_package_version
validation_errors = checker.validation_errors
is_git_checkout = checker.is_git_checkout
initialize_submodule = checker.initialize_submodule
sync_submodule = checker.sync_submodule


REVISION = "a" * 40


def test_major_minor_accepts_beta_release():
    assert major_minor("0.14.0b5") == "0.14"


def test_read_package_version(tmp_path: Path):
    cargo_toml = tmp_path / "Cargo.toml"
    cargo_toml.write_text(
        '[workspace]\n\n[package]\nname = "aw-server"\nversion = "0.14.0"\n'
    )

    assert read_package_version(cargo_toml) == "0.14.0"


def test_read_locked_server(tmp_path: Path):
    cargo_lock = tmp_path / "Cargo.lock"
    cargo_lock.write_text(
        '[[package]]\nname = "other"\nversion = "1.0.0"\n\n'
        '[[package]]\nname = "aw-server"\nversion = "0.14.0"\n'
        'source = "git+https://github.com/ActivityWatch/aw-server-rust.git?branch=master#'
        f'{REVISION}"\n'
    )

    assert read_locked_server(cargo_lock) == ("0.14.0", REVISION)


def test_valid_when_release_line_and_revisions_match():
    assert validation_errors("0.14.0b5", "0.14.0", REVISION, "0.14.0", REVISION) == []


def test_rejects_old_tauri_release_line():
    errors = validation_errors("0.14.0b5", "0.14.0", REVISION, "0.13.1", REVISION)

    assert errors == [
        "Tauri locks aw-server 0.13.1, which does not match release line 0.14"
    ]


def test_rejects_different_revision_even_on_same_release_line():
    errors = validation_errors("0.14.0b5", "0.14.0", REVISION, "0.14.0", "b" * 40)

    assert errors == [
        "Tauri locks aw-server-rust bbbbbbbbbbbb, but the release submodule is aaaaaaaaaaaa"
    ]


def test_rejects_invalid_version():
    with pytest.raises(ValueError, match="invalid version"):
        major_minor("dev")


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def make_git_repo(path: Path) -> tuple[str, str]:
    path.mkdir()
    subprocess.run(["git", "-C", str(path), "init"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(path), "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(path), "config", "user.name", "Test"], check=True
    )
    tracked = path / "tracked.txt"
    tracked.write_text("first\n")
    subprocess.run(["git", "-C", str(path), "add", "tracked.txt"], check=True)
    subprocess.run(
        ["git", "-C", str(path), "commit", "-m", "first"],
        check=True,
        capture_output=True,
    )
    first = git(path, "rev-parse", "HEAD")
    tracked.write_text("second\n")
    subprocess.run(
        ["git", "-C", str(path), "commit", "-am", "second"],
        check=True,
        capture_output=True,
    )
    return first, git(path, "rev-parse", "HEAD")


def test_sync_submodule_checks_out_locked_revision(tmp_path: Path):
    repo = tmp_path / "aw-server-rust"
    first, second = make_git_repo(repo)
    assert git(repo, "rev-parse", "HEAD") == second

    assert sync_submodule(repo, first)
    assert git(repo, "rev-parse", "HEAD") == first
    assert not sync_submodule(repo, first)


def test_sync_submodule_refuses_dirty_checkout(tmp_path: Path):
    repo = tmp_path / "aw-server-rust"
    _, current = make_git_repo(repo)
    (repo / "tracked.txt").write_text("dirty\n")

    with pytest.raises(ValueError, match="refusing to replace dirty"):
        sync_submodule(repo, current)


def test_sync_submodule_rejects_uninitialized_nested_directory(tmp_path: Path):
    parent = tmp_path / "activitywatch"
    _, _ = make_git_repo(parent)
    server = parent / "aw-server-rust"
    server.mkdir()

    with pytest.raises(ValueError, match="not initialized as a Git submodule"):
        sync_submodule(server, REVISION)


def test_is_git_checkout_requires_the_exact_repository_root(tmp_path: Path):
    repo = tmp_path / "activitywatch"
    _, _ = make_git_repo(repo)
    nested = repo / "aw-server-rust"
    nested.mkdir()

    assert is_git_checkout(repo)
    assert not is_git_checkout(nested)


def test_initialize_submodule_rejects_unrelated_checkout(tmp_path: Path):
    parent = tmp_path / "activitywatch"
    _, _ = make_git_repo(parent)
    unrelated = parent / "aw-server-rust"
    _, _ = make_git_repo(unrelated)

    with pytest.raises(ValueError, match="refusing unmanaged Git checkout"):
        initialize_submodule(parent, "aw-server-rust")


def test_initialize_submodule_rejects_old_form_checkout_with_migration_hint(
    tmp_path: Path,
):
    parent = tmp_path / "activitywatch"
    _, _ = make_git_repo(parent)
    server = parent / "aw-server-rust"
    _, _ = make_git_repo(server)
    url = "https://github.com/ActivityWatch/aw-server-rust.git"
    subprocess.run(
        ["git", "-C", str(server), "remote", "add", "origin", url], check=True
    )
    (parent / ".gitmodules").write_text(
        f'[submodule "aw-server-rust"]\n'
        "\tpath = aw-server-rust\n"
        f"\turl = {url}\n"
    )

    with pytest.raises(ValueError, match="git submodule absorbgitdirs aw-server-rust"):
        initialize_submodule(parent, "aw-server-rust")
