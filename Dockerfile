FROM ubuntu:20.04
LABEL maintainer="siguremo" \
      version="0.1" \
      description="yutto container"

# Install deps
RUN set -x \
    && apt update \
    && apt install -y ffmpeg python3.9 python3-pip \
    && rm -rf /var/lib/apt/lists/* \
    && python3.9 -m pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple \
    && python3.9 -m pip install --no-cache-dir yutto[uvloop]

CMD [ "bash" ]
