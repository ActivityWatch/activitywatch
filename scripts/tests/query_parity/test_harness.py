"""Tests for the parity harness itself (no aw-server needed)."""

import sys
from types import SimpleNamespace

from conftest import record_report
from servers import Server

# Listens on --port and answers /api/0/info, but only after 1.5 s the first
# time, like a server that accepts connections before it's ready.
SLOW_SERVER = """
import sys, time
from http.server import BaseHTTPRequestHandler, HTTPServer

port = int(sys.argv[sys.argv.index("--port") + 1])
first = [True]

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if first[0]:
            first[0] = False
            time.sleep(1.5)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"{}")

    def log_message(self, *args):
        pass

HTTPServer(("127.0.0.1", port), Handler).serve_forever()
"""


def test_start_retries_on_read_timeout():
    """A ReadTimeout while polling /api/0/info is retried, not raised"""
    server = Server("slow", [sys.executable, "-c", SLOW_SERVER], [])
    try:
        server.start(timeout=20)
    finally:
        server.stop()


def _report(when, outcome, nodeid="test_x.py::test_parity[case-1]"):
    return SimpleNamespace(
        when=when,
        nodeid=nodeid,
        skipped=outcome == "skipped",
        failed=outcome == "failed",
    )


def test_record_report_ignores_skipped_calls():
    ran, failed = [], []
    record_report(_report("call", "passed", "t.py::test_parity[a]"), ran, failed)
    record_report(_report("call", "failed", "t.py::test_parity[b]"), ran, failed)
    # pytest.skip() inside the test body: a call-phase report with skipped=True
    record_report(_report("call", "skipped", "t.py::test_parity[c]"), ran, failed)
    record_report(_report("setup", "failed", "t.py::test_parity[d]"), ran, failed)
    assert ran == ["a", "b"]
    assert failed == ["b"]
