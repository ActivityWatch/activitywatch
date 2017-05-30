import subprocess
from subprocess import PIPE
from time import sleep
import sys
from contextlib import contextmanager

import pytest


# TODO: Write a context manager for the server process
@contextmanager
def server_process():
    server_proc = subprocess.Popen(["aw-server", "--testing"], stdout=PIPE, stderr=PIPE)
    yield server_proc
    server_proc.kill()


def print_section(msg, title="unnamed section"):
    start_line = "=" * 5 + " " + title + " " + "=" * 5
    print(start_line)
    print(msg)
    print("=" * len(start_line))


if __name__ == "__main__":
    with server_process() as server_proc:
        # Startup time
        sleep(2)

        exit_code = pytest.main(["./aw-server/tests", "-v"])
        if exit_code != 0:
            print("Tests exit code: " + str(exit_code))

        # Cleanup time
        sleep(2)

    out, err = server_proc.communicate()
    out, err = (str(stream, "utf8") for stream in (out, err))
    print_section(err, title="aw-server output")

    error_indicators = ["ERROR"]
    for s in error_indicators:
        if s in err:
            print("Found ERROR indicator in stderr from server: {}".format(s))
            exit_code = 30 if exit_code == 0 else exit_code

    sys.exit(exit_code)
