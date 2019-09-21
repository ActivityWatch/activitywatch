#!/bin/bash

choco install -y innosetup

iscc scripts/package/activitywatch-setup.iss
