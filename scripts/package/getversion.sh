#!/bin/bash
set -e

SCRIPT_NAME="$(basename "$0")"
MODE=""

show_usage() {
    cat << EOF
Usage: $SCRIPT_NAME [MODE]

Get the version of ActivityWatch from git tags or CI environment variables.
This is the single source of truth for version calculation.

Modes (mutually exclusive, only one allowed):
    (default)          Output DISPLAY_VERSION (without 'v' prefix)
    --tag, -t          Output TAG_VERSION (with 'v' prefix, e.g., v0.14.0)
    --display, -d      Output DISPLAY_VERSION (without 'v' prefix, e.g., 0.14.0)
    --env, -e          Output shell variables for sourcing (export commands)
    --json, -j         Output JSON format with both versions
    --help, -h         Show this help message

Version Components:
    TAG_VERSION        With 'v' prefix, e.g., v0.14.0 or v0.14.0.dev-abc1234
    DISPLAY_VERSION    Without 'v' prefix, e.g., 0.14.0 or 0.14.0.dev-abc1234
                       Used for: Info.plist, zip filenames, installers, deb packages

Environment Variables (checked in priority order for CI):
    GITHUB_REF_NAME      GitHub Actions tag/ref (e.g., "v0.14.0")
    TRAVIS_TAG           Travis CI tag
    APPVEYOR_REPO_TAG_NAME AppVeyor CI tag

Fallback Logic:
    1. Exact git tag match → use that tag
    2. Latest tag + dev suffix → v0.14.0.dev-abc1234
    3. No tags → v0.0.0.dev-<commit>

Examples:
    # Get DISPLAY_VERSION (default, no 'v')
    $SCRIPT_NAME                    # 0.14.0 or 0.14.0.dev-abc1234
    $SCRIPT_NAME --display          # 0.14.0 or 0.14.0.dev-abc1234

    # Get TAG_VERSION (with 'v')
    $SCRIPT_NAME --tag              # v0.14.0 or v0.14.0.dev-abc1234

    # Output environment variables (for CI)
    $SCRIPT_NAME --env
    # export TAG_VERSION="v0.14.0"
    # export DISPLAY_VERSION="0.14.0"

    # Output JSON
    $SCRIPT_NAME --json
    # {"tag_version": "v0.14.0", "display_version": "0.14.0"}

    # Source in CI script
    eval "\$($SCRIPT_NAME --env)"
    echo "\$DISPLAY_VERSION"  # 0.14.0
EOF
}

parse_args() {
    local mode_count=0
    
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --tag|-t)
                MODE="tag"
                mode_count=$((mode_count + 1))
                shift
                ;;
            --display|-d)
                MODE="display"
                mode_count=$((mode_count + 1))
                shift
                ;;
            --env|-e)
                MODE="env"
                mode_count=$((mode_count + 1))
                shift
                ;;
            --json|-j)
                MODE="json"
                mode_count=$((mode_count + 1))
                shift
                ;;
            --help|-h)
                show_usage
                exit 0
                ;;
            *)
                echo "ERROR: Unknown argument: $1" >&2
                show_usage >&2
                exit 1
                ;;
        esac
    done
    
    if [[ $mode_count -gt 1 ]]; then
        echo "ERROR: Only one mode argument allowed (--tag, --display, --env, --json are mutually exclusive)" >&2
        show_usage >&2
        exit 1
    fi
    
    if [[ -z "$MODE" ]]; then
        MODE="display"
    fi
}

get_version_internal() {
    local _version=""
    
    if [[ -n "$GITHUB_REF_NAME" && "$GITHUB_REF_NAME" == v* ]]; then
        _version="$GITHUB_REF_NAME"
    elif [[ -n "$TRAVIS_TAG" ]]; then
        _version="$TRAVIS_TAG"
    elif [[ -n "$APPVEYOR_REPO_TAG_NAME" ]]; then
        _version="$APPVEYOR_REPO_TAG_NAME"
    else
        _version="$(git describe --tags --abbrev=0 --exact-match 2>/dev/null || true)"
        if [[ -z "$_version" ]]; then
            local _latest_tag
            _latest_tag="$(git describe --tags --abbrev=0 2>/dev/null || echo "v0.0.0")"
            local _commit_hash
            _commit_hash="$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")"
            _version="${_latest_tag}.dev-${_commit_hash}"
        fi
    fi
    
    echo "$_version"
}

strip_v_prefix() {
    local version="$1"
    echo "$version" | sed -e 's/^v//'
}

main() {
    parse_args "$@"
    
    local tag_version
    local display_version
    
    tag_version="$(get_version_internal)"
    display_version="$(strip_v_prefix "$tag_version")"
    
    case "$MODE" in
        tag)
            echo "$tag_version"
            ;;
        display)
            echo "$display_version"
            ;;
        env)
            cat << EOF
export TAG_VERSION="$tag_version"
export DISPLAY_VERSION="$display_version"
EOF
            ;;
        json)
            cat << EOF
{"tag_version": "$tag_version", "display_version": "$display_version"}
EOF
            ;;
    esac
}

main "$@"
