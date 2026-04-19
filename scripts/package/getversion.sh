#!/bin/bash
#
# ActivityWatch Version Determination Script
# =========================================
#
# This script determines the version for ActivityWatch builds.
# It supports multiple environments: GitHub Actions, Travis CI, AppVeyor,
# as well as local development environments.
#
# Priority Order:
#   1. Environment variable tags (GITHUB_REF_NAME, TRAVIS_TAG, APPVEYOR_REPO_TAG_NAME)
#   2. Git exact tag (if git is available and there's an exact tag match)
#   3. Git latest tag + commit hash (if git is available)
#   4. pyproject.toml version + commit hash (if git is available but no tags)
#   5. pyproject.toml version + nogit (if git is NOT available)
#
# Usage:
#   bash scripts/package/getversion.sh          # Tag version (with 'v' prefix)
#   bash scripts/package/getversion.sh --tag    # Tag version (with 'v' prefix)
#   bash scripts/package/getversion.sh --display # Display version (no 'v' prefix)
#   bash scripts/package/getversion.sh --env    # Output shell variables (for eval)
#   bash scripts/package/getversion.sh --json   # Output JSON (for programmatic use)
#   bash scripts/package/getversion.sh --help   # Show help
#
#   bash scripts/package/getversion.sh --self-test  # Run self-tests
#
# Environment Variables (tested in order):
#   GITHUB_REF_NAME           GitHub Actions tag (e.g., "v0.14.0")
#   TRAVIS_TAG                Travis CI tag
#   APPVEYOR_REPO_TAG_NAME    AppVeyor tag
#
# Exit Codes:
#   0:  Success
#   1:  Error
#   2:  Help shown
#
# =========================================

set -euo pipefail

# =====================================
# Configuration
# =====================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PYPROJECT_TOML="$PROJECT_ROOT/pyproject.toml"

# Default values (fallback if nothing else works)
FALLBACK_VERSION="0.0.0"
DEV_PREFIX="dev"

# =====================================
# Logging Functions
# =====================================

log_info() {
    echo "[INFO] $@" >&2
}

log_error() {
    echo "[ERROR] $@" >&2
}

log_warn() {
    echo "[WARN] $@" >&2
}

log_debug() {
    if [[ "${VERBOSE:-0}" == "1" ]]; then
        echo "[DEBUG] $@" >&2
    fi
}

# =====================================
# Helper Functions
# =====================================

show_help() {
    cat << EOF
ActivityWatch Version Determination Script

Usage: $(basename "$0") [OPTIONS]

Options:
  --tag, -t       Output tag version (with 'v' prefix, e.g., v0.14.0)
  --display, -d   Output display version (no 'v' prefix, e.g., 0.14.0)
  --env, -e       Output shell variables (for eval)
  --json, -j      Output JSON
  --help, -h      Show this help
  --self-test     Run self-tests
  --verbose, -v   Verbose output (for debugging)

Version Priority:
  1. Environment tags (GITHUB_REF_NAME, TRAVIS_TAG, APPVEYOR_REPO_TAG_NAME)
  2. Git exact tag (if available)
  3. Git latest tag + commit hash
  4. pyproject.toml version + commit hash
  5. pyproject.toml version + nogit (fallback)

Examples:
  # Get tag version (for git tags)
  scripts/package/getversion.sh --tag
  # Output: v0.14.0

  # Get display version (for filenames, Info.plist)
  scripts/package/getversion.sh --display
  # Output: 0.14.0

  # Use in scripts
  eval "\$(scripts/package/getversion.sh --env)"
  echo "\$TAG_VERSION"     # v0.14.0
  echo "\$DISPLAY_VERSION" # 0.14.0
EOF
    exit 2
}

# Check if git is available and we're in a git repository
has_git() {
    # Check if git command exists
    if ! command -v git &>/dev/null; then
        log_debug "git command not found"
        return 1
    fi
    
    # Check if we're in a git repository
    if ! git rev-parse --git-dir &>/dev/null 2>&1; then
        log_debug "Not in a git repository"
        return 1
    fi
    
    return 0
}

# Check if there are any tags in the repository
has_tags() {
    if ! has_git; then
        return 1
    fi
    
    local tag_count
    tag_count=$(git tag -l 2>/dev/null | wc -l)
    if [[ $tag_count -eq 0 ]]; then
        log_debug "No git tags found"
        return 1
    fi
    
    return 0
}

