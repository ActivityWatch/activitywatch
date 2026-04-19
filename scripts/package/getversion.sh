#!/bin/bash
set -e

SCRIPT_NAME="$(basename "$0")"
STRIP_V=false

show_usage() {
    cat << EOF
Usage: $SCRIPT_NAME [OPTIONS]

Get the version of ActivityWatch from git tags or CI environment variables.

Options:
    --strip-v, --no-v    Remove the 'v' prefix from the version (if present)
    --help, -h           Show this help message

Environment Variables (used in CI, checked in priority order):
    GITHUB_REF_NAME      GitHub Actions tag/ref (e.g., "v0.14.0")
    TRAVIS_TAG           Travis CI tag
    APPVEYOR_REPO_TAG_NAME AppVeyor CI tag

Version Format:
    - Release tag: v0.14.0
    - Dev version: v0.14.0.dev-abc1234
    - Beta/RC: v0.14.0b1, v0.14.0rc1

Examples:
    $SCRIPT_NAME                    # v0.14.0 or v0.14.0.dev-abc1234
    $SCRIPT_NAME --strip-v          # 0.14.0 or 0.14.0.dev-abc1234
EOF
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --strip-v|--no-v)
                STRIP_V=true
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
}

get_version_internal() {
    local _version=""
    
    if [[ -n "$GITHUB_REF" && "$GITHUB_REF" == refs/tags/v* ]]; then
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

main() {
    parse_args "$@"
    
    local version
    version="$(get_version_internal)"
    
    if $STRIP_V; then
        version="$(echo "$version" | sed -e 's/^v//')"
    fi
    
    echo "$version"
}

main "$@"
