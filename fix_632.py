import subprocess
import sys
import argparse

def codesign_windows_release(executable_path: str, certificate_path: str, password: str):
    """
    Signs and verifies a Windows executable using signtool.
    Raises CalledProcessError if signing or verification fails.
    """
    signtool_path = r"C:\Program Files (x86)\Windows Kits\10\App Certification Kit\signtool.exe"
    
    # FIX: Use /f for certificate path and /p for password, instead of /a
    sign_command = [
        signtool_path,
        "sign",
        "/f", certificate_path,
        "/p", password,
        "/fd", "SHA256",
        "/td", "SHA256",
        "/tr", "http://timestamp.digicert.com",
        executable_path
    ]
    
    # FIX: Use check=True to propagate failures and exit with non-zero status
    print(f"Signing {executable_path}...")
    subprocess.run(sign_command, check=True)
    
    # Verify signature
    verify_command = [
        signtool_path,
        "verify",
        "/pa",
        executable_path
    ]
    
    print(f"Verifying signature for {executable_path}...")
    subprocess.run(verify_command, check=True)
    print("Code signing and verification successful.")

def main():
    # FIX: Replace placeholders with argparse for CI/CD integration
    parser = argparse.ArgumentParser(description="Code sign Windows releases using signtool.")
    parser.add_argument("--executable", required=True, help="Path to the executable to sign")
    parser.add_argument("--certificate", required=True, help="Path to the PFX certificate file")
    parser.add_argument("--password", required=True, help="Password for the PFX certificate")
    
    args = parser.parse_args()
    
    try:
        codesign_windows_release(args.executable, args.certificate, args.password)
    except subprocess.CalledProcessError as e:
        print(f"Error: Code signing failed with exit code {e.returncode}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print("Error: signtool.exe not found. Ensure Windows SDK is installed.", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
