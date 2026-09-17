#!/usr/bin/env bash
#
# Bump every submodule to the tip of its master branch and commit the
# pointer updates, one confirmed commit at a time. Press Enter to accept
# each step, `n` to skip it, `q` to abort.
#
# Order matters because aw-tauri's Cargo.lock is authoritative for which
# aw-server-rust revision ships (see scripts/check_tauri_server.py and
# `make sync-tauri-server`):
#
#   1. nested aw-webui inside aw-server, aw-server-rust and aw-tauri
#      -> commit + push "build(deps): updated aw-webui" in each
#   2. every direct submodule: checkout master, fast-forward
#   3. aw-tauri/src-tauri/Cargo.lock: relock the aw-server-rust git deps
#      to the aw-server-rust submodule's HEAD
#      -> commit + push "build(deps): updated cargo locks" in aw-tauri
#   4. bundle: align aw-server-rust pointer to the Tauri lock, validate,
#      commit + push "build(deps): updated submodules"
#
# Policy: pure submodule-pointer bumps are pushed straight to master, no PR.
# There is nothing to review as long as the new pointer is upstream master
# (or an ancestor of it), and this script guarantees exactly that: it only
# ever fast-forwards a submodule to its origin/master, and it refuses to
# commit a pointer that is not already contained in an origin/ branch —
# so a parent's CI can always check the pinned commit out.
#
# Usage: scripts/bump-submodules.sh [--yes] [--no-push] [--dry-run] [--skip a,b]
#
#   --yes       accept every prompt
#   --no-push   commit locally but never push (step 3 is skipped: cargo
#               can only relock to a revision that exists on GitHub)
#   --dry-run   fetch and report what would change; move nothing
#   --skip      comma-separated submodules to leave alone (default: awatcher)

set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

YES=0 PUSH=1 DRY=0 SKIP="awatcher"
while [ $# -gt 0 ]; do
    case "$1" in
        --yes)     YES=1 ;;
        --no-push) PUSH=0 ;;
        --dry-run) DRY=1 ;;
        --skip)    SKIP="$2"; shift ;;
        -h|--help) sed -n '2,25p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "unknown option: $1" >&2; exit 2 ;;
    esac
    shift
done

# ---------------------------------------------------------------- helpers

bold() { printf '\033[1m%s\033[0m\n' "$*"; }
warn() { printf '\033[33mwarning:\033[0m %s\n' "$*" >&2; }
step() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }

# confirm "question" -> 0 = yes, 1 = skip. `q` aborts the whole run.
confirm() {
    if [ "$DRY" = 1 ]; then echo "  [dry-run] would: $*"; return 1; fi
    if [ "$YES" = 1 ]; then return 0; fi
    printf '%s [Enter=yes / n=skip / q=quit] ' "$*"
    read -r answer
    case "$answer" in
        q|Q) echo "aborted"; exit 1 ;;
        n|N) return 1 ;;
        *)   return 0 ;;
    esac
}

# run <dir> <git args...>: run git in a submodule, echoing under dry-run.
run() {
    local dir=$1; shift
    if [ "$DRY" = 1 ]; then echo "  [dry-run] (cd $dir && git $*)"; return 0; fi
    git -C "$dir" "$@"
}

in_skip() { case ",$SKIP," in *",$1,"*) return 0 ;; esac; return 1; }

# A parent may only pin a submodule commit that already exists on GitHub:
# CI checks the submodule out at that SHA. unpushed <repo> -> 0 if HEAD is
# not contained in any origin/ branch.
unpushed() {
    ! git -C "$1" branch -r --contains "$(git -C "$1" rev-parse HEAD)" 2>/dev/null | grep -q 'origin/'
}

# Dependency order for pushes: aw-tauri's lock references aw-server-rust,
# and the bundle references everything. Everything else is independent.
push_order() {
    local first="" rest=""
    for m in "$@"; do
        case "$m" in aw-server-rust) first="aw-server-rust $first" ;; aw-tauri) first="$first aw-tauri" ;; *) rest="$rest $m" ;; esac
    done
    echo $first $rest
}

# Tracked-file modifications inside a submodule (untracked files are fine).
dirty() { [ -n "$(git -C "$1" status --porcelain --untracked-files=no)" ]; }

# Where <dir> will be after this run: its HEAD normally, but under --dry-run
# nothing moves, so reason about origin/master instead (unless it is dirty
# and would be left alone).
target_sha() {
    if [ "$DRY" = 1 ] && ! dirty "$1"; then git -C "$1" rev-parse origin/master
    else git -C "$1" rev-parse HEAD; fi
}

# pointer_changed <repo> <path>: the gitlink <repo> records for <path>
# differs from where <path> is (or would be). Ignores modified content
# inside the submodule — only a moved pointer counts.
pointer_changed() {
    if [ "$DRY" = 1 ]; then
        [ "$(git -C "$1" rev-parse "HEAD:$2")" != "$(target_sha "$1/$2")" ]
    else
        ! git -C "$1" diff --quiet --ignore-submodules=dirty -- "$2"
    fi
}

