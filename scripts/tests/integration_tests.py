"""
ActivityWatch Integration Tests
===============================

This module provides robust, reproducible, and diagnosable integration tests.

Features:
- Health polling instead of fixed sleep
- Environment variable configuration
- Detailed log summary on failure/timeout
- Real API assertions (not just "did it start")
- Clean process cleanup

Environment Variables:
    AW_SERVER_BIN:     Path to the aw-server binary (default: "aw-server" from PATH)
    AW_SERVER_PORT:    Port to use (default: 5666 for testing)
    AW_SERVER_ARGS:    Extra arguments to pass to server (default: "--testing")
    AW_SERVER_TIMEOUT: Startup timeout in seconds (default: 30)
    AW_SERVER_POLL:    Poll interval in seconds (default: 1)
    AW_LOG_LINES:      Number of log lines to show on failure (default: 100)

Local Usage:
    # Run with default settings (requires aw-server in PATH)
    pytest scripts/tests/integration_tests.py -v

    # Run with specific server binary
    AW_SERVER_BIN=./dist/activitywatch/aw-server-rust/aw-server \
        pytest scripts/tests/integration_tests.py -v

    # Run with custom port and timeout
    AW_SERVER_PORT=5777 AW_SERVER_TIMEOUT=60 \
        pytest scripts/tests/integration_tests.py -v
"""

import os
import platform
import subprocess
import tempfile
import time
import shutil
import json
from typing import Optional, Tuple, Dict, Any

import pytest


try:
    import urllib.request
    import urllib.error
    HAS_URLLIB = True
except ImportError:
    HAS_URLLIB = False


def _windows_kill_process(pid: int):
    import ctypes
    PROCESS_TERMINATE = 1
    handle = ctypes.windll.kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
    ctypes.windll.kernel32.TerminateProcess(handle, -1)
    ctypes.windll.kernel32.CloseHandle(handle)


def _read_tail(filepath: str, lines: int = 100) -> str:
    try:
        with open(filepath, "rb") as f:
            f.seek(0, 2)
            file_size = f.tell()
            
            if file_size == 0:
                return "(empty)"
            
            block_size = 4096
            blocks = []
            current_pos = file_size
            
            while len(blocks) < lines and current_pos > 0:
                read_size = min(block_size, current_pos)
                current_pos -= read_size
                f.seek(current_pos)
                block = f.read(read_size)
                blocks.append(block)
            
            content = b"".join(reversed(blocks)).decode("utf-8", errors="replace")
            all_lines = content.splitlines()
            
            if len(all_lines) > lines:
                return "\n".join(all_lines[-lines:])
            return content
    except Exception as e:
        return f"(error reading log: {e})"


class ServerConfig:
    def __init__(self):
        self.server_bin = os.environ.get("AW_SERVER_BIN", "aw-server")
        self.port = int(os.environ.get("AW_SERVER_PORT", "5666"))
        self.timeout = int(os.environ.get("AW_SERVER_TIMEOUT", "30"))
        self.poll_interval = float(os.environ.get("AW_SERVER_POLL", "1.0"))
        self.log_lines = int(os.environ.get("AW_LOG_LINES", "100"))
        
        extra_args = os.environ.get("AW_SERVER_ARGS", "")
        if extra_args:
            self.args = extra_args.split()
        else:
            self.args = ["--testing"]
        
        if "--port" not in " ".join(self.args) and "-p" not in " ".join(self.args):
            self.args.extend(["--port", str(self.port)])
    
    def base_url(self) -> str:
        return f"http://localhost:{self.port}"
    
    def api_url(self, endpoint: str) -> str:
        endpoint = endpoint.lstrip("/")
        if endpoint.startswith("api/") or endpoint.startswith("0/"):
            return f"{self.base_url()}/{endpoint}"
        return f"{self.base_url()}/api/0/{endpoint}"


