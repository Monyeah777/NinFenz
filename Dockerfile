# syntax=docker/dockerfile:1
# NinFenz Content Gate — Glama / MCP stdio image.
#
# The server is stdlib-only: no pip install, no build step, no network at runtime.
# Glama builds this file and starts the container with `CMD` below, then performs
# `initialize` / `tools/list` / `resources/list` / `prompts/list` over stdio.
# Keep stdout pure JSON-RPC (the startup banner in nf.py goes to stderr).
# Digest from Dockerfile.crosscheck's pinned PY_BASE (SLSA check41: base images
# must be digest-pinned; a bare tag is rejected).
FROM python:3.11-slim@sha256:e88e9763f943ec1834f992a4b51e0f24500486803e8bc534c5767af9ea65f6ce

LABEL org.opencontainers.image.title="NinFenz Content Gate" \
      org.opencontainers.image.description="MCP server for deterministic contracts, release gates and evidence in the NinFenz content contract layer" \
      org.opencontainers.image.source="https://github.com/Monyeah777/NinFenz" \
      org.opencontainers.image.licenses="AGPL-3.0-only OR LicenseRef-Commercial"

# UTF-8 everywhere: repository paths and document titles contain Chinese characters.
# Unbuffered + no .pyc keeps stdio responsive and the image filesystem read-only-safe.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    PYTHONIOENCODING=utf-8 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

WORKDIR /app

# Run as an unprivileged user: the server only reads repository files.
RUN groupadd --gid 10001 nf \
 && useradd --uid 10001 --gid nf --create-home --shell /usr/sbin/nologin nf

# Only the files the read-only surface actually opens are copied.
# Explicit COPY (instead of `COPY . .`) keeps the image small and makes the
# runtime contract auditable: 03/04/05 content, community packs, library,
# patterns, protocol declarations, docs, and the MCP runtime itself.
COPY --chown=10001:10001 scripts/ scripts/
COPY --chown=10001:10001 desktop/src/ desktop/src/
COPY --chown=10001:10001 03_管线库/ 03_管线库/
COPY --chown=10001:10001 04_模块库/ 04_模块库/
COPY --chown=10001:10001 05_资产库/ 05_资产库/
COPY --chown=10001:10001 community/ community/
COPY --chown=10001:10001 library/ library/
COPY --chown=10001:10001 patterns/ patterns/
COPY --chown=10001:10001 protocol/ protocol/
COPY --chown=10001:10001 docs/ docs/
COPY --chown=10001:10001 *.md ./
COPY --chown=10001:10001 LICENSE ./

USER nf

# stdio transport only: no ports, no long-running HTTP listener.
# `serve` defaults to the live repository surface (no snapshot needed).
CMD ["python", "scripts/nf.py", "serve"]
