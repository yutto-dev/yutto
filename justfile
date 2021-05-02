DOCKER_NAME := "siguremo/yutto-env:v1"

docker-run:
  docker run -it --mount type=bind,source=`pwd`,destination=/src/yutto -w /src/yutto siguremo/{{DOCKER_NAME}} python -m yutto

docker-test:
  docker run -it --mount type=bind,source=`pwd`,destination=/src/yutto -w /src/yutto siguremo/{{DOCKER_NAME}} pytest

docker-build-env:
  docker build -t siguremo/{{DOCKER_NAME}} .

run:
  python -m yutto

test:
  python -m pytest

release:
  python setup.py upload

upgrade-pip:
  python -m pip install --upgrade yutto

upgrade:
  python setup.py build
  python setup.py install
