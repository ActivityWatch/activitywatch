from subprocess import run as _run, STDOUT, PIPE
import re


def run(cmd) -> str:
    return _run(cmd.split(" "), stdout=PIPE, stderr=STDOUT, encoding="utf8").stdout


def process_line(s: str, repo: str) -> str:
    """Generates links from commit and issue references (like 0c14d77, #123) to correct repo and such"""
    s = re.sub(r"#([0-9]+)", rf"[#\1](https://github.com/ActivityWatch/{repo}/issues/\1)", s)
    return s


def commit_linkify(commitid: str, repo: str) -> str:
    return f"[`{commitid}`](https://github.com/ActivityWatch/{repo}/commit/{commitid})"


def build():
    prev_release = run("git describe --tags --abbrev=0").strip()
    summary_bundle = run(f"git log {prev_release}...master --oneline --decorate")
    print("### activitywatch (bundle repo)")
    for line in summary_bundle.split("\n"):
        if line:
            commit = line.split(" ")[0]
            line = ' '.join(line.split(' ')[1:])
            commit_link = commit_linkify(commit, 'activitywatch')
            line = f" - {line} ({commit_link})"
            print(process_line(line, "activitywatch"))

    summary_subrepos = run(f"git submodule summary {prev_release}")
    for s in summary_subrepos.split("\n\n"):
        lines = s.split("\n")
        header = lines[0]
        if header.strip():
            _, name, commitrange, count = header.split(" ")
            name = name.strip(".").strip("/")
            print(f"\n### {name} {commitrange}")
            commits = [process_line(" - " + l.strip(" ").strip(">").strip(" "), name) for l in lines[1:]]
            print("\n".join(commits))


if __name__ == "__main__":
    build()
