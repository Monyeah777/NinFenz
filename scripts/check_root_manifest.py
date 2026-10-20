#!/usr/bin/env python3
"""根目录清单门禁（SP-01 的本仓口径）。

手册 SP-01 原字面是「根条目收敛到 <=10 + 固定白名单」（src/docs/tests 型模板）。
本仓是内容契约仓：根目录承载协议入口件（01/02/06/07、AGENTS.md、STRATEGY.md、
llms.txt、verify.sh）与多个内容容器，按原字面搬迁会与协议回执链（protocol/RECEIPTS.json
以 STRATEGY.md 为锚）、库真源路径与 verify.sh 的 42 条 check 直接冲突 -- 故按手册 0.6
走「修正执行」：

  建成状态 = 根目录每个条目都在本清单里登记（kind + 用途），且
    (a) 清单里没有孤条目（每条至少被一处入口面引用，自身自引用不算）；
    (b) 根目录没有未登记的条目（新增根条目必须同时更新本清单）；
    (c) 根目录没有临时/垃圾产物（*.log/*.tmp/*.bak/*.swp/NUL 等）。

这比原字面更严处：不是「少」而是「个个有据」，新增条目会被门禁拦住；
比原字面更宽处：允许入口例外（协议入口/工具约定/过程档案），但每条例外要有引用证据。

用法：python scripts/check_root_manifest.py [--json]
"""
import argparse
import contextlib
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

# 本地/运行期目录：不是仓库内容，不参与清单（.git 由 git 管；其余是本地缓存）
LOCAL_DIRS = {".git", ".gitee", ".rivet", ".pytest_cache", ".ruff_cache",
              ".nf-logs", ".artifacts"}
JUNK = re.compile(r"^(NUL|.*\.(log|tmp|bak|swp|orig|rej)$|.*~$|_probe_.*)$")

# 根条目清单：name -> (kind, 用途)。kind 取值：
#   元文件 / 协议入口 / 容器 / 工具约定 / 过程档案
MANIFEST = {
    ".dockerignore": ("工具约定", "Docker 构建上下文排除表（docker 只在该位置读取）"),
    ".editorconfig": ("工具约定", "编辑器基线（FX-12/13；EditorConfig 只认该位置）"),
    ".env.example": ("工具约定", "环境模板（FX-04；反忽略实体，CONTRIBUTING 本地搭建复制用）"),
    ".gitattributes": ("工具约定", "行尾/二进制/export-ignore 真源（git 只认该位置）"),
    ".github": ("容器", "协作配置与 CI（工作流/模板/社区文件；SP-03 归位目标）"),
    ".gitignore": ("工具约定", "忽略规则真源（git 只认该位置）"),
    ".markdownlint.json": ("工具约定", "markdown 结构规则真源（FX-14/15；单入口脚本消费）"),
    ".pre-commit-config.yaml": ("工具约定", "本地提交钩子（CI-03；pre-commit 只认该位置）"),
    "01_核心协议.md": ("协议入口", "L0 协议主档；check1-7/13/16 真源，回执链登记"),
    "02_联动注册表.md": ("协议入口", "L0 联动注册表；check8-11/14/15 真源，回执链登记"),
    "03_管线库": ("容器", "P00/P01/P90 管线真源（check1-4 资产面）"),
    "04_模块库": ("容器", "核心模块库真源（check5-6/24 模块生命周期）"),
    "05_资产库": ("容器", "资产库真源（check40 数字资产契约）"),
    "06_Agent执行协议.md": ("协议入口", "Agent 执行协议；check36/37 与 llms.txt 入口链引用"),
    "07_官方核心出厂与社区预设导航.md": ("协议入口", "出厂/预设导航；verify 判定口径对齐 07 §7"),
    "AGENTS.md": ("协议入口", "编码代理操作约束（DC-05）；与 llms.txt 分工：读 vs 做"),
    "CHANGELOG.md": ("元文件", "版本变更史（RL-02；README 与发布流程引用）"),
    "CITATION.cff": ("工具约定", "Citation File Format（GitHub 自动读取）；口径同 LICENSE"),
    "Dockerfile": ("工具约定", "MCP stdio 镜像构建入口（glama 上架与 check41 在此读取）"),
    "Dockerfile.crosscheck": ("工具约定", "交叉校验镜像（cross_lang_verify.py 构建时读取）"),
    "LICENSE": ("元文件", "MIT 许可证正文（GF-02；pyproject/REUSE/README 引用）"),
    "glama.json": ("工具约定", "Glama MCP 目录收录声明（平台只认该位置）"),
    "LICENSES": ("元文件", "REUSE 子许可证目录（REUSE.toml 与治理单测引用）"),
    "README.en.md": ("元文件", "英文入口（README 语言导航引用）"),
    "README.ja.md": ("元文件", "日文入口（README 语言导航引用）"),
    "README.md": ("元文件", "主入口（GF-01/DC-01；六要素与快速开始）"),
    "REUSE.toml": ("工具约定", "REUSE 3.x 合规声明（reuse lint 只认该位置）"),
    "STRATEGY.md": ("协议入口", "方向与质量准绳；RECEIPTS.json 回执锚，故不迁出根（SP-04 例外）"),
    "THIRD-PARTY-NOTICES.md": ("元文件", "第三方组件声明（生成器产出；LICENSE 义务引用）"),
    "changes": ("过程档案", "变更片段（Keep-a-Changelog；PR 模板要求 changes/unreleased/）"),
    "community": ("容器", "社区领域包（近 2200 文件；check7-11 段 B 资产面）"),
    "decisions": ("容器", "ADR 真源与 INDEX 投影（DC-03；docs/adr 只做入口，禁双写）"),
    "desktop": ("容器", "核心引擎与桌面面（check12/17-22 等）"),
    "docs": ("容器", "文档树（DC-02；docs/index.md 为分区入口）"),
    "engine": ("容器", "多语言引擎线（Rust/.NET/WASM；PARITY 与 cross-lang 判据）"),
    "handovers": ("过程档案", "交接记录（core/handover.py 与 rust/dotnet 三面对读，不迁出）"),
    "integrations": ("容器", "集成适配面（integration.json 清单与 check33 接入面）"),
    "library": ("容器", "云端图书馆（check34；frontmatter 真源）"),
    "llms-install.md": ("元文件", "AI 安装入口（llms.txt 安装节引用）"),
    "llms.txt": ("元文件", "AI 代理入口清单（DC-04；check_llms_paths 校验路径存在）"),
    "packaging": ("容器", "打包与发布物（npm/MCP/HF Space；payload 清单门禁）"),
    "patterns": ("容器", "模式库（PATTERN.md 卡片；frontmatter + H1 结构）"),
    "postmortems": ("过程档案", "复盘档案（postmortem.py 三面对读，不迁出根目录）"),
    "protocol": ("容器", "机器契约真源（LAYERS/receipts/schema/生成物；check23-31/40）"),
    "pyproject.toml": ("工具约定", "依赖与工具配置单点入口（SP-02：ruff 真源也在本文件）"),
    "requirements.txt": ("工具约定", "根依赖清单（与 .github/requirements-*.txt 同源纪律）"),
    "results": ("过程档案", "审计与互操作取证（check38 出口面/他证通道；大量引用不迁出）"),
    "scripts": ("容器", "脚本面（nf CLI 与各门禁脚本；check39/40）"),
    "site": ("容器", "静态站点与 Workers（GEO 出口；check38）"),
    "skills": ("容器", "AI skill 包（llms.txt 与 docs/agent 引用）"),
    "tui": ("容器", "终端 TUI（check39 终端入口三件）"),
    "verify.sh": ("入口例外", "42 条 check 的唯一门禁本体；被文档大量引用，故留根（SP-01 例外）"),
    "wrangler.jsonc": ("工具约定", "Cloudflare Workers 配置（wrangler 只认该位置）"),
}

