DOCKER_NAME := "siguremo/yutto-env:v1"

docker-run:
  docker run -it --mount type=bind,source=`pwd`,destination=/src/yutto -w /src/yutto siguremo/{{DOCKER_NAME}} python -m yutto

docker-test:
  docker run -it --mount type=bind,source=`pwd`,destination=/src/yutto -w /src/yutto siguremo/{{DOCKER_NAME}} pytest

docker-build-env:
  docker build -t siguremo/{{DOCKER_NAME}} .

run:
  python3 -m yutto

test:
  python3 -m pytest

release:
  python3 setup.py upload

upgrade-pip:
  python3 -m pip install --upgrade yutto

upgrade:
  python3 setup.py build
  python3 setup.py install

clean:
  find . -name "*.m4s" -print0 | xargs -0 rm -f
  find . -name "*.mp4" -print0 | xargs -0 rm -f
  find . -name "*.aac" -print0 | xargs -0 rm -f

clean-builds:
  rm -rf build/
  rm -rf dist/
  rm -rf yutto.egg-info/
