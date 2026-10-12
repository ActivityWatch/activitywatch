#!/bin/bash
# Architecture token for ActivityWatch package filenames.
#
# On Windows, Git Bash's `uname -m` reports x86_64 under x64 emulation even on
# ARM64 hosts (windows-11-arm). That named the Tauri ARM64 zip
# windows-x86_64 and overwrote the genuine Intel/AMD asset
# (ActivityWatch/activitywatch#1519). Prefer GitHub Actions' RUNNER_ARCH, then
# PROCESSOR_ARCHITECTURE / PROCESSOR_ARCHITEW6432. Linux and macOS keep
# `uname -m` so existing linux-aarch64 / macos-arm64 names stay put.

set -euo pipefail

_kernel="$(uname | tr '[:upper:]' '[:lower:]')"
_machine="$(uname -m)"

_is_windows=0
case "$_kernel" in
    mingw*|msys*|cygwin*) _is_windows=1 ;;
esac

_normalize_windows() {
    case "$(echo "$1" | tr '[:upper:]' '[:lower:]')" in
        arm64|aarch64) echo "aarch64" ;;
        x64|amd64|x86_64) echo "x86_64" ;;
        x86|i386|i686) echo "x86" ;;
        *) echo "$1" ;;
    esac
}

if [[ $_is_windows -eq 1 ]]; then
    if [[ -n "${RUNNER_ARCH:-}" ]]; then
        _normalize_windows "$RUNNER_ARCH"
        exit 0
    fi
    # WOW64 32-bit process on a 64-bit OS: the *native* arch is here.
    if [[ -n "${PROCESSOR_ARCHITEW6432:-}" ]]; then
        _normalize_windows "$PROCESSOR_ARCHITEW6432"
        exit 0
    fi
    if [[ -n "${PROCESSOR_ARCHITECTURE:-}" ]]; then
        _normalize_windows "$PROCESSOR_ARCHITECTURE"
        exit 0
    fi
    _normalize_windows "$_machine"
    exit 0
fi

echo "$_machine"
