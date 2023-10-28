set positional-arguments

VERSION := `poetry run python -c "import sys; from yutto.__version__ import VERSION as yutto_version; sys.stdout.write(yutto_version)"`
DOCKER_NAME := "siguremo/yutto"

run *ARGS:
  poetry run python -m yutto {{ARGS}}

install:
  poetry install

test:
  poetry run pytest -m '(api or e2e or processor) and not (ci_only or ignore)'
  just clean

fmt:
  poetry run ruff format .

lint:
  poetry run pyright yutto tests
  poetry run ruff check .

build:
  poetry build

release:
  @echo 'Tagging v{{VERSION}}...'
  git tag "v{{VERSION}}"
  @echo 'Push to GitHub to trigger publish process...'
  git push --tags

publish:
  touch yutto/py.typed
  poetry publish --build
  git tag "v{{VERSION}}"
  git push --tags
  just clean-builds

upgrade:
  just build
  python3 -m pip install ./dist/yutto-*.whl

upgrade-from-pypi:
  python3 -m pip install --upgrade --pre yutto

clean:
  find . -name "*.m4s" -print0 | xargs -0 rm -f
  find . -name "*.mp4" -print0 | xargs -0 rm -f
  find . -name "*.mkv" -print0 | xargs -0 rm -f
  find . -name "*.mov" -print0 | xargs -0 rm -f
  find . -name "*.aac" -print0 | xargs -0 rm -f
  find . -name "*.flac" -print0 | xargs -0 rm -f
  find . -name "*.srt" -print0 | xargs -0 rm -f
  find . -name "*.xml" -print0 | xargs -0 rm -f
  find . -name "*.ass" -print0 | xargs -0 rm -f
  find . -name "*.nfo" -print0 | xargs -0 rm -f
  find . -name "*.pb" -print0 | xargs -0 rm -f
  find . -name "*.pyc" -print0 | xargs -0 rm -f
  rm -rf .pytest_cache/
  rm -rf .mypy_cache/
  find . -maxdepth 3 -type d -empty -print0 | xargs -0 -r rm -r

clean-builds:
  rm -rf build/
  rm -rf dist/
  rm -rf yutto.egg-info/

ci-install:
  poetry install --no-interaction --no-root

ci-fmt-check:
  poetry run ruff format --check --diff .

ci-lint:
  just lint

ci-test:
  poetry run pytest -m "(api or processor) and not (ci_skip or ignore)" --reruns 3 --reruns-delay 1
  just clean

ci-e2e-test:
  poetry run pytest -m "e2e and not (ci_skip or ignore)"
  just clean

docker-run *ARGS:
  docker run --rm -it -v `pwd`:/app {{DOCKER_NAME}} {{ARGS}}

docker-build:
  docker build --no-cache -t "{{DOCKER_NAME}}:{{VERSION}}" -t "{{DOCKER_NAME}}:latest" .

docker-publish:
  docker buildx build --no-cache --platform=linux/amd64,linux/arm64 -t "{{DOCKER_NAME}}:{{VERSION}}" -t "{{DOCKER_NAME}}:latest" . --push
