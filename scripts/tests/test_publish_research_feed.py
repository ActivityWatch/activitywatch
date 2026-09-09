"""Release fixtures and real local Git remotes; never contact the public feed."""

import importlib.util
import json
from pathlib import Path
import subprocess

import pytest

SCRIPT = Path(__file__).parents[1] / "package" / "publish_research_feed.py"
spec = importlib.util.spec_from_file_location("publish_research_feed", SCRIPT)
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)


def fixture(beta=5):
    tag = f"v0.14.0b{beta}-research"
    base = f"https://github.com/ActivityWatch/activitywatch/releases/download/{tag}/"
    manifest = {
        "version": f"0.14.0-beta.{beta}",
        "notes": tag,
        "pub_date": "2026-09-09T00:00:00Z",
        "platforms": {},
    }
    release = {
        "tag_name": tag,
        "draft": False,
        "immutable": True,
        "published_at": "2026-09-09T00:00:00Z",
        "assets": [],
    }
    for target, extensions in publisher.TARGETS.items():
        name = f"activitywatch-tauri-research-0.14.0b{beta}-{target}.{extensions[0]}"
        manifest["platforms"][target] = {
            "url": base + name,
            "signature": "test-signature",
        }
        for asset in (name, name + ".sig"):
            release["assets"].append(
                {
                    "name": asset,
                    "state": "uploaded",
                    "size": 42,
                    "browser_download_url": base + asset,
                }
            )
    return manifest, release, tag


def validate(manifest, release, tag):
    publisher.validate_manifest(manifest, release, tag, lambda _: b"test-signature\n")


def test_valid_research_release():
    validate(*fixture())


@pytest.mark.parametrize(
    "mutation",
    [
        lambda m, r: m.update(pub_date="not a date"),
        lambda m, r: m.update(pub_date="2026-09-09T00:00:00+00:99"),
        lambda m, r: m.update(pub_date="2026-02-30T00:00:00Z"),
        lambda m, r: m.update(pub_date="2026-09-09T00:00:00"),
        lambda m, r: m.update(notes=123),
        lambda m, r: m.update(name="0.14.0-beta.6"),
        lambda m, r: m.update(url=123),
        lambda m, r: m["platforms"]["darwin-aarch64"].update(extra="unexpected"),
        lambda m, r: r.update(immutable=False),
        lambda m, r: r.pop("immutable"),
        lambda m, r: r.update(draft=True),
        lambda m, r: r.update(draft="false"),
        lambda m, r: r.update(published_at=None),
        lambda m, r: r.update(tag_name="v0.14.0b4-research"),
        lambda m, r: r["assets"].pop(0),  # bundle absent
        lambda m, r: r["assets"].pop(1),  # signature absent
        lambda m, r: r["assets"][0].update(size=0),
        lambda m, r: r["assets"][0].update(state="new"),
        lambda m, r: r["assets"][1].update(
            browser_download_url="https://example.com/signature"
        ),
        lambda m, r: r["assets"].append(r["assets"][0]),
        lambda m, r: m.update(version="0.14.0b5"),
        lambda m, r: m.update(version="0.14.0-beta.6"),
        lambda m, r: m["platforms"].pop("darwin-x86_64"),
        lambda m, r: m["platforms"].update({"unsupported-platform": {}}),
        lambda m, r: m["platforms"]["darwin-aarch64"].update(signature=""),
        lambda m, r: m["platforms"]["darwin-aarch64"].update(signature="wrong"),
    ],
)
def test_invalid_release_or_manifest(mutation):
    manifest, release, tag = fixture()
    mutation(manifest, release)
    with pytest.raises(ValueError):
        validate(manifest, release, tag)


@pytest.mark.parametrize(
    "replacement",
    [
        ("v0.14.0b5-research/", "v0.14.0b4-research/"),
        ("v0.14.0b5-research/", "v0.14.0b5/"),
        ("activitywatch-tauri-research-", "activitywatch-tauri-"),
        ("research-0.14.0b5-", "research-0.14.0b4-"),
        (".app.tar.gz", ".dmg"),
        ("https://github.com/", "https://example.com/"),
    ],
)
def test_wrong_edition_release_version_or_extension(replacement):
    manifest, release, tag = fixture()
    entry = manifest["platforms"]["darwin-aarch64"]
    entry["url"] = entry["url"].replace(*replacement)
    # Even if metadata claims this asset exists, it is not an allowed URL.
    release["assets"][0]["browser_download_url"] = entry["url"]
    with pytest.raises(ValueError):
        validate(manifest, release, tag)


@pytest.mark.parametrize(
    "tag",
    [
        "v0.14.0b5",
        "latest-research",
        "v0.14.0b05-research",
        "v0.14.0b5.dev-abcdef-research",
        "v0.14.0b5-research/other",
    ],
)
def test_invalid_release_tag(tag):
    manifest, release, _ = fixture()
    with pytest.raises(ValueError):
        validate(manifest, release, tag)


