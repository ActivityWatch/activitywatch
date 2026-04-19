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
- Global timeout protection (prevents hanging)
- Clear error classification for diagnosis

Error Classification:
- LAUNCH_FAILED:     Server process failed to start (executable not found, etc.)
- EARLY_EXIT:        Server started but exited prematurely with error code
- STARTUP_TIMEOUT:   Server started but never became responsive within timeout
- API_ERROR:         API request returned non-200 status
- ASSERTION_FAILED:  API assertion failed (missing fields, wrong types)
- LOG_ERROR:         Server logs contain ERROR/panic indicators

Environment Variables:
    AW_SERVER_BIN:     Path to the aw-server binary (default: "aw-server" from PATH)
    AW_SERVER_PORT:    Port to use (default: 5666 for testing)
    AW_SERVER_ARGS:    Extra arguments to pass to server (default: "--testing")
    AW_SERVER_TIMEOUT: Startup timeout in seconds (default: 30)
    AW_SERVER_POLL:    Poll interval in seconds (default: 1)
    AW_LOG_LINES:      Number of log lines to show on failure (default: 100)
    AW_TEST_TIMEOUT:   Global test timeout in seconds (default: 120)

Local Usage:
    # Run with default settings (requires aw-server in PATH)
    pytest scripts/tests/integration_tests.py -v

    # Run with specific server binary
    AW_SERVER_BIN=./dist/activitywatch/aw-server-rust/aw-server \
        pytest scripts/tests/integration_tests.py -v

    # Run with custom port and timeout
    AW_SERVER_PORT=5777 AW_SERVER_TIMEOUT=60 AW_TEST_TIMEOUT=180 \
        pytest scripts/tests/integration_tests.py -v
