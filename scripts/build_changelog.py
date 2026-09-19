#!/usr/bin/env python3
"""
Script that generates a changelog for the repository and its submodules, and outputs it in the current directory.

NOTE: This script can be downloaded as-is and run from your repository.

Repos using this script:
 - ActivityWatch/activitywatch
 - ErikBjare/gptme

Submodules are flattened into a single section per repo, ordered by `repo_order`.
A repo that is a submodule of several parents (like aw-webui, which is vendored by
aw-server, aw-server-rust and aw-tauri) therefore gets one section, not one per parent.
If those parents pin different commits, the section covers every pinned commit and
carries a warning listing what each parent pinned.

Manual actions needed to clean up for changelog:
 - Write the `## Summary` section (the human highlights, see the v0.13.0 release notes)
"""

import argparse
import logging
import os
import re
import shlex
from collections import defaultdict
from collections.abc import Collection
from dataclasses import dataclass, field
from pathlib import Path
from subprocess import PIPE, STDOUT
from subprocess import run as _run
from time import sleep
from typing import (
    Dict,
    List,
    Optional,
    Tuple,
)

import requests

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


script_dir = Path(__file__).parent.resolve()


def main():
    parser = argparse.ArgumentParser(description="Generate changelog from git history")

    # repo info
    parser.add_argument("--org", default="ActivityWatch", help="GitHub organization")
    parser.add_argument("--repo", default="activitywatch", help="GitHub repository")
    parser.add_argument(
        "--project-title", default="ActivityWatch", help="Project title"
    )

    # settings
    last_tag = run("git describe --tags --abbrev=0").strip()  # get latest tag
    branch = run("git rev-parse --abbrev-ref HEAD").strip()  # get current branch name
    parser.add_argument(
        "--range", default=f"{last_tag}...{branch}", help="Git commit range"
    )
    parser.add_argument("--path", default=".", help="Path to git repo")

    # output
    parser.add_argument(
        "--output", default="changelog.md", help="Path to output changelog"
    )
    parser.add_argument(
        "--add-version-header",
        action="store_true",
        help="Add version header and adjust heading levels for docs",
    )

    # parse args
    args = parser.parse_args()
    since, until = args.range.split("...", 1)

    # preferred output order for repos (unlisted repos are appended, in the order found)
    repo_order = [
        "activitywatch",
        "aw-server",
        "aw-server-rust",
        "aw-webui",
        "aw-watcher-afk",
        "aw-watcher-window",
        "aw-watcher-input",
        "awatcher",
        "aw-qt",
        "aw-tauri",
        "aw-notify",
        "aw-core",
        "aw-client",
        "media",
    ]

    build(
        args.org,
        args.repo,
        args.project_title,
        commit_range=(since, until),
        output_path=args.output,
        repo_order=repo_order,
        add_version_header=args.add_version_header,
    )


class CommitMsg:
    type: str
    subtype: str
    msg: str


@dataclass
class Commit:
    id: str
    msg: str
    org: str
    repo: str

    @property
    def msg_processed(self) -> str:
        """Generates links from commit and issue references (like 0c14d77, #123) to correct repo and such"""
        s = self.msg
        s = re.sub(
            rf"[^(-]https://github.com/{self.org}/([\-\w\d]+)/(issues|pulls)/(\d+)",
            rf"[#\3](https://github.com/{self.org}/\1/issues/\3)",
            s,
        )
        s = re.sub(
            r"#(\d+)",
            rf"[#\1](https://github.com/{self.org}/{self.repo}/issues/\1)",
            s,
        )
        s = re.sub(
            r"[\s\(][0-9a-f]{7}[\s\)]",
            rf"[`\0`](https://github.com/{self.org}/{self.repo}/issues/\0)",
            s,
        )
        # wrap html elements in backticks, if not already wrapped
        s = re.sub(r"(?<!`)<([^>]+)>(?!`)", r"`<\1>`", s)
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
        _type, _ = self.parse_type() or (None, None)
        return _type

    @property
    def subtype(self) -> Optional[str]:
        _, subtype = self.parse_type() or (None, None)
        return subtype

    def type_str(self) -> str:
        _type, subtype = self.parse_type() or (None, None)
        return f"{_type}" + (f"({subtype})" if subtype else "")

    def format(self) -> str:
        commit_link = commit_linkify(self.id, self.org, self.repo) if self.id else ""

        return f"{self.msg_processed}" + (f" ({commit_link})" if commit_link else "")