# checkout master and fast-forward; never merge. Returns 1 if skipped.
ff_master() {
    local dir=$1 before after
    if dirty "$dir"; then
        warn "$dir has local modifications; not touching it"
        git -C "$dir" status --porcelain --untracked-files=no | sed 's/^/    /' >&2
        return 1
    fi
    before=$(git -C "$dir" rev-parse HEAD)
    git -C "$dir" fetch -q origin master
    after=$(git -C "$dir" rev-parse origin/master)
    if [ "$before" = "$after" ] && [ "$(git -C "$dir" rev-parse --abbrev-ref HEAD)" = master ]; then
        echo "  $dir: master @ ${after:0:7} (up to date)"
        return 0
    fi
    if [ "$DRY" = 1 ]; then
        echo "  [dry-run] $dir: would fast-forward ${before:0:7} -> ${after:0:7}"
        git -C "$dir" log --oneline "${before}..${after}" | sed 's/^/      /'
        return 0
    fi
    git -C "$dir" checkout -q master
    if ! git -C "$dir" pull -q --ff-only origin master; then
        warn "$dir: local master has diverged from origin/master; resolve it by hand, leaving as-is"
        return 1
    fi
    echo "  $dir: master ${before:0:7} -> $(git -C "$dir" rev-parse --short HEAD)"
    git -C "$dir" log --oneline "${before}..HEAD" | sed 's/^/      /'
}

# commit_pointer <repo> <submodule path> <message>: commit a moved
# submodule pointer inside <repo>, then push <repo>'s master.
commit_pointer() {
    local repo=$1 path=$2 msg=$3
    if ! pointer_changed "$repo" "$path"; then
        echo "  $repo: $path pointer unchanged"
        return 0
    fi
    if [ "$DRY" = 1 ]; then
        echo "  [dry-run] $repo: $path $(git -C "$repo" rev-parse --short "HEAD:$path") -> $(git -C "$repo/$path" rev-parse --short origin/master)"
    else
        git -C "$repo" diff --submodule=log --ignore-submodules=dirty -- "$path" | sed 's/^/    /'
    fi
    confirm "commit in $repo: \"$msg\"?" || return 0
    run "$repo" add -- "$path"
    run "$repo" commit -q -m "$msg"
    push_master "$repo"
}

push_master() {
    local repo=$1
    [ "$PUSH" = 1 ] || { warn "$repo: not pushed (--no-push)"; return 0; }
    confirm "push $repo master to origin?" || { warn "$repo: not pushed"; return 0; }
    run "$repo" push -q origin master
    echo "  $repo: pushed $(git -C "$repo" rev-parse --short HEAD)"
}

# ---------------------------------------------------------------- preflight

step "preflight"
for tool in git python3 cargo; do
    command -v "$tool" >/dev/null || { echo "missing: $tool" >&2; exit 1; }
done
if [ -n "$(git diff --cached --name-only)" ]; then
    echo "bundle has staged changes; commit or unstage them first" >&2; exit 1
fi
git submodule update --init --recursive -q
echo "submodule branches before:"
./scripts/submodule-branch.sh | sed 's/^/  /'

DIRECT=$(git submodule --quiet foreach 'echo $sm_path')

# ---------------------------------------------------------------- 1. nested submodules

# Every submodule that a direct submodule carries itself (aw-webui inside
# aw-server / aw-server-rust / aw-tauri, media inside aw-qt and aw-webui, ...).
# Discovered, not listed, so a new nested submodule is picked up automatically.
step "1/4 nested submodules inside each direct submodule"
NESTED_PARENTS=""
for parent in $DIRECT; do
    in_skip "$parent" && { echo "  $parent: skipped"; continue; }
    nested=$(git -C "$parent" submodule --quiet foreach 'echo $sm_path' 2>/dev/null || true)
    [ -n "$nested" ] || continue
    ff_master "$parent" >/dev/null || continue          # parent itself on master first
    for child in $nested; do
        ff_master "$parent/$child" || continue
        commit_pointer "$parent" "$child" "build(deps): updated $(basename "$child")"
    done
    NESTED_PARENTS="$NESTED_PARENTS $parent"
done
[ -n "$NESTED_PARENTS" ] || echo "  (no direct submodule carries nested submodules)"

# ---------------------------------------------------------------- 2. direct submodules

step "2/4 direct submodules -> origin/master"
for m in $DIRECT; do
    in_skip "$m" && { echo "  $m: skipped"; continue; }
    ff_master "$m" || true
done

# ---------------------------------------------------------------- 3. Tauri Cargo pin

step "3/4 aw-tauri Cargo.lock -> aw-server-rust @ HEAD"
SERVER_SHA=$(target_sha aw-server-rust)
LOCK=aw-tauri/src-tauri/Cargo.lock
if in_skip aw-tauri || in_skip aw-server-rust; then
    echo "  skipped (aw-tauri or aw-server-rust in --skip)"
elif [ "$PUSH" = 0 ]; then
    warn "skipped: cargo can only relock to a revision on GitHub, and --no-push may leave ${SERVER_SHA:0:7} local-only"
