#!/bin/bash

aw-server --testing &
serverpid=$!

sleep 2

pytest aw-server
tests_exitcode=$?

kill $serverpid

exit $tests_exitcode
