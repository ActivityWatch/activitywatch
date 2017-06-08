import subprocess
from time import sleep
import sys
from contextlib import contextmanager
import tempfile

import pytest


@pytest.fixture(scope="session")
def server_process():
    logfile_stdout = tempfile.NamedTemporaryFile(delete=False)
    logfile_stderr = tempfile.NamedTemporaryFile(delete=False)

    # logfile_stdout.close()
    # logfile_stderr.close()

    @contextmanager
    def _cm_server_process():
        server_proc = subprocess.Popen(["aw-server", "--testing"], stdout=logfile_stdout, stderr=logfile_stderr)
        sleep(2)  # Startup time
        yield server_proc
        sleep(2)  # Cleanup time, could probably be removed once tests are synchronous
        server_proc.kill()
        server_proc.wait()
        server_proc.communicate()

    with _cm_server_process() as server_proc:
        yield server_proc

    error_indicators = ["ERROR"]

    with open(logfile_stdout.name, "r+b") as f:
        stdout = f.read()
        if stdout:
            pytest.fail("Server shouldn't write anything to stdout")

    with open(logfile_stderr.name, "r+b") as f:
        stderr = str(f.read(), "utf8")
        if not stderr:
            pytest.fail("No output to stderr from server")

        # print("STDERR from server:\n" + stderr)
        for s in error_indicators:
            if s in stderr:
                pytest.fail("Found ERROR indicator in stderr from server: {}".format(s))


# TODO: Use the fixture in the tests instead of this thing here
def test_integration(server_process):
    # This is just here so that the server_process fixture is initialized
    pass

    # exit_code = pytest.main(["./aw-server/tests", "-v"])
    # if exit_code != 0:
    #     pytest.fail("Tests exited with non-zero code: " + str(exit_code))
