set positional-arguments

VERSION := `uv run scripts/get-version.py src/yutto/__version__.py`
BILIASS_VERSION := `uv run scripts/get-version.py packages/biliass/src/biliass/__version__.py`
DOCKER_NAME := "siguremo/yutto"

run *ARGS:
  uv run python -m yutto {{ARGS}}

install:
  uv sync

test:
  uv run pytest -m '(api or e2e or processor or biliass) and not (ci_only or ignore)'
  just clean

fmt:
  uv run ruff format .

lint:
  uv run pyright src/yutto packages/biliass/src/biliass tests
  uv run ruff check .
  uv run typos

build:
  uv build

release:
  @echo 'Tagging v{{VERSION}}...'
  git tag "v{{VERSION}}"
  @echo 'Push to GitHub to trigger publish process...'
  git push --tags

publish:
  uv build
  uv publish
  git push --tags
  just clean-builds

clean:
  fd \
    -u \
    -E tests/test_biliass/test_corpus/ \
    -e m4s \
    -e mp4 \
    -e mkv \
    -e mov \
    -e m4a \
    -e aac \
    -e mp3 \
    -e flac \
    -e srt \
    -e xml \
    -e ass \
    -e nfo \
    -e pb \
    -e pyc \
    -e jpg \
    -e ini \
    -x rm
  rm -rf .pytest_cache/
  rm -rf .mypy_cache/
  find . -maxdepth 3 -type d -empty -print0 | xargs -0 -r rm -r

clean-builds:
  rm -rf build/
  rm -rf dist/
  rm -rf yutto.egg-info/

generate-schema:
  uv run scripts/generate-schema.py

# CI specific
ci-install:
  uv sync --all-extras --dev

ci-fmt-check:
  uv run ruff format --check --diff .

ci-lint:
  just lint

ci-test:
  uv run pytest -m "(api or processor or biliass) and not (ci_skip or ignore)" --reruns 3 --reruns-delay 1

ci-e2e-test:
  uv run pytest -m "e2e and not (ci_skip or ignore)"

# docker specific
docker-run *ARGS:
  docker run --rm -it -v `pwd`:/app {{DOCKER_NAME}} {{ARGS}}

docker-build:
  docker build --no-cache -t "{{DOCKER_NAME}}:{{VERSION}}" -t "{{DOCKER_NAME}}:latest" .

docker-publish:
  docker buildx build --no-cache --platform=linux/amd64,linux/arm64 -t "{{DOCKER_NAME}}:{{VERSION}}" -t "{{DOCKER_NAME}}:latest" . --push

# docs specific
docs-setup:
  cd docs; pnpm i

docs-dev:
  cd docs; pnpm dev

docs-build:
  cd docs; pnpm build

# biliass specific
build-biliass:
  cd packages/biliass; maturin build

develop-biliass *ARGS:
  cd packages/biliass; maturin develop --uv {{ARGS}}

release-biliass:
  @echo 'Tagging biliass@{{BILIASS_VERSION}}...'
  git tag "biliass@{{BILIASS_VERSION}}"
  @echo 'Push to GitHub to trigger publish process...'
  git push --tags

snapshot-update:
  uv run pytest tests/test_biliass/test_corpus --snapshot-update

fetch-corpus *ARGS:
  cd tests/test_biliass/test_corpus; uv run scripts/fetch-corpus.py {{ARGS}}

test-corpus:
  uv run pytest tests/test_biliass/test_corpus --capture=no -vv
