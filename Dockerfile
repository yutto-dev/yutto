FROM alpine:3.21
LABEL maintainer="siguremo" \
      version="2.0.3" \
      description="light-weight container based on alpine for yutto"

RUN set -x \
    && sed -i 's/dl-cdn.alpinelinux.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apk/repositories \
    && apk add -q --progress --update --no-cache ffmpeg python3 tzdata \
    && python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --compile yutto \
    && cp /usr/share/zoneinfo/Asia/Shanghai /etc/localtime

WORKDIR /app

ENTRYPOINT ["/opt/venv/bin/yutto", "-d", "/app"]
