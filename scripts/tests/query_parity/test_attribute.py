"""Unit tests for attribute.py (no servers needed)."""

from pathlib import Path
from typing import Dict, Iterable

import pytest

from attribute import attribute


def _write(d: Path, runs: Dict[str, Iterable[str]]) -> Path:
    for name, cases in runs.items():
        (d / f"{name}.txt").write_text("".join(c + "\n" for c in cases))
    return d


def test_single_and_combination(tmp_path):
    runs = {
        "base": ["one", "both", "either"],
        "CORE_162": ["both"],
        "CORE_163": ["one", "both"],
        "all": [],
        "all-CORE_162": ["one", "both"],
        "all-CORE_163": ["both"],
    }
    out, problems = attribute(_write(tmp_path, runs), {})
    assert out == {
        "one": "CORE_162",
        "both": "CORE_162,CORE_163",
        "either": "CORE_162|CORE_163",
    }
    assert problems == []


def test_verified_combination_that_fails_is_a_problem(tmp_path):
    # Leave-one-out says CORE_162 and CORE_163 are needed, but running exactly
    # those two shows it isn't enough (it needs CORE_161 or CORE_164 as well).
    runs = {
        "base": ["c"],
        "CORE_161": ["c"],
        "CORE_162": ["c"],
        "CORE_163": ["c"],
        "CORE_164": ["c"],
        "all": [],
        "all-CORE_161": [],
        "all-CORE_162": ["c"],
        "all-CORE_163": ["c"],
        "all-CORE_164": [],
        "CORE_162+CORE_163": ["c"],
    }
    _, problems = attribute(_write(tmp_path, runs), {})
    assert any(p.startswith("underdetermined: c") for p in problems)


def test_passing_superset_with_unneeded_key_is_a_problem(tmp_path):
    # CORE_161+CORE_162+CORE_163 passes, leave-one-out shows CORE_163 isn't
    # needed, and CORE_161+CORE_162 was never run: don't record the superset.
    runs = {
        "base": ["c"],
        "CORE_161": ["c"],
        "CORE_162": ["c"],
        "CORE_163": ["c"],
        "all": [],
        "all-CORE_161": ["c"],
        "all-CORE_162": [],
        "all-CORE_163": [],
        "CORE_161+CORE_162+CORE_163": [],
    }
    _, problems = attribute(_write(tmp_path, runs), {})
    assert any("CORE_162, CORE_163" in p or "runs without" in p for p in problems)


def test_single_and_disjoint_combination(tmp_path):
    # A alone fixes it, and so does B+C (neither alone): record both
    runs = {
        "base": ["c"],
        "CORE_161": [],
        "CORE_162": ["c"],
        "CORE_163": ["c"],
        "all": [],
        "all-CORE_161": [],
        "all-CORE_162": [],
        "all-CORE_163": [],
        "CORE_162+CORE_163": [],
    }
    out, problems = attribute(_write(tmp_path, runs), {})
    assert out["c"] == "CORE_161|CORE_162,CORE_163"
    assert problems == []


def test_redundant_superset_alternative_is_dropped(tmp_path):
    # CORE_163 alone suffices, so "CORE_163 | CORE_161,CORE_163" is just CORE_163
    runs = {
        "base": ["c"],
        "CORE_161": ["c"],
        "CORE_163": [],
        "all": [],
        "all-CORE_161": ["c"],
        "all-CORE_163": ["c"],
    }
    out, problems = attribute(_write(tmp_path, runs), {})
    assert out["c"] == "CORE_163"
    assert problems == []


def test_underdetermined_single_needed_key(tmp_path):
    # c needs A plus either B or C: only all-A fails, but A alone doesn't fix it
    runs = {
        "base": ["c"],
        "CORE_161": ["c"],
        "CORE_162": ["c"],
        "CORE_163": ["c"],
        "all": [],
        "all-CORE_161": ["c"],
        "all-CORE_162": [],
        "all-CORE_163": [],
    }
    out, problems = attribute(_write(tmp_path, runs), {})
    assert out["c"] != "CORE_161"
    assert any(p.startswith("underdetermined: c") for p in problems)


def test_underdetermined_resolved_by_combination_runs(tmp_path):
    # c needs A plus either B or C, and the runs the diagnostic asks for exist
    runs = {
        "base": ["c"],
        "CORE_161": ["c"],
        "CORE_162": ["c"],
        "CORE_163": ["c"],
        "all": [],
        "all-CORE_161": ["c"],
        "all-CORE_162": [],
        "all-CORE_163": [],
        "CORE_161+CORE_162": [],
        "CORE_161+CORE_163": [],
        "CORE_161+CORE_162+CORE_163": [],
    }
    out, problems = attribute(_write(tmp_path, runs), {})
    assert out["c"] == "CORE_161,CORE_162|CORE_161,CORE_163"
    assert problems == []


def test_residual_keeps_alternatives(tmp_path):
    runs = {
        "base": ["c"],
        "CORE_162": ["c"],
        "all": ["c"],
        "all-CORE_162": ["c"],
    }
    out, problems = attribute(_write(tmp_path, runs), {"c": "SHAPE|CORE_162,PRECISION"})
    assert out["c"] == "SHAPE|PRECISION"
    assert problems == []


def test_residual_with_only_fixed_keys_is_a_problem(tmp_path):
    runs = {"base": ["c"], "CORE_162": ["c"], "all": ["c"], "all-CORE_162": ["c"]}
    _, problems = attribute(_write(tmp_path, runs), {"c": "CORE_162"})
    assert any(p.startswith("unexplained: c") for p in problems)


@pytest.mark.parametrize(
    "runs",
    [
        {},  # nothing at all (e.g. a mistyped directory)
        {"base": [], "CORE_162": [], "all": [], "all-CORE_162": []},  # empty base
        {"base": ["c"], "all": []},  # no fixes
        {"base": ["c"], "CORE_162": [], "all": []},  # leave-one-out run missing
        {"base": ["c"], "CORE_162": [], "all-CORE_162": ["c"]},  # all.txt missing
        {  # all-<KEY> without <KEY>
            "base": ["c"],
            "CORE_162": [],
            "all": [],
            "all-CORE_162": ["c"],
            "all-CORE_163": ["c"],
        },
        {"base": ["c"], "CORE_999": [], "all": []},  # not an ISSUES key
    ],
    ids=[
        "missing",
        "empty-base",
        "no-fixes",
        "no-loo",
        "no-all",
        "orphan-loo",
        "bad-key",
    ],
)
def test_refuses_incomplete_results(tmp_path, runs):
    with pytest.raises(SystemExit):
        attribute(_write(tmp_path, runs), {})
