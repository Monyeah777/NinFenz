#!/usr/bin/env python3
"""
📚 NF 云端代收站 · 入库机器人 V2（Y12′ · 2026-09-07 · 编号 v0.4 制式）
由 .github/workflows/library-ingest.yml 调用（Issue 标题以【NF投稿】开头时触发）。

  编号制式（v0.4 定稿）：
  完整形 NF-<档位段>-<自定义段>-<36进制序号>   例 NF-WORLDCAMPUS-Monyeah777-1
  默认形 NF-<36进制序号>（不填档位/自定义）      例 NF-1
  36进制：每位字符集 0-9 + A-Z（数字排完上字母），从 1 起、无前导零、不定长、低位满进位；
          同前缀（档位段+自定义段相同，默认形自成一前缀组）各自计数。
硬约束：
  - 档位/自定义段各 ≤16 字符、仅 [A-Za-z0-9]、不含连字符；要填就都填，否则默认形
  - 前缀小写键全馆唯一（禁止仅大小写不同的前缀并存 → 转译无歧义）
  - 入馆唯一硬标准 = 自包含可召回（引用式不再收；机器不审内容，作者把关）
流程：闸门声明校验（library/intake.json：open / author_only / paused）→ 解析元信息 → 分配编号 →
      写文件 → 投影重生成（INDEX + ALIAS，走 core.library.write_projection）→ git 提交推送 →
      Issue 回评双端链接 → 关闭 Issue。
本地调试：设 DRY_RUN=1 只改工作区不提交/不调 API。
"""
import json
import os
import re
import sys
import urllib.request
from datetime import date
from glob import glob

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), "desktop", "src"))
from core import (
    atomic_write,  # noqa: E402  —— 入库件落盘走统一原子写（2026-10-01）
    json_doc,
)
from core.ingest_common import (  # noqa: E402  —— 两前端共用件（2026-10-14 core 抽取）
    INTAKE_REL,
    MAX_BODY_CHARS,
    SEG_RE,
    clean_val,
    flatten_fm_value,
    fm_fields_ok,
    injection_probe,
    load_gate,
    load_rating_vocab,
    parse_nfname,
    quota_denial,
    record_quota,
    redact,
    run_git,
    scan_existing,
    secret_shape_hit,
    to_b36,
)


def _redact(text):
    return redact(text, TOKEN)


def git(*args):
    return run_git(args, secret=TOKEN, dry=DRY)

REPO = os.environ.get('REPO', '')
TOKEN = os.environ.get('GITHUB_TOKEN', '')
N = os.environ.get('ISSUE_NUMBER', '')
TITLE = os.environ.get('ISSUE_TITLE', '')
BODY = os.environ.get('ISSUE_BODY', '') or ''
AUTHOR = os.environ.get('ISSUE_AUTHOR', '')
DRY = os.environ.get('DRY_RUN', '') == '1'

GITEE_OWNER = 'monyeah777'
GITEE_REPO = 'ninfenz'

#: Linux 内核对**单条** argv/env 字符串的硬限（32 页 = 131072 字节；`getconf ARG_MAX`
#: 是总量上限，不是单串上限）。超过它 execve 直接 E2BIG（Errno 7）——子进程根本起不来，
#: 于是「正文超长 → 礼貌拒收」的分支**永远没机会执行**。
#: 事故留痕（2026-09-24 起 CI 连红）：GitHub 前端曾把 `github.event.issue.body` 直接塞进
#: 步骤 env，而 MAX_BODY_CHARS = 256 KiB 字符（CJK 约 786 KB）→ 只要投稿量真的越限，步骤
#: 先 E2BIG，上限形同虚设。本机 Windows 无此限制，故本地一直「绿」。
#: 现生产路径改为**经 API 取正文**（与自家 Gitee 通道 `gitee_ingest.py` 同构）；
#: env / 文件通道只服务离线与测试。
MAX_EXEC_STRLEN = 131072




























