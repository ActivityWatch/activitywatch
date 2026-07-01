#!/bin/sh

set -eu

export KEY_CHAIN="${KEY_CHAIN:-build.keychain-db}"
export CERTIFICATE_P12="${CERTIFICATE_P12:-aw_certificate.p12}"

# Recreate the certificate from the secure environment variable.
printf '%s' "$CERTIFICATE_MACOS_P12_BASE64" | base64 --decode > "$CERTIFICATE_P12"

# Recreate the temporary keychain on every run so stale state cannot leak between jobs.
security -v delete-keychain "$KEY_CHAIN" >/dev/null 2>&1 || true
security -v create-keychain -p travis "$KEY_CHAIN"
security -v default-keychain -s "$KEY_CHAIN"
security -v unlock-keychain -p travis "$KEY_CHAIN"
security -v set-keychain-settings -lut 21600 "$KEY_CHAIN"
security -v list-keychains -d user -s "$KEY_CHAIN" login.keychain-db login.keychain

security -v import "$CERTIFICATE_P12" -k "$KEY_CHAIN" -P "$CERTIFICATE_MACOS_P12_PASSWORD" -A
security -v set-key-partition-list -S apple-tool:,apple: -s -k travis "$KEY_CHAIN"
security -v find-identity -v -p codesigning "$KEY_CHAIN"

rm -f "$CERTIFICATE_P12"
