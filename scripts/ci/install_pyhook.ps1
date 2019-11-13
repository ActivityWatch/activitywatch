function main ($arch) {
    If ( $arch -eq "64" ) {
        $url="https://github.com/ActivityWatch/wheels/raw/master/pyHook-1.5.1-cp36-cp36m-win_amd64.whl"
    } ElseIf ( $arch -eq "32" ) {
        $url="https://github.com/ActivityWatch/wheels/raw/master/pyHook-1.5.1-cp36-cp36m-win32.whl"
    } Else {
        Write-Output "Invalid architecture"
        return -1
    }
    pip install --user $url
}

main $env:PYTHON_ARCH