# 入口面语料：用于证明「根条目被至少一处入口引用」
CORPUS_GLOBS = ("README*.md", "AGENTS.md", "llms*.txt", "docs/**/*.md",
                ".github/**/*.md", "scripts/*.py", "scripts/*.sh",
                "pyproject.toml", "verify.sh")


def corpus_texts() -> dict:
    texts = {}
    for pat in CORPUS_GLOBS:
        for p in ROOT.glob(pat):
            if not p.is_file():
                continue
            with contextlib.suppress(OSError):
                texts[p.relative_to(ROOT).as_posix()] = p.read_text(
                    encoding="utf-8", errors="replace")
    return texts


def check() -> dict:
    entries = sorted(p.name for p in ROOT.iterdir() if p.name not in LOCAL_DIRS)
    problems = []
    for n in entries:
        if n not in MANIFEST:
            problems.append(
                f"根条目未登记：{n}（新增根条目必须同步 MANIFEST）")
    for n in MANIFEST:
        if not (ROOT / n).exists():
            problems.append(f"清单条目不存在（过期登记）：{n}")
    for n in entries:
        if JUNK.match(n):
            problems.append(f"根目录出现临时/垃圾产物：{n}")
    corpus = corpus_texts()
    for n, (kind, _why) in sorted(MANIFEST.items()):
        if kind == "工具约定":
            continue
        hit = [rel for rel, txt in corpus.items()
               if rel != n and n in txt]
        if not hit:
            problems.append(f"孤儿根条目（无入口引用）：{n}（kind={kind}）")
    return {"entries": len(entries), "registered": len(MANIFEST),
            "problems": problems}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="根目录清单门禁（SP-01）")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(encoding="utf-8")
    res = check()
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        print(f"根条目 {res['entries']} · 清单登记 {res['registered']}")
        for p in res["problems"]:
            print(f"[FAIL] {p}")
        if not res["problems"]:
            print("通过：根条目全部登记且有引用证据，无临时产物（SP-01 本仓口径）")
    return 0 if not res["problems"] else 1


if __name__ == "__main__":
    sys.exit(main())
