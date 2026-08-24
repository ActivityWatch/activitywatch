#!/usr/bin/env python3
"""Patch aw-server-rust export endpoints for the Research Edition build.

Run as part of the CI build for research edition:

    python3 scripts/patch_research_edition_export.py [repo-root]

Standard builds never run this script, so `/api/0/export` stays byte-for-byte
unchanged outside Research Edition. The patch is fail-closed: missing markers
abort the build rather than shipping an unsanitized artifact.
"""
from __future__ import annotations

import pathlib
import shutil
import sys

MARKER = "RESEARCH_EDITION_EXPORT_SANITIZE"

EXPORT_INSERT_NEEDLE = """        export.buckets.insert(bid, bucket);
    }

    Ok(export.into())
"""

EXPORT_INSERT_REPLACEMENT = f"""        export.buckets.insert(bid, bucket);
    }}

    // {MARKER}
    let export = match super::export_sanitize::sanitize_buckets_export(export) {{
        Ok(export) => export,
        Err(err) => {{
            return Err(HttpErrorJson::new(rocket::http::Status::Conflict, err))
        }}
    }};
    Ok(export.into())
"""

BUCKET_INSERT_NEEDLE = """    export.buckets.insert(bucket_id.into(), bucket);

    Ok(export.into())
"""

BUCKET_INSERT_REPLACEMENT = f"""    export.buckets.insert(bucket_id.into(), bucket);

    // {MARKER}
    let export = match super::export_sanitize::sanitize_buckets_export(export) {{
        Ok(export) => export,
        Err(err) => return Err(HttpErrorJson::new(Status::Conflict, err)),
    }};
    Ok(export.into())
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
    export_rs = endpoints / "export.rs"
    bucket_rs = endpoints / "bucket.rs"
    mod_rs = endpoints / "mod.rs"
    dest = endpoints / "export_sanitize.rs"

    for required in (export_rs, bucket_rs, mod_rs):
        if not required.is_file():
            raise FileNotFoundError(f"expected Rust export source at {required}")

    shutil.copyfile(source, dest)

    _replace_once(mod_rs, MOD_NEEDLE, MOD_REPLACEMENT, "mod export_sanitize;")
    _replace_once(export_rs, EXPORT_INSERT_NEEDLE, EXPORT_INSERT_REPLACEMENT, MARKER)
    _replace_once(bucket_rs, BUCKET_INSERT_NEEDLE, BUCKET_INSERT_REPLACEMENT, MARKER)


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
