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


def build_tree(tmp_path: Path, server_start: int = 0, rust_start: int = 0) -> dict:
    """
    A miniature of the ActivityWatch tree: a bundle repo with two server repos,
    both of which vendor the same webui repo.

        bundle ─┬─ server ──────┬─ webui
                └─ server-rust ─┘

    webui has three commits; `server_start`/`rust_start` index which one each server
    vendors at the start of the release, so the parents can begin out of sync.

    Returns the bundle path, the tag-like "since" commit, and a `release()` that bumps
    what it is told to and returns the "until" commit.
    """
    webui = init(tmp_path, "webui")
    webui_commits = [
        short(webui),
        commit(webui, "fix(webui): stop the spinner from spinning forever"),
        commit(webui, "feat(webui): add a button"),
    ]

    for name, start in (("server", server_start), ("server-rust", rust_start)):
        add_submodule(init(tmp_path, name), "webui", at=webui_commits[start])

    bundle = init(tmp_path, "bundle")
    for name in ("server", "server-rust"):
        add_submodule(bundle, name)
    git(bundle, "submodule", "update", "--init", "--recursive", "-q")
    since = short(bundle)

    def release(
        server_webui: int = 2, rust_webui: int = 2, bump_rust: bool = True
    ) -> str:
        """The release: the servers bump the webui they vendor, the bundle follows."""
        bump_submodule(tmp_path / "server", "webui", to=webui_commits[server_webui])
        commit(tmp_path / "server", "fix(server): return 200 instead of 500")
        bump_submodule(bundle, "server")
        if bump_rust:
            bump_submodule(
                tmp_path / "server-rust", "webui", to=webui_commits[rust_webui]
            )
            bump_submodule(bundle, "server-rust")
        return short(bundle)

    return {
        "path": bundle,
        "webui": webui,
        "commits": webui_commits,
        "since": since,
        "release": release,
    }


@pytest.fixture
def bundle(tmp_path: Path) -> dict:
    """The usual case: both servers start the release on the same webui commit."""
    return build_tree(tmp_path)


def render(bundle: Path, since: str, until: str) -> str:
    repos = changelog.collect_repos("bundle", str(bundle), (since, until))
    changelog.collect_pins(str(bundle), repos, "bundle")
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
    until = bundle["release"](rust_webui=1)
    out = render(bundle["path"], bundle["since"], until)

    assert sections(out).count("webui") == 1
    assert "pin different commits" in out
    assert f"`server` → `{bundle['commits'][2]}`" in out
    assert f"`server-rust` → `{bundle['commits'][1]}`" in out
    # the union: the commit only `server` points at is still in the changelog
    assert "feat(webui): add a button" in out
    assert "fix(webui): stop the spinner" in out


def test_parent_that_never_bumped_is_named_in_the_warning(bundle):
    # only server bumps webui; server-rust ships the commit it was already on.
    # `git submodule summary` says nothing about a submodule that didn't move, so this
    # only works because the current pins are read separately.
    until = bundle["release"](bump_rust=False)
    out = render(bundle["path"], bundle["since"], until)

    assert sections(out).count("webui") == 1
    assert "pin different commits" in out
    assert f"`server` → `{bundle['commits'][2]}`" in out
    assert f"`server-rust` → `{bundle['commits'][0]}`" in out


def test_union_keeps_commits_when_the_parents_started_apart(tmp_path):
    # server starts a commit ahead of server-rust, and both land on the same commit:
    # the commit in between is only in server-rust's range and must not be dropped
    bundle = build_tree(tmp_path, server_start=1, rust_start=0)
    until = bundle["release"]()
    out = render(bundle["path"], bundle["since"], until)

    assert "fix(webui): stop the spinner" in out
    assert "feat(webui): add a button" in out
    # they agree on what ships now, so there is nothing to warn about
    assert "pin different commits" not in out


def test_in_sync_parents_get_no_warning(bundle):
    until = bundle["release"]()
    out = render(bundle["path"], bundle["since"], until)

    assert "pin different commits" not in out
    assert "⚠️" not in out


def test_parent_that_newly_vendors_a_repo_does_not_replay_its_history(tmp_path):
    # server has vendored webui for a while and bumps it; server-rust adopts webui
    # during this release, which is not a reason to list webui's whole history
    webui = init(tmp_path, "webui")
    old = short(webui)
    commit(webui, "fix(webui): stop the spinner from spinning forever")
    new = commit(webui, "feat(webui): add a button")

    server = init(tmp_path, "server")
    add_submodule(server, "webui", at=old)
    server_rust = init(tmp_path, "server-rust")

    bundle = init(tmp_path, "bundle")
    for name in ("server", "server-rust"):
        add_submodule(bundle, name)
    git(bundle, "submodule", "update", "--init", "--recursive", "-q")
    since = short(bundle)

    bump_submodule(server, "webui", to=new)
    add_submodule(server_rust, "webui", at=new)
    for name in ("server", "server-rust"):
        bump_submodule(bundle, name)

    out = render(bundle, since, short(bundle))

    assert "feat(webui): add a button" in out  # what server actually bumped to
    assert "chore: initial commit" not in out  # not webui's history from the start


