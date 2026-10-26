#!/usr/bin/env bash
# ============================================================
# NinFenz quickstart_check.sh —— 五分钟可复现入口的可执行判据
#
# 用法：bash scripts/quickstart_check.sh [--audit]
#   无参数   静态审计 → 按 docs/quickstart.md 的 6 步顺序跑最短路径 → 核对墙钟
#   --audit  只做静态审计（步数 / 步号 / 命令面），不执行任何 nf 命令
#
# 三条判据（全部机读，末行固定输出）：
#   1) 退出码 0
#   2) 墙钟 ≤ NF_QUICKSTART_MAX_SECONDS（300 秒）
#   3) 文档步数 == 脚本步数（NF_QUICKSTART_DOC_STEPS == NF_QUICKSTART_SCRIPT_STEPS）
#
# 步数真源：本文件里的 `# nf-step: N slug` 行 ↔ docs/quickstart.md 里的
#           `<!-- nf-step: N slug -->` 行。两边序列必须逐项相同，顺序也必须相同；
#           只改一边（增删步 / 换命令）即审计失败，verify.sh 的 check39 立刻红。
# 产物落点：默认写系统临时目录并在退出时删除；仓库树内不留未跟踪件。
# ============================================================
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || { echo '无法进入仓库根目录' >&2; exit 2; }

DOC='docs/quickstart.md'
SELF='scripts/quickstart_check.sh'
MAX_SECONDS=300
TOTAL_STEPS=6
DOC_STEPS=0
SCRIPT_STEPS=0
STEP_AT=0
FAILED=0
WORK=''
AUDIT_ONLY=0
SECONDS=0

while [ $# -gt 0 ]; do
  case "$1" in
    --audit) AUDIT_ONLY=1 ;;
    -h|--help) sed -n '2,20p' "$SELF"; exit 0 ;;
    *) printf '未知参数：%s（用法：bash scripts/quickstart_check.sh [--audit]）\n' "$1" >&2; exit 2 ;;
  esac
  shift
done

say(){ printf '  [quickstart] %s\n' "$1"; }
die(){ printf '  [quickstart][FAIL] %s\n' "$1" >&2; FAILED=$((FAILED + 1)); exit 1; }

cleanup(){
  if [ -n "$WORK" ] && [ -d "$WORK" ]; then rm -rf "$WORK"; fi
  printf 'NF_QUICKSTART_MAX_SECONDS=%s\n' "$MAX_SECONDS"
  printf 'NF_QUICKSTART_ELAPSED_SECONDS=%s\n' "$SECONDS"
  printf 'NF_QUICKSTART_DOC_STEPS=%s\n' "$DOC_STEPS"
  printf 'NF_QUICKSTART_SCRIPT_STEPS=%s\n' "$SCRIPT_STEPS"
  if [ "$FAILED" -eq 0 ]; then
    printf 'NF_QUICKSTART_OK=1\n'
  else
    printf 'NF_QUICKSTART_OK=0\n'
  fi
}
trap cleanup EXIT

# ---- Python 解释器（与 verify.sh 同口径：能真正执行 import sys 才算可用）----
PY=''
if command -v python3 >/dev/null 2>&1 && python3 -c 'import sys' >/dev/null 2>&1; then
  PY='python3'
elif command -v python >/dev/null 2>&1 && python -c 'import sys' >/dev/null 2>&1; then
  PY='python'
fi
[ -n "$PY" ] || die '找不到可用的 Python 3（判据：python3/python -c "import sys" 能执行）'
"$PY" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' \
  || die "Python 版本低于 3.10（实测：$("$PY" -V 2>&1)）"

# ---- 静态审计：文档 ↔ 脚本的步序列 / 步号 / 命令面 ----
_steps_of(){ tr -d '\r' < "$1" | grep -o 'nf-step: [0-9][0-9]* [a-z0-9-]*' | sed 's/^nf-step: //'; }
_count(){ printf '%s\n' "$1" | awk 'NF{n++} END{print n+0}'; }
_join_ids(){ printf '%s\n' "$1" | awk 'NF{printf "%s%s", (n++?" ":""), $1}'; }

[ -f "$DOC" ] || die "缺入口文档 $DOC（修复指引：补回该文件，或同步修改本脚本）"
[ -f "$SELF" ] || die "缺入口脚本 $SELF（修复指引：补回该文件，或同步修改 docs/quickstart.md）"

