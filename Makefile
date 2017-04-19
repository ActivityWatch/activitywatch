# I recommend creating a virtualenv as such before running before this makefile:
#  - virtualenv --python=python3 venv
#  - source ./venv/bin/activate

.PHONY: build install test clean

build:
	make --directory=aw-core build
	make --directory=aw-client build
#
	make --directory=aw-webui build
	cp -r aw-webui/dist/* aw-server/aw_server/static/
#
	cd aw-watcher-afk && python3 setup.py install
	cd aw-watcher-window && python3 setup.py install
	make --directory=aw-server build
	make --directory=aw-qt build
#
#	./scripts/build.sh
#	make clean
	make test

install:
	./scripts/install.sh

test:
	pip install pytest
	pytest aw-core/tests
	./scripts/integration_tests.sh

package:
	./scripts/package.sh

clean:
	rm -r build dist
	mkdir dist
	mkdir dist/activitywatch
