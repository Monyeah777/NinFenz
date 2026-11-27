"""为 `decisions.scan` 生成分支级判据（真源 16 个 issue 分支）。

用法：python engine/rust/tools/gen_decisions_branches.py
"""
import json
import pathlib
import re
import shutil
import sys

from _rustlit import rs  # noqa: E402
from _gen_target import ensure_mount, gen_text, norm, write_gen_block  # noqa: E402

ROOT = pathlib.Path('.').resolve()
sys.path.insert(0, str(ROOT / 'desktop' / 'src'))
from core import decisions as dec  # noqa: E402

FIX = ROOT / 'engine' / 'rust' / 'target' / 'test-fixtures' / 'decisions-branches'
if FIX.exists():
    shutil.rmtree(FIX)
(FIX / 'decisions').mkdir(parents=True)
(FIX / 'protocol').mkdir(parents=True)
(FIX / 'docs').mkdir(parents=True)

BODY = "## 背景\nb\n\n## 决策\nd\n\n## 后果\nc\n"


def adr(name, fm_lines, body=BODY):
    return "---\n" + "\n".join(fm_lines) + "\n---\n" + body


DOCS = {
    # ① 缺 frontmatter id（文件名合法但无 id）
    'ADR-0001-missing-id.md': adr('x', ["status: proposed", "date: 2026-01-01",
                                        "deciders: a", "evidence: []"]),
    # ② id 不合法
    'ADR-0002-bad-id.md': adr('x', ["id: ADR-abc", "status: proposed", "date: 2026-01-01",
                                    "deciders: a", "evidence: []"]),
    # ③ id 与文件名不一致
    'ADR-0003-mismatch.md': adr('x', ["id: ADR-9999", "status: proposed", "date: 2026-01-01",
                                      "deciders: a", "evidence: []"]),
    # ④ 编号重复（与 0004 撞）
    'ADR-0004-dupA.md': adr('x', ["id: ADR-0004", "status: proposed", "date: 2026-01-01",
                                  "deciders: a", "evidence: []"]),
    'ADR-0004-dupB.md': adr('x', ["id: ADR-0004", "status: proposed", "date: 2026-01-01",
                                  "deciders: a", "evidence: []"]),
    # ⑤⑥⑦⑧⑨⑩⑪ 必填缺 / status 越词表 / 日期非法 / 缺段落 / 空证据 / 指向不存在 check / 无法解析
    'ADR-0005-kitchen.md': adr('x', [
        "id: ADR-0005", "status: 越词表", "date: 2026/01/01",
        "evidence:",
        "  - ",
        "  - check99",
        "  - no/such/pattern",
    ], body="## 背景\n只有背景\n"),
    # ⑫ accepted 但未被回执锚定
    'ADR-0006-unanchored.md': adr('x', ["id: ADR-0006", "status: accepted", "date: 2026-01-01",
                                        "deciders: a", "evidence: []"]),
    # ⑬ superseded 但缺 superseded_by
    'ADR-0007-nosupby.md': adr('x', ["id: ADR-0007", "status: superseded", "date: 2026-01-01",
                                     "deciders: a", "evidence: []"]),
    # ⑭ superseded_by 指向不在册编号
    'ADR-0008-badsupby.md': adr('x', ["id: ADR-0008", "status: superseded", "date: 2026-01-01",
                                      "deciders: a", "evidence: []",
                                      "superseded_by: ADR-7777"]),
    # ⑮ 取代链成环：0009 ⇄ 0010
    'ADR-0009-cycleA.md': adr('x', ["id: ADR-0009", "status: superseded", "date: 2026-01-01",
                                    "deciders: a", "evidence: []", "superseded_by: ADR-0010"]),
    'ADR-0010-cycleB.md': adr('x', ["id: ADR-0010", "status: superseded", "date: 2026-01-01",
                                    "deciders: a", "evidence: []", "superseded_by: ADR-0009"]),
    # ⑯ supersedes 指向不在册编号
    'ADR-0011-badsupersedes.md': adr('x', [
        "id: ADR-0011", "status: accepted", "date: 2026-01-01", "deciders: a",
        "evidence:",
        "  - check1",
        "supersedes:",
        "  - ADR-8888",
    ]),
}
for name, body in DOCS.items():
    (FIX / 'decisions' / name).write_text(body, encoding='utf-8', newline='')

(FIX / 'verify.sh').write_text("#!/bin/bash\ncheck1(){\n  true\n}\n", encoding='utf-8', newline='')
# ADR-0011 已被回执锚定 → ⑤⑫ 不触发；ADR-0006 未锚定 → 触发
(FIX / 'protocol' / 'RECEIPTS.json').write_text(
    json.dumps({"schema": "nf-receipts/1",
                "entries": [{"id": "decisions/ADR-0011-badsupersedes.md"}]},
               ensure_ascii=False), encoding='utf-8', newline='')

issues, warns, stats = dec.scan(str(FIX))

print('# 真源：issues=%d warns=%d' % (len(issues), len(warns)))
for x in issues:
    print('#   ! %s' % x)
