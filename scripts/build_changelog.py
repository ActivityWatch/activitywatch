#!/usr/bin/python3
"""
Script that outputs a changelog for the repository in the current directory and its submodules.

Manual actions needed to clean up for changelog:
 - Reorder modules in a logical order (aw-webui, aw-server, aw-server-rust, aw-watcher-window, aw-watcher-afk, ...)
 - Remove duplicate aw-webui entries
"""

import shlex
import re
import argparse
import os
from time import sleep
from typing import Optional, Tuple, List
from subprocess import run as _run, STDOUT, PIPE
from dataclasses import dataclass
from collections import defaultdict

import requests

# preferred repository order
repo_order = [
    "activitywatch",
    "aw-server",
    "aw-server-rust",
    "aw-webui",
    "aw-watcher-afk",
    "aw-watcher-window",
    "aw-qt",
    "aw-core",
    "aw-client",
]


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


contributor_emails = set()


def summary_repo(path: str, commitrange: str, filter_types: List[str]) -> str:
    if commitrange.endswith("0000000"):
        # Happens when a submodule has been removed
        return ""
    dirname = run("bash -c 'basename $(pwd)'", cwd=path).strip()
    out = f"\n## {dirname}"

    feats = ""
    fixes = ""
    misc = ""

    # pretty format is modified version of: https://stackoverflow.com/a/1441062/965332
    summary_bundle = run(
        f"git log {commitrange} --no-decorate --pretty=format:'%h%x09%an%x09%ae%x09%s'",
        cwd=path,
    )
    for line in summary_bundle.split("\n"):
        if line:
            _id, _author, email, msg = line.split("\t")
            # will add author email to contributor list
            # the `contributor_emails` is global and collected later
            contributor_emails.add(email)
            commit = Commit(
                id=_id,
                msg=msg,
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
    subrepos = {}
    for header, *_ in [s.split("\n") for s in summary_subrepos.split("\n\n")]:
        if header.startswith("fatal: not a git repository"):
            # Happens when a submodule has been removed
            continue
        if header.strip():
            if len(header.split(" ")) < 4:
                # Submodule may have been deleted
                continue

            _, name, commitrange, count = header.split(" ")
            name = name.strip(".").strip("/")

            subrepos[name] = summary_repo(
                f"{path}/{name}", commitrange, filter_types=filter_types
            )

    # pick subrepos in repo_order, and remove from dict
    for name in repo_order:
        if name in subrepos:
            out += "\n"
            out += subrepos[name]
            del subrepos[name]

    # add remaining repos
    for name, output in subrepos.items():
        out += "\n"
        out += output

    return out


# FIXME: Doesn't work, messy af, just gonna have to remove the aw-webui section by hand
def remove_duplicates(s: List[str], minlen=10, only_sections=True) -> List[str]:
    """
    Removes the longest sequence of repeated elements (they don't have to be adjacent), if sequence if longer than `minlen`.
    Preserves order of elements.
    """
    if len(s) < minlen:
        return s
    out = []
    longest: List[str] = []
    for i in range(len(s)):
        if i == 0 or s[i] not in out:
            # Not matching any previous line,
            # so add longest and new line to output, and reset longest
            if len(longest) < minlen:
                out.extend(longest)
            else:
                duplicate = "\n".join(longest)
                print(f"Removing duplicate '{duplicate[:80]}...'")
            out.append(s[i])
            longest = []
        else:
            # Matches a previous line, so add to longest
            # If longest is empty and only_sections is True, check that the line is a section start
            if only_sections:
                if not longest and s[i].startswith("#"):
                    longest.append(s[i])
                else:
                    out.append(s[i])
            else:
                longest.append(s[i])

    return out


def build(filter_types=["build", "ci", "tests", "test"]):
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

    since, until = args.range.split("...")

    # provides a commit summary for the repo and subrepos, recursively looking up subrepos
    # NOTE: this must be done *before* `get_all_contributors` is called,
    #       as the latter relies on summary_repo looking up all users and storing in a global.
    output_changelog = summary_repo(
        ".", commitrange=args.range, filter_types=filter_types
    )

    output_changelog = f"""
# Changelog

Changes since {since}

{output_changelog}
    """.strip()

    usernames = get_all_contributors()
    output_contributors = f"""# Contributors

The following people have contributed to this release:

{', '.join(('@' + username for username in usernames))}"""

    output = f"""# {until}"""
    output += "\n\n"
    output += f"This is the release notes for the {until} release.".strip()
    output += "\n\n"
    output += output_contributors.strip() + "\n\n"
    output += output_changelog.strip() + "\n\n"

    output = output.replace("# activitywatch", "# activitywatch (bundle repo)")
    with open(args.output, "w") as f:
        f.write(output)
    print(f"Wrote {len(output.splitlines())} lines to {args.output}")


def get_all_contributors():
    # TODO: Merge with contributor-stats?
    filename = "changelog_contributors.md"

    # mapping from username to one or more emails
    usernames = defaultdict(set)

    # some hardcoded ones that don't resolve...
    usernames["iloveitaly"] = {"iloveitaly@gmail.com"}
    usernames["kewde"] = {"kewde@particl.io"}
    usernames["victorwinberg"] = {"kewde@particl.iovictor.m.winberg@gmail.com"}

    # read existing contributors, to avoid extra calls to the GitHub API
    if os.path.exists(filename):
        with open(filename, "r") as f:
            s = f.read()
        for line in s.split("\n"):
            if not line:
                continue
            username, *emails = line.split("\t")
            for email in emails:
                usernames[username].add(email)
        print(f"Read {len(usernames)} contributors from {filename}")

    resolved_emails = set(
        email for email_set in usernames.values() for email in email_set
    )
    for email in contributor_emails:
        if email in resolved_emails:
            continue
        if "users.noreply.github.com" in email:
            username = email.split("@")[0]
            if "+" in username:
                username = username.split("+")[1]
            # TODO: Verify username is valid using the GitHub API
            print(f"Contributor: @{username}")
            usernames[username].add(email)
        else:
            try:
                resp = requests.get(
                    f"https://api.github.com/search/users?q={email}+in%3Aemail"
                )
                resp.raise_for_status()
                data = resp.json()
                if data["total_count"] == 0:
                    print("No match for email:", email)
                    continue
                if data["total_count"] >= 0:
                    username = data["items"][0]["login"]
                    print(f"Contributor: @{username}  (by email: {email})")
                    usernames[username].add(email)
                if data["total_count"] > 1:
                    print(f"Multiple matches for email: {email}")
            except requests.exceptions.RequestException as e:
                print(f"Error: {e}")
            finally:
                # Just to respect API limits...
                sleep(5)

    with open(filename, "w") as f:
        for username, email_set in usernames.items():
            emails_str = "\t".join(email_set)
            f.write(f"{username}\t{emails_str}")
            f.write("\n")

    print(f"Wrote {len(usernames)} contributors to {filename}")

    return usernames.keys()


if __name__ == "__main__":
    build()
