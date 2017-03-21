#!/bin/bash

aw-server --testing &
serverpid=$!

sleep 2

nosetests aw-server
tests_exitcode=$?

kill $serverpid

exit $tests_exitcode
