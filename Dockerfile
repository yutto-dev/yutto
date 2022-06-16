FROM alpine:3.16
LABEL maintainer="siguremo" \
      version="2.0.0-beta.14" \
      description="light-weight container based on alpine for yutto"

RUN set -x \
    && sed -i 's/dl-cdn.alpinelinux.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apk/repositories \
    && apk add -q --progress --update --no-cache --virtual .build-deps gcc g++ build-base python3-dev libffi-dev \
    && apk add -q --progress --update --no-cache ffmpeg python3 py-pip tzdata \
    && python3 -m pip install --no-cache-dir --pre yutto[uvloop] -i https://pypi.tuna.tsinghua.edu.cn/simple \
    && cp /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \
    && apk del --purge .build-deps

WORKDIR /app

ENTRYPOINT ["yutto", "-d", "/app"]
