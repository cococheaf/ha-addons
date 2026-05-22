FROM ghcr.io/home-assistant/base:latest

ARG BUILD_VERSION=1.0.0
ARG BUILD_ARCH=amd64

LABEL \
  io.hass.version="${BUILD_VERSION}" \
  io.hass.type="app" \
  io.hass.arch="${BUILD_ARCH}"

RUN apk add --no-cache python3 py3-pip

WORKDIR /app

COPY requirements.txt /app/requirements.txt

RUN pip3 install --no-cache-dir --break-system-packages -r /app/requirements.txt

COPY run.sh /run.sh
COPY app.py /app/app.py

RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
