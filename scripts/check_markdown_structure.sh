#!/usr/bin/env bash
# markdown 结构检查（FX-14 / FX-15 的**单一执行入口**：本地与 CI 用同一条命令）。
#
# 规则真源：.markdownlint.json（MD001/MD009/MD025/MD041/MD047 显式启用；MD013 显式关闭，理由见该文件）。
# 扫描面：全仓 md，排除**非文档面**（每类都写明理由，不是为变绿而剪）：
#   community/ 与 library/NF-*  第三方投稿正文（版权归投稿人；正文形态由 library frontmatter 真源与许可证门守）
#   results/**                  审计流水账/取证档案（机器产出的过程记录，不是文档入口面）
#   packaging/npm/payload/**    npm 发布物镜像树（生成物，由 payload 清单门禁守）
#   docs/standards/**           标准目录（geo_export.py --write 生成、文件头写明禁止手改；结构由生成器与
#                               check38 出口面守——手工调标题会被下一次生成覆盖）
#   changes/**                  变更片段（Keep-a-Changelog 片段形态：被发布工具整段嵌入版本小节，
#                               片段自身不是一个独立文档，强加 H1 会改掉片段语义）
#   docs/examples/**            示例产物（演示用渲染结果，不是说明文档）
#   .github/ISSUE_TEMPLATE/**   平台表单/模板（fragment，由平台 schema 与 CW-01 判据守）
#   .github/PULL_REQUEST_TEMPLATE.md  同上
#   desktop/tests/fixtures/**   字节级测试夹具（roundtrip 必须逐字节还原；改一个字节就会让
#                               test_import_adapter 的 byte-exact 判据失效——它们不是文档）
# 用法：bash scripts/check_markdown_structure.sh [--fix]
set -uo pipefail
cd "$(dirname "$0")/.." || exit 2
VERSION="markdownlint-cli2@0.23.3"
ARGS=( "**/*.md"
       "#community/**" "#packaging/npm/payload/**" "#results/**" "#library/NF-*.md"
       "#docs/standards/**" "#changes/**" "#docs/examples/**"
       "#.github/ISSUE_TEMPLATE/**" "#.github/PULL_REQUEST_TEMPLATE.md"
       "#desktop/tests/fixtures/**" )
FIX=""
[ "${1:-}" = "--fix" ] && FIX="--fix"
if command -v markdownlint-cli2 >/dev/null 2>&1; then
  markdownlint-cli2 "${ARGS[@]}" $FIX
else
  npx --yes "$VERSION" "${ARGS[@]}" $FIX
fi
