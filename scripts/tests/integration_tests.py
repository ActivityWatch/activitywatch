import subprocess
from subprocess import PIPE
from time import sleep

import pytest

server_proc = subprocess.Popen(["aw-server", "--testing"], stdout=PIPE, stderr=PIPE)

# Startup time
sleep(2)

exit_code = pytest.main(["./aw-server/tests", "-v"])
print("Tests exit code: " + str(exit_code))

# Cleanup time
sleep(2)

server_proc.kill()
out, err = server_proc.communicate()

start_line = "=" * 5 + " aw-server output " + "=" * 5
print(start_line)
print(str(err, "utf8"))
print("=" * len(start_line))
