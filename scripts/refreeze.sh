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
# 用法：
#   bash scripts/refreeze.sh                # 重冻并落盘（提交前用）
#   bash scripts/refreeze.sh --check        # **只校验**：跑完整链条后要求工作树零 diff
#                                           #（CI 拿它当判据：提交件必须 == 干净检出上重算的结果）
#   bash scripts/refreeze.sh --by <审批人>   # 指定审批人
#
# 为什么要有 `--check`（2026-10-29）：本轮两次 main 红都是"提交件与实时重算差一个快照"，
# 根因是冻结顺序与日志污染。人工纪律不可靠 ⇒ 把"幂等"变成 CI 里可执行、可挡合并的判据。
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

BY="Monyeah777"
CHECK_ONLY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --check) CHECK_ONLY=1; shift ;;
    --by) BY="${2:-Monyeah777}"; shift 2 ;;
    *) shift ;;
  esac
done

echo "== 1/5 分发物 → 自述数字 → 站点数字（顺序：payload 清单先于 repo_stats，后者先于站点）"
(cd packaging/npm && npm run stage -- --sync-readme >/dev/null)
python scripts/nf.py stats --write >/dev/null     # protocol/repo_stats.json（站点数字的真源）
node site/tools/sync-numbers.mjs --write >/dev/null

echo "== 2/5 代码/风格/SAST/耦合基线"
python scripts/code_metrics.py --write >/dev/null
python scripts/coupling_metrics.py --write >/dev/null
python scripts/style_check.py --write >/dev/null
python scripts/sast_check.py --write >/dev/null

echo "== 3/5 层次投影 → 审计重绑 → conformance → 审批 → 回执"
python scripts/nf.py layers --write >/dev/null
python scripts/nf.py audit rebind --note "refreeze.sh（统一冻结入口）" >/dev/null
python scripts/nf.py conformance --write >/dev/null
python scripts/nf.py approve protocol/conformance_report.json --by "$BY" --note "refreeze.sh" >/dev/null
python scripts/nf.py receipts --scope protocol --write >/dev/null

echo "== 4/5 卡册 → 验证报告 + 自检（顺序关键：报告必须最后写）"
# 为什么 cards 要在 report 之前（2026-10-29 实测）：`build_verification_cards.py --write`
# 会改写被报告统计的 `docs/verification-cards.md`；若它排在 report 之后，报告一落盘就过期，
# 于是「提交件 == 实时重算」判据在 CI 与本机同时红（且本机自检也会红）。
python scripts/build_verification_cards.py --write >/dev/null
python scripts/verify_report.py --write >/dev/null

if [ "$CHECK_ONLY" -eq 1 ]; then
  # 判据本体：干净检出上重跑完整冻结链后，工作树必须**零 diff**。
  # 有任何改动 ⇒ 提交件不是"树上实时重算的结果" ⇒ 判红（把失败挡在合并之前）。
  if [ -n "$(git status --porcelain)" ]; then
    echo "::error::冻结链不幂等：重跑后工作树仍有改动（提交件 != 实时重算）"
    git status --porcelain | head -40
    echo "---- diff 统计 ----"
    git diff --stat | tail -20
    exit 1
  fi
  echo "OK 冻结链幂等：干净检出重跑后工作树零 diff（提交件 == 实时重算）"
  exit 0
fi

bash verify.sh --checks-only | tail -2
# 自检必须包含"提交件 == 实时重算"的**执行侧**判据（只看 checks-only 会漏掉它们：
# 这两条在 unittest 矩阵里，不在 42 条静态 check 里）。
PYTHONIOENCODING=utf-8 python -m unittest discover -s desktop/tests -p "test_verify_report.py" >/dev/null
PYTHONIOENCODING=utf-8 python -m unittest discover -s desktop/tests -p "test_role_model.py" >/dev/null
echo "自检通过（checks-only + verify_report + role_model）。可提交。"

echo "== 5/5 幂等：再跑一遍不应产生任何 diff"
git diff --stat > /tmp/_rfz_before.txt || true
