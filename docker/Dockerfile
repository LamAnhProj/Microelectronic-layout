# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm
# Optional CA build secret supports managed environments; normal laptop builds need none.
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then \
      cp /run/secrets/proxy_ca /usr/local/share/ca-certificates/lab-build-proxy.crt; \
      update-ca-certificates; \
    fi; \
    apt-get update && apt-get install -y --no-install-recommends ngspice magic netgen-lvs xschem \
    && rm -rf /var/lib/apt/lists/* \
    && rm -f /usr/local/share/ca-certificates/lab-build-proxy.crt \
    && update-ca-certificates --fresh
WORKDIR /lab
COPY src/ /lab/src/
COPY examples/ /lab/examples/
RUN chmod -R a+rX /lab
ENV PYTHONPATH=/lab/src PYTHONDONTWRITEBYTECODE=1 HOME=/tmp OMP_NUM_THREADS=1
USER 10001:10001
ENTRYPOINT ["python", "-m", "chip_lab"]
CMD ["simulate", "--output", "/results"]
