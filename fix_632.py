import os
import subprocess

def codesign_windows_release(executable_path, certificate_path, password):
    # Use the signtool.exe to sign the executable
    signtool_path = "C:\\Program Files (x86)\\Windows Kits\\10\\App Certification Kit\\signtool.exe"
    command = f'"{signtool_path}" sign /a /fd SHA256 /td SHA256 /tr http://timestamp.digicert.com /p {password} "{executable_path}"'
    subprocess.run(command, shell=True)

    # Verify the signature
    verify_command = f'"{signtool_path}" verify /pa /q "{executable_path}"'
    subprocess.run(verify_command, shell=True)

def main():
    # Replace with the actual paths
    executable_path = "path_to_your_executable.exe"
    certificate_path = "path_to_your_certificate.pfx"
    password = "your_certificate_password"

    codesign_windows_release(executable_path, certificate_path, password)

if __name__ == "__main__":
    main()