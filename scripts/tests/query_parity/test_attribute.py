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
    runs = {
        "base": ["c"],
        "CORE_162": ["c"],
        "CORE_163": ["c"],
        "all": [],
        "all-CORE_162": ["c"],
        "all-CORE_163": ["c"],
        "CORE_162+CORE_163": ["c"],
    }
    _, problems = attribute(_write(tmp_path, runs), {})
    assert any(p.startswith("underdetermined: c") for p in problems)


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
