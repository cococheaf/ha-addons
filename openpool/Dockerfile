FROM ghcr.io/home-assistant/base:latest

ARG BUILD_ARCH
ARG BUILD_VERSION

LABEL \
  io.hass.name="OpenPool" \
  io.hass.description="OpenSource Pool System Controller" \
  io.hass.type="app" \
  io.hass.version="${BUILD_VERSION}" \
  io.hass.arch="${BUILD_ARCH}"

RUN apk add --no-cache python3

WORKDIR /app

COPY server.py /app/server.py
COPY run.sh /run.sh
COPY www /app/www

RUN chmod a+x /run.sh

CMD ["/run.sh"]