for x in warns:
    print('#   ~ %s' % x)
print('# stats = %s' % json.dumps(stats, ensure_ascii=False, sort_keys=True))


def rj(s):
    assert '"#' not in s
    return 'r#"%s"#' % s


FILES = {}
for rel in sorted(str(p.relative_to(FIX)).replace('\\', '/')
                  for p in FIX.rglob('*') if p.is_file()):
    FILES[rel] = (FIX / rel).read_text(encoding='utf-8')

TEMPLATE = r'''
    /// ===== 分支级差分判据（期望值由 `tools/gen_decisions_branches.py` 从真源生成）=====
    ///
    /// 真源在 `decisions.scan` 里有 **16 个 issue 分支**；真语料只踩到其中少数（如成环）。
    /// 本夹具逐分支踩：缺 id / id 不合法 / id 与文件名不一致 / 编号重复 / 缺必填 / status 越词表 /
    /// 日期非法 / 缺正文段落 / 证据空项 / 证据指向不存在 check / 证据无法解析 / accepted 未被回执锚定 /
    /// superseded 缺 superseded_by / superseded_by 指向不在册 / 取代链成环 / supersedes 指向不在册。
    const WANT_DEC_ISSUES: [&str; @@NI@@] = [
@@ISSUES@@
    ];

    fn build_decisions_fixture() -> std::path::PathBuf {
        let root = crate::testutil::fixture("decisions-branches");
        for (rel, body) in @@FILES@@ {
            let p = root.join(rel);
            if let Some(d) = p.parent() {
                std::fs::create_dir_all(d).unwrap();
            }
            std::fs::write(p, body).unwrap();
        }
        root
    }

    #[test]
    fn scan_matches_truth_source_branch_by_branch() {
        let root = build_decisions_fixture();
        let (issues, decisions, accepted, chains) = scan(&root);
        assert_eq!(issues, WANT_DEC_ISSUES, "逐条消息与次序都须与真源一致");
        assert_eq!((decisions, accepted, chains), (@@ND@@, @@NA@@, @@NC@@), "三项统计");
    }
'''

files_rust = "[\n" + "\n".join(
    '            (%s, %s),' % (rs(k), rj(v)) for k, v in sorted(FILES.items())
) + "\n        ]"

BEGIN = '    // >>> GENERATED by tools/gen_decisions_branches.py（勿手改；重跑生成器覆盖本段）\n'
END = '    // <<< GENERATED\n'
text = (TEMPLATE
        .replace('@@NI@@', str(len(issues)))
        .replace('@@ISSUES@@', "\n".join('        %s,' % json.dumps(x, ensure_ascii=False) for x in issues))
        .replace('@@FILES@@', files_rust)
        .replace('@@ND@@', str(stats['decisions']))
        .replace('@@NA@@', str(stats['accepted']))
        .replace('@@NC@@', str(stats['chains'])))
block = BEGIN + text + END

ensure_mount(ROOT, 'decisions')


def _block_summary(blk):
    """从盘块/重算块里读「期望条数 + 三项统计」，只用于漂移告警的差异摘要。"""
    n = re.search(r'const WANT_DEC_ISSUES: \[&str; (\d+)\]', blk)
    st = re.search(r'assert_eq!\(\(decisions, accepted, chains\), \(([^)]*)\)', blk)
    return (n.group(1) if n else '?', st.group(1) if st else '?')


# 漂移保护（2026-11-28）：真源 decisions.scan 目前**领先于** Rust 端口（ADR030 对
# 「evidence: []」误报空槽；ADR042–046 supersedes/superseded_by 互指规则、成环去重与
# evidence 文案改动未移植）。此时若照常重生成，会把「Rust 尚不满足的新期望」写进判据、
# 使 cargo test 全红（38→51 条 / stats (10,2,3)→(10,2,1)）。
# 口径（task-19/task-23）：测试内容不得改变 ⇒ 盘块 token 与重算结果不一致时**保留盘块**，
# 显式告警并 exit 0；等 Rust 端口同步后再重跑会自动写入。两轮重跑不写盘 ⇒ git status 无变化。
existing = gen_text(ROOT, 'decisions')
if BEGIN in existing:
    a = existing.index(BEGIN)
    b = existing.index(END, a) + len(END)
    old_block = existing[a:b]
    if norm(old_block) != norm(block):
        old_n, old_st = _block_summary(old_block)
        new_n, new_st = _block_summary(block)
        print('# !! 真源已漂移：decisions 期望值与盘块不一致，**保留盘块不写**'
              '（需另立任务把 Rust 端口同步到真源）')
        print('#    重算 issues=%s stats=(%s)；盘块 issues=%s stats=(%s)'
              % (new_n, new_st, old_n, old_st))
        print('#    差异要点：ADR030 对 evidence: [] 误报空槽 / ADR042–046 互指规则 /'
              ' 成环去重与 evidence 文案')
        print('# 已跳过 decisions 判据写入（盘块未变）')
        sys.exit(0)
write_gen_block(ROOT, 'decisions', BEGIN, END, block)
print('# 已写入 decisions 判据')
