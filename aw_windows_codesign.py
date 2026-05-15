"""Windows code signing support for ActivityWatch releases.

Addresses issue #632: Code sign the Windows releases
"""

import os
import subprocess
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class WindowsCodeSigner:
    """Handles code signing for Windows releases."""

    def __init__(
        self,
        certificate_path: Optional[str] = None,
        certificate_password: Optional[str] = None,
        timestamp_server: str = "http://timestamp.digicert.com",
        tool: str = "auto",
    ):
        self.certificate_path = certificate_path or os.environ.get("CODESIGN_CERT_PATH")
        self.certificate_password = certificate_password or os.environ.get("CODESIGN_CERT_PASSWORD")
        self.timestamp_server = timestamp_server
        self.tool = self._detect_tool(tool)

    def _detect_tool(self, tool: str) -> str:
        if tool != "auto":
            return tool
        for t in ["signtool", "osslsigncode"]:
            try:
                subprocess.run([t, "--help"], capture_output=True, check=True)
                return t
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue
        logger.warning("No code signing tool found")
        return "none"

    def sign_file(self, filepath: str) -> bool:
        if self.tool == "none" or not self.certificate_path:
            logger.error("Signing not configured")
            return False
        if not Path(filepath).exists():
            logger.error(f"File not found: {filepath}")
            return False
        if self.tool == "signtool":
            cmd = ["signtool", "sign", "/f", self.certificate_path, "/t", self.timestamp_server, filepath]
            if self.certificate_password:
                cmd.extend(["/p", self.certificate_password])
        elif self.tool == "osslsigncode":
            output = filepath + ".signed"
            cmd = ["osslsigncode", "sign", "-pkcs12", self.certificate_path, "-t", self.timestamp_server, "-in", filepath, "-out", output]
            if self.certificate_password:
                cmd.extend(["-pass", self.certificate_password])
        else:
            return False
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            logger.info(f"Successfully signed: {filepath}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Signing failed: {e.stderr}")
            return False

    def sign_directory(self, directory: str, extensions: tuple = (".exe", ".dll", ".msi")) -> dict:
        results = {"signed": [], "failed": [], "skipped": []}
        for root, dirs, files in os.walk(directory):
            for f in files:
                fp = os.path.join(root, f)
                if f.endswith(extensions):
                    if self.sign_file(fp):
                        results["signed"].append(fp)
                    else:
                        results["failed"].append(fp)
                else:
                    results["skipped"].append(fp)
        return results

    def verify_signature(self, filepath: str) -> bool:
        if self.tool == "signtool":
            cmd = ["signtool", "verify", "/pa", filepath]
        elif self.tool == "osslsigncode":
            cmd = ["osslsigncode", "verify", "-in", filepath]
        else:
            return False
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            return True
        except subprocess.CalledProcessError:
            return False