def run(cmd, cwd=".") -> str:
    logger.debug(f"Running in {cwd}: {cmd}")
    p = _run(shlex.split(cmd), stdout=PIPE, stderr=STDOUT, encoding="utf8", cwd=cwd)
    if p.returncode != 0:
        print(p.stdout)
        print(p.stderr)
        raise Exception
    return p.stdout


def run_ok(cmd, cwd=".") -> bool:
    """Like `run`, but returns whether the command succeeded instead of its output."""
    logger.debug(f"Running in {cwd}: {cmd}")
    p = _run(shlex.split(cmd), stdout=PIPE, stderr=STDOUT, encoding="utf8", cwd=cwd)
    return p.returncode == 0


def pr_linkify(prid: str, org: str, repo: str) -> str:
    return f"[#{prid}](https://github.com/{org}/{repo}/pulls/{prid})"


def commit_linkify(commitid: str, org: str, repo: str) -> str:
    return f"[`{commitid}`](https://github.com/{org}/{repo}/commit/{commitid})"


def wrap_details(title, body, wraplines=5):
    """Wrap lines into a <details> element if body is longer than `wraplines`"""
    out = f"\n\n### {title}"
    wrap = body.strip().count("\n") > wraplines
    if wrap:
        out += "\n<details><summary>Click to expand</summary>\n<p>"
    out += f"\n{body.rstrip()}"
    if wrap:
        out += "\n\n</p>\n</details>"
    return out


contributor_emails = set()


@dataclass(frozen=True)
class Pointer:
    """One reference to a repo: the parent that points at it, where its checkout is, and the commit range."""

    parent: Optional[str]
    path: str
    commit_range: Tuple[str, str]


@dataclass(frozen=True)
class Pin:
    """The commit a parent currently pins a submodule at, whether or not it moved."""

    parent: str
    path: str
    commit: str


@dataclass
class Repo:
    """A repo in the submodule tree, with every pointer to it (a shared submodule has several)."""

    name: str
    pointers: List[Pointer] = field(default_factory=list)
    pins: List[Pin] = field(default_factory=list)

    @property
    def out_of_sync(self) -> bool:
        """True if the parents that vendor this repo pin different commits."""
        return len({pin.commit for pin in self.pins}) > 1


def collect_repos(
    repo: str,
    path: str,
    commit_range: Tuple[str, str],
    parent: Optional[str] = None,
    repos: Optional[Dict[str, Repo]] = None,
) -> Dict[str, Repo]:
    """
    Walks the submodule tree and records every pointer to every repo.

    Repos are keyed by name, so a submodule vendored by several parents (aw-webui, which
    is a submodule of aw-server, aw-server-rust and aw-tauri) ends up as a single entry
    with one pointer per parent, instead of one section per parent in the changelog.
    """
    if repos is None:
        repos = {}

    if commit_range[0] == "0000000":
        # Happens when a submodule has been added
        commit_range = ("", "")  # no range = all commits for new submodule

    entry = repos.setdefault(repo, Repo(name=repo))
    pointer = Pointer(parent=parent, path=path, commit_range=commit_range)
    if pointer in entry.pointers:
        return repos
    entry.pointers.append(pointer)

    if commit_range[1] == "0000000":
        # Happens when a submodule has been removed, nothing to recurse into
        return repos

    summary_subrepos = run(
        f"git submodule summary --cached {commit_range[0]}", cwd=path
    )
    for header, *_ in [s.split("\n") for s in summary_subrepos.split("\n\n")]:
        if header.startswith("fatal: not a git repository"):
            # Happens when a submodule has been removed
            continue
        if not header.strip():
            continue
        if len(header.split(" ")) < 4:
            # Submodule may have been deleted
            continue

        _, name, crange, count = header.split(" ")
        subrange: Tuple[str, str] = tuple(crange.split("...", 1))  # type: ignore
        count = count.strip().lstrip("(").rstrip("):")
        name = name.strip(".").strip("/")
        logger.info(f"Found {name} in {repo}, range: {subrange} ({count} commits)")

        collect_repos(name, f"{path}/{name}", subrange, parent=repo, repos=repos)

    return repos