def test_unresolvable_pointers_are_reported_not_silently_dropped(tmp_path):
    # a checkout that has none of the commits (a shallow clone, say): the repo should
    # still show up saying so, rather than quietly vanishing from the release notes
    repo = changelog.Repo(name="webui")
    repo.pointers.append(
        changelog.Pointer(
            parent="server", path=str(tmp_path), commit_range=("1111111", "2222222")
        )
    )
    repo.pins.append(
        changelog.Pin(parent="server", path=str(tmp_path), commit="2222222")
    )

    out = changelog.summary_repo("Test", repo, FILTER_TYPES)

    assert "## 📦 webui" in out
    assert "Could not resolve" in out


def test_newly_vendored_pin_keeps_the_commits_only_it_has(tmp_path):
    # server bumps webui partway; server-rust adopts webui at a *later* commit, which
    # is the only place that commit ships from — it still belongs in the changelog
    webui = init(tmp_path, "webui")
    old = short(webui)
    middle = commit(webui, "fix(webui): stop the spinner from spinning forever")
    newest = commit(webui, "feat(webui): add a button")

    server = init(tmp_path, "server")
    add_submodule(server, "webui", at=old)
    server_rust = init(tmp_path, "server-rust")

    bundle = init(tmp_path, "bundle")
    for name in ("server", "server-rust"):
        add_submodule(bundle, name)
    git(bundle, "submodule", "update", "--init", "--recursive", "-q")
    since = short(bundle)

    bump_submodule(server, "webui", to=middle)
    add_submodule(server_rust, "webui", at=newest)
    for name in ("server", "server-rust"):
        bump_submodule(bundle, name)

    out = render(bundle, since, short(bundle))

    assert "fix(webui): stop the spinner" in out  # what server bumped to
    assert "feat(webui): add a button" in out  # only server-rust's new pin has it
    assert "chore: initial commit" not in out  # still not the whole history


def test_warning_survives_when_every_commit_is_filtered(tmp_path):
    # the only webui commit this release is a filtered one, and the parents disagree:
    # the section has nothing to list, but the mismatch still has to be reported
    # both parents start on the newest webui, so the release only moves server, and
    # only onto a filtered commit
    bundle = build_tree(tmp_path, server_start=2, rust_start=2)
    bundle["commits"].append(
        commit(bundle["webui"], "build(deps): bump some dependency")
    )
    until = bundle["release"](server_webui=3, rust_webui=2)
    out = render(bundle["path"], bundle["since"], until)

    assert "## 📦 webui" in out
    assert "pin different commits" in out


def test_adoption_alone_does_not_replay_history(tmp_path):
    # server has vendored webui all along and doesn't touch it this release; server-rust
    # adopts webui at a newer commit. Nothing "bumped", but the history still isn't new.
    webui = init(tmp_path, "webui")
    commit(webui, "fix(webui): stop the spinner from spinning forever")
    middle = short(webui)
    newest = commit(webui, "feat(webui): add a button")

    server = init(tmp_path, "server")
    add_submodule(server, "webui", at=middle)
    server_rust = init(tmp_path, "server-rust")

    bundle = init(tmp_path, "bundle")
    for name in ("server", "server-rust"):
        add_submodule(bundle, name)
    git(bundle, "submodule", "update", "--init", "--recursive", "-q")
    since = short(bundle)

    add_submodule(server_rust, "webui", at=newest)
    bump_submodule(bundle, "server-rust")

    out = render(bundle, since, short(bundle))

    assert "chore: initial commit" not in out  # not webui's whole history
    assert "feat(webui): add a button" in out  # what the new pin brings
    assert "pin different commits" in out  # server still ships the older one


def test_uninitialized_submodule_does_not_derail_pin_collection(tmp_path):
    # a deinitialized submodule leaves an empty directory whose git commands answer for
    # the superproject: `git ls-files --stage` there reports the gitlink itself as "./"
    bundle = build_tree(tmp_path)
    until = bundle["release"]()
    git(bundle["path"], "submodule", "deinit", "-f", "-q", "server")

    repos = changelog.collect_repos(
        "bundle", str(bundle["path"]), (bundle["since"], until)
    )
    changelog.collect_pins(str(bundle["path"]), repos, "bundle")

    assert "server" in repos
    assert "./" not in repos  # the superproject's own gitlink, read from inside
