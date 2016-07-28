#!/bin/bash

aw-server --testing &
serverpid=$!

sleep 2

nosetests aw-server

kill $serverpid

