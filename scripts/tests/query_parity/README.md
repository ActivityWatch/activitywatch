# Query parity: aw-server vs aw-server-rust

Runs the same query corpus on aw-server (Python, `aw_query`/`aw_transform` from
aw-core) and aw-server-rust, on identical events, and fails when the normalized
results differ. It also checks invariants on each server's own output (sorting,
no overlap after `union_no_overlap`/`period_union`/`flood`, duration conservation).

- `scenarios.py`: hand-written edge cases (containment, adjacency, zero-duration,
  identical ranges, unsorted input, equal timestamps, DST offsets, fractional
  seconds, period clipping, odd data) and seeded random event sets, including
  window/afk/browser/android buckets for two desktop hosts and a phone.
- `corpus.py`: each shared transform on its own, the aw-client canonical queries
  (`fullDesktopQuery`, `canonicalEvents`, Android) and the aw-webui multidevice query.
- `normalize.py`: drops event ids, parses timestamps to UTC, compares times with a
  2 µs tolerance, and compares unordered results as multisets.
- `known_issues.py` / `known_failures.txt`: current divergences, each linked to an issue.

## Running

Both servers start on free ephemeral ports with `--testing` and a temporary
`HOME`, so a running ActivityWatch install is never touched.

```sh
cargo build --release --bin aw-server --manifest-path aw-server-rust/Cargo.toml
pip install ./aw-core ./aw-client ./aw-server pytest requests
make test-query-parity
```

Point at other builds with `AW_PARITY_RUST_SERVER=/path/to/aw-server` and
`AW_PARITY_PYTHON_SERVER="python -m aw_server"`. Without a server the tests are
skipped, unless `AW_PARITY_REQUIRE=1` (as in CI).

## Known divergences

Cases listed in `known_failures.txt` are strict xfails: the suite is green today,
and when a fix lands in the pinned submodules those cases XPASS and fail the run.
Then regenerate the list:

```sh
python -m pytest scripts/tests/query_parity --update-known-failures
```

It prints any failure that no pattern in `known_issues.py` explains: that is a new
divergence, which needs an issue and a pattern before it goes into the list.