# Get version from pyproject.toml
get_pyproject_version() {
    if [[ ! -f "$PYPROJECT_TOML" ]]; then
        log_debug "pyproject.toml not found at: $PYPROJECT_TOML"
        echo "$FALLBACK_VERSION"
        return
    fi
    
    # Try to parse version from pyproject.toml
    # Format: version = "0.13.2"
    # Use basic sed regex for cross-platform compatibility (macOS + Linux)
    local version_line
    version_line=$(grep -E '^version\s*=' "$PYPROJECT_TOML" 2>/dev/null | head -1)
    
    if [[ -z "$version_line" ]]; then
        log_debug "Could not find version line in pyproject.toml, using fallback"
        echo "$FALLBACK_VERSION"
        return
    fi
    
    # Extract value between quotes using basic regex
    # Works on both macOS and Linux
    local version
    version=$(echo "$version_line" | sed 's/.*"\([^"]*\)".*/\1/')
    
    if [[ -z "$version" ]] || [[ "$version" == *"version"* ]]; then
        log_debug "Could not parse version from pyproject.toml, using fallback"
        echo "$FALLBACK_VERSION"
        return
    fi
    
    log_debug "Read version from pyproject.toml: $version"
    echo "$version"
}

# Get short commit hash
get_commit_hash() {
    if ! has_git; then
        echo "nogit"
        return
    fi
    
    local hash
    hash=$(git rev-parse --short HEAD 2>/dev/null) || hash="nogit"
    echo "$hash"
}

# Strip 'v' prefix from version
strip_v_prefix() {
    local version="$1"
    if [[ "$version" == v* ]]; then
        echo "${version:1}"
    else
        echo "$version"
    fi
}

# Ensure version has 'v' prefix
ensure_v_prefix() {
    local version="$1"
    if [[ "$version" == v* ]]; then
        echo "$version"
    else
        echo "v$version"
    fi
}

# =====================================
# Version Determination Logic
# =====================================

determine_version() {
    local tag_version
    local source="unknown"
    
    # =====================================
    # Priority 1: Check environment variables (CI tags)
    # =====================================
    
    # Check GITHUB_REF_NAME (GitHub Actions)
    if [[ -n "${GITHUB_REF_NAME:-}" ]]; then
        # Only use if it looks like a tag (starts with 'v' or is a version)
        if [[ "$GITHUB_REF_NAME" == v* ]] || [[ "$GITHUB_REF_NAME" =~ ^[0-9]+\.[0-9]+\.[0-9]+ ]]; then
            tag_version="$GITHUB_REF_NAME"
            source="GITHUB_REF_NAME"
            log_debug "Using version from GITHUB_REF_NAME: $tag_version"
        fi
    fi
    
    # Check TRAVIS_TAG (Travis CI)
    if [[ -z "${tag_version:-}" ]] && [[ -n "${TRAVIS_TAG:-}" ]]; then
        tag_version="$TRAVIS_TAG"
        source="TRAVIS_TAG"
        log_debug "Using version from TRAVIS_TAG: $tag_version"
    fi
    
    # Check APPVEYOR_REPO_TAG_NAME (AppVeyor)
    if [[ -z "${tag_version:-}" ]] && [[ -n "${APPVEYOR_REPO_TAG_NAME:-}" ]]; then
        tag_version="$APPVEYOR_REPO_TAG_NAME"
        source="APPVEYOR_REPO_TAG_NAME"
        log_debug "Using version from APPVEYOR_REPO_TAG_NAME: $tag_version"
    fi
    
    # =====================================
    # Priority 2: Check git for exact tag match
    # =====================================
    
    if [[ -z "${tag_version:-}" ]] && has_git; then
        # Try exact tag match
        local exact_tag
        exact_tag=$(git describe --tags --abbrev=0 --exact-match 2>/dev/null) || true
        
        if [[ -n "$exact_tag" ]]; then
            tag_version="$exact_tag"
            source="git-exact-tag"
            log_debug "Using version from git exact tag: $tag_version"
        fi
    fi
    
    # =====================================
    # Priority 3: Git latest tag + commit hash (dev version)
    # =====================================
    
    if [[ -z "${tag_version:-}" ]] && has_git && has_tags; then
        # Get latest tag
        local latest_tag
        latest_tag=$(git describe --tags --abbrev=0 2>/dev/null) || true
        
        if [[ -n "$latest_tag" ]]; then
            local commit_hash
            commit_hash=$(get_commit_hash)
            tag_version="$(ensure_v_prefix "$latest_tag").${DEV_PREFIX}-${commit_hash}"
            source="git-latest-tag"
            log_debug "Using version from git latest tag + commit: $tag_version"
        fi
    fi
    
    # =====================================
    # Priority 4: pyproject.toml version + commit hash
    # =====================================
    
    if [[ -z "${tag_version:-}" ]] && has_git; then
        local pyproject_version
        pyproject_version=$(get_pyproject_version)
        local commit_hash
        commit_hash=$(get_commit_hash)
        tag_version="v${pyproject_version}.${DEV_PREFIX}-${commit_hash}"
        source="pyproject+git"
        log_debug "Using version from pyproject.toml + git commit: $tag_version"
    fi
    
    # =====================================
    # Priority 5: pyproject.toml version + nogit (fallback)
    # =====================================
    
    if [[ -z "${tag_version:-}" ]]; then
        local pyproject_version
        pyproject_version=$(get_pyproject_version)
        tag_version="v${pyproject_version}+nogit"
        source="pyproject+nogit"
        log_debug "Using version from pyproject.toml + nogit: $tag_version"
        log_warn "Git not available, using fallback version: $tag_version"
    fi
    
    # =====================================
    # Compute display version (without 'v' prefix)
    # =====================================
    
    local display_version
    display_version=$(strip_v_prefix "$tag_version")
    
    # Return both versions
    echo "$tag_version|$display_version|$source"
}