elif ! git -C aw-server-rust branch -r --contains "$SERVER_SHA" | grep -q 'origin/master'; then
    warn "skipped: aw-server-rust ${SERVER_SHA:0:7} is not on origin/master yet (push it first)"
elif grep -q "aw-server-rust.git?branch=master#$SERVER_SHA" "$LOCK" \
     && [ "$(grep -c "aw-server-rust.git?branch=master#" "$LOCK")" = "$(grep -c "aw-server-rust.git?branch=master#$SERVER_SHA" "$LOCK")" ]; then
    echo "  $LOCK already at ${SERVER_SHA:0:7} for every aw-* crate"
elif [ "$DRY" = 1 ]; then
    echo "  [dry-run] would relock aw-server-rust git deps to ${SERVER_SHA:0:7}:"
    # crates whose [[package]] source is the aw-server-rust git repo
    awk '/^\[\[package\]\]/{n=""} /^name = /{n=$3} /^source = .*aw-server-rust\.git/{print "    " n}' "$LOCK" | sort -u
else
    # One --precise moves every package that shares the git source.
    (cd aw-tauri/src-tauri && cargo update -q -p aw-server --precise "$SERVER_SHA")
    stale=$(grep "aw-server-rust.git?branch=master#" "$LOCK" | grep -vc "#$SERVER_SHA" || true)
    if [ "$stale" != 0 ]; then
        echo "some aw-server-rust crates did not relock to ${SERVER_SHA:0:7}:" >&2
        grep -B3 "aw-server-rust.git?branch=master#" "$LOCK" | grep -E 'name|source' | grep -v "#$SERVER_SHA" >&2
        exit 1
    fi
    git -C aw-tauri diff --stat -- src-tauri/Cargo.lock | sed 's/^/    /'
    if confirm "commit in aw-tauri: \"build(deps): updated cargo locks\" (aw-server-rust -> ${SERVER_SHA:0:7})?"; then
        run aw-tauri add -- src-tauri/Cargo.lock
        run aw-tauri commit -q -m "build(deps): updated cargo locks

aw-server-rust -> $SERVER_SHA"
        push_master aw-tauri
    fi
fi

# ---------------------------------------------------------------- 4. bundle

step "4/4 bundle: align, validate, commit"
VERSION=$(sed -n 's/^version = "\(.*\)"/\1/p' aw-server-rust/aw-server/Cargo.toml | head -1)
if [ "$DRY" = 1 ]; then
    echo "  [dry-run] would run: check_tauri_server.py --sync && check_tauri_server.py $VERSION"
else
    python3 scripts/check_tauri_server.py --sync | sed 's/^/  /'
    python3 scripts/check_tauri_server.py "$VERSION" | sed 's/^/  /'
fi

CHANGED=""
for m in $DIRECT; do
    in_skip "$m" && continue
    pointer_changed . "$m" && CHANGED="$CHANGED $m"
done
if [ -z "$CHANGED" ]; then
    echo "  no submodule pointers changed; nothing to commit"
else
    git diff --submodule=log -- $CHANGED | sed 's/^/    /'

    # Guard: every pointer we are about to commit must already be on GitHub,
    # otherwise the bundle's CI fails checking out an unpushed submodule SHA.
    NEED_PUSH=""
    for m in $CHANGED; do unpushed "$m" && NEED_PUSH="$NEED_PUSH $m"; done
    NEED_PUSH=$(push_order $NEED_PUSH)
    BLOCKED=0
    if [ -n "$NEED_PUSH" ]; then
        warn "these submodule commits are not on GitHub yet:$(printf ' %s' $NEED_PUSH)"
        if [ "$PUSH" = 1 ] && confirm "push them first, in this order:$(printf ' %s' $NEED_PUSH)?"; then
            for m in $NEED_PUSH; do run "$m" push -q origin master; echo "  $m: pushed $(git -C "$m" rev-parse --short HEAD)"; done
        else
            BLOCKED=1
        fi
    fi

    if [ "$BLOCKED" = 1 ]; then
        warn "bundle commit skipped: push the submodules above first, then re-run"
    elif confirm "commit in bundle: \"build(deps): updated submodules\" ($(echo $CHANGED | wc -w | tr -d ' ') pointer(s))?"; then
        run . add -- $CHANGED
        run . commit -q -m "build(deps): updated submodules"
        push_master .
    fi
fi

# Under --no-push (or declined pushes) say exactly what must be pushed, and
# in what order, so CI never sees a pointer to a commit it cannot fetch.
if [ "$DRY" = 0 ]; then
    TODO=""
    for m in $DIRECT; do
        case " $TODO " in *" $m "*) continue ;; esac
        in_skip "$m" && continue
        unpushed "$m" && TODO="$TODO $m"
    done
    if [ -n "$TODO" ] || unpushed .; then
        step "push order still required"
        n=0
        for m in $(push_order $TODO); do n=$((n+1)); echo "  $n. git -C $m push origin master"; done
        unpushed . && { n=$((n+1)); echo "  $n. git push origin master   # bundle, last"; }
    fi
fi

step "done"
echo "submodule branches after:"
./scripts/submodule-branch.sh | sed 's/^/  /'
