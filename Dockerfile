# Pinned to a digest, not a tag: `python:3.13-alpine` moves, and a server holding
# Instagram tokens should not change underneath you on a rebuild.
FROM python:3.13-alpine@sha256:540c7d91f98ff6880174c40e99067bf5941eb54d818a7a5e094d188b196a934d AS build

WORKDIR /app
RUN pip install --no-cache-dir hatchling
COPY pyproject.toml README.md LICENSE SKILL.md ./
COPY src ./src
RUN pip wheel --no-cache-dir --no-deps -w /wheels .

FROM python:3.13-alpine@sha256:540c7d91f98ff6880174c40e99067bf5941eb54d818a7a5e094d188b196a934d

# Build the optional unofficial tier in with --build-arg UNOFFICIAL=1. It is off
# by default here for the same reason it is off in the package: it drives
# Instagram's private API and that is against their terms.
ARG UNOFFICIAL=0

COPY --from=build /wheels /wheels
RUN if [ "$UNOFFICIAL" = "1" ]; then \
      pip install --no-cache-dir /wheels/*.whl[unofficial] ; \
    else \
      pip install --no-cache-dir /wheels/*.whl ; \
    fi \
 && rm -rf /wheels

# Not root. The data directory holds tokens, a session file and the audit log.
RUN adduser -D -h /data instagram
USER instagram
ENV IG_MCP_DATA_DIR=/data
VOLUME ["/data"]

EXPOSE 8000

# HTTP has no authentication of its own. Put it behind TLS and an
# authenticating proxy. Do not publish this port to the internet directly.
ENTRYPOINT ["instagram-mcp"]
CMD ["--http", "--host", "0.0.0.0", "--port", "8000"]
