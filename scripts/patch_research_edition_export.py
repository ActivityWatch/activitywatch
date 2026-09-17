#!/usr/bin/env python3
"""Patch aw-server-rust's export path for the Research Edition build.

Run as part of the CI build for research edition:

    python3 scripts/patch_research_edition_export.py [repo-root]

Standard builds never run this script, so `/api/0/export` stays byte-for-byte
unchanged outside Research Edition. The patch is fail-closed: missing markers
abort the build rather than shipping an unsanitized artifact.

Where the sanitizer hooks in: since aw-server-rust#677 the export is streamed
by `aw_datastore::export_to_file` with bounded event buffering, and both
`/api/0/export` and `/api/0/buckets/<id>/export` are one-line calls to
`BucketsExportRocket::new` in `endpoints/util.rs`. No whole `BucketsExport`
value exists at the endpoints any more, so the sanitizer — which needs the
whole export to fail closed on unfiltered events and to detect identity
collisions across buckets — is spliced into `BucketsExportRocket::new`: the
spooled JSON is re-read, sanitized, and spooled again. Research exports are
category-only, so this relaxes the streaming memory bound only where the
data is already small.
"""
from __future__ import annotations

import pathlib
import shutil
import sys

MARKER = "RESEARCH_EDITION_EXPORT_SANITIZE"

# The two lines in BucketsExportRocket::new that spool the export and rewind
# it. The sanitizer is inserted right after them and shadows `file`.
EXPORT_INSERT_NEEDLE = """        let (mut file, name) = datastore.export_to_file(bucket_id, file)?;
        file.seek(SeekFrom::Start(0)).map_err(io_error)?;
"""

EXPORT_INSERT_REPLACEMENT = f"""        let (mut file, name) = datastore.export_to_file(bucket_id, file)?;
        file.seek(SeekFrom::Start(0)).map_err(io_error)?;
        // {MARKER}
        // The datastore streams the export with bounded event buffering, so no
        // whole `BucketsExport` exists here. The Research Edition sanitizer
        // needs one (fail closed on unfiltered events, identity rewriting with
        // collision detection across buckets): re-read the spooled JSON,
        // sanitize, and spool again. Research exports are category-only, so
        // this relaxes the memory bound only where the data is already small.
        let file = {{
            let export: aw_models::BucketsExport =
                serde_json::from_reader(std::io::BufReader::new(&file)).map_err(|err| {{
                    error!("Failed to parse export for sanitizing: {{err}}");
                    HttpErrorJson::new(
                        Status::InternalServerError,
                        "Failed to prepare export file".into(),
                    )
                }})?;
            let export = super::export_sanitize::sanitize_buckets_export(export)
                .map_err(|err| HttpErrorJson::new(Status::Conflict, err))?;
            let mut sanitized = tempfile::tempfile().map_err(io_error)?;
            {{
                let mut writer = std::io::BufWriter::new(&mut sanitized);
                serde_json::to_writer(&mut writer, &export).map_err(|err| {{
                    error!("Failed to write sanitized export: {{err}}");
                    HttpErrorJson::new(
                        Status::InternalServerError,
                        "Failed to prepare export file".into(),
                    )
                }})?;
                std::io::Write::flush(&mut writer).map_err(io_error)?;
            }}
            sanitized.seek(SeekFrom::Start(0)).map_err(io_error)?;
            sanitized
        }};
"""

MOD_NEEDLE = "mod export;\n"
MOD_REPLACEMENT = "mod export;\nmod export_sanitize;\n"


def repo_root_from_args(argv: list[str]) -> pathlib.Path:
    if len(argv) > 1:
        return pathlib.Path(argv[1]).resolve()
    return pathlib.Path.cwd().resolve()


def _replace_once(path: pathlib.Path, needle: str, replacement: str, already_ok: str) -> None:
    text = path.read_text(encoding="utf-8")
    if already_ok in text:
        return
    count = text.count(needle)
    if count != 1:
        raise ValueError(
            f"{path}: expected exactly one export-sanitizer insertion point, found {count}"
        )
    path.write_text(text.replace(needle, replacement, 1), encoding="utf-8")


def patch_tree(repo_root: pathlib.Path) -> None:
    script_dir = pathlib.Path(__file__).resolve().parent
    source = script_dir / "research_edition" / "export_sanitize.rs"
    if not source.is_file():
        raise FileNotFoundError(f"missing sanitizer module: {source}")

    endpoints = (
        repo_root / "aw-server-rust" / "aw-server" / "src" / "endpoints"
    )
    util_rs = endpoints / "util.rs"
    mod_rs = endpoints / "mod.rs"
    dest = endpoints / "export_sanitize.rs"

    for required in (util_rs, mod_rs):
        if not required.is_file():
            raise FileNotFoundError(f"expected Rust export source at {required}")

    shutil.copyfile(source, dest)

    _replace_once(mod_rs, MOD_NEEDLE, MOD_REPLACEMENT, "mod export_sanitize;")
    _replace_once(util_rs, EXPORT_INSERT_NEEDLE, EXPORT_INSERT_REPLACEMENT, MARKER)


def main() -> None:
    repo_root = repo_root_from_args(sys.argv)
    try:
        patch_tree(repo_root)
    except (OSError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
    print(f"Patched Research Edition export sanitizer under {repo_root / 'aw-server-rust'}")


if __name__ == "__main__":
    main()
