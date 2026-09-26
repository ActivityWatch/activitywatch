#!/usr/bin/env python3
"""Patch aw-server-rust's export endpoints for the Research Edition build.

Run as part of the CI build for research edition:

    python3 scripts/patch_research_edition_export.py [repo-root]

Standard builds never run this script, so the export endpoints stay unchanged
outside Research Edition. The patch is fail-closed: every anchor below must
match exactly once (or already be patched), otherwise the build aborts rather
than shipping an unsanitized artifact.

What it does (ActivityWatch/activitywatch#1449 anchored the sanitizer the last
time; this follows aw-server-rust#721 and #722):

A. JSON export (``/api/0/export``, ``/api/0/buckets/<id>/export``). Since
   aw-server-rust#721 the export is serialized on a background thread after the
   200 headers are sent, so a sanitizer failure there could no longer turn
   into an error response. In research builds ``BucketsExportRocket::new``
   instead spools the export, sanitizes it and spools the result again, all
   before any headers, so a failure is still a fail-closed 409 (500 for I/O
   errors), and ``respond_to`` only streams the sanitized tempfile. The
   sanitizer needs the whole export (fail closed on unfiltered events, identity
   collisions across buckets); research exports are category-only, so this
   gives up stream-after-headers only where the data is already small.
B. CSV export (``/api/0/buckets/<id>/export/csv``, aw-server-rust#722) streams
   raw events and has no sanitizer, so research builds disable it:
   ``BucketEventsCsvRocket::new`` returns 403.

Tempfiles come from ``tempfile::tempfile()``, which are unnamed (unlinked on
Unix, delete-on-close on Windows), so they are removed on every path, including
errors, as soon as the handle is dropped.
"""
from __future__ import annotations

import pathlib
import shutil
import sys
from typing import List, Tuple

# One marker per anchor, so a partially patched tree is detected.
MARKER = "RESEARCH_EDITION_EXPORT_SANITIZE"
STRUCT_MARKER = "RESEARCH_EDITION_EXPORT_STRUCT"
CSV_MARKER = "RESEARCH_EDITION_CSV_EXPORT_DISABLED"

# A: the export struct gains the sanitized spool.
STRUCT_NEEDLE = """pub struct BucketsExportRocket {
    datastore: aw_datastore::Datastore,
    bucket_id: Option<String>,
    filename: String,
}
"""

STRUCT_REPLACEMENT = f"""// {STRUCT_MARKER}: research builds serve a sanitized spool built before
// headers; the streaming fields are kept but unused.
#[allow(dead_code)]
pub struct BucketsExportRocket {{
    datastore: aw_datastore::Datastore,
    bucket_id: Option<String>,
    filename: String,
    sanitized: File,
}}

/// Export, sanitize and re-spool, before any headers are sent, so a failure is
/// an error response (409 when the sanitizer refuses) instead of a 200 with a
/// truncated body. Both tempfiles are unnamed and removed when dropped.
fn research_sanitized_export(
    datastore: &aw_datastore::Datastore,
    bucket_id: Option<&str>,
) -> Result<File, HttpErrorJson> {{
    let io_error = |err: std::io::Error| {{
        error!("Failed to prepare sanitized export: {{err}}");
        HttpErrorJson::new(
            Status::InternalServerError,
            "Failed to prepare export file".into(),
        )
    }};
    let staging = tempfile::tempfile().map_err(io_error)?;
    let (mut staging, _) = datastore.export_to_file(bucket_id, staging)?;
    staging.seek(SeekFrom::Start(0)).map_err(io_error)?;
    let export: aw_models::BucketsExport =
        serde_json::from_reader(std::io::BufReader::new(&staging)).map_err(|err| {{
            error!("Failed to parse export for sanitizing: {{err}}");
            HttpErrorJson::new(
                Status::InternalServerError,
                "Failed to prepare export file".into(),
            )
        }})?;
    drop(staging);
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
    Ok(sanitized)
}}
"""

# A: BucketsExportRocket::new and its Responder, as of aw-server-rust#721.
EXPORT_INSERT_NEEDLE = """impl BucketsExportRocket {
    pub fn new(
        datastore: &aw_datastore::Datastore,
        bucket_id: Option<&str>,
    ) -> Result<Self, HttpErrorJson> {
        // Resolve the download name and 404 missing buckets before the
        // response is built. Serialization itself runs after headers so a
        // slow export does not look like a hung connection.
        let filename = export_filename(datastore, bucket_id)?;
        Ok(Self {
            datastore: datastore.clone(),
            bucket_id: bucket_id.map(str::to_owned),
            filename,
        })
    }
}

impl<'r> Responder<'r, 'static> for BucketsExportRocket {
    fn respond_to(self, _: &Request) -> response::Result<'static> {
        let (reader, writer) = pipe().map_err(|err| {
            error!("Failed to open export pipe: {err}");
            Status::InternalServerError
        })?;
        spawn_export_stream(self.datastore, self.bucket_id, writer);
        Response::build()
            .status(Status::Ok)
            .header(Header::new("Content-Disposition", self.filename))
            .header(ContentType::JSON)
            .streamed_body(rocket::tokio::fs::File::from_std(pipe_reader_to_file(
                reader,
            )))
            .ok()
    }
}
"""

