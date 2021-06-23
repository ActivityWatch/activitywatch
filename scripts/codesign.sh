#!/bin/bash

#set -e

# Not available on macOS bash
#shopt -s globstar

signer=XM9GC3SUL2
appsrc=dist/ActivityWatch-unsigned.app
apploc=dist/ActivityWatch.app
entitlements=scripts/package/entitlements.plist

echo 'Copying app to working location'
rm -r $apploc
cp -r $appsrc $apploc

solibs=$(find $apploc/Contents/MacOS -name '*.so')  # no -type f because some header files in .so dirs
dylibs=$(find $apploc/Contents/MacOS -type f -name '*.dylib')
execs=$(find $apploc/Contents/MacOS -type f -name 'aw-*')
jxa=$(find $apploc/Contents/MacOS -type f -name '*.jxa')
qt=$(find $apploc/Contents/MacOS -type f -name 'Qt*' -maxdepth 1)
python="$apploc/Contents/MacOS/Python"

if [[ $SIGN = "true" ]]; then
    echo 'Signing...'
    #codesign -s $signer --deep $execs
    codesign --deep -s $signer --entitlements $entitlements --option runtime $apploc
    #codesign -s $signer $solibs $dylibs $pylibs $qt $python $jxa $execs

    #echo 'Whole .app'
    #codesign -s $signer $apploc

    echo 'Checking...'
    codesign -v $apploc
else
    echo 'Env var SIGN not set, skipping'
fi
