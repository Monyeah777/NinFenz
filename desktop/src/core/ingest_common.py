"""入库前端共用件（GitHub / Gitee 两通道的公共件）—— 2026-10-14 core 抽取。

**为什么成件**：两个入库前端此前各写一份公共逻辑（凭据脱敏、git 出口、frontmatter 压平、
文件名解析、模板残留净化、闸门/词表读取），并且 `gitee_ingest.py` 反向 `from library_ingest
import …`——一个机器人把另一个机器人当库用。同一份「模板残留」词表因此有两个写者，实测漂移：
GitHub 侧内嵌 8 条、Gitee 侧 10 条（多出两句模板占位句），于是 GitHub 侧会把自己空壳检测
明确要拒的占位句当**有效值**（标题/形态被写成模板提示语）。

纪律：只读纯函数 + 明确的 IO 出口（git）；不依赖具体通道（GitHub / Gitee 各自保留 API 面）。
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from glob import glob

from core import json_doc

#: 投稿闸门声明（机读真相）：mode ∈ open / author_only / paused；白名单随声明走。
#: 2026-09-20 收口（作者裁决）：闸门此前是代码常量 `ALLOWED = {'monyeah777'}`——改闸门不留痕、
#: 读者从 INDEX 看不出「谁能投」。现改为读声明件，并由 verify check34 断言「声明 ⇄ 须知措辞 ⇄
#: 两个机器人引用」三方一致（外部实证：某精选清单因投稿腐化整仓停投，闸门须可见可控）。
INTAKE_REL = 'library/intake.json'

#: 投稿正文长度上限（字符）。零门槛通道下正文会**原样**成为仓库文件并进 CI 检出，
#: 不设上限则任何人一次投稿即可把仓库撑大 / 拖长每次检出与门禁（可用性面）。
#: 现役最长条目 ~61k 字符，256k 给了 4 倍余量。
MAX_BODY_CHARS = 256 * 1024

B36 = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'

MAX_SEG = 16

SEG_RE = re.compile(r'^[A-Za-z0-9]{1,%d}$' % MAX_SEG)

#: frontmatter 标量里的控制字符（含 CR/LF）——**结构注入口**，见 flatten_fm_value。
_FM_CTRL = re.compile(r"[\x00-\x1f\x7f]+")

def flatten_fm_value(v):
    """frontmatter 标量压平：控制字符（含 CR/LF）→ 空格，再 strip。**两个前端共用的唯一实现**。

    为什么（2026-10-10 审计 Y2，P1）：投稿的 Issue 标题等外部字段是不可信输入，而条目
    frontmatter 是**按行读**的（core.library_entries.parse_frontmatter）——值里一个换行就能
    **注入新键**（示例：标题尾部放 \nstatus: retired ⇒ 条目生命周期被投稿人改写）。
    换行是结构分隔，不是内容：一律压平，不让它进结构。
    """
    return _FM_CTRL.sub(" ", str(v or "")).strip()

def fm_scalar_ok(v) -> bool:
    """压平后的值能否被 parse_frontmatter **原样读回**（不能则该投稿拒收，失败关闭）。

    该解析器对一行 key: value 只有三条分支：空 → 空表；方括号成对 → 列表；其余 → 剥首尾引号。
    故「往返安全」= 非空 + 首尾无空白 + 不以方括号成对 + 首尾无引号。
    **刻意不做转义**：那个极简解析器不认转义，硬塞 JSON 引号会把反斜杠留在字段里（改坏内容）。
    """
    v = str(v or "")
    if not v or v != v.strip():
        return False
    if v[0] == "[" and v[-1] == "]":
        return False
    return v.strip("'\"") == v

def fm_fields_ok(fields) -> str:
    """→ 第一个不能安全写入 frontmatter 的字段名（全安全则空串）。调用方据此拒收并回评。"""
    for key, val in fields:
        if not fm_scalar_ok(flatten_fm_value(val)):
            return key
    return ""

def load_gate(channel='github'):
    """读投稿闸门声明 → (mode, allowlist)。**fail-closed**：声明缺失 / 不可解析 / mode 非法，
    一律按 `paused` 处理（宁可暂停接收并让作者看到修复指引，也不静默放行）。

    mode 取值：`open`（零门槛直投）/ `author_only`（白名单）/ `paused`（暂停接收）。
    """
    try:
        with open(INTAKE_REL, encoding='utf-8') as f:
            data = json_doc.loads(f.read(), dict, what=INTAKE_REL)
        ch = (data.get('channels') or {}).get(channel) or {}
        mode = str(ch.get('mode') or '')
        allow = {str(x).strip().lower() for x in (ch.get('allowlist') or []) if str(x).strip()}
        if mode in ('open', 'author_only', 'paused'):
            return mode, allow
        print(f'⚠ 闸门声明 mode 非法：{mode!r}（修复指引：{INTAKE_REL} 的 channels.{channel}.mode '
              f'取值 open / author_only / paused）')
    except Exception as exc:
        print(f'⚠ 闸门声明不可读（{exc}）：修复指引：确认 {INTAKE_REL} 存在且为合法 JSON')
    return 'paused', set()

#: 疑似明文密钥形状（与 `.github/workflows/ci-verify.yml` 的扫描正则同源，另加 GitLab 令牌形态）
_SECRET_SHAPES = re.compile(
    r'ghp_[0-9A-Za-z]{36}|github_pat_[0-9A-Za-z_]{22,}|gho_[0-9A-Za-z]{36}|'
    r'glpat-[0-9A-Za-z_\-]{20,}|sk-[0-9A-Za-z]{20,}|AIza[0-9A-Za-z_\-]{35}|'
    r'AKIA[0-9A-Z]{16}|xox[baprs]-[0-9A-Za-z\-]{10,}')

def secret_shape_hit(text):
    """→ 命中的**脱敏**形状前缀（无命中返回空串）。

    只回显前 4 字符：拒绝说明要进公开 Issue 评论，不能把疑似密钥再抄一遍
    （否则等于用「提示」把密钥第二次分发出去）。
    """
    m = _SECRET_SHAPES.search(str(text or ''))
    return (m.group(0)[:4] + '…') if m else ''

def load_rating_vocab():
    """分级词表真源 = `library/intake.json` 的 `rating.vocabulary`（缺失即用默认词表）。

    机器人为什么也要读它：声明件写明「缺 `rating` 即 FAIL」，入库产物若不带该字段，
    每次成功入库都会把 verify check34（rating_gate）判红 = 自伤门禁。
    词表按**声明**走，不在代码里另写死一份。
    """
    try:
        with open(INTAKE_REL, encoding='utf-8') as f:
            data = json_doc.loads(f.read(), dict, what=INTAKE_REL)
        vocab = [str(v) for v in ((data.get('rating') or {}).get('vocabulary') or [])]
        if vocab:
            return vocab
    except Exception as exc:
        print(f'⚠ 分级词表不可读（{exc}）：修复指引：确认 {INTAKE_REL} 存在且 rating.vocabulary 合法')
    return ['general', 'teen', 'mature', 'unrated']

def fail(msg):
    print('❌ ' + msg)
    sys.exit(1)

def to_b36(n):
    """十进制 → 36进制字符串（n>=1，无前导零）。"""
    if n <= 0:
        n = 1
    s = ''
    while n > 0:
        n, r = divmod(n, 36)
        s = B36[r] + s
    return s

def from_b36(s):
    return int(s, 36)

def parse_nfname(name):
    """解析文件名（去 .md）→ (档位段|None, 自定义段|None, 序号str)；不合法返回 None。"""
    m = re.match(r'^NF-([A-Za-z0-9]+)-([A-Za-z0-9]+)-([0-9A-Z]+)$', name)
    if m:
        return (m.group(1), m.group(2), m.group(3))
    m = re.match(r'^NF-([0-9A-Z]+)$', name)
    if m:
        return (None, None, m.group(1))
    return None

def scan_existing():
    """扫描 library/NF-*.md → {前缀key: [序号int,...]}。key：完整形=(档位,自定义)，默认形=None。"""
    groups = {}
    prefixes = set()
    for f in glob('library/NF-*.md'):
        base = os.path.basename(f)[:-3]
        p = parse_nfname(base)
        if p is None:
            print(f'⚠ 跳过无法解析的现有文件: {base}')
            continue
        seg1, seg2, seq = p
        key = (seg1, seg2) if seg1 is not None else None
        groups.setdefault(key, []).append(from_b36(seq))
        prefixes.add((seg1.lower(), seg2.lower()) if seg1 is not None else None)
    return groups, prefixes

def injection_probe(text):
    """→ 命中清单（单源 = `core.trust_boundary.detect`）；核心不可用时返回 `None` 并如实记。

    为什么在入库前扫（**咨询面，不拒收**）：投稿正文会**原样发布**到公开仓并被消费方读取，
    06 §12 要求「疑似内嵌指令一律忽略并**记档**」——机器人是这条纪律在**公开边界**上的执行点。
    内容仍是数据：本扫描只记档（回评告知 + 日志），不拦截——正当的「注入防御」题材投稿
    不该被误杀。
    """
    try:
        sys.path.insert(0, os.path.join(os.getcwd(), 'desktop', 'src'))
        from core import trust_boundary as tb  # noqa: PLC0415
        return tb.detect(text)
    except Exception:                                    # noqa: BLE001 - 扫描不可用时如实降级
        return None

#: 模板残留说明短语（**单一真源**）：投稿人 = 蠢用户，机器兜底。
#: 2026-10-14 取并集——此前 GitHub 侧 8 条 / Gitee 侧 10 条，两句模板占位句只在 Gitee 侧生效。
FILLER_PATS = ('如 校园情感世界', '作品名，同时', '可选，一句话', '可选，编号',
               '编号规则', '从这里开始粘贴', '两者都填', '填了就必须',
               '把 AI 产物全文整篇粘贴到这条线下面', '此占位行务必删掉')


def clean_val(v):
    """模板残留净化：说明文字/括号示例一律视为未填。"""
    v = flatten_fm_value(v)              # 先压平（含 CR/LF）——frontmatter 行读，换行即注入
    if not v:
        return ''
    if v.startswith(('（', '(')):
        return ''
    for pat in FILLER_PATS:
        if v.startswith(pat):
            return ''
    return v


def redact(text, secret=''):
    """令牌脱敏：任何要进日志 / 异常 / 回评的字符串都先过这里（CWE-532）。"""
    out = str(text)
    if secret:
        out = out.replace(secret, '***')
    return out


def run_git(args, secret='', dry=False):
    """git 调用统一出口：日志与异常一律脱敏（令牌绝不进 CI 日志——CWE-532）。

    输出由本函数捕获后经 redact 回吐：git 在鉴权/网络失败时会把**含凭证的 URL**
    打进 stderr，直接继承 stdout/stderr 等于把令牌写进 Actions 日志。
    """
    print('$ git', *(redact(a, secret) for a in args))
    if dry:
        return
    proc = subprocess.run(['git', *args], capture_output=True, text=True,
                          encoding='utf-8', errors='replace')
    for stream in (proc.stdout, proc.stderr):
        if stream:
            print(redact(stream, secret), end='')
    if proc.returncode != 0:
        raise RuntimeError('git 退出码 %d：%s（修复指引：检查远端可达性与令牌权限）'
                           % (proc.returncode, redact(' '.join(args), secret)))
