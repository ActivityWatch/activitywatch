import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import textwrap

import pytest

ROOT = Path(__file__).parents[2]
CONFIGURE = ROOT / "scripts/package/configure_tauri_release.py"
GENERATOR = ROOT / "scripts/package/generate_latest_json.py"
RESEARCH_ENDPOINT = (
    "https://raw.githubusercontent.com/ActivityWatch/activitywatch/"
    "research-updates/latest-research.json"
)

sys.path.insert(0, str(ROOT / "scripts/package"))
from configure_tauri_release import configure, msi_rejects  # noqa: E402


def key(material=b"r" * 32, comment="fixture", key_id=b"i" * 8):
    packet = base64.b64encode(b"Ed" + key_id + material).decode()
    return base64.b64encode(
        f"untrusted comment: {comment}\n{packet}\n".encode()
    ).decode()


@pytest.fixture
def config(tmp_path):
    # Exercise the real pinned Tauri config, including its standard public key.
    source = ROOT / "aw-tauri/src-tauri/tauri.conf.json"
    assert source.exists(), "Initialize the aw-tauri submodule before these tests"
    path = tmp_path / "tauri.conf.json"
    path.write_bytes(source.read_bytes())
    return path


def run_configure(config, *args, public="", private="", version="v0.14.0b5-research"):
    env = dict(
        os.environ,
        TAURI_UPDATER_PUBLIC_KEY_RESEARCH=public,
        TAURI_SIGNING_PRIVATE_KEY=private,
    )
    return subprocess.run(
        [
            sys.executable,
            str(CONFIGURE),
            "--config",
            str(config),
            "--version",
            version,
            *args,
        ],
        env=env,
        text=True,
        capture_output=True,
    )


@pytest.mark.parametrize(
    "version,rejects",
    [
        ("0.14.0", False),
        ("0.14.0-5", False),
        ("0.14.0-beta.5", True),
        ("0.14.0-dev.gabc1234", True),
        ("0.14.0-rc.1", True),
    ],
)
def test_msi_rejects(version, rejects):
    assert msi_rejects(version) is rejects


def test_windows_drops_msi_for_non_numeric_prerelease(config):
    # v0.14.0b5 -> "0.14.0-beta.5", which the msi (WiX) bundler rejects.
    configure(
        config, "v0.14.0b5", research=False, require_signing_key=False, platform="win32"
    )
    after = json.loads(config.read_text())
    assert after["version"] == "0.14.0-beta.5"
    assert after["bundle"]["targets"] == ["nsis"]


def test_non_windows_keeps_all_targets_for_non_numeric_prerelease(config):
    configure(
        config,
        "v0.14.0b5",
        research=False,
        require_signing_key=False,
        platform="darwin",
    )
    after = json.loads(config.read_text())
    assert after["bundle"]["targets"] == "all"


def test_windows_keeps_all_targets_for_msi_safe_version(config):
    configure(
        config, "v0.14.0", research=False, require_signing_key=False, platform="win32"
    )
    after = json.loads(config.read_text())
    assert after["version"] == "0.14.0"
    assert after["bundle"]["targets"] == "all"


def test_standard_version_changes_without_changing_update_trust(config):
    before = json.loads(config.read_text())
    result = run_configure(config, version="v0.14.0rc2")
    assert result.returncode == 0, result.stderr
    after = json.loads(config.read_text())
    assert after["version"] == "0.14.0-rc.2"
    before["version"] = after["version"]
    assert after == before


def test_research_release_replaces_endpoint_and_key(config):
    result = run_configure(
        config,
        "--research",
        "--require-signing-key",
        public=key(),
        private="fixture-secret-presence-only",
    )
    assert result.returncode == 0, result.stderr
    after = json.loads(config.read_text())
    assert after["version"] == "0.14.0-beta.5"
    assert after["plugins"]["updater"]["endpoints"] == [RESEARCH_ENDPOINT]
    assert after["plugins"]["updater"]["pubkey"] == key()


def test_secretless_research_smoke_build_has_no_update_trust(config):
    result = run_configure(config, "--research")
    assert result.returncode == 0, result.stderr
    updater = json.loads(config.read_text())["plugins"]["updater"]
    assert updater["endpoints"] == []
    assert updater["pubkey"] == ""


@pytest.mark.parametrize("public,private", [("", ""), (key(), ""), ("", "secret")])
def test_release_missing_either_key_fails_without_modifying_config(
    config, public, private
):
    before = config.read_bytes()
    result = run_configure(
        config, "--research", "--require-signing-key", public=public, private=private
    )
    assert result.returncode != 0
    assert "require their own public and signing keys" in result.stderr
    assert config.read_bytes() == before