def _submodule_pins(path: str) -> List[Tuple[str, str]]:
    """The submodules a repo currently pins, as (name, commit), read from its index."""
    if not os.path.isdir(path):
        return []
    pins = []
    for line in run("git ls-files --stage", cwd=path).splitlines():
        # gitlinks look like: 160000 <sha> 0\t<path>
        if not line.startswith("160000 "):
            continue
        meta, _, name = line.partition("\t")
        pins.append((name.strip(), meta.split()[1]))
    return pins


def collect_pins(
    path: str,
    repos: Dict[str, Repo],
    parent: str,
    seen: Optional[set] = None,
) -> Dict[str, Repo]:
    """
    Records what each parent currently pins, including parents that didn't move.

    `git submodule summary` only reports submodules that changed, so a parent left behind
    on an older commit is invisible to `collect_repos`. Reading the pins separately is
    what lets an unbumped parent still show up in the out-of-sync warning.
    """
    if seen is None:
        seen = set()
    if path in seen:
        return repos
    seen.add(path)

    for name, commit in _submodule_pins(path):
        entry = repos.setdefault(name, Repo(name=name))
        pin = Pin(parent=parent, path=f"{path}/{name}", commit=commit[:7])
        if pin not in entry.pins:
            entry.pins.append(pin)
        collect_pins(f"{path}/{name}", repos, name, seen)

    return repos


def _has_commit(path: str, ref: str) -> bool:
    return run_ok(f"git cat-file -e {ref}^{{commit}}", cwd=path)


def _pick_checkout(repo: Repo) -> Tuple[Optional[str], List[Pointer]]:
    """
    Picks which checkout to run `git log` in, or None if there is no usable one.

    Each parent has its own clone of a shared submodule, so when parents are out of sync
    a sibling's commits may be missing from any given one. Returns the checkout that
    resolves the most pointers, along with the pointers it cannot resolve.
    """
    best: Tuple[Optional[str], List[Pointer]] = (None, repo.pointers)
    for pointer in repo.pointers:
        if not os.path.isdir(pointer.path):
            continue
        unresolved = [
            p
            for p in repo.pointers
            if not all(_has_commit(pointer.path, ref) for ref in p.commit_range if ref)
        ]
        if best[0] is None or len(unresolved) < len(best[1]):
            best = (pointer.path, unresolved)
        if not unresolved:
            break
    return best


def _log_commits(
    path: str, ranges: List[Tuple[str, str]]
) -> List[Tuple[str, str, str]]:
    """
    The commits in the union of `ranges`, newest first, as (id, email, msg).

    Each range is logged on its own and the results merged, rather than asking git for
    `tip1 tip2 --not base1 base2`: that spec drops any commit one parent's range contains
    but another parent's base already includes, which is exactly what happens when the
    parents of a shared submodule started the release from different commits.
    """
    # pretty format is modified version of: https://stackoverflow.com/a/1441062/965332
    pretty = "format:'%h%x09%ct%x09%an%x09%ae%x09%s'"
    commits: Dict[str, Tuple[int, str, str, str]] = {}
    for commit_range in ranges:
        rev = "...".join(commit_range) if any(commit_range) else ""
        for line in run(
            f"git log {rev} --no-decorate --pretty={pretty}", cwd=path
        ).split("\n"):
            if line:
                _id, timestamp, _author, email, msg = line.split("\t")
                commits.setdefault(_id, (int(timestamp), _id, email, msg))

    found = list(commits.values())
    if len(ranges) > 1:
        # merged ranges come out interleaved, so put them back in order
        found.sort(key=lambda commit: -commit[0])
    return [(_id, email, msg) for _, _id, email, msg in found]


def _pick_by_ancestry(path: str, refs: List[str], newest: bool) -> str:
    """Picks the newest (or oldest) of `refs` by ancestry, falling back to the first."""
    refs = [ref for ref in dict.fromkeys(refs) if ref]
    if not refs:
        return ""
    best = refs[0]
    for ref in refs[1:]:
        older, newer = (best, ref) if newest else (ref, best)
        if run_ok(f"git merge-base --is-ancestor {older} {newer}", cwd=path):
            best = ref
    return best


