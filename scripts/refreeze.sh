#!/usr/bin/env bash
# 统一冻结入口（唯一正确顺序）。
#
# 为什么需要（2026-10-29 实测，一次真实的 CI 红）：
#   冻结链里有多个生成件**统计仓库件集合与文件内容**（`protocol/role_coordinates.json`、
#   `protocol/verification_report.json`、各基线）。若先跑冻结、后跑 `npm run stage`（它会改写
#   被统计的跟踪文件），提交进仓的产物就与"提交后树上的实时重算"差一个快照 ——
#   CI 的「提交件 == 实时重算」判据必然红，而本机当时也是红的，却容易被误判为"平台差异"。
#   本脚本把顺序固定为：**分发物 → 站点数字 → 冻结链 → 自检**，任何人只要跑它就得到自洽的树。
#
# 用法：bash scripts/refreeze.sh [--by <审批人>]
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

BY="Monyeah777"
if [ "${1:-}" = "--by" ] && [ -n "${2:-}" ]; then BY="$2"; fi

echo "== 1/4 分发物与站点数字（先做：它们会改写被统计的跟踪文件）"
(cd packaging/npm && npm run stage -- --sync-readme >/dev/null)
node site/tools/sync-numbers.mjs --write >/dev/null

echo "== 2/4 代码/风格/SAST/耦合基线"
python scripts/code_metrics.py --write >/dev/null
python scripts/coupling_metrics.py --write >/dev/null
python scripts/style_check.py --write >/dev/null
python scripts/sast_check.py --write >/dev/null

echo "== 3/4 层次投影 → 审计重绑 → conformance → 审批 → 回执"
python scripts/nf.py layers --write >/dev/null
python scripts/nf.py audit rebind --note "refreeze.sh（统一冻结入口）" >/dev/null
python scripts/nf.py conformance --write >/dev/null
python scripts/nf.py approve protocol/conformance_report.json --by "$BY" --note "refreeze.sh" >/dev/null
python scripts/nf.py receipts --scope protocol --write >/dev/null

echo "== 4/4 验证报告与卡册 + 自检（必须全绿才算冻结完成）"
python scripts/verify_report.py --write >/dev/null
python scripts/build_verification_cards.py --write >/dev/null
bash verify.sh --checks-only | tail -2
echo "冻结完成。可提交；提交后再跑一次本脚本可验证幂等（不应产生任何 diff）。"
