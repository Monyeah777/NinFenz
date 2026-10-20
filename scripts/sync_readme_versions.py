#!/usr/bin/env python
"""把 README 的「版本块」改写成功能口径，并给三语 README 加统一切换栏与版本块。

为什么用脚本改而不是手改三份：三语必须**同源同步**，手改必然漂移（本仓既有教训）。
脚本幂等：重复跑不会重复插入。
"""
# ruff: noqa: E501
# 为何整文件豁免行长：本脚本的主体是**Markdown 正文常量**（表格行不可折断），
# 折行会改变渲染结果；代码部分本身很短。
from __future__ import annotations

import contextlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _pin_stdio() -> None:
    """入口打印中文 => 钉 UTF-8 stdio（Windows 默认 GBK 会炸）。"""
    for stream in (sys.stdout, sys.stderr):
        with contextlib.suppress(AttributeError, OSError):
            stream.reconfigure(encoding="utf-8")

SWITCH = {
    "zh": "语言 / Languages：**[中文](README.md)** · [English](README.en.md) · [日本語](README.ja.md)",
    "en": "语言 / Languages：[中文](README.md) · **[English](README.en.md)** · [日本語](README.ja.md)",
    "ja": "语言 / Languages：[中文](README.md) · [English](README.en.md) · **[日本語](README.ja.md)**",
}

VERSIONS = {
    "zh": """## 版本

现在安装就是 **`ninfenz` 1.0.4**（npm 与 GitHub Packages 同步发布），装上即可用：

```bash
npm i -g ninfenz@latest   # 装或升级
nf --version             # 看当前版本
nf stats                 # 看门禁与仓库状态
```

同一份代码里有三条版本线，各自独立升：

| 线 | 当前 | 这条线管什么 |
|---|---|---|
| **内容与协议** | **v2.12.0** | 文档模板、领域包、规范本身 —— 决定「能生成什么」 |
| **命令行工具** | **1.0.4** | `nf` 命令 / npm 包 / MCP 服务 —— 决定「怎么用」 |
| **质量门禁** | 见 `nf stats` | 仓库自检通过情况 —— 决定「有没有改坏」 |

最近三版内容线，按**加了什么功能**排（不是按编号堆）：

| 版本 | 时间 | 这一版加了什么 |
|---|---|---|
| v2.12.0 | 2026-10-05 | 知识层检索、终端形态、数字资产契约（资产可跨项目复用） |
| v2.11.0 | 2026-09-10 | 世界状态模型：确定性抽象状态 + 槽位（同一输入必得同一输出） |
| v2.10.0 | 2026-09-09 | 质量纵深 45 项 + 基础层 A 组收口 |

发版规则：内容线 `v2.x.y`（新增能力升次版本、纯修复升补丁），CLI 线 `1.0.x` 独立编号；
每次发版同步写 `CHANGELOG.md`，tag 只打在**带功能的那次提交**上。
""",
    "en": """## Versions

Install **`ninfenz` 1.0.4** today — published to both npm and GitHub Packages:

```bash
npm i -g ninfenz@latest   # install or upgrade
nf --version             # show current version
nf stats                 # show gate and repo status
```

Three independent version lines ship from the same repository:

| Line | Current | What it governs |
|---|---|---|
| **Content & protocol** | **v2.12.0** | Templates, domain packs, specs — *what* can be generated |
| **Command-line tool** | **1.0.4** | the `nf` command / npm package / MCP server — *how* you use it |
| **Quality gate** | see `nf stats` | self-check status — *whether* something broke |

Last three content releases, described by **what they add**:

| Version | Date | What this release adds |
|---|---|---|
| v2.12.0 | 2026-10-05 | knowledge-layer retrieval, terminal surface, digital-asset contracts (reusable across projects) |
| v2.11.0 | 2026-09-10 | world-state model: deterministic abstract state + slots (same input, same output) |
| v2.10.0 | 2026-09-09 | 45-point quality depth plus foundation layer A |

Release rules: content line uses `v2.x.y` (minor for new capability, patch for fixes); the CLI line
is versioned independently as `1.0.x`; every release updates `CHANGELOG.md`, and tags are placed
on the commit that **carries the feature**.
""",
    "ja": """## バージョン

**`ninfenz` 1.0.4** をそのまま導入できます（npm と GitHub Packages の同時公開）:

```bash
npm i -g ninfenz@latest   # 導入・更新
nf --version             # 現在のバージョン
nf stats                 # ゲートとリポジトリの状態
```

同じリポジトリから 3 本のバージョン系列を独立して出しています:

| 系列 | 現在 | 何を決めるか |
|---|---|---|
| **コンテンツ / プロトコル** | **v2.12.0** | テンプレート・ドメインパック・仕様 —「何を生成できるか」 |
| **コマンドラインツール** | **1.0.4** | `nf` コマンド / npm パッケージ / MCP サーバー —「どう使うか」 |
| **品質ゲート** | `nf stats` を参照 | 自己検査の状態 —「壊れていないか」 |

直近 3 つのコンテンツ版（番号ではなく**追加された機能**で）:

| バージョン | 日付 | この版で増えたもの |
|---|---|---|
| v2.12.0 | 2026-10-05 | 知識層の検索、ターミナル形態、デジタル資産契約（資産を横断再利用） |
| v2.11.0 | 2026-09-10 | 世界状態モデル：決定的な抽象状態＋スロット（同じ入力なら同じ出力） |
| v2.10.0 | 2026-09-09 | 品質纵深 45 項目＋基盤層 A |

リリース規則：コンテンツ系列は `v2.x.y`（機能追加は minor、修正は patch）、CLI 系列は
`1.0.x` で独立。リリースごとに `CHANGELOG.md` を更新し、タグは**機能を含むコミット**に打ちます。
""",
}


def patch(name: str, lang: str) -> None:
    p = ROOT / name
    text = p.read_text(encoding="utf-8")

    # 1) 切换栏：替换既有 nf:locales 行（或标题后插入）
    line = f"<!-- nf:locales --> {SWITCH[lang]}"
    if re.search(r"^<!-- nf:locales -->.*$", text, re.M):
        text = re.sub(r"^<!-- nf:locales -->.*$", line, text, count=1, flags=re.M)
    else:
        text = re.sub(r"^(# .*\n)", r"\1\n" + line + "\n", text, count=1, flags=re.M)

    # 2) 版本块：替换整节（到下一个二级标题或文件尾）
    block = VERSIONS[lang].strip() + "\n"
    pat = re.compile(r"^## (版本|Versions|バージョン)\n.*?(?=^## |\Z)", re.M | re.S)
    if pat.search(text):
        text = pat.sub(block + "\n", text, count=1)
    else:
        text = text.rstrip() + "\n\n" + block

    p.write_text(text, encoding="utf-8", newline="\n")
    print(f"✓ {name}: 切换栏 + 版本块已同步")


if __name__ == "__main__":
    _pin_stdio()
    patch("README.md", "zh")
    patch("README.en.md", "en")
    patch("README.ja.md", "ja")