def _sync_notes(repo: Repo, unresolved: List[Pointer]) -> str:
    """Notes about parents that disagree, or pointers we could not resolve locally."""
    notes = ""
    if repo.out_of_sync:
        pinned = ", ".join(f"`{pin.parent}` → `{pin.commit}`" for pin in repo.pins)
        logger.warning(
            f"Submodule {repo.name} is out of sync between parents: {pinned}"
        )
        notes += (
            f"\n\n> ⚠️ `{repo.name}` is vendored by parents that pin different commits"
            f" ({pinned}). The changes below cover every pinned commit, so not all of"
            " them ship in every parent."
        )
    if unresolved:
        missing = ", ".join(
            f"`{p.parent}` → `{p.commit_range[1]}`" for p in unresolved if p.parent
        )
        logger.warning(f"Could not resolve {repo.name} pointers: {missing}")
        notes += (
            f"\n\n> ⚠️ Could not resolve the commits pinned by {missing} in any local"
            f" checkout of `{repo.name}`, so those changes are missing below."
            " Run `git submodule update --init --recursive` and regenerate."
        )
    return notes


def summary_repo(org: str, repo: Repo, filter_types: List[str]) -> str:
    """Renders a single changelog section for a repo, covering every pointer to it."""
    if not repo.pointers:
        # only reached through parents that didn't move it, so nothing changed
        return ""

    path, unresolved = _pick_checkout(repo)
    pointers = [
        p
        for p in repo.pointers
        if p not in unresolved and p.commit_range[1] != "0000000"
    ]
    if path is None or not pointers:
        # Happens when a submodule has been removed, or nothing could be resolved
        logger.warning(f"Nothing resolvable to report for {repo.name}, skipping")
        return ""

    ranges = list(dict.fromkeys(p.commit_range for p in pointers))
    out = f"\n## 📦 {repo.name}"
    out += _sync_notes(repo, unresolved)

    feats = ""
    fixes = ""
    misc = ""
    hidden = 0

    found = _log_commits(path, ranges)
    print(f"Found {len(found)} commits in {repo.name}")
    for _id, email, msg in found:
        # will add author email to contributor list
        # the `contributor_emails` is global and collected later
        contributor_emails.add(email)
        commit = Commit(id=_id, msg=msg, org=org, repo=repo.name)

        entry = f"\n - {commit.format()}"
        if commit.type == "feat":
            feats += entry
        elif commit.type == "fix":
            fixes += entry
        elif commit.type not in filter_types:
            misc += entry
        else:
            hidden += 1

    for name, entries in (
        ("✨ Features", feats),
        ("🐛 Fixes", fixes),
        ("🔨 Misc", misc),
    ):
        if entries:
            _count = len(entries.strip().split("\n"))
            title = f"{name} ({_count})"
            if "Misc" in name or "Fixes" in name:
                out += wrap_details(title, entries)
            else:
                out += f"\n\n### {title}\n"
                out += entries
    has_content = bool(feats or fixes or misc)
    if hidden > 1:
        # for shared submodules, compare the oldest base against the newest tip
        base = _pick_by_ancestry(path, [since for since, _ in ranges], newest=False)
        tip = _pick_by_ancestry(path, [until for _, until in ranges], newest=True)
        full_history_url = (
            f"https://github.com/{org}/{repo.name}/compare/{base}...{tip}"
        )
        out += f"\n\n*(excluded {hidden} less relevant [commits]({full_history_url}))*"
        has_content = True

    if not has_content:
        # nothing worth a section (a parent that only bumped a submodule, say)
        return ""

    return out


def summary_repos(
    org: str,
    root: str,
    repos: Dict[str, Repo],
    repo_order: List[str],
    filter_types: List[str],
) -> str:
    """
    Renders one section per repo: the root first, then `repo_order`, then the rest as found.

    Submodules are flattened into this single list rather than nested under their parents,
    so a repo reachable through several parents gets one section, not one per parent.
    """
    ordered = [root]
    ordered += [name for name in repo_order if name in repos and name not in ordered]
    ordered += [name for name in repos if name not in ordered]

    sections = []
    for name in ordered:
        if not repos[name].pointers:
            continue  # only seen through parents that didn't move it
        section = summary_repo(org, repos[name], filter_types=filter_types)
        if section:
            logger.info(f"{name:20} length: \t{len(section)}")
            sections.append(section)
    return "\n".join(sections)


