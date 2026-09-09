# Research updater feed publisher

`publish_research_feed.py` prepares an ordinary commit of
`latest-research.json` on the `research-updates` branch. It preserves branch
history and existing files. The default invocation changes only a new local
checkout. `--publish` explicitly enables the remote update.

This command is manual. There is no release-published trigger. Before live
use, the release owner must verify research signing keys, bundle contents,
installed-app upgrades, and the disposition of older research clients that
still contain the standard updater endpoint/key. The publisher does not prove
those properties or enable an update channel in an installed client.

## Prepare and review

Requires Git, a configured Git author, and `uv` (the script declares its
`semver` dependency). Run from the ActivityWatch checkout, using a new output
directory for each attempt:

```sh
REPO_ROOT=$(git rev-parse --show-toplevel)
TAG=v0.14.0b6-research
MANIFEST=/absolute/path/to/reviewed/latest-research.json
CANDIDATE=/absolute/path/to/new-feed-candidate

# Read the current remote head. Use the literal 'absent' only if this
# succeeds and returns no matching ref (initial provisioning).
git ls-remote --refs https://github.com/ActivityWatch/activitywatch.git \
  refs/heads/research-updates
PARENT=<full-sha-from-the-output>

uv run --script "$REPO_ROOT/scripts/package/publish_research_feed.py" \
  --tag "$TAG" --manifest "$MANIFEST" --expected-parent "$PARENT" \
  --work-dir "$CANDIDATE"

git -C "$CANDIDATE" show HEAD
```

The supplied manifest must already use normalized SemVer, for example
`0.14.0-beta.6`. Tags and asset filenames retain their release spelling
(`v0.14.0b6-research` / `activitywatch-tauri-research-0.14.0b6-…`).
This publisher accepts stable and a/b/rc research tags, not development builds.
Build/app version normalization is owned by the release configuration work;
this command validates the tag/version association without modifying builds.

Validation requires:

- An unauthenticated GitHub API read of the exact published, immutable,
  non-draft research release.
- All five release targets: macOS arm64/x86_64, Linux arm64/x86_64, and Windows
  x86_64. A reduced platform rollout requires an explicit code review.
- A supported updater bundle and nonempty uploaded `.sig` asset for each
  platform, under the exact selected release and research filename prefix.
- The manifest signature must equal the publicly downloaded `.sig` contents.
  Cryptographic signature verification and embedded payload-version/edition
  verification remain release-owner gates; this command does not download
  the potentially large bundles.
- A valid static updater manifest, with RFC3339 publication date and string
  notes. Unknown fields are refused to avoid alternate updater parsing paths.

## Publish after release acceptance

After reviewing the candidate and satisfying the release gates, rerun the
same invocation with a **new** work directory and `--publish`. It repeats all
release checks and compares the feed's current SemVer before committing.
Git's configured credentials authorize the push; public release reads do not
use those credentials. Keep the recorded parent unchanged; a stale parent is
an error, not permission to overwrite new work.

An older version is refused. Equal SemVer precedence with different content
(including metadata/build-identifier changes) is refused. Identical parsed
manifest content is an explicit no-op. Formatting/key order differences alone
do not mint another commit. A changed release needs a higher version.

The publisher checks the remote parent at fetch and in pre-push against Git's
advertised OID, then pushes normally without force. Git's receive-side old-OID
check closes the remaining race. The wrapper invokes any existing pre-push
hook with the original arguments/stdin and preserves its refusal. Concurrent
creation, advancement, deletion, or rewind requires a fresh invocation with a
reread parent; version ordering is evaluated again, so a late b5 job cannot
replace b6 even after retry. Failed candidates remain on disk for inspection.

After a successful push, verify the public feed separately:
`https://raw.githubusercontent.com/ActivityWatch/activitywatch/research-updates/latest-research.json`.
A Git push alone does not prove CDN freshness or a successful installed update.
Standard release publication does not invoke this command or change this branch.

## Tests

```sh
uv run --with pytest --with 'semver>=3,<4' python3 -m pytest \
  "$REPO_ROOT/scripts/tests/test_publish_research_feed.py" -q
```

The tests use release fixtures and temporary local Git remotes. They cover
provisioning, advancement, replay, rollback refusal, racing publishers,
branch deletion/rewind, incomplete releases, metadata validation, and existing
push-hook enforcement. They never publish to GitHub.