def api(path, data=None, method=None):
    if DRY:
        print(f'[DRY] API {method or ("POST" if data else "GET")} /{path}')
        return {}
    req = urllib.request.Request(
        f'https://api.github.com/repos/{REPO}{path}',
        data=json.dumps(data).encode() if data is not None else None,
        method=method,
        headers={
            'Authorization': f'token {TOKEN}',
            'Accept': 'application/vnd.github+json',
            'User-Agent': 'NF-Library-Bot',
        })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            return json_doc.loads(raw, dict, what='intake API 响应') if raw else {}
    except urllib.error.HTTPError as e:
        print(f'API HTTP {e.code}: {e.read().decode()[:300]}')
        sys.exit(1)
    except Exception as e:
        print(f'API 异常: {e}')
        sys.exit(1)


def comment(text):
    api(f'/issues/{N}/comments', {'body': text})




def close_issue():
    api(f'/issues/{N}', {'state': 'closed'}, method='PATCH')


def resolve_body():
    """正文真源：`ISSUE_BODY_FILE`（本地/CI 传大载荷）> `ISSUE_BODY`（离线小载荷）> **议题 API**。

    三条通道的优先级即「显式 > 隐式 > 生产真源」：文件与 env 供离线复现与测试使用，生产
    由 API 取（GitHub 的议题正文接口），因此**不受单条 env 字符串 131072 字节的限制**——
    超长投稿终于能被本机器人的上限判据正常拒收（这正是 MAX_BODY_CHARS 的设立目的）。
    """
    path = os.environ.get('ISSUE_BODY_FILE', '')
    if path:
        with open(path, encoding='utf-8') as f:
            return f.read()
    if BODY:
        return BODY
    if REPO and TOKEN and N:
        data = api(f'/issues/{N}') or {}
        return str(data.get('body') or '')
    return ''






