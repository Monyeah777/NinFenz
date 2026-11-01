#!/usr/bin/env bash
# 45 A4 · verify 版本标签多文件同步（vX.Y 换标；check 数/PASS 不变时使用）。
# 用法：scripts/bump_verify.sh v2.21 [--dry-run]
#
# 2026-10-13 修：本脚本曾把当前版本 token 写死成 `v2.22`——而 verify.sh 已是 v2.30，
# 于是它“跑成功但什么都没改”（实为静默失效）。现改为**从 verify.sh 版本头自动识别**，
# 换标再也不会因脚本落后而空转。
set -e
cd "$(dirname "$0")/.."
NEW="$1"
if [[ ! "$NEW" =~ ^v[0-9]+\.[0-9]+$ ]]; then
  echo "用法: scripts/bump_verify.sh vX.Y [--dry-run]" >&2; exit 2
fi
DRY="${2:-}"
if [ "$DRY" = "--dry-run" ]; then
  export DRY=1
  MODE=dry
else
  MODE=apply
fi
python - "$NEW" <<'PY'
import os
import re
import sys

new = sys.argv[1]
verify = open('verify.sh', encoding='utf-8').read()
m = re.search(r'^# 版本 : (v\d+\.\d+)', verify, re.M)
if not m:
    sys.exit('verify.sh 缺版本头 `# 版本 : vX.Y`——无法定位当前 token')
old = m.group(1)
if old == new:
    print('no-op：当前已是 %s' % new)
    sys.exit(0)
dry = os.environ.get('DRY') == '1'
total = 0


def _write(p, text):
    if not dry:
        open(p, 'w', encoding='utf-8', newline='\n').write(text)


# verify.sh：全量替换当前版本 token（历史注解不以 vX.Y 出现）。
n = verify.count(old)
if n:
    total += n
    _write('verify.sh', verify.replace(old, new))
print(('dry ' if dry else '') + 'updated verify.sh (from %s) x%d' % (old, n))

# README：只替换当前基线行（跳过发布历史块 `> **v...**`），避免时间线错乱。
d = open('README.md', encoding='utf-8').read()
lines = d.splitlines(keepends=True)
out = []
n = 0
for ln in lines:
    if ln.startswith('> **v') and old in ln:
        out.append(ln)
    elif not ln.startswith('> **v') and old in ln:
        n += 1
        out.append(ln.replace(old, new))
    else:
        out.append(ln)
if n:
    total += n
    _write('README.md', ''.join(out))
print(('dry ' if dry else '') + 'updated README.md x%d' % n)
if total == 0:
    print('no %s label found（verify.sh 与 README 都未出现当前 token）' % old)
PY
if [ "$MODE" = "dry" ]; then
  echo "dry-run done（未写盘）"
else
  python scripts/nf.py release --fast
  echo "bump done: verify label -> ${NEW}（改动已写入，确认后提交）"
fi
