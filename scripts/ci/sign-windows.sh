#!/usr/bin/env bash
#
# Sign Windows release artifacts (exe/dll/pyd) with signtool.
#
# Resolves #632: signs the PyInstaller binaries and the Inno Setup installer
# so Windows SmartScreen / AppLocker / antivirus tooling can validate them.
#
# Certificate resolution:
#   - If WINDOWS_CERTIFICATE_BASE64 (+ WINDOWS_CERTIFICATE_PASSWORD) is set,
#     the real code-signing PFX is used (available on tag builds in the
#     upstream repo; fork PRs never see repo secrets).
#   - Otherwise a self-signed placeholder certificate ("sham cert", as
#     requested in #632) is generated on the fly so the signing pipeline is
#     exercised end-to-end on every build. The placeholder is NOT trusted by
#     Windows, it only proves the plumbing works until the maintainer adds
#     the real certificate.
#
# Usage:
#   sign-windows.sh <dir>        sign every *.exe/*.dll/*.pyd under <dir>
#   sign-windows.sh <file>       sign a single file
#   sign-windows.sh --installers sign installer exe(s) at the dist/ root
#   sign-windows.sh (no args)    sign binaries under dist/activitywatch/
#                                plus installer exe(s) at the dist/ root
#
# The Makefile hook runs before package-all.sh so the .zip and the Inno Setup
# installer embed already-signed binaries; the release workflow then signs
# the installer itself.
set -euo pipefail

SIGNTOOL=""
for d in "/c/Program Files (x86)/Windows Kits/10/bin/"*/x64/signtool.exe; do
    if [ -f "$d" ]; then
        SIGNTOOL="$d"
        break
    fi
done
if [ -z "$SIGNTOOL" ] && [ -f "/c/Program Files (x86)/Windows Kits/10/App Certification Kit/signtool.exe" ]; then
    SIGNTOOL="/c/Program Files (x86)/Windows Kits/10/App Certification Kit/signtool.exe"
fi
if [ -z "$SIGNTOOL" ]; then
    echo "ERROR: signtool.exe not found (Windows SDK required)" >&2
    exit 1
fi
echo "Using signtool: $SIGNTOOL"

CERT_PFX=""
CERT_PASSWORD=""
REAL_CERT=false
if [ -n "${WINDOWS_CERTIFICATE_BASE64:-}" ]; then
    CERT_PFX="$(mktemp --suffix=.pfx)"
    printf '%s' "${WINDOWS_CERTIFICATE_BASE64}" | base64 -d > "$CERT_PFX"
    CERT_PASSWORD="${WINDOWS_CERTIFICATE_PASSWORD:-}"
    REAL_CERT=true
    echo "Using code-signing certificate from WINDOWS_CERTIFICATE_BASE64"
else
    echo "WINDOWS_CERTIFICATE_BASE64 not set - generating self-signed placeholder certificate"
    CERT_PFX="$(mktemp --suffix=.pfx)"
    CERT_PASSWORD="placeholder$(date +%s)"
    WIN_PFX_PATH="$(cygpath -w "$CERT_PFX")"
    powershell.exe -NoProfile -Command "
        \$cert = New-SelfSignedCertificate -Type CodeSigningCert -Subject 'CN=ActivityWatch CI (placeholder)' -CertStoreLocation Cert:\CurrentUser\My -KeyExportPolicy Exportable
        \$pw = ConvertTo-SecureString '$CERT_PASSWORD' -Force -AsPlainText
        Export-PfxCertificate -Cert \$cert -FilePath '$WIN_PFX_PATH' -Password \$pw -Force | Out-Null
        Remove-Item ('Cert:\CurrentUser\My\' + \$cert.Thumbprint)
    "
    echo "WARNING: using a self-signed placeholder certificate (not trusted by Windows)"
fi
trap 'rm -f "$CERT_PFX"' EXIT

SIGNED_COUNT=0

sign_one() {
    local file="$1"
    "$SIGNTOOL" sign /f "$CERT_PFX" /p "$CERT_PASSWORD" \
        /fd SHA256 /td SHA256 /tr http://timestamp.digicert.com "$file"
    SIGNED_COUNT=$((SIGNED_COUNT + 1))
}

sign_dir() {
    local dir="$1"
    if [ ! -d "$dir" ]; then
        echo "ERROR: directory not found: $dir" >&2
        exit 1
    fi
    local file
    while IFS= read -r -d '' file; do
        sign_one "$file"
    done < <(find "$dir" -type f \( -iname '*.exe' -o -iname '*.dll' -o -iname '*.pyd' \) -print0)
}

sign_installers() {
    local installer
    while IFS= read -r -d '' installer; do
        sign_one "$installer"
    done < <(find dist -maxdepth 1 -type f -iname '*.exe' -print0)
}

verify_one() {
    local file="$1"
    # Structural signature check (works for both placeholder and real certs).
    "$SIGNTOOL" verify /v "$file"
    # Full chain-trust check only for real certificates: a self-signed
    # placeholder is expected to fail /pa by design.
    if [ "$REAL_CERT" = true ]; then
        "$SIGNTOOL" verify /pa /v "$file"
    fi
}

verify_dir() {
    local dir="$1"
    local first
    first="$(find "$dir" -type f -iname '*.exe' | head -n1)"
    if [ -n "$first" ]; then
        verify_one "$first"
    fi
}

verify_installers() {
    local installer
    while IFS= read -r -d '' installer; do
        verify_one "$installer"
    done < <(find dist -maxdepth 1 -type f -iname '*.exe' -print0)
}

TARGET="${1:-}"
case "$TARGET" in
    --installers)
        sign_installers
        verify_installers
        ;;
    "")
        sign_dir dist/activitywatch
        sign_installers
        verify_dir dist/activitywatch
        verify_installers
        ;;
    *)
        if [ -d "$TARGET" ]; then
            sign_dir "$TARGET"
            verify_dir "$TARGET"
        else
            sign_one "$TARGET"
            verify_one "$TARGET"
        fi
        ;;
esac

echo "Signed and verified $SIGNED_COUNT file(s)"
