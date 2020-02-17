#!/bin/sh
# Source: https://www.update.rocks/blog/osx-signing-with-travis/
export KEY_CHAIN=aw-build.keychain
export CERTIFICATE_P12="aw_certificate"

# Recreate the certificate from the secure environment variable
echo $CERTIFICATE_OSX_P12 | base64 --decode > $CERTIFICATE_P12

#create a keychain
security -v create-keychain -p travis $KEY_CHAIN
# Make the keychain the default so identities are found
security -v default-keychain -s $KEY_CHAIN
# Unlock the keychain
security -v unlock-keychain -p travis $KEY_CHAIN

security -v import $CERTIFICATE_P12 -k $KEY_CHAIN -P $CERTIFICATE_PASSWORD -T /usr/bin/codesign;
security -v set-key-partition-list -S apple-tool:,apple: -s -k travis $KEY_CHAIN

# remove certs
rm -rf *.p12
