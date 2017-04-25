#!/bin/bash

function install_with_brew() {
    # Will get the latest version in brew.
    # As of writing, 3.6 and later won't work with PyInstaller so this method is avoided for now.
    brew update;
    brew install python3;
}

function install_with_pkg() {
    wget -O python3.pkg https://www.python.org/ftp/python/3.5.2/python-3.5.2-macosx10.6.pkg;
    sudo installer -pkg python3.pkg -target /;
}

install_with_pkg
pip3 install --upgrade virtualenv;
virtualenv venv -p python3;

# Now run `source venv/bin/activate` in the shell where the virtualenv should be used