def build(
    org: str,
    repo: str,
    project_name: str,
    commit_range: Tuple[str, str],
    output_path: str,
    repo_order: List[str],
    filter_types: Optional[List[str]] = None,
    add_version_header: bool = False,
):
    # provides a commit summary for the repo and subrepos, recursively looking up subrepos
    # NOTE: this must be done *before* `get_all_contributors` is called,
    #       as the latter relies on summary_repo looking up all users and storing in a global.
    if not filter_types:
        filter_types = ["build", "ci", "tests", "test"]

    logger.info("Generating commit summary")
    since, tag = commit_range

    # walk the submodule tree first, so that repos reachable through several parents
    # (aw-webui) are rendered once, instead of once per parent
    repos = collect_repos(repo, ".", commit_range)
    # what each parent pins now, including parents that didn't move this release
    collect_pins(".", repos, repo)
    logger.info(f"Found {len(repos)} repos: {', '.join(repos)}")

    output_changelog = summary_repos(org, repo, repos, repo_order, filter_types)

    output_changelog = f"""
# Changelog

Changes since [{since}](https://github.com/{org}/{repo}/releases/tag/{since}):

{output_changelog}
    """.strip()

    # Would ideally sort by number of commits or something, but that's tricky
    usernames = sorted(get_all_contributors(), key=str.casefold)
    usernames = [u for u in usernames if not u.endswith("[bot]")]
    twitter_handles = get_twitter_of_ghusers(usernames)
    print(
        "Twitter handles: "
        + ", ".join("@" + handle for handle in twitter_handles.values() if handle),
    )

    output_contributors = f"""# Contributors

Thanks to everyone who contributed to this release:

{', '.join(('@' + username for username in usernames))}"""

    # Header starts here
    logger.info("Building final output")
    output = f"These are the release notes for {project_name} version {tag}.".strip()
    output += "\n\n"

    # hardcoded for now
    if repo == "activitywatch":
        output += "**New to ActivityWatch?** Check out the [website](https://activitywatch.net) and the [README](https://github.com/ActivityWatch/activitywatch/blob/master/README.md)."
        output += "\n\n"
        output += """# Installation

See the [getting started guide in the documentation](https://docs.activitywatch.net/en/latest/getting-started.html).
        """.strip()
        output += "\n\n"
        # Tauri auto-updater AppImage assets use version without the 'v' prefix
        tag_no_v = tag.lstrip("v")
        base = f"https://github.com/ActivityWatch/activitywatch/releases/download/{tag}"
        output += f"""# Downloads

## Classic distribution

 - [**Windows**]({base}/activitywatch-{tag}-windows-x86_64-setup.exe) (.exe installer)
 - **macOS**: [Intel]({base}/activitywatch-{tag}-macos-x86_64.dmg) | [Apple Silicon]({base}/activitywatch-{tag}-macos-arm64.dmg) (.dmg)
 - **Linux**: [.zip]({base}/activitywatch-{tag}-linux-x86_64.zip) | [.AppImage]({base}/activitywatch-linux-x86_64.AppImage) | [.deb]({base}/activitywatch-{tag}-linux-x86_64.deb)

## Tauri distribution (experimental — native Wayland support on Linux)

 - [**Windows**]({base}/activitywatch-tauri-{tag}-windows-x86_64-setup.exe) (.exe installer)
 - **macOS**: [Intel]({base}/activitywatch-tauri-{tag}-macos-x86_64.dmg) | [Apple Silicon]({base}/activitywatch-tauri-{tag}-macos-arm64.dmg) (.dmg)
 - **Linux**: [.AppImage]({base}/activitywatch-tauri-{tag_no_v}-linux-x86_64.AppImage) | [.zip]({base}/activitywatch-tauri-{tag}-linux-x86_64.zip)
     """.strip()
        output += "\n\n"

    output += output_contributors.strip() + "\n\n"
    output += output_changelog.strip() + "\n\n"
    output += (
        f"**Full Changelog**: https://github.com/{org}/{repo}/compare/{since}...{tag}"
    )

    if repo == "activitywatch":
        output = output.replace("# activitywatch", "# activitywatch (bundle repo)")

    if add_version_header:
        output = f"# {tag}\n\n" + output
        output = output.replace("\n# Contributors\n", "\n## Contributors\n")
        output = output.replace("\n# Changelog\n", "\n## Changelog\n")

    with open(output_path, "w") as f:
        f.write(output)
    print(f"Wrote {len(output.splitlines())} lines to {output_path}")