class ServerProcess:
    def __init__(self, config: ServerConfig):
        self.config = config
        self.process: Optional[subprocess.Popen] = None
        self.stdout_path: Optional[str] = None
        self.stderr_path: Optional[str] = None
        self._cleanup_called = False
    
    def start(self):
        which_server = shutil.which(self.config.server_bin)
        if which_server:
            print(f"[INFO] Server binary: {which_server}")
        else:
            print(f"[WARN] Server binary not found in PATH: {self.config.server_bin}")
        
        print(f"[INFO] Server port: {self.config.port}")
        print(f"[INFO] Server args: {' '.join(self.config.args)}")
        print(f"[INFO] Startup timeout: {self.config.timeout}s")
        
        stdout_file = tempfile.NamedTemporaryFile(delete=False, mode="w+", suffix=".stdout.log")
        stderr_file = tempfile.NamedTemporaryFile(delete=False, mode="w+", suffix=".stderr.log")
        self.stdout_path = stdout_file.name
        self.stderr_path = stderr_file.name
        
        print(f"[INFO] stdout log: {self.stdout_path}")
        print(f"[INFO] stderr log: {self.stderr_path}")
        
        cmd = [self.config.server_bin] + self.config.args
        print(f"[INFO] Starting server: {' '.join(cmd)}")
        
        self.process = subprocess.Popen(
            cmd,
            stdout=stdout_file,
            stderr=stderr_file,
            bufsize=1,
            text=True
        )
        
        stdout_file.close()
        stderr_file.close()
    
    def _make_request(self, endpoint: str, method: str = "GET") -> Tuple[int, Optional[Dict[str, Any]]]:
        url = self.config.api_url(endpoint)
        try:
            req = urllib.request.Request(url, method=method)
            with urllib.request.urlopen(req, timeout=2) as resp:
                body = resp.read().decode("utf-8")
                try:
                    return resp.status, json.loads(body)
                except json.JSONDecodeError:
                    return resp.status, {"_raw": body}
        except urllib.error.HTTPError as e:
            return e.code, None
        except Exception:
            return -1, None
    
    def is_alive(self) -> bool:
        if not HAS_URLLIB:
            return self.process.poll() is None
        
        status, data = self._make_request("info")
        return status == 200 and data is not None
    
    def wait_for_ready(self) -> bool:
        print(f"[INFO] Waiting for server to be ready (timeout: {self.config.timeout}s)...")
        
        start_time = time.time()
        poll_count = 0
        
        while time.time() - start_time < self.config.timeout:
            if self.process.poll() is not None:
                print(f"[ERROR] Server exited prematurely with code: {self.process.returncode}")
                self._print_log_summary("Server exited during startup")
                return False
            
            if self.is_alive():
                elapsed = time.time() - start_time
                print(f"[INFO] Server is ready after {elapsed:.1f}s ({poll_count} polls)")
                return True
            
            poll_count += 1
            time.sleep(self.config.poll_interval)
        
        print(f"[ERROR] Server did not become ready within {self.config.timeout}s")
        self._print_log_summary("Startup timeout")
        return False
    
    def _print_log_summary(self, context: str):
        lines = self.config.log_lines
        print(f"\n{'='*80}")
        print(f"[LOG SUMMARY] {context}")
        print(f"{'='*80}")
        
        print(f"\n--- STDOUT (last {lines} lines) ---")
        if self.stdout_path:
            print(_read_tail(self.stdout_path, lines))
        else:
            print("(no stdout log)")
        
        print(f"\n--- STDERR (last {lines} lines) ---")
        if self.stderr_path:
            print(_read_tail(self.stderr_path, lines))
        else:
            print("(no stderr log)")
        
        print(f"\n{'='*80}\n")
    
    def check_for_errors(self):
        error_indicators = ["ERROR", "panic", "thread '", "stack backtrace", "fatal"]
        
        found_errors = []
        
        if self.stdout_path:
            with open(self.stdout_path, "r", encoding="utf-8", errors="replace") as f:
                stdout = f.read()
                for indicator in error_indicators:
                    if indicator in stdout:
                        found_errors.append(f"stdout contains '{indicator}'")
        
        if self.stderr_path:
            with open(self.stderr_path, "r", encoding="utf-8", errors="replace") as f:
                stderr = f.read()
                for indicator in error_indicators:
                    if indicator in stderr:
                        found_errors.append(f"stderr contains '{indicator}'")
        
        if found_errors:
            self._print_log_summary("Error indicators found in logs")
            pytest.fail(f"Found error indicators in server logs: {', '.join(found_errors)}")
    
    def get_api_info(self) -> Dict[str, Any]:
        if not HAS_URLLIB:
            pytest.skip("urllib not available")
        
        status, data = self._make_request("info")
        if status != 200 or data is None:
            self._print_log_summary(f"API /info request failed (status: {status})")
            pytest.fail(f"GET /api/0/info failed with status {status}")
        
        return data
    
    def get_api_buckets(self) -> Dict[str, Any]:
        if not HAS_URLLIB:
            pytest.skip("urllib not available")
        
        status, data = self._make_request("buckets")
        if status != 200:
            self._print_log_summary(f"API /buckets request failed (status: {status})")
            pytest.fail(f"GET /api/0/buckets failed with status {status}")
        
        return data
    
    def cleanup(self):
        if self._cleanup_called:
            return
        self._cleanup_called = True
        
        if self.process:
            print(f"[INFO] Stopping server (PID: {self.process.pid})...")
            
            try:
                if platform.system() == "Windows":
                    _windows_kill_process(self.process.pid)
                else:
                    self.process.kill()
                
                self.process.wait(timeout=5)
                self.process.communicate(timeout=5)
                print(f"[INFO] Server stopped with code: {self.process.returncode}")
            except subprocess.TimeoutExpired:
                print(f"[WARN] Server did not terminate gracefully, process may still be running")
            except Exception as e:
                print(f"[WARN] Error during cleanup: {e}")
        
        for path in [self.stdout_path, self.stderr_path]:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass


@pytest.fixture(scope="session")
def server_config():
    return ServerConfig()


@pytest.fixture(scope="session")
def server_process(server_config):
    server = ServerProcess(server_config)
    
    try:
        server.start()
        
        if not server.wait_for_ready():
            server.cleanup()
            pytest.fail("Server failed to start within timeout")
        
        yield server
        
        server.check_for_errors()
        
    finally:
        server.cleanup()


class TestServerBasics:
    def test_server_starts(self, server_process):
        assert server_process.is_alive(), "Server should be alive after startup"
    
    def test_api_info_endpoint(self, server_process):
        info = server_process.get_api_info()
        
        assert "version" in info, "API /info should contain 'version' field"
        print(f"[INFO] Server version from API: {info.get('version')}")
        
        assert "hostname" in info, "API /info should contain 'hostname' field"
        print(f"[INFO] Server hostname: {info.get('hostname')}")
    
    def test_api_buckets_endpoint(self, server_process):
        buckets = server_process.get_api_buckets()
        
        assert isinstance(buckets, dict) or isinstance(buckets, list), \
            f"API /buckets should return dict or list, got {type(buckets)}"
        
        if isinstance(buckets, dict):
            print(f"[INFO] Found {len(buckets)} buckets (as dict)")
        elif isinstance(buckets, list):
            print(f"[INFO] Found {len(buckets)} buckets (as list)")


class TestServerHealth:
    def test_no_error_indicators_in_logs(self, server_process):
        server_process.check_for_errors()