# =====================================
# Output Functions
# =====================================

output_tag() {
    local result
    result=$(determine_version)
    local tag_version
    tag_version=$(echo "$result" | cut -d'|' -f1)
    echo "$tag_version"
}

output_display() {
    local result
    result=$(determine_version)
    local display_version
    display_version=$(echo "$result" | cut -d'|' -f2)
    echo "$display_version"
}

output_env() {
    local result
    result=$(determine_version)
    local tag_version
    local display_version
    local source
    tag_version=$(echo "$result" | cut -d'|' -f1)
    display_version=$(echo "$result" | cut -d'|' -f2)
    source=$(echo "$result" | cut -d'|' -f3)
    
    cat << EOF
export TAG_VERSION="$tag_version"
export DISPLAY_VERSION="$display_version"
export VERSION_SOURCE="$source"
EOF
}

output_json() {
    local result
    result=$(determine_version)
    local tag_version
    local display_version
    local source
    tag_version=$(echo "$result" | cut -d'|' -f1)
    display_version=$(echo "$result" | cut -d'|' -f2)
    source=$(echo "$result" | cut -d'|' -f3)
    
    cat << EOF
{"tag_version":"$tag_version","display_version":"$display_version","source":"$source"}
EOF
}

# =====================================
# Self-Test Functions
# =====================================

SELF_TEST_PASSED=0
SELF_TEST_FAILED=0

test_assert() {
    local condition="$1"
    local test_name="$2"
    
    if eval "$condition"; then
        ((SELF_TEST_PASSED++))
        echo "  [PASS] $test_name"
    else
        ((SELF_TEST_FAILED++))
        echo "  [FAIL] $test_name"
    fi
}

test_assert_equal() {
    local actual="$1"
    local expected="$2"
    local test_name="$3"
    
    if [[ "$actual" == "$expected" ]]; then
        ((SELF_TEST_PASSED++))
        echo "  [PASS] $test_name"
    else
        ((SELF_TEST_FAILED++))
        echo "  [FAIL] $test_name"
        echo "         Expected: '$expected'"
        echo "         Actual:   '$actual'"
    fi
}

