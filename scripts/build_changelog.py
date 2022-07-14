#!/usr/bin/python3
"""
Script that outputs a changelog for the repository in the current directory and its submodules.

Manual actions needed to clean up for changelog:
 - Reorder modules in a logical order (aw-webui, aw-server, aw-server-rust, aw-watcher-window, aw-watcher-afk, ...)
 - Add the "bundle repo" notice to the main ActivityWatch repo.
"""

import shlex
import re
import argparse
from typing import Optional, Tuple, List
from subprocess import run as _run, STDOUT, PIPE
from dataclasses import dataclass


class CommitMsg:
    type: str
    subtype: str
    msg: str


@dataclass
class Commit:
    id: str
    msg: str
    repo: str

    @property
    def msg_processed(self) -> str:
        """Generates links from commit and issue references (like 0c14d77, #123) to correct repo and such"""
        s = self.msg
        s = re.sub(
            r"[^(-]https://github.com/ActivityWatch/([\-\w\d]+)/(issues|pulls)/(\d+)",
            r"[#\3](https://github.com/ActivityWatch/\1/issues/\3)",
            s,
        )
        s = re.sub(
            r"#(\d+)",
            rf"[#\1](https://github.com/ActivityWatch/{self.repo}/issues/\1)",
            s,
        )
        s = re.sub(
            r"[\s\(][0-9a-f]{7}[\s\)]",
            rf"[`\0`](https://github.com/ActivityWatch/{self.repo}/issues/\0)",
            s,
        )
        return s

    def parse_type(self) -> Optional[Tuple[str, str]]:
        # Needs to handle '!' indicating breaking change
        match = re.search(r"^(\w+)(\((.+)\))?[!]?:", self.msg)
        if match:
            type = match.group(1)
            subtype = match.group(3)
            if type in ["build", "ci", "fix", "feat"]:
                return type, subtype
        return None

    @property
    def type(self) -> Optional[str]:
        type, _ = self.parse_type() or (None, None)
        return type

    @property
    def subtype(self) -> Optional[str]:
        _, subtype = self.parse_type() or (None, None)
        return subtype

    def type_str(self) -> str:
        type, subtype = self.parse_type() or (None, None)
        return f"{type}" + (f"({subtype})" if subtype else "")

    def format(self) -> str:
        commit_link = commit_linkify(self.id, self.repo) if self.id else ""

        return f"{self.msg_processed}" + (f" ({commit_link})" if commit_link else "")


def run(cmd, cwd=".") -> str:
    p = _run(shlex.split(cmd), stdout=PIPE, stderr=STDOUT, encoding="utf8", cwd=cwd)
    if p.returncode != 0:
        print(p.stdout)
        print(p.stderr)
        raise Exception
    return p.stdout


def pr_linkify(prid: str, repo: str) -> str:
    return f"[#{prid}](https://github.com/ActivityWatch/{repo}/pulls/{prid})"


def commit_linkify(commitid: str, repo: str) -> str:
    return f"[`{commitid}`](https://github.com/ActivityWatch/{repo}/commit/{commitid})"


def wrap_details(title, body, wraplines=5):
    """Wrap lines into a <details> element if body is longer than `wraplines`"""
    out = f"\n\n### {title}"
    if body.count("\n") > wraplines:
        out += "\n<details><summary>Click to expand</summary>"
    out += f"\n<p>\n\n{body.strip()}\n\n</p>\n"
    if body.count("\n") > wraplines:
        out += "</details>"
    return out


def summary_repo(path: str, commitrange: str, filter_types: List[str]) -> str:
    if commitrange.endswith("0000000"):
        # Happens when a submodule has been removed
        return ""
    dirname = run("bash -c 'basename $(pwd)'", cwd=path).strip()
    out = f"\n## {dirname}"

    feats = ""
    fixes = ""
    misc = ""

    summary_bundle = run(f"git log {commitrange} --oneline --no-decorate", cwd=path)
    for line in summary_bundle.split("\n"):
        if line:
            commit = Commit(
                id=line.split(" ")[0],
                msg=" ".join(line.split(" ")[1:]),
                repo=dirname,
            )

            entry = f"\n - {commit.format()}"
            if commit.type == "feat":
                feats += entry
            elif commit.type == "fix":
                fixes += entry
            elif commit.type not in filter_types:
                misc += entry

    for name, entries in (("✨ Features", feats), ("🐛 Fixes", fixes), ("🔨 Misc", misc)):
        if entries:
            _count = len(entries.strip().split("\n"))
            title = f"{name} ({_count})"
            if "Misc" in name or "Fixes" in name:
                out += wrap_details(title, entries)
            else:
                out += f"\n\n### {title}"
                out += entries

    # NOTE: For now, these TODOs can be manually fixed for each changelog.
    # TODO: Fix issue where subsubmodules can appear twice (like aw-webui)
    # TODO: Use specific order (aw-webui should be one of the first, for example)
    summary_subrepos = run(
        f"git submodule summary {commitrange.split('...')[0]}", cwd=path
    )
    for s in summary_subrepos.split("\n\n"):
        lines = s.split("\n")
        header = lines[0]
        if header.startswith("fatal: not a git repository"):
            # Happens when a submodule has been removed
            continue
        if header.strip():
            out += "\n"
            if len(header.split(" ")) < 4:
                # Submodule may have been deleted
                continue

            _, name, commitrange, count = header.split(" ")
            name = name.strip(".").strip("/")

            output = summary_repo(
                f"{path}/{name}", commitrange, filter_types=filter_types
            )
            out += output

    return out


def build(filter_types=["build", "ci", "tests"]):
    prev_release = run("git describe --tags --abbrev=0").strip()
    next_release = "master"

    parser = argparse.ArgumentParser(description="Generate changelog from git history")
    parser.add_argument(
        "--range", default=f"{prev_release}...{next_release}", help="Git commit range"
    )
    parser.add_argument("--path", default=".", help="Path to git repo")
    parser.add_argument(
        "--output", default="changelog.md", help="Path to output changelog"
    )
    args = parser.parse_args()
    args.range

    output = summary_repo(".", commitrange=args.range, filter_types=filter_types)

    output = f"""
# Changelog

Changes since {args.range.split('...', 1)[0]}

{output}
    """.strip()

    with open(args.output, "w") as f:
        f.write(output)
    print(f"Wrote {len(output.splitlines())} lines to {args.output}")


if __name__ == "__main__":
    build()
