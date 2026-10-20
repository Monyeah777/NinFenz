#!/usr/bin/env python
"""把内容线版本从 v2.x 重排为 0.x 两位数序列（2026-10-20 作者裁决）。

判定规则（作者原话）：小更新**合并**、稍有突破 **+0.01**、创新突破 **+0.1**。
故历史 tag 里纯修复/打点的五个被并入相邻版本，其余按功能增量重编号。

本脚本只做**可复算**的两件事：
1. 依据映射表重打本地 tag（同提交、换编号、换功能摘要注释）；
2. 把 CHANGELOG / VERSION-MATRIX / 三语 README / CONTRIBUTING 里的版本号换成新号。
不含网络动作——推送由调用方决定。
"""
from __future__ import annotations

import contextlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 旧 tag -> 新编号；None = 该版并入前一版（小更新合并，不单独发版）
MAPPING: dict[str, str | None] = {
    "v0.1.0": "v0.01",
    "v0.2.0": "v0.11",
    "v0.3.0": None,
    "v0.3.1": None,
    "v0.3.2": None,
    "v0.3.3": None,
    "v0.4.0": "v0.12",
    "v0.5.0": None,
    "v0.7.0": "v0.22",
    "v0.8.0": "v0.23",
    "v0.9.0": "v0.24",
    "v1.0.0": "v0.34",
    "v1.1.0": "v0.35",
    "v2.0.0": "v0.45",
    "v2.1.0": "v0.46",
    "v2.2.0": "v0.47",
    "v2.3.0": "v0.48",
    "v2.4.0": "v0.49",
    "v2.5.0": "v0.59",
    "v2.6.0": "v0.60",
    "v2.7.0": "v0.70",
    "v2.8.0": "v0.71",
    "v2.9.0": "v0.72",
    "v2.10.0": "v0.82",
    "v2.11.0": "v0.92",
    "v2.12.0": "v0.93",
}

# 新编号的功能摘要（tag 注释；人话，不写内部字段）
SUMMARY: dict[str, str] = {
    "v0.01": "首个可分发版本：Release 产物按平台加后缀，macOS 可打包",
    "v0.11": "桌面形态成型：五屏 UI + controller；此后打包链修正与该阶段小修一并计入本版",
    "v0.12": "新增领域包（校园情感 / 西幻生存）：模板从单一走向成组",
    "v0.22": "协议对外开放：自定义协议 + 模块组合；新增 --check 只读差异模式",
    "v0.23": "自定义模块组合可复用",
    "v0.24": "移动端接入：Android 同步门禁 + UI 启动安全静态断言",
    "v0.34": "全平台正式版：C0–C8 九项一致性齐备",
    "v0.35": "通用核心基础包（T4-1）落地",
    "v0.45": "导出层：出口适配器（上游生成器可被外部消费）",
    "v0.46": "技术文档域包 + 市场命令面（nf market）",
    "v0.47": "外部吸收首波：可验证性为主的校验器体系",
    "v0.48": "规则出口打通 + 变体装配（模板选择与重叠仲裁）",
    "v0.49": "导出物规范体检升至 spec_version 3",
    "v0.59": ".NET 引擎接入：多语言执行线成型",
    "v0.60": "端壳接线：应用主窗口 / 市场目录 / 规则渲染出口接进 MCP",
    "v0.70": "首个无壳基础层版本：供应链台账 + 管线脚手架",
    "v0.71": "波 C 首个内容版本：内容装配面打通",
    "v0.72": "需求装配三入口（nf assemble：自定义流 / 收敛漏斗 / --save）+ 执行演练扩展",
    "v0.82": "质量纵深 45 项：演练 / 判级 / 文档卫生 / 覆盖度成套",
    "v0.92": "世界状态模型（确定性抽象状态 + 槽位）+ 吸收七面 + 图书馆机器面 + 治理面",
    "v0.93": "知识层检索 + 终端线（nf shell）+ 顶尖对标补齐（发布编排/变更日志/i18n/接入面）+ 数字资产契约层",
}


def sh(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=ROOT, text=True, capture_output=True, check=check)


def renumber_tags() -> None:
    """删旧 tag、按映射建新 tag（同提交）。"""
    for old, new in MAPPING.items():
        commit = sh("git", "rev-parse", f"{old}^{{commit}}", check=False)
        if commit.returncode != 0:
            print(f"  跳过 {old}（不存在）")
            continue
        sha = commit.stdout.strip()
        sh("git", "tag", "-d", old, check=False)
        if new is None:
            print(f"  - {old} 并入前一版（不单独发版）")
            continue
        sh("git", "tag", "-a", new, "-m", f"{new} {SUMMARY[new]}", sha)
        print(f"  ✓ {old} -> {new}")


DOC_FILES = ["CHANGELOG.md", "docs/meta/VERSION-MATRIX.md", "README.md", "README.en.md", "README.ja.md"]


def _token_map() -> list[tuple[str, str]]:
    """版本 token 替换表：长号先换，避免前缀互吃。"""
    pairs = [(old.lstrip("v"), new.lstrip("v")) for old, new in MAPPING.items() if new]
    # 并入的旧号统一指向其所属新版本（0.3.x / 0.5.0 → 0.11）
    for old in ("0.3.0", "0.3.1", "0.3.2", "0.3.3", "0.5.0"):
        pairs.append((old, "0.11"))
    return sorted(pairs, key=lambda x: -len(x[0]))


def renumber_docs() -> None:
    pairs = _token_map()
    for rel in DOC_FILES:
        p = ROOT / rel
        text = p.read_text(encoding="utf-8")
        for old, new in pairs:
            text = re.sub(rf"(?<![\d.]){re.escape(old)}(?![\d.])", new, text)
        p.write_text(text, encoding="utf-8", newline="\n")
        print(f"  ✓ {rel}")


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        with contextlib.suppress(AttributeError, OSError):
            stream.reconfigure(encoding="utf-8")
    print("== 1/2 重打 tag ==")
    renumber_tags()
    print("== 2/2 文档版本号 ==")
    renumber_docs()
    return 0


if __name__ == "__main__":
    sys.exit(main())
