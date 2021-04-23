DOCKER_NAME := "siguremo/yutto-env:v1"

run:
	docker run -it --mount type=bind,source=`pwd`,destination=/src/yutto -w /src/yutto siguremo/{{DOCKER_NAME}} python -m yutto

test:
	docker run -it --mount type=bind,source=`pwd`,destination=/src/yutto -w /src/yutto siguremo/{{DOCKER_NAME}} pytest

build:
	docker build -t siguremo/{{DOCKER_NAME}} .