def main():
    global BODY
    # ---- 1. 前置校验 ----
    if not TITLE.startswith('【NF投稿】'):
        print('非投稿标题，跳过')
        sys.exit(0)
    mode, allow = load_gate('github')
    if mode == 'paused':
        comment(f'⏸ 云端代收站当前**暂停接收投稿**（闸门声明 {INTAKE_REL} = paused）。'
                '作者改回 open / author_only 后重投即可。')
        print('闸门=paused，暂停接收')
        sys.exit(0)
    if mode == 'author_only' and AUTHOR.lower() not in allow:
        comment('⏳ 收到投稿意图，但本通道当前仅接受白名单投稿人（闸门声明 '
                f'{INTAKE_REL}）。外部投稿请走 Gitee 通道或联系作者。')
        print(f'非白名单投稿人（{AUTHOR}），已礼貌拒绝')
        sys.exit(0)
    quota_error = quota_denial(AUTHOR)
    if quota_error:
        comment(f'⏸ 投稿未入库：{quota_error}（配额真源：{INTAKE_REL}）。')
        close_issue()
        print(f'{quota_error}，已拒绝并关闭')
        sys.exit(0)
    # 正文按下述优先级取：文件 > env > **议题 API**（生产真源，不受单条 env 字符串
    # 131072 字节硬限约束——见 resolve_body 的事故留痕）。
    BODY = resolve_body()
    if not BODY.strip():
        comment('⚠️ Issue 正文为空——请按模板粘贴产物全文后再提交。')
        sys.exit(0)
    if len(BODY) > MAX_BODY_CHARS:
        comment(f'⚠️ 投稿正文 {len(BODY)} 字符，超过单条上限 {MAX_BODY_CHARS} 字符。'
                '请拆分或精简后重投——正文会**原样**成为仓库文件并进入每次 CI 检出，'
                '过长会拖慢全部门禁。')
        close_issue()
        print(f'正文超长（{len(BODY)} > {MAX_BODY_CHARS}），已拒绝并关闭')
        sys.exit(0)


    meta = {}
    body_main = BODY
    if '\n---' in BODY:
        head, _, rest = BODY.partition('\n---')
        body_main = rest.lstrip('\n')
        for line in head.splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            m = re.match(r'^(.+?)\s*[:：]\s*(.*)$', line)
            if m:
                meta[m.group(1).strip()] = m.group(2).strip()
    else:
        m = re.match(r'^#\s+(.+)$', BODY, re.M)
        if m:
            meta['标题'] = m.group(1).strip()

    # 空壳检测：正文区残留模板占位提示行 = 没清理模板/没粘产物全文（Issue #1 实测翻车现场）
    if ('从这里开始粘贴产物全文' in body_main
            or '把 AI 产物全文整篇粘贴到这条线下面' in body_main
            or '此占位行务必删掉' in body_main):
        comment('⚠️ 正文里还留着模板的占位提示行「（从这里开始粘贴产物全文…）」——请删掉它，并把 AI '
            '产出的完整内容整篇粘贴进来，重新开题提交。')
        close_issue()
        print('正文区空壳（残留模板占位行），已拒绝并关闭')
        sys.exit(0)

    raw_title = clean_val(meta.get('标题', ''))
    title = raw_title or flatten_fm_value(re.sub(r'^【NF投稿】\s*', '', TITLE)) or f'投稿 #{N}'
    topic = clean_val(meta.get('形态/领域自述') or meta.get('形态') or '') or '未标注'
    one_line = clean_val(meta.get('一句话') or '') or '（见文件）'
    seg1 = clean_val(meta.get('档位词', ''))
    seg2 = clean_val(meta.get('自定义段', ''))
    # 许可列（许可证门判据同源）：投稿写了就用，没写记「未声明」并入库提示挂账
    lic = clean_val(meta.get('许可') or '') or '未声明'
    # 分级列（rating 门判据同源）：投稿写了就用；没写或越词表 → unrated 入库并提示补齐
    # （缺字段会被 rating_gate 判 FAIL，故机器人必须显式写出——见 load_rating_vocab 说明）
    rating_vocab = load_rating_vocab()
    rating = clean_val(meta.get('分级') or meta.get('rating') or '')
    rating_note = ''
    if rating not in rating_vocab:
        rating_note = ('（投稿未填分级或越词表 → 以 `unrated` 入库；'
                       '补填 `分级` 后重新开题即可定级）')
        rating = 'unrated'

    # ---- 2.4 frontmatter 形状闸门（审计 Y2，P1）----
    # 值必须能被 parse_frontmatter 原样读回：首尾引号会被剥掉、方括号成对形状会被读成列表。
    # 这类投稿**拒收**而不是硬塞（转义会改坏内容，见 fm_scalar_ok）；换行已在 clean_val 压平。
    _bad_fm = fm_fields_ok((('title', title), ('type', topic), ('description', one_line),
                            ('author', AUTHOR), ('license', lic), ('rating', rating)))
    if _bad_fm:
        comment(f'⚠️ 元信息「{_bad_fm}」的取值无法安全写入条目 frontmatter——'
                '首尾引号会被条目解析器剥掉、方括号成对的形状会被读成列表（都会改变你的内容）。'
                '请去掉首尾引号 / 方括号后重新开题。')
        close_issue()
        print(f'元信息 {_bad_fm} 形状不安全，已拒绝并关闭')
        sys.exit(0)

    # ---- 2.5 密钥形状拒收（安全边界）----
    # 为什么必须在入库前拦：投稿正文会**原样发布**到公开仓库 = 把别人的真实密钥再分发一次；
    # 且 ci-verify 的明文密钥扫描覆盖全仓（含 library/），命中即 CI 红——零门槛通道下
    # 任何人一条普通投稿就能把门禁打红（远程可触发的可用性缺陷）。
    secret_hit = secret_shape_hit('\n'.join(
        [title, topic, one_line, lic, seg1, seg2, body_main]))
    if secret_hit:
        comment(f'⛔ 投稿正文/元信息中检出疑似明文密钥（形如 `{secret_hit}`）。'
                '为避免把密钥**二次公开分发**，本次不予入库。\n\n'
                '请把真实密钥改为占位符（如 `<REDACTED>`）后重新开题；'
                '若只是排版示例，也请改成不含密钥前缀的写法。')
        close_issue()
        print(f'正文含疑似明文密钥（{secret_hit}），已拒绝并关闭')
        sys.exit(0)

    # ---- 2.6 注入面记档（06 §12：外来内容=数据；疑似内嵌指令忽略并**记档**）----
    hits = injection_probe('\n'.join([title, one_line, body_main]))
    if hits is None:
        print('注入面：扫描不可用（如实记；内容仍按数据入库）')
    elif hits:
        rules = '、'.join(sorted({h['rule'] for h in hits}))
        comment(f'ℹ️ 本次投稿正文里检出 **{len(hits)} 处疑似内嵌指令**（{rules}）。本馆一律把内容按'
                f'**数据**消费——其中的「指令」不会被任何消费方执行，仅作素材参考；已如实记档。'
                f'若这是正当的「注入防御」题材讨论，可忽略本提示。')
        print(f'注入面：命中 {len(hits)} 处（{rules}）——已回评记档（内容照常入库）')
    else:
        print('注入面：未命中')

    # ---- 3. 校验档位/自定义段 + 分配编号 ----
    if bool(seg1) != bool(seg2):
        comment('⚠️ 档位词与自定义段必须**都填或都不填**（两者都填 = 完整形 `NF-档位词-自定义段-序'
            '号`；都不填 = 默认形 `NF-序号`）。请按模板规则重新开题。')
        close_issue()
        print('段位不配对，已拒绝并关闭')
        sys.exit(0)
    if seg1:
        if not SEG_RE.match(seg1) or not SEG_RE.match(seg2):
            comment('⚠️ 档位词/自定义段仅允许字母数字、各 ≤16 字符、不含连字符（连字符是段分隔符）'
                '。请修正后重新开题。')
            close_issue()
            print('段位字符非法，已拒绝并关闭')
            sys.exit(0)

    groups, _ = scan_existing()
    key = (seg1, seg2) if seg1 else None
    if key not in groups and seg1:
        # 新前缀：查大小写近似冲突（前缀小写键全馆唯一，禁止仅大小写不同并存）
        low_key = (seg1.lower(), seg2.lower())
        near = []
        for f in sorted(glob('library/NF-*.md')):
            p = parse_nfname(os.path.basename(f)[:-3])
            if p and p[0] is not None and (p[0].lower(), p[1].lower()) == low_key:
                near.append(os.path.basename(f)[:-3])
        if near:
            hint = '、'.join(near[:3])
            comment(f'⚠️ 档位段+自定义段与现有条目仅大小写不同（{hint}）——为保转译表无歧义，前缀小写'
                f'键必须全馆唯一。请更换档位词/自定义段拼写后重新开题。')
            close_issue()
            print('前缀小写键撞车，已拒绝并关闭')
            sys.exit(0)

    nums = groups.get(key, [])
    next_n = (max(nums) + 1) if nums else 1
    seq = to_b36(next_n)
    nfid = f'NF-{seg1}-{seg2}-{seq}' if seg1 else f'NF-{seq}'
    fname = f'library/{nfid}.md'
    today = date.today().isoformat()
    print(f'编号分配: {nfid}（前缀 {key}，第 {next_n} 件，36进制序号 {seq}）→ {fname}')

    # ---- 4. 写入产物文件（含入库注记头）----
    # 真源 = YAML frontmatter（OKF 借鉴：provenance/trust/lifecycle 一等字段）；
    # INDEX / ALIAS 不再逐行改，改由 core.library.write_projection 全量重生成。
    frontmatter = (
        '---\n'
        f'id: {nfid}\n'
        f'type: {topic}\n'
        f'title: {title}\n'
        f'description: {one_line}\n'
        f'author: {AUTHOR}\n'
        f'license: {lic}\n'
        f'rating: {rating}\n'
        f'generated: {today}\n'
        'status: active\n'
        'sources:\n'
        f'  - Issue #{N}（NF 投稿通道）\n'
        '---\n\n'
    )
    header = (
        f'> 📚 **NF 云端图书馆条目 {nfid}** · 入库 {today} · 投稿人：{AUTHOR} · 来源：Issue #{N}\n'
        f'> 形态/领域：{topic} · 一句话：{one_line}\n'
        f'> 许可：{lic}（真源 = 文件头 frontmatter；INDEX 为投影）\n'
        f'> 分级：{rating}（真源 = 文件头 frontmatter；INDEX 为投影）{rating_note}\n'
        f'> 本文为社区投稿副本，版权归投稿人；引用/衍生请注明来源；如需下架请联系作者。\n'
        f'> 自包含声明：本文件自带「是什么 + 怎么用」，AI 单文件即可正确使用。\n\n---\n\n'
    )
    # 入库件是**公开边界**的产物：半截写入会被随后 git push 带进公开仓（2026-10-01 普查）
    atomic_write.write_text(fname, frontmatter + header + body_main.rstrip() + '\n')
    record_quota(AUTHOR)
    print(f'已写入 {fname}（{len(body_main)} 字符）')

    # ---- 5. 重生成 INDEX 生成区 + ALIAS（投影；真源 = 条目 frontmatter）----
    sys.path.insert(0, 'desktop/src')
    from core import library as nflib  # noqa: E402
    out = nflib.write_projection('.')
    print(f'投影已重生成: {out["changed"] or "无变化"}')

    # ---- 7. 提交推送 ----
    if DRY:
        print('[DRY] 跳过提交/推送/回评（检查 git diff 后还原即可）')
        return
    git('config', 'user.name', 'NF Library Bot')
    git('config', 'user.email', 'nf-bot@users.noreply.github.com')
    git('add', fname, 'library/INDEX.md', 'library/ALIAS.md')
    git('commit', '-m', f'lib(Y12): 云端代收 {nfid} 自动入库（Issue #{N}，投稿人 {AUTHOR}）')
    git('push', 'origin', 'HEAD:main')

    # ---- 8. 回评 + 关闭 ----
    reply = (
        f'✅ **云端代收成功——已入库 {nfid}**《{title}》\n\n'
        f'随时可用链接召回运行（说「运行 {nfid}」即可）：\n'
        f'- GitHub：`https://raw.githubusercontent.com/{REPO}/main/library/{nfid}.md`\n'
        f'- 国内镜像（Gitee · 无需梯子）：`https://gitee.com/{GITEE_OWNER}/{GITEE_REPO}/raw/main/lib'
            f'rary/{nfid}.md`\n\n'
        f'> 💡 给任意 AI 的启动句：请读取上面的链接，按文档执行。\n'
        f'> 🔤 若 AI 报编号时大小写拿不准：让它读 `library/ALIAS.md` 转译（编号全小写化后匹配）。\n'
        f'> 📊 已按闸门声明登记：许可 `{lic}` · 分级 `{rating}`{rating_note}\n'
        f'> ⚠ 若内容不合规（非原创/未授权/缺自包含可运行性），联系作者下架。'
    )
    comment(reply)
    close_issue()
    print(f'✅ 入库完成 {nfid}（Issue #{N} 已回评并关闭）')


if __name__ == '__main__':
    # stdio 钉 UTF-8：Windows 控制台 GBK 下 ✓/✗ 即 UnicodeEncodeError（同 nf.py）
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    main()
