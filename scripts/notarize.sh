#!/bin/bash

applemail=$APPLE_EMAIL # Email address used for Apple ID
password=$APPLE_PASSWORD # See apps-specific password https://support.apple.com/en-us/HT204397
teamid=$APPLE_TEAMID # Team idenitifer (if single developer, then set to developer identifier)
keychain_profile="activitywatch-$APPLE_PERSONALID"  # name of the keychain profile to use
bundleid=net.activitywatch.ActivityWatch # Match aw.spec
app=dist/ActivityWatch.app
dmg=dist/ActivityWatch.dmg

# XCode >= 13
run_notarytool() {
    dist=$1
    # Setup the credentials for notarization
    xcrun notarytool store-credentials $keychain_profile --apple-id $applemail --team-id $teamid --password $password
    # Notarize and wait; capture output to extract submission ID on failure
    echo "Notarization: starting for $dist"
    echo "Notarization: in progress for $dist"
    submission_output=$(xcrun notarytool submit $dist --keychain-profile $keychain_profile --wait 2>&1)
    submission_exit=$?
    echo "$submission_output"
    # On failure, retrieve the detailed rejection log from Apple's server.
    # This avoids having to run 'notarytool log' manually after the fact.
    if echo "$submission_output" | grep -q "status: Invalid"; then
        uuid=$(echo "$submission_output" | grep '^\s*id:' | head -1 | awk '{print $NF}')
        if [ -n "$uuid" ]; then
            echo ""
            echo "=== Notarization rejected (status: Invalid) — fetching rejection log for $uuid ==="
            xcrun notarytool log "$uuid" --keychain-profile $keychain_profile 2>&1 || true
            echo "=== End of rejection log ==="
        fi
        return 1
    fi
    return $submission_exit
}

# XCode < 13 
run_altool() {
    dist=$1
    # Setup the credentials for notarization
    xcrun altool --store-password-in-keychain-item $keychain_profile -u $applemail -p $password
    # Notarize and wait
    echo "Notarization: starting for $dist"
    upload=$(xcrun altool --notarize-app -t osx -f $dist --primary-bundle-id $bundleid -u $applemail --password "@keychain:$keychain_profile")
    uuid = $(/usr/libexec/PlistBuddy -c "Print :notarization-upload:RequestUUID" $upload)
    while true; do 
        req=$(xcrun altool --notarization-info $uuid -u $applemail -p $password --output-format xml)
        status=$(/usr/libexec/PlistBuddy -c "Print :notarization-info:Status" $req)
        if [ $status != "in progress" ]; then 
            break
        else
            echo "Notarization: in progress for $dist"
        fi
        sleep 10
    done
}

# Staples the notarization certificate to the executable/bunldle
run_stapler() {
    dist=$1
    xcrun stapler staple $dist
}

echo 'Detecting availability of notarization tools'
notarization_method=exit
# Detect if notarytool is available
xcrun notarytool >/dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "+ Found notarytool"
    notarization_method=run_notarytool
fi
# Fallbqck to altool
output=xcrun altool >/dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "+ Found altool"
    notarization_method=run_altool
fi

if [ $notarization_method = "exit" ]; then
    echo "- Found no tools, exiting"
    $notarization_method
fi

if test -d "$app"; then
    echo "Notarizing: $app"
    zip=$app.zip
    # Turn the app into a zip file that notarization will accept
    ditto -c -k --keepParent "$app" "$zip"
    $notarization_method "$zip"
    run_stapler "$app"
else
    echo "Skipping: $app (expected .app bundle directory)"
fi

if test -f "$dmg"; then
    echo "Notarizing: $dmg"
    $notarization_method "$dmg"
    run_stapler "$dmg"
else
    echo "Skipping: $dmg"
fi
