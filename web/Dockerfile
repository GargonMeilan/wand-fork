FROM node:22.16.0-alpine3.22 AS ruffle
WORKDIR /build
COPY ruffle/package.json ruffle/package-lock.json ./
RUN npm ci --ignore-scripts --no-audit --no-fund

FROM nginx:1.28.0-alpine3.21

COPY --from=ruffle /build/node_modules/@ruffle-rs/ruffle/ /opt/wand/ruffle/
COPY ruffle/legacy.js ruffle/legacy.css /opt/wand/ruffle/

ENV DOCKERIZE_VERSION v0.7.0
RUN ARCH=$(arch | sed s/aarch64/arm64/ | sed s/x86_64/amd64/) && wget https://github.com/jwilder/dockerize/releases/download/$DOCKERIZE_VERSION/dockerize-linux-$ARCH-$DOCKERIZE_VERSION.tar.gz \
    && tar -C /usr/local/bin -xzvf dockerize-linux-$ARCH-$DOCKERIZE_VERSION.tar.gz \
    && rm dockerize-linux-$ARCH-$DOCKERIZE_VERSION.tar.gz
