FROM alpine:3.15
LABEL maintainer="siguremo" \
      version="2.0.0-beta.9" \
      description="light-weight container based on alpine for yutto"

RUN set -x \
    && sed -i 's/dl-cdn.alpinelinux.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apk/repositories \
    && apk add -q --progress --update --no-cache --virtual .build-deps gcc g++ build-base \
    && apk add -q --progress --update --no-cache ffmpeg python3 python3-dev py-pip linux-headers libffi-dev openssl-dev \
    && python3 -m pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple \
    && python3 -m pip install --no-cache-dir --pre yutto[uvloop] \
    && apk del .build-deps

WORKDIR /app

ENTRYPOINT ["yutto", "-d", "/app"]