DOC_SEQ="$(_steps_of "$DOC")"
SH_SEQ="$(_steps_of "$SELF")"
DOC_STEPS="$(_count "$DOC_SEQ")"
SCRIPT_STEPS="$(_count "$SH_SEQ")"

if [ "$DOC_SEQ" != "$SH_SEQ" ]; then
  printf '  [quickstart][FAIL] 文档步序列 != 脚本步序列（判据 3）\n' >&2
  printf '    文档：%s\n' "$(printf '%s' "$DOC_SEQ" | tr '\n' '|')" >&2
  printf '    脚本：%s\n' "$(printf '%s' "$SH_SEQ" | tr '\n' '|')" >&2
  FAILED=$((FAILED + 1)); exit 1
fi
[ "$DOC_STEPS" -gt 0 ] || die "两边都没有 nf-step 步标记（判据失效：审计不能空转）"
[ "$DOC_STEPS" -eq "$TOTAL_STEPS" ] \
  || die "步数 $DOC_STEPS != 本脚本声明的 TOTAL_STEPS=$TOTAL_STEPS（修复指引：同步步标记与执行函数）"

EXPECT_IDS=''
_i=1
while [ "$_i" -le "$DOC_STEPS" ]; do EXPECT_IDS="$EXPECT_IDS${EXPECT_IDS:+ }$_i"; _i=$((_i + 1)); done
[ "$(_join_ids "$DOC_SEQ")" = "$EXPECT_IDS" ] \
  || die "步号不连续或重号：期望「$EXPECT_IDS」，实际「$(_join_ids "$DOC_SEQ")」"

# 每一步的文档块里至少有一条可复制粘贴的命令（python … / cmp …）
_missing_cmds="$(awk '
  /<!--[[:space:]]*nf-step:/ {
    if (step > 0 && !has) print step
    step++; has = 0; next
  }
  /^python scripts\/nf\.py / { has = 1 }
  /^cmp / { has = 1 }
  END { if (step > 0 && !has) print step }
' "$DOC")"
[ -z "$_missing_cmds" ] \
  || die "步骤块没有可执行命令（步号：$(printf '%s' "$_missing_cmds" | tr '\n' ' ')）"

# 文档里的 nf 子命令序列必须与脚本一致（防「文档写 doctor、脚本跑 demo」）
_doc_nf="$(tr -d '\r' < "$DOC" | grep -oE 'scripts/nf\.py [a-z][a-z0-9-]*' | awk '{print $2}')"
_sh_nf="$(tr -d '\r' < "$SELF" | grep -oE 'scripts/nf\.py [a-z][a-z0-9-]*' | awk '{print $2}')"
[ "$_doc_nf" = "$_sh_nf" ] \
  || die "文档 nf 命令序列 != 脚本执行序列（文档：$(printf '%s' "$_doc_nf" | tr '\n' ' ')；脚本：$(printf '%s' "$_sh_nf" | tr '\n' ' ')）"

# 每个 nf 子命令都必须真在 CLI 注册表里（防改名残留）
CLI_CMDS="$(grep -oE 'sub\.add_parser\([[:space:]]*"[a-z0-9-]+"' scripts/nf.py \
  | grep -oE '"[a-z0-9-]+"' | tr -d '"')"
for _cmd in $_doc_nf; do
  printf '%s\n' "$CLI_CMDS" | grep -qx -- "$_cmd" \
    || die "文档命令 \`nf $_cmd\` 不是 CLI 子命令（修复指引：核对 scripts/nf.py 的 add_parser 表）"
done

say "静态审计通过：文档 $DOC_STEPS 步 == 脚本 $SCRIPT_STEPS 步（命令序列：$(printf '%s' "$_doc_nf" | tr '\n' ' ')）"
printf 'NF_QUICKSTART_AUDIT=1\n'
if [ "$AUDIT_ONLY" -eq 1 ]; then
  exit 0
fi

# ---- 执行最短路径（与 docs/quickstart.md 的 6 步同序）----
WORK="$(mktemp -d "${TMPDIR:-/tmp}/nf_quickstart.XXXXXX" 2>/dev/null)" \
  || die '无法创建临时目录（请设 TMPDIR 指向可写目录）'
[ -d "$WORK" ] || die '临时目录创建失败'

enter_step(){
  STEP_AT=$((STEP_AT + 1))
  [ "$1" -eq "$STEP_AT" ] || die "执行步序错乱：期望第 $STEP_AT 步，实际调用第 $1 步"
  say "步 $1/$TOTAL_STEPS · $2"
}