def _resolve_email(email: str) -> Optional[str]:
    if "users.noreply.github.com" in email:
        username = email.split("@")[0]
        if "+" in username:
            username = username.split("+")[1]
        # TODO: Verify username is valid using the GitHub API
        print(f"Contributor: @{username}")
        return username
    else:
        resp = None
        backoff = 0
        max_backoff = 2
        while resp is None:
            if backoff >= max_backoff:
                logger.warning(f"Backed off {max_backoff} times, giving up")
                break
            try:
                logger.info(f"Sending request for {email}")
                _resp = requests.get(
                    f"https://api.github.com/search/users?q={email}+in%3Aemail"
                )
                _resp.raise_for_status()
                resp = _resp
                backoff = 0
            # if rate limit exceeded, back off
            except requests.exceptions.RequestException as e:
                if isinstance(e, requests.exceptions.HTTPError):
                    if e.response.status_code == 403:
                        logger.warning("Rate limit exceeded, backing off...")
                        backoff += 1
                        sleep(3)
                        continue
                else:
                    raise e
            finally:
                # Just to respect API limits...
                sleep(1)

        if resp:
            data = resp.json()
            if data["total_count"] == 0:
                logger.info(f"No match for email: {email}")
            if data["total_count"] > 1:
                logger.warning(f"Multiple matches for email: {email}")
            if data["total_count"] >= 1:
                username = data["items"][0]["login"]
                logger.info(f"Contributor: @{username}  (by email: {email})")
                return username
    return None


def get_all_contributors() -> set[str]:
    # TODO: Merge with contributor-stats?
    logger.info("Getting all contributors")

    # We will commit this file, to act as a cache (preventing us from querying GitHub API every time)
    filename = script_dir / "changelog_contributors.csv"

    # mapping from username to one or more emails
    usernames: Dict[str, set] = defaultdict(set)

    # some hardcoded ones, some that don't resolve...
    usernames["erikbjare"] |= {"erik.bjareholt@gmail.com", "erik@bjareho.lt"}
    usernames["iloveitaly"] |= {"iloveitaly@gmail.com"}
    usernames["kewde"] |= {"kewde@particl.io"}
    usernames["victorwinberg"] |= {"victor.m.winberg@gmail.com"}
    usernames["NicoWeio"] |= {"nico.weio@gmail.com"}
    usernames["2e3s"] |= {"2e3s19@gmail.com"}
    usernames["alwinator"] |= {"accounts@alwinschuster.at"}

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
        logger.info(f"Read {len(usernames)} contributors from {filename}")

    resolved_emails = set(
        email for email_set in usernames.values() for email in email_set
    )
    unresolved_emails = contributor_emails - resolved_emails
    for email in unresolved_emails:
        username_opt = _resolve_email(email)
        if username_opt:
            usernames[username_opt].add(email)

    with open(filename, "w") as f:
        for username, email_set in sorted(usernames.items()):
            emails_str = "\t".join(sorted(email_set))
            f.write(f"{username}\t{emails_str}")
            f.write("\n")

    logger.info(f"Wrote {len(usernames)} contributors to {filename}")

    email_to_username = {
        email: username for username, emails in usernames.items() for email in emails
    }

    return set(
        email_to_username[email]
        for email in contributor_emails
        if email in email_to_username
    )


def get_twitter_of_ghusers(ghusers: Collection[str]):
    logger.info("Getting twitter of GitHub usernames")

    # We will commit this file, to act as a cache (preventing us from querying GitHub API every time)
    filename = script_dir / "changelog_contributors_twitter.csv"

    twitter = {}

    # read existing contributors, to avoid extra calls to the GitHub API
    if os.path.exists(filename):
        with open(filename, "r") as f:
            s = f.read()
        for line in s.split("\n"):
            if not line:
                continue
            gh_username, twitter_username = line.split("\t")
            twitter[gh_username] = twitter_username
        logger.info(f"Read {len(twitter)} Twitter handles from {filename}")

    for username in ghusers:
        if username in twitter:
            continue
        try:
            resp = requests.get(f"https://api.github.com/users/{username}")
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.warning(f"Failed to get twitter of {username}: {e}")
            continue

        twitter_username = data["twitter_username"]
        if twitter_username:
            twitter[username] = twitter_username

    with open(filename, "w") as f:
        for username, twitter_username in sorted(twitter.items()):
            f.write(f"{username}\t{twitter_username}")
            f.write("\n")

    return twitter


if __name__ == "__main__":
    main()
