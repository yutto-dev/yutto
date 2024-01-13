FROM alpine:3.19
LABEL maintainer="siguremo" \
      version="2.0.0-beta.33" \
      description="light-weight container based on alpine for yutto"

RUN set -x \
    && sed -i 's/dl-cdn.alpinelinux.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apk/repositories \
    && apk add -q --progress --update --no-cache --virtual .build-deps gcc g++ build-base python3-dev libffi-dev \
    && apk add -q --progress --update --no-cache ffmpeg python3 tzdata \
    && python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --pre yutto \
    && cp /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \
    && apk del --purge .build-deps

WORKDIR /app

ENTRYPOINT ["/opt/venv/bin/yutto", "-d", "/app"]
