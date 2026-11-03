# syntax=docker/dockerfile:1
FROM debian:trixie-slim AS magic-build
ARG MAGIC_REVISION=d914f66693e6ce0bd30dc1f2b265c2bcd7b20762
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export GIT_SSL_CAINFO=/run/secrets/proxy_ca; fi; \
    apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      ca-certificates git build-essential m4 csh tcl-dev tk-dev libx11-dev libxext-dev \
      libxrender-dev libglu1-mesa-dev libcairo2-dev libncurses-dev \
    && git clone https://github.com/RTimothyEdwards/magic.git /build/magic \
    && cd /build/magic && git checkout "$MAGIC_REVISION" \
    && ./configure --prefix=/opt/eda && make -j2 && make install

FROM python:3.12-slim-trixie
# Optional CA build secret supports managed environments; normal laptop builds need none.
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then \
      cp /run/secrets/proxy_ca /usr/local/share/ca-certificates/lab-build-proxy.crt; \
      update-ca-certificates; \
    fi; \
    apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      ngspice netgen-lvs xschem klayout xvfb xauth git libglu1-mesa libcairo2 libncurses6 \
    && rm -rf /var/lib/apt/lists/* \
    && rm -f /usr/local/share/ca-certificates/lab-build-proxy.crt \
    && update-ca-certificates --fresh
WORKDIR /lab
COPY --from=magic-build /opt/eda /opt/eda
COPY src/ /lab/src/
COPY examples/ /lab/examples/
COPY config/ /lab/config/
COPY bridge/ /lab/bridge/
COPY knowledge/ /lab/knowledge/
COPY tests/ /lab/tests/
RUN chmod -R a+rX /lab
ENV PYTHONPATH=/lab/src PYTHONDONTWRITEBYTECODE=1 HOME=/tmp OMP_NUM_THREADS=1 QT_QPA_PLATFORM=offscreen
ENV PATH="/opt/eda/bin:${PATH}"
USER 10001:10001
ENTRYPOINT ["python", "-m", "chip_lab"]
CMD ["simulate", "--output", "/results"]