@pytest.fixture
def remote(tmp_path, monkeypatch):
    config = tmp_path / "gitconfig"
    config.write_text("[user]\nname = Publisher test\nemail = test@example.invalid\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    # Isolate test repositories from any enclosing harness Git invocation.
    for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        monkeypatch.delenv(name, raising=False)
    remote = tmp_path / "remote.git"
    remote.mkdir()
    publisher.git(remote, "init", "--bare", "--quiet")
    return str(remote)


def candidate(tmp_path, remote, name, parent="absent", beta=5):
    repo = tmp_path / name
    manifest = fixture(beta)[0]
    commit = publisher.prepare(repo, remote, parent, manifest)
    return repo, commit


def test_initial_preparation_does_not_publish(tmp_path, remote):
    repo, commit = candidate(tmp_path, remote, "candidate")
    assert publisher.remote_parent(repo, remote) == "absent"
    assert publisher.git(repo, "rev-list", "--parents", "-n", "1", commit) == commit
    assert json.loads((repo / publisher.MANIFEST).read_text()) == fixture()[0]
    publisher.publish(repo, remote, "absent", commit)
    assert publisher.remote_parent(repo, remote) == commit


def test_advance_preserves_history_and_unrelated_files(tmp_path, remote):
    repo, first = candidate(tmp_path, remote, "first")
    (repo / "README.md").write_text("Feed history\n")
    publisher.git(repo, "add", "README.md")
    publisher.git(repo, "commit", "-m", "Document feed")
    parent = publisher.git(repo, "rev-parse", "HEAD")
    publisher.git(repo, "push", remote, f"{parent}:{publisher.REF}")
    new_repo, second = candidate(tmp_path, remote, "second", parent, 6)
    publisher.publish(new_repo, remote, parent, second)
    assert publisher.git(new_repo, "rev-parse", f"{second}^") == parent
    assert publisher.git(new_repo, "rev-parse", f"{second}^^") == first
    assert (new_repo / "README.md").read_text() == "Feed history\n"


def test_replay_is_noop_and_conflicting_equal_version_rejected(tmp_path, remote):
    repo, first = candidate(tmp_path, remote, "first")
    publisher.publish(repo, remote, "absent", first)
    _, repeated = candidate(tmp_path, remote, "replay", first)
    assert repeated is None
    different = fixture()[0]
    different["notes"] = "changed"
    with pytest.raises(ValueError, match="Conflicting"):
        publisher.prepare(tmp_path / "conflict", remote, first, different)
    assert publisher.remote_parent(repo, remote) == first


def test_late_b5_cannot_replace_b6(tmp_path, remote):
    repo, first = candidate(tmp_path, remote, "b6", beta=6)
    publisher.publish(repo, remote, "absent", first)
    with pytest.raises(ValueError, match="regression"):
        candidate(tmp_path, remote, "late-b5", first, 5)


def test_numeric_semver_order(tmp_path, remote):
    repo, first = candidate(tmp_path, remote, "b9", beta=9)
    publisher.publish(repo, remote, "absent", first)
    new_repo, second = candidate(tmp_path, remote, "b10", first, 10)
    publisher.publish(new_repo, remote, first, second)
    assert publisher.remote_parent(repo, remote) == second


@pytest.mark.parametrize("provision", [False, True])
def test_same_parent_race_and_retry_revalidates_order(tmp_path, remote, provision):
    parent = "absent"
    if not provision:
        repo, parent = candidate(tmp_path, remote, "seed", beta=4)
        publisher.publish(repo, remote, "absent", parent)
    slow_repo, slow = candidate(tmp_path, remote, "slow", parent, 5)
    fast_repo, fast = candidate(tmp_path, remote, "fast", parent, 6)
    publisher.publish(fast_repo, remote, parent, fast)
    with pytest.raises(subprocess.CalledProcessError):
        publisher.publish(slow_repo, remote, parent, slow)
    assert publisher.remote_parent(fast_repo, remote) == fast
    with pytest.raises(ValueError, match="Stale"):
        candidate(tmp_path, remote, "stale", parent, 5)
    with pytest.raises(ValueError, match="regression"):
        candidate(tmp_path, remote, "retry", fast, 5)


def test_deleted_parent_cannot_be_silently_recreated(tmp_path, remote):
    repo, parent = candidate(tmp_path, remote, "seed")
    publisher.publish(repo, remote, "absent", parent)
    new_repo, second = candidate(tmp_path, remote, "second", parent, 6)
    # Simulate an administrator's intervening ref deletion, not publisher behavior.
    publisher.git(Path(remote), "update-ref", "-d", publisher.REF)
    with pytest.raises(subprocess.CalledProcessError, match="returned non-zero"):
        publisher.publish(new_repo, remote, parent, second)
    assert publisher.remote_parent(repo, remote) == "absent"


def test_rewound_parent_is_rejected_even_when_push_would_fast_forward(tmp_path, remote):
    repo, first = candidate(tmp_path, remote, "first", beta=4)
    publisher.publish(repo, remote, "absent", first)
    second_repo, second = candidate(tmp_path, remote, "second", first, 5)
    publisher.publish(second_repo, remote, first, second)
    third_repo, third = candidate(tmp_path, remote, "third", second, 6)
    publisher.git(Path(remote), "update-ref", publisher.REF, first)
    with pytest.raises(subprocess.CalledProcessError):
        publisher.publish(third_repo, remote, second, third)
    assert publisher.remote_parent(repo, remote) == first


def test_existing_pre_push_hook_is_preserved(tmp_path, remote):
    repo, commit = candidate(tmp_path, remote, "candidate")
    hooks = tmp_path / "hooks"
    hooks.mkdir()
    sentinel = tmp_path / "hook-ran"
    hook = hooks / "pre-push"
    hook.write_text(f'#!/bin/sh\ncat > "{sentinel}"\nexit 1\n')
    hook.chmod(0o755)
    publisher.git(repo, "config", "core.hooksPath", str(hooks))
    with pytest.raises(subprocess.CalledProcessError):
        publisher.publish(repo, remote, "absent", commit)
    assert commit in sentinel.read_text()
    assert publisher.remote_parent(repo, remote) == "absent"


def test_prepare_rejects_existing_workdir(tmp_path, remote):
    repo = tmp_path / "owned"
    repo.mkdir()
    (repo / "precious").write_text("keep")
    with pytest.raises(FileExistsError):
        publisher.prepare(repo, remote, "absent", fixture()[0])
    assert (repo / "precious").read_text() == "keep"


def test_cli_validates_before_prepare(tmp_path, monkeypatch):
    manifest, release, tag = fixture()
    manifest["platforms"].pop("linux-aarch64")
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    monkeypatch.setattr(
        publisher, "public_bytes", lambda _: json.dumps(release).encode()
    )
    work = tmp_path / "candidate"
    with pytest.raises(SystemExit) as error:
        publisher.main(
            [
                "--manifest",
                str(path),
                "--tag",
                tag,
                "--expected-parent",
                "absent",
                "--work-dir",
                str(work),
            ]
        )
    assert error.value.code == 1
    assert not work.exists()


def test_receive_side_rejects_race_after_parent_was_advertised(tmp_path, remote):
    repo, first = candidate(tmp_path, remote, "seed", beta=4)
    publisher.publish(repo, remote, "absent", first)
    slow_repo, slow = candidate(tmp_path, remote, "slow", first, 5)
    fast_repo, fast = candidate(tmp_path, remote, "fast", first, 6)
    # Put the competing commit object on the remote without moving the feed yet.
    publisher.git(fast_repo, "push", remote, f"{fast}:refs/heads/competing")
    hooks = tmp_path / "race-hooks"
    hooks.mkdir()
    hook = hooks / "pre-push"
    hook.write_text(
        f'#!/bin/sh\ngit -C "{remote}" update-ref {publisher.REF} {fast} {first}\n'
    )
    hook.chmod(0o755)
    publisher.git(slow_repo, "config", "core.hooksPath", str(hooks))
    with pytest.raises(subprocess.CalledProcessError):
        publisher.publish(slow_repo, remote, first, slow)
    assert publisher.remote_parent(repo, remote) == fast


@pytest.mark.parametrize("do_publish", [False, True])
def test_cli_public_checks_and_explicit_publish_flag(
    tmp_path, remote, monkeypatch, capsys, do_publish
):
    manifest, release, tag = fixture()
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    urls = []

    def public(url):
        urls.append(url)
        return (
            json.dumps(release).encode()
            if url.startswith("https://api.github.com/")
            else b"test-signature\n"
        )

    real_git = publisher.git

    def local_git(repo, *args, **kwargs):
        return real_git(
            repo,
            *(
                remote
                if arg == "https://github.com/ActivityWatch/activitywatch.git"
                else arg
                for arg in args
            ),
            **kwargs,
        )

    monkeypatch.setattr(publisher, "public_bytes", public)
    monkeypatch.setattr(publisher, "git", local_git)
    work = tmp_path / "candidate"
    args = [
        "--manifest",
        str(path),
        "--tag",
        tag,
        "--expected-parent",
        "absent",
        "--work-dir",
        str(work),
    ]
    if do_publish:
        args.append("--publish")
    publisher.main(args)
    result = capsys.readouterr().out
    assert result.startswith("Published" if do_publish else "Prepared")
    assert len(urls) == 6  # public release metadata and all five public signatures
    assert (publisher.remote_parent(work, remote) != "absent") == do_publish


def test_failed_public_signature_read_leaves_no_candidate(
    tmp_path, remote, monkeypatch
):
    manifest, release, tag = fixture()
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))

    def public(url):
        if url.startswith("https://api.github.com/"):
            return json.dumps(release).encode()
        raise OSError("signature HTTP 404")

    monkeypatch.setattr(publisher, "public_bytes", public)
    work = tmp_path / "candidate"
    with pytest.raises(SystemExit) as error:
        publisher.main(
            [
                "--manifest",
                str(path),
                "--tag",
                tag,
                "--expected-parent",
                "absent",
                "--work-dir",
                str(work),
                "--publish",
            ]
        )
    assert error.value.code == 1
    assert not work.exists()
