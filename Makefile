# I recommend creating a virtualenv as such before running before this makefile:
#  - virtualenv --python=python3 venv
#  - source ./venv/bin/activate

.PHONY: build install test clean

# TODO: Currently no way to do a `setup.py develop`/`pip install --editable`
build:
	make --directory=aw-core build
	make --directory=aw-client build
#
	make --directory=aw-webui build
	cp -r aw-webui/dist/* aw-server/aw_server/static/
#
	make --directory=aw-server build
	make --directory=aw-watcher-afk build
	make --directory=aw-watcher-window build
	make --directory=aw-qt build

install:
	make --directory=aw-qt install
# Installation is already happening in the `make build` step currently.
# We might want to change this.
# We should also add some option to install as user (pip3 install --user) or editable (pip3 install --editable)

uninstall:
	./scripts/uninstall.sh

test:
	make --directory=aw-core test
	make --directory=aw-qt test
	# TODO: Move "integration tests" to aw-client
	./scripts/tests/integration_tests.sh

package:
	mkdir -p dist/activitywatch
#
	make --directory=aw-watcher-afk package
	cp -r aw-watcher-afk/dist/aw-watcher-afk/* dist/activitywatch
#
	make --directory=aw-watcher-window package
	cp -r aw-watcher-window/dist/aw-watcher-window/* dist/activitywatch
#
	make --directory=aw-server package
	cp -r aw-server/dist/aw-server/* dist/activitywatch
#
	make --directory=aw-qt package
	cp -r aw-qt/dist/aw-qt/* dist/activitywatch
#
	bash scripts/package/package-zip.sh

clean:
	rm -r build dist
	mkdir dist
	mkdir dist/activitywatch