@pytest.mark.parametrize("change_envelope", [False, True])
def test_same_standard_key_rejected_even_with_changed_comment_and_id(
    config, change_envelope
):
    before = config.read_bytes()
    standard = json.loads(before)["plugins"]["updater"]["pubkey"]
    if change_envelope:
        packet = base64.b64decode(base64.b64decode(standard).decode().splitlines()[1])
        standard = key(packet[10:], comment="research", key_id=b"j" * 8)
    result = run_configure(config, "--research", public=standard)
    assert result.returncode != 0
    assert "must differ" in result.stderr
    assert config.read_bytes() == before


@pytest.mark.parametrize("bad_key", ["bad-base64", "dGVzdA==", key(b"short")])
def test_malformed_public_key_rejected(config, bad_key):
    before = config.read_bytes()
    result = run_configure(config, "--research", public=bad_key)
    assert result.returncode != 0
    assert config.read_bytes() == before


def test_endpoint_drift_fails_closed(config):
    data = json.loads(config.read_text())
    data["plugins"]["updater"]["endpoints"].append("https://example.com/latest.json")
    config.write_text(json.dumps(data))
    before = config.read_bytes()
    result = run_configure(config, "--research", public=key())
    assert result.returncode != 0
    assert "Unexpected source updater endpoint" in result.stderr
    assert config.read_bytes() == before


@pytest.mark.parametrize(
    "event,ref,research,success",
    [
        ("push", "refs/tags/v0.14.0b5-research", "true", False),
        ("workflow_dispatch", "refs/heads/master", "true", False),
        ("pull_request", "refs/pull/1/merge", "true", True),
        ("push", "refs/heads/master", "true", True),
        ("push", "refs/tags/v0.14.0", "false", True),
    ],
)
def test_workflow_requires_keys_only_for_publishable_research_builds(
    config,
    event,
    ref,
    research,
    success,
):
    workflow = (ROOT / ".github/workflows/release.yml").read_text()
    step = workflow.split(
        "      - name: Configure Tauri release version and update channel\n"
    )[1]
    script = textwrap.dedent(
        step.split("        run: |\n")[1].split("        env:\n")[0]
    )
    work = config.parent / "build"
    shutil.copytree(ROOT / "scripts/package", work / "scripts/package")
    target = work / "aw-tauri/src-tauri/tauri.conf.json"
    target.parent.mkdir(parents=True)
    shutil.copyfile(config, target)
    env = dict(
        os.environ,
        AW_RESEARCH_EDITION=research,
        GITHUB_REF=ref,
        GITHUB_EVENT_NAME=event,
        VERSION_NO_V="0.14.0b5",
        TAURI_UPDATER_PUBLIC_KEY_RESEARCH="",
        TAURI_SIGNING_PRIVATE_KEY="",
    )
    result = subprocess.run(
        ["bash", "-e", "-c", script], cwd=work, env=env, text=True, capture_output=True
    )
    assert (result.returncode == 0) == success, result.stderr
    if success and research == "true":
        assert json.loads(target.read_text())["plugins"]["updater"]["endpoints"] == []
    if not success:
        assert target.read_bytes() == config.read_bytes()


@pytest.mark.parametrize("edition", ["standard", "research"])
def test_manifest_and_compiled_config_share_version_and_partition_assets(
    config, edition
):
    tag = "v0.14.0b5" + ("-research" if edition == "research" else "")
    result = run_configure(
        config,
        *(["--research"] if edition == "research" else []),
        version=tag,
        public=key(),
    )
    assert result.returncode == 0, result.stderr
    for token in ("", "-research"):
        bundle = (
            config.parent / f"activitywatch-tauri{token}-0.14.0b5-linux-x86_64.AppImage"
        )
        bundle.write_bytes(b"fixture, not a cryptographic verification")
        bundle.with_suffix(".AppImage.sig").write_text("sig" + token)
    output = config.parent / (
        "latest-research.json" if edition == "research" else "latest.json"
    )
    result = subprocess.run(
        [
            sys.executable,
            str(GENERATOR),
            "--version",
            tag,
            "--tag",
            tag,
            "--edition",
            edition,
            "--repo",
            "ActivityWatch/activitywatch",
            "--notes",
            "fixture",
            "--dist",
            str(config.parent),
            "--output",
            str(output),
        ],
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    manifest = json.loads(output.read_text())
    assert (
        manifest["version"]
        == json.loads(config.read_text())["version"]
        == "0.14.0-beta.5"
    )
    assert list(manifest["platforms"]) == ["linux-x86_64"]
    target = manifest["platforms"]["linux-x86_64"]
    assert ("-research" in target["url"]) == (edition == "research")
    assert f"/releases/download/{tag}/" in target["url"]
    assert target["signature"] == "sig" + ("-research" if edition == "research" else "")
