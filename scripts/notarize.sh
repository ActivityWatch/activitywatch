appleid="<name@domain.com>" # Email address used for Apple ID
password="<secret_2FA_password>" # See apps-specific password https://support.apple.com/en-us/HT204397
teamid="XM9GC3SUL2" # Team idenitifer (if single developer, then set to developer identifier)
bundleid=net.activitywatch.ActivityWatch # Match aw.spec
app=dist/ActivityWatch.app
dmg=dist/ActivityWatch.dmg

# XCode >= 13 
run_notarytool() {
    dist=$1
    # Setup the credentials for notarization
    xcrun notarytool store-credentials "ActivityWatchSigner" --apple-id $appleid --team-id $teamid --password $password
    # Notarize and wait
    echo "Notarization: starting for $dist"
    echo "Notarization: in progress for $dist"
    xcrun notarytool submit $dist --keychain-profile "ActivityWatchSigner" --wait
}

# XCode < 13 
run_altool() {
    dist=$1
    # Setup the credentials for notarization
    xcrun altool --store-password-in-keychain-item "ActivityWatchSigner" -u $appleid -p $password
    # Notarize and wait
    echo "Notarization: starting for $dist"
    upload=$(xcrun altool --notarize-app -t osx -f $dist --primary-bundle-id $bundleid -u $appleid --password "@keychain:ActivityWatchSigner")
    uuid = $(/usr/libexec/PlistBuddy -c "Print :notarization-upload:RequestUUID" $upload)
    while true; do 
        req=$(xcrun altool --notarization-info $uuid -u $username -p $password --output-format xml)
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

if test -f "$app"; then
    echo "Notarizing: $app"
    zip=$app.zip
    # Turn the app into a zip file that notarization will accept
    ditto -c -k --keepParent $app $zip
    $notarization_method $zip
    run_stapler $app
else
    echo "Skipping: $app"
fi

if test -f "$dmg"; then
    echo "Notarizing: $dmg"
    $notarization_method $dmg
    run_stapler $dmg
else
    echo "Skipping: $dmg"
fi