EXPORT_INSERT_REPLACEMENT = f"""impl BucketsExportRocket {{
    pub fn new(
        datastore: &aw_datastore::Datastore,
        bucket_id: Option<&str>,
    ) -> Result<Self, HttpErrorJson> {{
        let filename = export_filename(datastore, bucket_id)?;
        // {MARKER}: sanitize before headers so failures stay fail-closed.
        let sanitized = research_sanitized_export(datastore, bucket_id)?;
        Ok(Self {{
            datastore: datastore.clone(),
            bucket_id: bucket_id.map(str::to_owned),
            filename,
            sanitized,
        }})
    }}
}}

impl<'r> Responder<'r, 'static> for BucketsExportRocket {{
    fn respond_to(self, _: &Request) -> response::Result<'static> {{
        // Research Edition: only the sanitized spool built in `new` is sent.
        Response::build()
            .status(Status::Ok)
            .header(Header::new("Content-Disposition", self.filename))
            .header(ContentType::JSON)
            .streamed_body(rocket::tokio::fs::File::from_std(self.sanitized))
            .ok()
    }}
}}
"""

# B: the CSV export (aw-server-rust#722) streams raw events; disable it.
CSV_NEEDLE = """impl BucketEventsCsvRocket {
    pub fn new(
        datastore: &aw_datastore::Datastore,
        bucket_id: &str,
        start: Option<DateTime<Utc>>,
        end: Option<DateTime<Utc>>,
        limit: Option<u64>,
    ) -> Result<Self, HttpErrorJson> {
"""

CSV_REPLACEMENT = f"""impl BucketEventsCsvRocket {{
    #[allow(unreachable_code, unused_variables)]
    pub fn new(
        datastore: &aw_datastore::Datastore,
        bucket_id: &str,
        start: Option<DateTime<Utc>>,
        end: Option<DateTime<Utc>>,
        limit: Option<u64>,
    ) -> Result<Self, HttpErrorJson> {{
        // {CSV_MARKER}: raw-event CSV export has no sanitizer.
        return Err(HttpErrorJson::new(
            Status::Forbidden,
            "CSV export is disabled in Research Edition".into(),
        ));
"""

MOD_NEEDLE = "mod export;\n"
MOD_REPLACEMENT = "mod export;\nmod export_sanitize;\n"

# (name, needle, replacement, marker)
UTIL_EDITS: List[Tuple[str, str, str, str]] = [
    ("export-struct", STRUCT_NEEDLE, STRUCT_REPLACEMENT, STRUCT_MARKER),
    ("export-sanitizer", EXPORT_INSERT_NEEDLE, EXPORT_INSERT_REPLACEMENT, MARKER),
    ("csv-export", CSV_NEEDLE, CSV_REPLACEMENT, CSV_MARKER),
]


def repo_root_from_args(argv: list[str]) -> pathlib.Path:
    if len(argv) > 1:
        return pathlib.Path(argv[1]).resolve()
    return pathlib.Path.cwd().resolve()


def _edited_text(path: pathlib.Path, edits: List[Tuple[str, str, str, str]]) -> str:
    """The patched text of ``path``; raises if any anchor isn't found exactly once."""
    text = path.read_text(encoding="utf-8")
    for name, needle, replacement, marker in edits:
        if marker in text:
            continue  # already patched
        count = text.count(needle)
        if count != 1:
            raise ValueError(
                f"{path}: expected exactly one {name} insertion point, found {count}"
            )
        text = text.replace(needle, replacement, 1)
    return text


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

    # Check every anchor before writing anything, so a missing one leaves the
    # tree untouched and the build fails.
    util_text = _edited_text(util_rs, UTIL_EDITS)
    mod_text = _edited_text(
        mod_rs,
        [("export-sanitize module", MOD_NEEDLE, MOD_REPLACEMENT, "mod export_sanitize;")],
    )
    shutil.copyfile(source, dest)
    util_rs.write_text(util_text, encoding="utf-8")
    mod_rs.write_text(mod_text, encoding="utf-8")


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
