set positional-arguments

VERSION := `uv run python -c "import sys; from yutto.__version__ import VERSION as yutto_version; sys.stdout.write(yutto_version)"`
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
  uv run pyright src/yutto tests
  uv run ruff check .
  uv run typos

build:
  uv build

release:
  @echo 'Tagging v{{VERSION}}...'
  git tag "v{{VERSION}}"
  @echo 'Push to GitHub to trigger publish process...'
  git push --tags

# Missing command for uv
# publish:
#   poetry publish --build
#   git tag "v{{VERSION}}"
#   git push --tags
#   just clean-builds

clean:
  find . -name "*.m4s" -print0 | xargs -0 rm -f
  find . -name "*.mp4" -print0 | xargs -0 rm -f
  find . -name "*.mkv" -print0 | xargs -0 rm -f
  find . -name "*.mov" -print0 | xargs -0 rm -f
  find . -name "*.aac" -print0 | xargs -0 rm -f
  find . -name "*.mp3" -print0 | xargs -0 rm -f
  find . -name "*.flac" -print0 | xargs -0 rm -f
  find . -name "*.srt" -print0 | xargs -0 rm -f
  find . -name "*.xml" -print0 | xargs -0 rm -f
  find . -name "*.ass" -print0 | xargs -0 rm -f
  find . -name "*.nfo" -print0 | xargs -0 rm -f
  find . -name "*.pb" -print0 | xargs -0 rm -f
  find . -name "*.pyc" -print0 | xargs -0 rm -f
  find . -name "*.jpg" -print0 | xargs -0 rm -f
  find . -name "*.ini" -print0 | xargs -0 rm -f
  rm -rf .pytest_cache/
  rm -rf .mypy_cache/
  find . -maxdepth 3 -type d -empty -print0 | xargs -0 -r rm -r

clean-builds:
  rm -rf build/
  rm -rf dist/
  rm -rf yutto.egg-info/

ci-install:
  uv sync --all-extras --dev

ci-fmt-check:
  uv run ruff format --check --diff .

ci-lint:
  just lint

ci-test:
  uv run pytest -m "(api or processor or biliass) and not (ci_skip or ignore)" --reruns 3 --reruns-delay 1
  just clean

ci-e2e-test:
  uv run pytest -m "e2e and not (ci_skip or ignore)"
  just clean

docker-run *ARGS:
  docker run --rm -it -v `pwd`:/app {{DOCKER_NAME}} {{ARGS}}

docker-build:
  docker build --no-cache -t "{{DOCKER_NAME}}:{{VERSION}}" -t "{{DOCKER_NAME}}:latest" .

docker-publish:
  docker buildx build --no-cache --platform=linux/amd64,linux/arm64 -t "{{DOCKER_NAME}}:{{VERSION}}" -t "{{DOCKER_NAME}}:latest" . --push

compile-protobuf:
  cd packages/biliass; protoc protobuf/danmaku.proto --python_out=src/biliass --pyi_out=src/biliass