run_self_tests() {
    echo "========================================"
    echo "Running Self-Tests"
    echo "========================================"
    echo ""
    
    local original_github="${GITHUB_REF_NAME:-}"
    local original_travis="${TRAVIS_TAG:-}"
    local original_appveyor="${APPVEYOR_REPO_TAG_NAME:-}"
    
    # =====================================
    # Test 1: strip_v_prefix
    # =====================================
    echo "Test Group: strip_v_prefix"
    
    test_assert_equal "$(strip_v_prefix "v0.14.0")" "0.14.0" "strip_v_prefix('v0.14.0')"
    test_assert_equal "$(strip_v_prefix "0.14.0")" "0.14.0" "strip_v_prefix('0.14.0')"
    test_assert_equal "$(strip_v_prefix "v0.14.0b1.dev-abc123")" "0.14.0b1.dev-abc123" "strip_v_prefix(dev version)"
    
    echo ""
    
    # =====================================
    # Test 2: ensure_v_prefix
    # =====================================
    echo "Test Group: ensure_v_prefix"
    
    test_assert_equal "$(ensure_v_prefix "0.14.0")" "v0.14.0" "ensure_v_prefix('0.14.0')"
    test_assert_equal "$(ensure_v_prefix "v0.14.0")" "v0.14.0" "ensure_v_prefix('v0.14.0')"
    
    echo ""
    
    # =====================================
    # Test 3: get_pyproject_version
    # =====================================
    echo "Test Group: get_pyproject_version"
    
    local pyproject_version
    pyproject_version=$(get_pyproject_version)
    echo "  [INFO] pyproject.toml version: $pyproject_version"
    
    # Should not be empty or fallback
    test_assert "[[ \"$pyproject_version\" != \"\" ]]" "get_pyproject_version returns non-empty"
    test_assert "[[ \"$pyproject_version\" != \"$FALLBACK_VERSION\" ]]" "get_pyproject_version is not fallback"
    test_assert "[[ \"$pyproject_version\" =~ ^[0-9]+\.[0-9]+\.[0-9]+ ]]" "get_pyproject_version matches semver pattern"
    
    echo ""
    
    # =====================================
    # Test 4: Environment variable priority
    # =====================================
    echo "Test Group: Environment Variable Priority"
    
    # Test GITHUB_REF_NAME
    export GITHUB_REF_NAME="v0.15.0"
    unset TRAVIS_TAG 2>/dev/null || true
    unset APPVEYOR_REPO_TAG_NAME 2>/dev/null || true
    
    local result
    result=$(determine_version)
    local tag_version
    tag_version=$(echo "$result" | cut -d'|' -f1)
    local source
    source=$(echo "$result" | cut -d'|' -f3)
    
    test_assert "[[ \"$tag_version\" == \"v0.15.0\" ]]" "GITHUB_REF_NAME sets version"
    test_assert "[[ \"$source\" == \"GITHUB_REF_NAME\" ]]" "GITHUB_REF_NAME is the source"
    
    echo ""
    
    # =====================================
    # Test 5: TRAVIS_TAG
    # =====================================
    echo "Test Group: TRAVIS_TAG"
    
    unset GITHUB_REF_NAME 2>/dev/null || true
    export TRAVIS_TAG="v0.16.0"
    unset APPVEYOR_REPO_TAG_NAME 2>/dev/null || true
    
    result=$(determine_version)
    tag_version=$(echo "$result" | cut -d'|' -f1)
    source=$(echo "$result" | cut -d'|' -f3)
    
    test_assert "[[ \"$tag_version\" == \"v0.16.0\" ]]" "TRAVIS_TAG sets version"
    test_assert "[[ \"$source\" == \"TRAVIS_TAG\" ]]" "TRAVIS_TAG is the source"
    
    echo ""
    
    # =====================================
    # Test 6: APPVEYOR_REPO_TAG_NAME
    # =====================================
    echo "Test Group: APPVEYOR_REPO_TAG_NAME"
    
    unset GITHUB_REF_NAME 2>/dev/null || true
    unset TRAVIS_TAG 2>/dev/null || true
    export APPVEYOR_REPO_TAG_NAME="v0.17.0"
    
    result=$(determine_version)
    tag_version=$(echo "$result" | cut -d'|' -f1)
    source=$(echo "$result" | cut -d'|' -f3)
    
    test_assert "[[ \"$tag_version\" == \"v0.17.0\" ]]" "APPVEYOR_REPO_TAG_NAME sets version"
    test_assert "[[ \"$source\" == \"APPVEYOR_REPO_TAG_NAME\" ]]" "APPVEYOR_REPO_TAG_NAME is the source"
    
    echo ""
    
    # =====================================
    # Test 7: Environment variables without 'v' prefix
    # =====================================
    echo "Test Group: Environment Variables Without 'v' Prefix"
    
    unset GITHUB_REF_NAME 2>/dev/null || true
    unset TRAVIS_TAG 2>/dev/null || true
    unset APPVEYOR_REPO_TAG_NAME 2>/dev/null || true
    export GITHUB_REF_NAME="0.18.0"  # Without 'v' prefix
    
    result=$(determine_version)
    tag_version=$(echo "$result" | cut -d'|' -f1)
    local display_version
    display_version=$(echo "$result" | cut -d'|' -f2)
    
    # The version should be used as-is (strip_v_prefix in output functions handles it)
    test_assert_equal "$display_version" "0.18.0" "Display version without 'v'"
    
    echo ""
    
    # =====================================
    # Test 8: Display version (strip_v_prefix)
    # =====================================
    echo "Test Group: Display Version"
    
    # Test with 'v' prefix
    unset GITHUB_REF_NAME 2>/dev/null || true
    unset TRAVIS_TAG 2>/dev/null || true
    unset APPVEYOR_REPO_TAG_NAME 2>/dev/null || true
    export GITHUB_REF_NAME="v1.2.3"
    
    local display
    display=$(output_display)
    test_assert_equal "$display" "1.2.3" "display version strips 'v' prefix"
    
    echo ""
    
    # =====================================
    # Test 9: has_git (should work in this repo)
    # =====================================
    echo "Test Group: Git Detection"
    
    if has_git; then
        test_assert "true" "has_git returns true in this repo"
        
        local commit_hash
        commit_hash=$(get_commit_hash)
        test_assert "[[ \"$commit_hash\" != \"nogit\" ]]" "get_commit_hash returns hash"
        test_assert "[[ \"$commit_hash\" =~ ^[a-f0-9]{7,} ]]" "commit_hash looks like git hash"
    else
        test_assert "true" "has_git returns false (not in git repo)"
    fi
    
    echo ""
    
    # =====================================
    # Restore original environment
    # =====================================
    if [[ -n "$original_github" ]]; then
        export GITHUB_REF_NAME="$original_github"
    else
        unset GITHUB_REF_NAME 2>/dev/null || true
    fi
    
    if [[ -n "$original_travis" ]]; then
        export TRAVIS_TAG="$original_travis"
    else
        unset TRAVIS_TAG 2>/dev/null || true
    fi
    
    if [[ -n "$original_appveyor" ]]; then
        export APPVEYOR_REPO_TAG_NAME="$original_appveyor"
    else
        unset APPVEYOR_REPO_TAG_NAME 2>/dev/null || true
    fi
    
    # =====================================
    # Test Summary
    # =====================================
    echo "========================================"
    echo "Self-Test Summary"
    echo "========================================"
    echo "  Passed: $SELF_TEST_PASSED"
    echo "  Failed: $SELF_TEST_FAILED"
    echo ""
    
    if [[ $SELF_TEST_FAILED -gt 0 ]]; then
        echo "[ERROR] Some tests failed!"
        exit 1
    else
        echo "[OK] All tests passed!"
        exit 0
    fi
}

# =====================================
# Main
# =====================================

main() {
    local output_mode="tag"  # Default: tag version (with 'v' prefix)
    VERBOSE=0
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --tag|-t)
                output_mode="tag"
                shift
                ;;
            --display|-d)
                output_mode="display"
                shift
                ;;
            --env|-e)
                output_mode="env"
                shift
                ;;
            --json|-j)
                output_mode="json"
                shift
                ;;
            --verbose|-v)
                VERBOSE=1
                shift
                ;;
            --help|-h)
                show_help
                ;;
            --self-test|--test)
                run_self_tests
                ;;
            *)
                # Legacy: treat as default (tag mode)
                # First argument used to be --strip-v
                shift
                ;;
        esac
    done
    
    # Handle legacy --strip-v (now --display is preferred)
    # For backward compatibility, if no arguments, output tag version
    # If user passes --strip-v, output display version (old behavior)
    
    # Output based on mode
    case "$output_mode" in
        tag)
            output_tag
            ;;
        display)
            output_display
            ;;
        env)
            output_env
            ;;
        json)
            output_json
            ;;
    esac
}

# Run main if not sourced
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
