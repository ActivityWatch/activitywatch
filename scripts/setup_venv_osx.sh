#!/bin/bash

brew update;
brew install python3;
pip3 install --upgrade virtualenv;
virtualenv venv -p python3;

# Now run `source venv/bin/activate` in the shell where the virtualenv should be used
