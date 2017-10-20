# I recommend creating a virtualenv as such before running before this makefile:
#  - virtualenv --python=python3 venv
#  - source ./venv/bin/activate

.PHONY: build install test docs clean clean_all

# When `make build DEV=true` is used all `pip install` commands will be run with `--editable` for easier development
build:
	make --directory=aw-core build DEV=$(DEV)
	make --directory=aw-client build DEV=$(DEV)
#
	make --directory=aw-webui build DEV=$(DEV)
	cp -r aw-webui/dist/* aw-server/aw_server/static/
#
	make --directory=aw-server build DEV=$(DEV)
	make --directory=aw-watcher-afk build DEV=$(DEV)
	make --directory=aw-watcher-window build DEV=$(DEV)
	make --directory=aw-qt build DEV=$(DEV)

install:
	make --directory=aw-qt install
# Installation is already happening in the `make build` step currently.
# We might want to change this.
# We should also add some option to install as user (pip3 install --user)

uninstall:
	./scripts/uninstall.sh

test:
	make --directory=aw-core test
	make --directory=aw-server test
	make --directory=aw-qt test

test-integration:
	# TODO: Move "integration tests" to aw-client
	# FIXME: For whatever reason the script stalls on Appveyor
	#        Example: https://ci.appveyor.com/project/ErikBjare/activitywatch/build/1.0.167/job/k1ulexsc5ar5uv4v
	pytest ./scripts/tests/integration_tests.py ./aw-server/tests/ -v

package:
	mkdir -p dist/activitywatch
#
	make --directory=aw-watcher-afk package
	cp -r aw-watcher-afk/dist/aw-watcher-afk/. dist/activitywatch
#
	make --directory=aw-watcher-window package
	cp -r aw-watcher-window/dist/aw-watcher-window/. dist/activitywatch
#
	make --directory=aw-server package
	cp -r aw-server/dist/aw-server/. dist/activitywatch
#
	make --directory=aw-qt package
	cp -r aw-qt/dist/aw-qt/. dist/activitywatch
#
	bash scripts/package/package-zip.sh

docs:
	make --directory=docs html

docs-deps:
	pip3 install --user -r docs/requirements.txt

clean:
	rm -rf build dist

# Clean all subprojects
clean_all: clean
	make --directory=aw-client clean
	make --directory=aw-core clean
	make --directory=aw-qt clean
	make --directory=aw-server clean
	make --directory=aw-watcher-afk clean
	make --directory=aw-watcher-window clean
	make --directory=aw-webui clean
