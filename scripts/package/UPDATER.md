# Tauri release configuration

`release.yml` runs `configure_tauri_release.py` before compiling aw-tauri.
It writes the release version to `aw-tauri/src-tauri/tauri.conf.json`, which
Tauri embeds as its package version. `generate_latest_json.py` uses the same
`tauri_version()` conversion for the manifest: `v0.14.0b5` becomes
`0.14.0-beta.5`. Original AW spellings remain in asset filenames and tag URLs.
Development builds also receive a SemVer version, with a `dev.g<hash>` suffix.

The standard build keeps its checked-in updater endpoint and public key.
Research builds use only:

```text
https://raw.githubusercontent.com/ActivityWatch/activitywatch/research-updates/latest-research.json
```

Configure these repository settings before a research tag or manual build:

| Setting | Purpose |
| --- | --- |
| Variable `TAURI_UPDATER_PUBLIC_KEY_RESEARCH` | Base64-encoded minisign public-key file emitted by Tauri's signer |
| Secret `TAURI_SIGNING_PRIVATE_KEY_RESEARCH` | Research-only signing key in Tauri's expected format |
| Secret `TAURI_SIGNING_PRIVATE_KEY_PASSWORD_RESEARCH` | Password for that key (empty for an unencrypted key) |

The workflow selects secret **names** by edition. A missing research secret
never falls back to a standard secret. The configurator rejects a research
public key containing the standard key material, even if its comment or key
ID differs. Research tag/manual builds fail if either key is missing.
Secretless research PR smoke builds clear both updater endpoints and the
public key. They cannot consume the standard channel.

`aw-tauri/Makefile` enables `bundle.createUpdaterArtifacts` by passing a
`--config` override to the Tauri build when `TAURI_SIGNING_PRIVATE_KEY` is
present. That setting is therefore absent from the checked-in JSON even
though release builds produce signatures. Both the initial build and the
research-profile rebuild receive the edition's selected signing key.

## Release acceptance still required

This configuration does not create the `research-updates` branch, publish
its manifest, verify that a private key matches the configured public key,
or change any already installed client. Before offering an update:

- Provision the channel and verify its public URL. Publish only a complete,
  verified manifest after its versioned release is public; use a normal
  fast-forward commit with an expected parent and a monotonic version check
  so a late release job cannot overwrite a newer feed.
- Verify actual bundle signatures with the research key and reject standard
  signatures. Config/fixture checks alone are insufficient.
- Verify the built app's version, equal-version no-update, one newer-version
  upgrade, and no repeated offer after restart. Both versions must preserve
  the research profile, privacy defaults, install identity, and bundled
  watchers/aw-sync. Native updater bundles and full AW packages require a
  payload-equivalence check.
- Replace or verifiably contain any already distributed research app that
  embedded the standard endpoint/key **before publishing a valid standard
  stable manifest**. A future configuration cannot repair an installed app.

The pipeline creates a draft versioned release. Its `latest-research.json`
asset is distinct from the live branch feed; uploading the asset does not
advance that feed. Do not publish the draft until these gates are satisfied.

## Focused checks

Initialize the pinned `aw-tauri` submodule, then run:

```sh
python3 -m pytest scripts/tests/test_generate_latest_json.py scripts/tests/test_configure_tauri_release.py -q
```

These tests execute both CLIs against the pinned config, exercise missing and
same-key rejection, preserve standard trust, and check both directions of
asset partitioning. Dummy signatures in these fixtures do not prove signing
or installation.
