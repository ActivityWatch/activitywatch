"""Start aw-server (Python) and aw-server-rust as throwaway test instances.

Both servers run with ``--testing`` on free ephemeral ports, with ``HOME`` and
the ``XDG_*`` dirs pointed at a temporary directory, so they never touch a
real ActivityWatch install (ports 5600/5666, real databases or configs).
"""

import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional

import requests

REPO_ROOT = Path(__file__).resolve().parents[3]
RESERVED_PORTS = {5600, 5666}
REQUEST_TIMEOUT = 60  # seconds, so a stuck server fails the run instead of hanging it


def free_port() -> int:
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        if port not in RESERVED_PORTS:
            return port


def python_server_cmd() -> Optional[List[str]]:
    """Command for the Python aw-server, or None if it is not importable."""
    env_cmd = os.environ.get("AW_PARITY_PYTHON_SERVER")
    if env_cmd:
        return env_cmd.split()
    try:
        import aw_server  # noqa: F401
    except ImportError:
        return None
    return [sys.executable, "-m", "aw_server"]


def rust_server_cmd() -> Optional[List[str]]:
    """Command for aw-server-rust, or None if no binary is found."""
    env_bin = os.environ.get("AW_PARITY_RUST_SERVER")
    candidates = [Path(env_bin)] if env_bin else []
    target = Path(
        os.environ.get("CARGO_TARGET_DIR", REPO_ROOT / "aw-server-rust" / "target")
    )
    candidates += [target / "release" / "aw-server", target / "debug" / "aw-server"]
    for c in candidates:
        if c.is_file():
            return [str(c)]
    return None


class Server:
    def __init__(self, name: str, cmd: List[str], extra_args: List[str]):
        self.name = name
        self.port = free_port()
        self.url = f"http://127.0.0.1:{self.port}"
        self.tmpdir = Path(tempfile.mkdtemp(prefix=f"aw-parity-{name}-"))
        self.cmd = (
            cmd
            + ["--testing", "--port", str(self.port)]
            + [a.format(tmp=self.tmpdir) for a in extra_args]
        )
        self.log = open(self.tmpdir / "server.log", "w+")
        self.proc: Optional[subprocess.Popen] = None
        self.session = requests.Session()

    def _env(self) -> Dict[str, str]:
        env = dict(os.environ)
        env["HOME"] = str(self.tmpdir)
        env["USERPROFILE"] = str(self.tmpdir)
        for var in (
            "XDG_DATA_HOME",
            "XDG_CONFIG_HOME",
            "XDG_CACHE_HOME",
            "XDG_STATE_HOME",
        ):
            env[var] = str(self.tmpdir / var.lower())
        return env

    def start(self, timeout: float = 60) -> None:
        assert self.port not in RESERVED_PORTS
        self.proc = subprocess.Popen(
            self.cmd, stdout=self.log, stderr=subprocess.STDOUT, env=self._env()
        )
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError(f"{self.name} exited early:\n{self.logs()}")
            try:
                if self.session.get(f"{self.url}/api/0/info", timeout=1).ok:
                    return
            except requests.ConnectionError:
                pass  # not listening yet, retry until the deadline
            time.sleep(0.2)
        self.stop()
        raise RuntimeError(
            f"{self.name} did not start within {timeout}s:\n{self.logs()}"
        )

    def logs(self) -> str:
        self.log.flush()
        return (self.tmpdir / "server.log").read_text(errors="replace")[-5000:]

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(5)
        self.log.close()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    # --- API helpers ---

    def create_bucket(self, bucket_id: str, btype: str, hostname: str) -> None:
        r = self.session.post(
            f"{self.url}/api/0/buckets/{bucket_id}",
            json={"client": "aw-query-parity", "type": btype, "hostname": hostname},
            timeout=REQUEST_TIMEOUT,
        )
        assert r.status_code in (200, 201, 304), (
            f"{self.name}: {r.status_code} {r.text}"
        )

    def insert_events(self, bucket_id: str, events: List[dict]) -> None:
        if not events:
            return
        r = self.session.post(
            f"{self.url}/api/0/buckets/{bucket_id}/events",
            json=events,
            timeout=REQUEST_TIMEOUT,
        )
        assert r.ok, f"{self.name}: {r.status_code} {r.text}"

    def query(self, query: str, period: str):
        """Run a query. Returns the result, or {"__error__": status} on failure."""
        r = self.session.post(
            f"{self.url}/api/0/query/",
            json={"query": [query], "timeperiods": [period]},
            timeout=REQUEST_TIMEOUT,
        )
        if not r.ok:
            return {"__error__": r.status_code, "__message__": r.text[:500]}
        return r.json()[0]
