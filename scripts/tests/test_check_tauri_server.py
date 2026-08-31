import importlib.util
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