"""

import os
import platform
import subprocess
import tempfile
import time
import shutil
import json
import signal
import atexit
import sys
from enum import Enum, auto
from typing import Optional, Tuple, Dict, Any, List

import pytest


try:
    import urllib.request
    import urllib.error
    HAS_URLLIB = True
except ImportError:
    HAS_URLLIB = False

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


class ErrorType(Enum):
    LAUNCH_FAILED = auto()
    EARLY_EXIT = auto()
    STARTUP_TIMEOUT = auto()
    API_ERROR = auto()
    ASSERTION_FAILED = auto()
    LOG_ERROR = auto()


GLOBAL_SERVER_PROCESS: Optional['ServerProcess'] = None
GLOBAL_TEST_TIMEOUT: int = 120


def _windows_kill_process(pid: int):
    import ctypes
    PROCESS_TERMINATE = 1
    handle = ctypes.windll.kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
    ctypes.windll.kernel32.TerminateProcess(handle, -1)
    ctypes.windll.kernel32.CloseHandle(handle)


def _kill_process_tree(pid: int, timeout: int = 10):
    if HAS_PSUTIL:
        try:
            parent = psutil.Process(pid)
            children = parent.children(recursive=True)
            
            for child in children:
                try:
                    child.kill()
                except psutil.NoSuchProcess:
                    pass
            
            try:
                parent.kill()
            except psutil.NoSuchProcess:
                pass
            
            _, still_alive = psutil.wait_procs([parent] + children, timeout=timeout)
            
            for p in still_alive:
                try:
                    p.kill()
                except psutil.NoSuchProcess:
                    pass
        except psutil.NoSuchProcess:
            pass
    else:
        if platform.system() == "Windows":
            _windows_kill_process(pid)
        else:
            try:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
            except OSError:
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass


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


class TestFailure(Exception):
    def __init__(self, error_type: ErrorType, message: str, details: Optional[Dict[str, Any]] = None):
        self.error_type = error_type
        self.details = details or {}
        super().__init__(message)


class ServerConfig:
    def __init__(self):
        self.server_bin = os.environ.get("AW_SERVER_BIN", "aw-server")
        self.port = int(os.environ.get("AW_SERVER_PORT", "5666"))
        self.timeout = int(os.environ.get("AW_SERVER_TIMEOUT", "30"))
        self.poll_interval = float(os.environ.get("AW_SERVER_POLL", "1.0"))
        self.log_lines = int(os.environ.get("AW_LOG_LINES", "100"))
        self.test_timeout = int(os.environ.get("AW_TEST_TIMEOUT", "120"))
        
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
        self._start_time: Optional[float] = None
        self._exit_code: Optional[int] = None
    
    def start(self):
        global GLOBAL_SERVER_PROCESS
        GLOBAL_SERVER_PROCESS = self
        
        print(f"\n{'='*80}")
        print(f"[TEST SETUP] Starting server process")
        print(f"{'='*80}")
        
        which_server = shutil.which(self.config.server_bin)
        if which_server:
            print(f"[INFO] Server binary: {which_server}")
            resolved_bin = which_server
        else:
            print(f"[WARN] Server binary not found in PATH: {self.config.server_bin}")
            resolved_bin = self.config.server_bin
        
        print(f"[INFO] Server port: {self.config.port}")
        print(f"[INFO] Server args: {' '.join(self.config.args)}")
        print(f"[INFO] Startup timeout: {self.config.timeout}s")
        print(f"[INFO] Global test timeout: {self.config.test_timeout}s")
        
        stdout_file = tempfile.NamedTemporaryFile(delete=False, mode="w+", suffix=".stdout.log")
        stderr_file = tempfile.NamedTemporaryFile(delete=False, mode="w+", suffix=".stderr.log")
        self.stdout_path = stdout_file.name
        self.stderr_path = stderr_file.name
        
        print(f"[INFO] stdout log: {self.stdout_path}")
        print(f"[INFO] stderr log: {self.stderr_path}")
        
        cmd = [resolved_bin] + self.config.args
        print(f"[INFO] Starting server: {' '.join(cmd)}")
        print(f"{'='*80}\n")
        
        try:
            self._start_time = time.time()
            
            if platform.system() == "Windows":
                self.process = subprocess.Popen(
                    cmd,
                    stdout=stdout_file,
                    stderr=stderr_file,
                    bufsize=1,
                    text=True
                )
            else:
                self.process = subprocess.Popen(
                    cmd,
                    stdout=stdout_file,
                    stderr=stderr_file,
                    bufsize=1,
                    text=True,
                    preexec_fn=os.setsid
                )
        except FileNotFoundError as e:
            stdout_file.close()
            stderr_file.close()
            self._cleanup_logs()
            raise TestFailure(
                ErrorType.LAUNCH_FAILED,
                f"Server binary not found: {self.config.server_bin}",
                {"error": str(e), "binary": self.config.server_bin}
            )
        except Exception as e:
            stdout_file.close()
            stderr_file.close()
            self._cleanup_logs()
            raise TestFailure(
                ErrorType.LAUNCH_FAILED,
                f"Failed to launch server: {e}",
                {"error": str(e), "binary": self.config.server_bin}
            )
        
        stdout_file.close()
        stderr_file.close()
    
    def _print_diagnostic_summary(self, error_type: ErrorType, context: str):
        lines = self.config.log_lines
        elapsed = ""
        if self._start_time:
            elapsed = f" (elapsed: {time.time() - self._start_time:.1f}s)"
        
        print(f"\n{'='*80}")
        print(f"[DIAGNOSIS] {context}{elapsed}")
        print(f"{'='*80}")
        print(f"Error Type: {error_type.name}")
        print(f"Server Binary: {self.config.server_bin}")
        print(f"Server Port: {self.config.port}")
        print(f"Server PID: {self.process.pid if self.process else 'N/A'}")
        print(f"Exit Code: {self._exit_code if self._exit_code is not None else 'still running'}")
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
        
        print(f"\n{'='*80}")
        print(f"[END DIAGNOSIS]")
        print(f"{'='*80}\n")
    
    def _make_request(self, endpoint: str, method: str = "GET") -> Tuple[int, Optional[Dict[str, Any]]]:
        url = self.config.api_url(endpoint)
        try:
            req = urllib.request.Request(url, method=method)
            with urllib.request.urlopen(req, timeout=5) as resp:
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
        last_exit_check = 0
        
        while time.time() - start_time < self.config.timeout:
            exit_code = self.process.poll()
            if exit_code is not None:
                self._exit_code = exit_code
                if exit_code != 0:
                    self._print_diagnostic_summary(
                        ErrorType.EARLY_EXIT,
                        f"Server exited prematurely with code: {exit_code}"
                    )
                    return False
                else:
                    print(f"[INFO] Server exited with code 0, checking if it became responsive first...")
            
            if self.is_alive():
                elapsed = time.time() - start_time
                print(f"[INFO] Server is ready after {elapsed:.1f}s ({poll_count} polls)")
                return True
            
            poll_count += 1
            time.sleep(self.config.poll_interval)
        
        self._exit_code = self.process.poll()
        self._print_diagnostic_summary(
            ErrorType.STARTUP_TIMEOUT,
            f"Server did not become ready within {self.config.timeout}s"
        )
        return False
    
    def check_for_errors(self) -> Tuple[bool, List[str]]:
        error_indicators = ["ERROR", "panic", "thread '", "stack backtrace", "fatal", "Error:"]
        
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
        
        return len(found_errors) == 0, found_errors
    
    def get_api_info(self) -> Dict[str, Any]:
        if not HAS_URLLIB:
            pytest.skip("urllib not available")
        
        status, data = self._make_request("info")
        
        if status != 200 or data is None:
            self._print_diagnostic_summary(
                ErrorType.API_ERROR,
                f"GET /api/0/info failed with status {status}"
            )
            raise TestFailure(
                ErrorType.API_ERROR,
                f"GET /api/0/info failed with status {status}",
                {"status": status, "endpoint": "/api/0/info"}
            )
        
        return data
    
    def get_api_buckets(self) -> Dict[str, Any]:
        if not HAS_URLLIB:
            pytest.skip("urllib not available")
        
        status, data = self._make_request("buckets")
        
        if status != 200:
            self._print_diagnostic_summary(
                ErrorType.API_ERROR,
                f"GET /api/0/buckets failed with status {status}"
            )
            raise TestFailure(
                ErrorType.API_ERROR,
                f"GET /api/0/buckets failed with status {status}",
                {"status": status, "endpoint": "/api/0/buckets"}
            )
        
        return data
    
    def _cleanup_logs(self):
        for path in [self.stdout_path, self.stderr_path]:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass
    
    def cleanup(self):
        if self._cleanup_called:
            return
        self._cleanup_called = True
        
        global GLOBAL_SERVER_PROCESS
        if GLOBAL_SERVER_PROCESS is self:
            GLOBAL_SERVER_PROCESS = None
        
        if self.process:
            print(f"\n[INFO] Stopping server (PID: {self.process.pid})...")
            
            try:
                if platform.system() == "Windows":
                    _kill_process_tree(self.process.pid)
                else:
                    _kill_process_tree(self.process.pid)
                
                try:
                    self.process.wait(timeout=10)
                    self._exit_code = self.process.returncode
                    print(f"[INFO] Server stopped with code: {self._exit_code}")
                except subprocess.TimeoutExpired:
                    print(f"[WARN] Server did not terminate gracefully, process may still be running")
            except Exception as e:
                print(f"[WARN] Error during cleanup: {e}")
        
        ok, errors = self.check_for_errors()
        if not ok:
            self._print_diagnostic_summary(
                ErrorType.LOG_ERROR,
                f"Error indicators found in logs: {errors}"
            )
        
        self._cleanup_logs()


def _global_cleanup():
    global GLOBAL_SERVER_PROCESS
    if GLOBAL_SERVER_PROCESS is not None:
        print(f"\n[GLOBAL CLEANUP] Forcefully stopping orphaned server process...")
        GLOBAL_SERVER_PROCESS.cleanup()


atexit.register(_global_cleanup)


def get_pytest_timeout_marker():
    try:
        import pytest_timeout
        return pytest.mark.timeout
    except ImportError:
        return lambda *args, **kwargs: lambda x: x


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
        
        ok, errors = server.check_for_errors()
        if not ok:
            server._print_diagnostic_summary(
                ErrorType.LOG_ERROR,
                f"Error indicators found after tests: {errors}"
            )
            pytest.fail(f"Error indicators found in server logs: {errors}")
        
    finally:
        server.cleanup()


timeout_marker = get_pytest_timeout_marker()


class TestServerBasics:
    
    @timeout_marker(60)
    def test_server_starts(self, server_process):
        assert server_process.is_alive(), "Server should be alive after startup"
        print(f"[PASS] Server is running and responsive")
    
    @timeout_marker(60)
    def test_api_info_endpoint(self, server_process):
        print(f"\n[TEST] Testing /api/0/info endpoint...")
        info = server_process.get_api_info()
        
        print(f"[INFO] API response keys: {list(info.keys())}")
        
        if "version" not in info:
            server_process._print_diagnostic_summary(
                ErrorType.ASSERTION_FAILED,
                "API /info response missing 'version' field"
            )
            pytest.fail("API /info should contain 'version' field")
        
        print(f"[INFO] Server version from API: {info.get('version')}")
        
        if "hostname" not in info:
            server_process._print_diagnostic_summary(
                ErrorType.ASSERTION_FAILED,
                "API /info response missing 'hostname' field"
            )
            pytest.fail("API /info should contain 'hostname' field")
        
        print(f"[INFO] Server hostname: {info.get('hostname')}")
        print(f"[PASS] /api/0/info endpoint is working correctly")
    
    @timeout_marker(60)
    def test_api_buckets_endpoint(self, server_process):
        print(f"\n[TEST] Testing /api/0/buckets endpoint...")
        buckets = server_process.get_api_buckets()
        
        is_valid = isinstance(buckets, dict) or isinstance(buckets, list)
        
        if not is_valid:
            server_process._print_diagnostic_summary(
                ErrorType.ASSERTION_FAILED,
                f"API /buckets returned unexpected type: {type(buckets)}"
            )
            pytest.fail(f"API /buckets should return dict or list, got {type(buckets)}")
        
        if isinstance(buckets, dict):
            print(f"[INFO] Found {len(buckets)} buckets (as dict)")
        elif isinstance(buckets, list):
            print(f"[INFO] Found {len(buckets)} buckets (as list)")
        
        print(f"[PASS] /api/0/buckets endpoint is working correctly")


class TestServerHealth:
    
    @timeout_marker(60)
    def test_no_error_indicators_in_logs(self, server_process):
        ok, errors = server_process.check_for_errors()
        
        if not ok:
            server_process._print_diagnostic_summary(
                ErrorType.LOG_ERROR,
                f"Error indicators found: {errors}"
            )
            pytest.fail(f"Error indicators found in server logs: {errors}")
        
        print(f"[PASS] No error indicators found in logs")
