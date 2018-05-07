import subprocess
from time import sleep
import tempfile
import platform

import pytest


def _windows_kill_process(pid):
    import ctypes
    PROCESS_TERMINATE = 1
    handle = ctypes.windll.kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
    ctypes.windll.kernel32.TerminateProcess(handle, -1)
    ctypes.windll.kernel32.CloseHandle(handle)


@pytest.fixture(scope="session")
def server_process():
    logfile_stdout = tempfile.NamedTemporaryFile(delete=False)
    logfile_stderr = tempfile.NamedTemporaryFile(delete=False)

    server_proc = subprocess.Popen(["aw-server", "--testing"], stdout=logfile_stdout, stderr=logfile_stderr)

    # Wait for server to start up properly
    # TODO: Ping the server until it's alive to remove this sleep
    sleep(5)

    yield server_proc

    if platform.system() == "Windows":
        # On Windows, for whatever reason, server_proc.kill() doesn't do the job.
        _windows_kill_process(server_proc.pid)
    else:
        server_proc.kill()
    server_proc.wait(5)
    server_proc.communicate()

    error_indicators = ["ERROR"]

    with open(logfile_stdout.name, "r+b") as f:
        stdout = str(f.read(), "utf8")
        if any(e in stdout for e in error_indicators):
            pytest.fail("Found ERROR indicator in stdout from server: {}".format(stdout))

    with open(logfile_stderr.name, "r+b") as f:
        stderr = str(f.read(), "utf8")
        if not stderr:
            pytest.fail("No output to stderr from server")

        # Will show in case pytest fails
        print(stderr)

        for s in error_indicators:
            if s in stderr:
                pytest.fail("Found ERROR indicator in stderr from server: {}".format(s))

    # NOTE: returncode was -9 for whatever reason
    # if server_proc.returncode != 0:
    #     pytest.fail("Exit code was non-zero ({})".format(server_proc.returncode))


# TODO: Use the fixture in the tests instead of this thing here
def test_integration(server_process):
    # This is just here so that the server_process fixture is initialized
    pass

    # exit_code = pytest.main(["./aw-server/tests", "-v"])
    # if exit_code != 0:
    #     pytest.fail("Tests exited with non-zero code: " + str(exit_code))
