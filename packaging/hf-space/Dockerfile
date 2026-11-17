# S1 入口：Docker Space（零第三方 Python 依赖，与 NF「只用标准库」纪律一致）。
#
# E1（2026-10-10 全仓审计 P1）：此前是 `COPY nf/ /app/nf/`，依赖本地产物 `hf-space/nf/`
# （由 tools/stage-space.mjs 从 npm payload 复制），而它是 .gitignore 的忽略面 ⇒ **从干净检出
# 不可构建**（实测 Test-Path hf-space/nf = False）。
# 现改为**多阶段**：从**已发布**的 npm 包取 payload——这正是 stage-space 的口径（「使 Space 与
# npm 包同源同版本」），且不再要求构建上下文里存在本地产物。
#
# 发新版时：把 NF_VERSION 与 packaging/npm/package.json 的 version 同步；release 链已判两处一致性。
# Scorecard PinnedDependenciesID（2026-11-09）：两级基座都按 digest 钉死（升级=显式改 digest）。
FROM node:22-slim@sha256:5ec23b7c622b00547753bc6ffd78085dd868a68aeb41c8e0a1418f033e13d96d AS nfpayload
ARG NF_VERSION=1.0.5
WORKDIR /tmp/nf
RUN npm pack "ninfenz@${NF_VERSION}" \
 && tar -xzf ninfenz-*.tgz \
 && test -d package/payload \
 && mv package/payload /nf

FROM python:3.15-slim@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928

ENV PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    PYTHONIOENCODING=utf-8 \
    NF_AUTOSTART=0 \
    PORT=7860

WORKDIR /app
COPY --from=nfpayload /nf /app/nf/
COPY server.py /app/server.py

EXPOSE 7860
CMD ["python", "server.py"]
