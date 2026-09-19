"""
Tests for the changelog generator, focused on submodules that several parents share.

aw-webui is a submodule of aw-server, aw-server-rust and aw-tauri, which used to give it
one changelog section per parent (see the v0.14.0b8 release notes).
"""

import importlib.util
import subprocess
from pathlib import Path
from typing import List

import pytest

SCRIPT = Path(__file__).parents[1] / "build_changelog.py"

FILTER_TYPES = ["build", "ci", "tests", "test"]
REPO_ORDER = ["bundle", "server", "server-rust", "webui"]


def _load():
    spec = importlib.util.spec_from_file_location("build_changelog", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


changelog = _load()


def git(cwd: Path, *args: str) -> str:
    """Runs git with a deterministic identity, and local submodule URLs allowed."""
    cmd = [
        "git",
        "-c",
        "protocol.file.allow=always",
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.com",
        "-c",
        "commit.gpgsign=false",
        *args,
    ]
    return subprocess.run(
        cmd, cwd=cwd, check=True, capture_output=True, text=True
    ).stdout


def short(repo: Path, rev: str = "HEAD") -> str:
    return git(repo, "rev-parse", "--short", rev).strip()


def commit(repo: Path, msg: str) -> str:
    with (repo / "log.txt").open("a") as f:
        f.write(msg + "\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", msg)
    return short(repo)


def init(root: Path, name: str) -> Path:
    git(root, "init", "-q", "-b", "master", name)
    repo = root / name
    (repo / "name.txt").write_text(
        name + "\n"
    )  # so the repos don't share commit hashes
    commit(repo, "chore: initial commit")
    return repo


def add_submodule(parent: Path, name: str, at: str = "HEAD") -> None:
    git(parent, "submodule", "add", "-q", f"../{name}", name)
    git(parent / name, "checkout", "-q", "--detach", at)
    git(parent, "add", name)
    commit(parent, f"build(deps): add {name}")


def bump_submodule(parent: Path, name: str, to: str = "origin/master") -> None:
    """Points `parent` at another commit of its `name` submodule, as a release bump does."""
    git(parent / name, "fetch", "-q", "origin")
    git(parent / name, "checkout", "-q", "--detach", to)
    git(parent, "add", name)
    # sync nested submodules to what the new commit points at (as a release checkout does)
    git(parent, "submodule", "update", "--init", "--recursive", "-q")
    commit(parent, f"build(deps): bump {name}")


@pytest.fixture
def bundle(tmp_path: Path):
    """
    A miniature of the ActivityWatch tree: a bundle repo with two server repos,
    both of which vendor the same webui repo.

        bundle ─┬─ server ──────┬─ webui
                └─ server-rust ─┘

    Yields the bundle path, the tag-like "since" commit, and a `release()` that bumps
    everything and returns the "until" commit.
    """
    webui = init(tmp_path, "webui")
    old_webui = short(webui)
    commit(webui, "fix(webui): stop the spinner from spinning forever")
    new_webui = commit(webui, "feat(webui): add a button")

    for name in ("server", "server-rust"):
        repo = init(tmp_path, name)
        add_submodule(repo, "webui", at=old_webui)

    bundle = init(tmp_path, "bundle")
    for name in ("server", "server-rust"):
        add_submodule(bundle, name)
    git(bundle, "submodule", "update", "--init", "--recursive", "-q")
    since = short(bundle)

    def release(rust_webui: str = new_webui) -> str:
        """The release: both servers bump the webui they vendor, the bundle follows."""
        bump_submodule(tmp_path / "server", "webui", to=new_webui)
        commit(tmp_path / "server", "fix(server): return 200 instead of 500")
        bump_submodule(tmp_path / "server-rust", "webui", to=rust_webui)
        for name in ("server", "server-rust"):
            bump_submodule(bundle, name)
        return short(bundle)

    yield {
        "path": bundle,
        "webui": webui,
        "since": since,
        "release": release,
        "old_webui": old_webui,
        "new_webui": new_webui,
    }


def render(bundle: Path, since: str, until: str) -> str:
    repos = changelog.collect_repos("bundle", str(bundle), (since, until))
    return changelog.summary_repos("Test", "bundle", repos, REPO_ORDER, FILTER_TYPES)


def sections(out: str) -> List[str]:
    return [
        line.removeprefix("## 📦 ")
        for line in out.splitlines()
        if line.startswith("## 📦 ")
    ]


def test_shared_submodule_gets_a_single_section(bundle):
    until = bundle["release"]()
    out = render(bundle["path"], bundle["since"], until)

    # webui is vendored by both servers, but is only reported once
    assert sections(out).count("webui") == 1
    assert out.count("feat(webui): add a button") == 1
    assert "fix(webui): stop the spinner" in out


def test_sections_are_flat_and_follow_repo_order(bundle):
    until = bundle["release"]()
    out = render(bundle["path"], bundle["since"], until)

    # one level, ordered by repo_order, instead of nested under each parent
    # (server-rust is dropped: it only bumped webui)
    assert sections(out) == ["bundle", "server", "webui"]


def test_parent_with_only_a_submodule_bump_is_dropped(bundle):
    # server-rust only bumps webui, so it has nothing of its own to report
    until = bundle["release"]()
    out = render(bundle["path"], bundle["since"], until)

    assert "server-rust" not in sections(out)
    assert "fix(server): return 200 instead of 500" in out


def test_out_of_sync_parents_get_the_union_and_a_warning(bundle):
    # server-rust lags one commit behind the webui that server vendors
    lagging = short(bundle["webui"], "HEAD~1")
    until = bundle["release"](rust_webui=lagging)
    out = render(bundle["path"], bundle["since"], until)

    assert sections(out).count("webui") == 1
    assert "point at different commits" in out
    assert f"`server` → `{bundle['new_webui']}`" in out
    assert f"`server-rust` → `{lagging}`" in out
    # the union: the commit only `server` points at is still in the changelog
    assert "feat(webui): add a button" in out
    assert "fix(webui): stop the spinner" in out


def test_in_sync_parents_get_no_warning(bundle):
    until = bundle["release"]()
    out = render(bundle["path"], bundle["since"], until)

    assert "point at different commits" not in out
    assert "⚠️" not in out
