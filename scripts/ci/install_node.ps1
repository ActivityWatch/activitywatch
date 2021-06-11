$msipath = "$PSScriptRoot\node-installer.msi"

function RunCommand ($command, $command_args) {
    Write-Host $command $command_args
    Start-Process -FilePath $command -ArgumentList $command_args -Wait -Passthru
}

function InstallNode () {
    DownloadNodeMSI
    InstallNodeMSI
}

function DownloadNodeMSI () {
    $url = "https://nodejs.org/dist/v12.18.4/node-v12.18.4-x64.msi"
    $start_time = Get-Date

    Write-Output "Downloading node msi"
    Invoke-WebRequest -Uri $url -OutFile $msipath
    Write-Output "Time taken: $((Get-Date).Subtract($start_time).Seconds) second(s)"
}

function InstallNodeMSI () {
    $install_args = "/qn /log node_install.log /i $msipath"
    $uninstall_args = "/qn /x $msipath"
    RunCommand "msiexec.exe" $install_args

    #if (-not(Test-Path $python_home)) {
    #    Write-Host "Python seems to be installed else-where, reinstalling."
    #    RunCommand "msiexec.exe" $uninstall_args
    #    RunCommand "msiexec.exe" $install_args
    #}
}


function main () {
    InstallNode
    rm $msipath
}

main
