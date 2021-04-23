FROM python:3.10.0a7-alpine3.13

RUN set -x; apk add gcc \
  && apk add musl-dev \
  && apk add build-base \
  && pip install -U setuptools pip \
  && pip install cython \
  && pip install pytest \
  && pip install aiohttp \
  && pip install aiofiles \
  && pip install asyncio \
  && pip install uvloop
