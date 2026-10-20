"""The bundle identity must reach the Tauri compile, not only its config."""

import os
from pathlib import Path
import subprocess

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("version", ["v0.14.2", "v0.14.0b5", "v0.14.0b5-research"])
def test_tauri_build_receives_original_bundle_version(tmp_path, version):
    workflow = yaml.safe_load((ROOT / ".github/workflows/release.yml").read_text())
    jobs = [
        job
        for job in workflow["jobs"].values()
        if job.get("env", {}).get("TAURI_BUILD") is True
    ]
    assert len(jobs) == 1
    steps = jobs[0]["steps"]
    determine = next(
        step for step in steps if step.get("name") == "Determine and output version"
    )
    build = next(step for step in steps if step.get("name") == "Build")
    assert steps.index(determine) < steps.index(build)
    script = tmp_path / "scripts/package/getversion.sh"
    script.parent.mkdir(parents=True)
    script.write_text(f"printf '%s\\n' '{version}'\n")
    output = tmp_path / "github-env"
    # These two expressions are diagnostic echo statements, not version inputs.
    command = (
        determine["run"]
        .replace("${{ github.ref }}", "refs/tags/" + version)
        .replace("${{ github.ref_name }}", version)
    )
    subprocess.run(
        ["bash", "-e", "-c", command],
        cwd=tmp_path,
        env=dict(os.environ, GITHUB_ENV=str(output)),
        check=True,
    )
    exported = dict(line.split("=", 1) for line in output.read_text().splitlines())
    assert exported["AW_VERSION"] == version
    assert exported["VERSION_WITH_V"] == version.removesuffix("-research")
    assert "make build" in build["with"]["command"]
    # Job/step environment does not shadow the GITHUB_ENV input before make.
    assert "AW_VERSION" not in jobs[0].get("env", {})
    assert "AW_VERSION" not in build.get("env", {})