# nf-step: 1 version
step_version(){
  enter_step 1 version
  "$PY" scripts/nf.py --version >"$WORK/01.log" 2>&1 \
    || die '步 1 失败：nf --version 退出码非 0'
  local out
  out="$(tr -d '\r' < "$WORK/01.log" | sed -n '1p')"
  printf '%s' "$out" | grep -Eq '^nf [0-9]+\.[0-9]+\.[0-9]+' \
    || die "步 1 输出不是版本行：$out"
  say "版本行：$out"
}

# nf-step: 2 doctor
step_doctor(){
  enter_step 2 doctor
  "$PY" scripts/nf.py doctor >"$WORK/02.log" 2>&1 \
    || die '步 2 失败：nf doctor 退出码非 0'
  local out
  out="$(tr -d '\r' < "$WORK/02.log")"
  printf '%s\n' "$out" | grep -q '体检：' || die '步 2 输出缺「体检：」汇总行'
  printf '%s\n' "$out" | grep -q '通过' || die '步 2 体检未通过'
  if printf '%s\n' "$out" | grep -q '\[FAIL\]'; then
    die '步 2 体检出现 [FAIL] 行'
  fi
  say "$(printf '%s\n' "$out" | grep '体检：' | tail -1)"
}

# nf-step: 3 demo
step_demo(){
  enter_step 3 demo
  "$PY" scripts/nf.py demo >"$WORK/03.log" 2>&1 \
    || die '步 3 失败：nf demo 退出码非 0'
  local out
  out="$(tr -d '\r' < "$WORK/03.log")"
  printf '%s\n' "$out" | grep -q '质量门：' || die '步 3 输出缺「质量门：」行'
  printf '%s\n' "$out" | grep -q 'FAIL 0' || die '步 3 质量门 FAIL 非 0'
  printf '%s\n' "$out" | grep -q '产物：' || die '步 3 未打印产物路径'
  say '质量门 FAIL 0；交付物（Markdown）已生成'
}

# nf-step: 4 assemble
step_assemble(){
  enter_step 4 assemble
  rm -rf "$WORK/out1"
  "$PY" scripts/nf.py assemble "写一份技术文档，要术语表和修订记录" --build --dest "$WORK/out1" \
    >"$WORK/04.log" 2>&1 \
    || die '步 4 失败：nf assemble --build 退出码非 0'
  A1="$(find "$WORK/out1" -maxdepth 1 -name '*.md' -type f 2>/dev/null | head -1)"
  [ -n "$A1" ] && [ -s "$A1" ] || die '步 4 失败：未产出非空的 .md 完整版'
  say "产物：$(basename "$A1")（$(wc -c < "$A1" | tr -d ' ') 字节）"
}

# nf-step: 5 reproducible
step_reproducible(){
  enter_step 5 reproducible
  rm -rf "$WORK/out2"
  "$PY" scripts/nf.py assemble "写一份技术文档，要术语表和修订记录" --build --dest "$WORK/out2" \
    >"$WORK/05.log" 2>&1 \
    || die '步 5 失败：第二次 nf assemble --build 退出码非 0'
  A2="$(find "$WORK/out2" -maxdepth 1 -name '*.md' -type f 2>/dev/null | head -1)"
  [ -n "$A2" ] && [ -s "$A2" ] || die '步 5 失败：第二份产物缺失或为空'
  cmp -s "$A1" "$A2" || die '步 5 失败：同一需求两次产物不逐字节相同（可复现判据红）'
  say '两份产物逐字节相同（cmp 退出码 0）'
}

# nf-step: 6 check
step_check(){
  enter_step 6 check
  "$PY" scripts/nf.py assemble "写一份技术文档，要术语表和修订记录" --check "$A1" \
    >"$WORK/06.log" 2>&1 \
    || die '步 6 失败：nf assemble --check 退出码非 0'
  tr -d '\r' < "$WORK/06.log" | grep -q '成品通过自组装机器验收' \
    || die '步 6 输出缺「成品通过自组装机器验收」'
  say '成品通过自组装机器验收'
}

step_version
step_doctor
step_demo
step_assemble
step_reproducible
step_check

# ---- 判据 2：墙钟 ----
if [ "$SECONDS" -gt "$MAX_SECONDS" ]; then
  die "墙钟 ${SECONDS}s 超过上限 ${MAX_SECONDS}s（判据 2）"
fi
printf 'NF_QUICKSTART_WALL_OK=1\n'
say "全部通过：$STEP_AT 步 · 墙钟 ${SECONDS}s ≤ ${MAX_SECONDS}s"
