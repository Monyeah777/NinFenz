"""核心文面去叙述（域中立）判据——R8 的独立实现件。

为什么独立成件：`core/purity_scan.py` 有冻结的规模/复杂度上限（protocol/code_metrics_baseline.json），
把词表与逐行扫描塞进去会顶破上限。按仓库既有先例（判据独立成件、由父判据调用），本件承载词表与扫描，
`purity_scan` 只保留一段调用，归入 check27 的同一个门（**不新增 check 序号**）。

判据：`03_管线库/**/*.md` 与 `04_模块库/**/*.md` 正文不得出现叙述/题材专属词。
机制通用词（交互 / 裁剪 / 回合 / 存档 / 视角域 / 事件池 / 构建 …）已是核心词汇，**不在表内**。
前缀豁免：非 / 跨 / 反 / 去（如「非叙事领域」）；显式放行：DOMAIN_ALLOW。
"""
import glob
import os
import re

#: 叙述/题材专属词表（去叙述·域中立的判定面）。
DOMAIN_TERMS = ("叙事", "叙述", "故事", "剧情", "主角", "玩家", "NPC", "台词", "情感", "情绪",
                "好感", "冲动", "遗憾", "幽灵", "战斗", "魔法", "校园", "西幻", "文风", "白描",
                "恋爱", "悬疑", "恐怖", "情书", "情敌", "角色卡", "人物卡", "三冲动")

#: 否定/跨越语境前缀豁免（如「非叙事领域」「跨领域」）。
DOMAIN_OK_PREFIX = ("非", "跨", "反", "去")

#: 显式放行：键 = (仓库相对路径, 词)，须附理由（空集 = 无一例外）。
DOMAIN_ALLOW: set = set()

#: 被扫面（与 purity_scan.OWN_PATTERNS 的同名两项保持一致，缓存面才不陈旧）。
FACE = ("03_管线库/**/*.md", "04_模块库/**/*.md")

_DOMAIN_PAT = re.compile("|".join(DOMAIN_TERMS))


def scan(root: str = ".") -> tuple:
    """扫核心文面，返回 (issues, stats)。逐行判定，命中即给修复指引。"""
    from core import conformance_scan as csc          # 共享语料读（同一次只读调用内同件只读一遍）
    issues = []
    files = 0
    for rel_pat in FACE:
        for f in sorted(glob.glob(os.path.join(root, rel_pat), recursive=True)):
            rel = os.path.relpath(f, root).replace("\\", "/")
            try:
                text = csc.read_text_cached(f)
            except OSError:  # 尽力而为：跳过不可读项
                continue
            files += 1
            for i, line in enumerate(text.splitlines(), 1):
                for m in _DOMAIN_PAT.finditer(line):
                    term = m.group(0)
                    if line[max(0, m.start() - 1):m.start()] in DOMAIN_OK_PREFIX:
                        continue
                    if (rel, term) in DOMAIN_ALLOW:
                        continue
                    issues.append("%s:%d 核心文面含叙述/题材词「%s」：%s（修复指引：改域中立表述；"
                                  "确属必要改在 core/domain_neutral.DOMAIN_ALLOW 登记理由）"
                                  % (rel, i, term, line.strip()[:80]))
    return issues, {"files": files, "hits": len(issues)}
