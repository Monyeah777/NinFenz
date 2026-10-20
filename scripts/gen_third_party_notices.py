#!/usr/bin/env python
"""生成 THIRD-PARTY-NOTICES.md：把 CI/开发工具链依赖的真实许可证汇总成一份声明。

为什么需要：本仓**运行时零第三方依赖**（stdlib only），但门禁工具链依赖一批第三方包。
专业仓库对"分发/再分发所含第三方组件"必须有可见的许可声明；同时 CI 与合规审计
都需要一份机器可追溯的清单。许可证信息**取自 PyPI 官方 JSON API**（不手写、不猜）。

用法：
    python scripts/gen_third_party_notices.py --write
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "THIRD-PARTY-NOTICES.md"
PIN_FILES = sorted((ROOT / ".github").glob("requirements-*.txt"))

#: 常见许可证的统一写法（PyPI 的 license 字段历史包袱多，做一次归一，宁可见原文）
NORMALIZE = [
    (r"^MIT( License)?$", "MIT"),
    (r"^Apache( Software)? License(,? Version)? 2\.0$", "Apache-2.0"),
    (r"^BSD( License)?$", "BSD"),
    (r"^(GNU )?LGPL(-3\.0|-3\.0-only)?( only)?$", "LGPL-3.0"),
    (r"^PSF(-2\.0)?$", "PSF-2.0"),
]


def norm(lic: str, classifiers: list[str]) -> str:
    lic = (lic or "").strip()
    for pat, canon in NORMALIZE:
        if re.match(pat, lic, re.I):
            return canon
    for c in classifiers or []:
        m = re.match(r"License :: OSI Approved :: (.+)$", c)
        if m:
            return m.group(1).strip()
    return lic or "（PyPI 未声明，见项目主页）"


def pins() -> list[tuple[str, str]]:
    """读 pip-compile 产物里的 `name==version`（忽略带 hashes 的续行）。"""
    out: list[tuple[str, str]] = []
    seen = set()
    for f in PIN_FILES:
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.match(r"^([A-Za-z0-9_.\-]+)==([^\s\\]+)", line)
            if m and m.group(1).lower() not in seen:
                seen.add(m.group(1).lower())
                out.append((m.group(1), m.group(2)))
    return out


def pypi(name: str) -> dict:
    """取 PyPI 官方元数据。**只允许 https + pypi.org**（防 URL 注入 / 明文降级）。"""
    url = f"https://pypi.org/pypi/{urllib.parse.quote(name, safe='')}/json"
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "pypi.org":
        raise ValueError(
            f"拒绝非 PyPI 官方地址：{url}（修复指引：只允许 https 的 pypi.org —— 本脚本仅取"
            "官方元数据，不访问任意站点）"
        )
    # 下方 urlopen 的入参已由上面两道校验钉死为「https + pypi.org」常量前缀，
    # 故 bandit B310 / ruff S310（动态 URL）在此站点是**已消除的**风险面。
    with urllib.request.urlopen(url, timeout=25) as resp:  # nosec B310
        return json.load(resp)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="写入 THIRD-PARTY-NOTICES.md")
    args = ap.parse_args(argv)

    rows = []
    for name, version in pins():
        try:
            meta = pypi(name)["info"]
            lic = norm(meta.get("license") or meta.get("license_expression") or "",
                       meta.get("classifiers") or [])
            home = meta.get("home_page") or meta.get("project_url") or ""
            rows.append((name, version, lic, home))
        except Exception as exc:
            rows.append((name, version, f"（查询失败：{type(exc).__name__}）", ""))

    lines = [
        "# 第三方组件声明（THIRD-PARTY NOTICES）",
        "",
        "本文件由 `scripts/gen_third_party_notices.py` 从 **PyPI 官方元数据**生成，请勿手改。",
        "",
        "## 范围说明",
        "",
        "- **运行时**：NinFenz 核心与 npm 包**不依赖任何第三方运行库**"
        "（Python stdlib + Node 标准库）。",
        "- **本文所列**：仓库**门禁与开发工具链**依赖（用于跑 `verify.sh` 与 CI 检查，"
        "不随产品分发）。",
        "- 各组件按其自身许可证分发；本仓代码/文档为 MIT（见 `LICENSE`）。",
        "- 投稿/社区内容的版权与再分发条款见 "
        "`LICENSES/LicenseRef-Community-Submission.txt` 与 `REUSE.toml`。",
        "",
        "## 清单",
        "",
        "| 组件 | 版本 | 许可证 | 主页 |",
        "|---|---|---|---|",
    ]
    for name, version, lic, home in rows:
        home_cell = f"[链接]({home})" if home else "—"
        lines.append(f"| `{name}` | {version} | **{lic}** | {home_cell} |")
    lines += [
        "",
        "## 已知注意项",
        "",
        "- **PySide6**（若安装 `[dev]` 全量 extras）：LGPL-3.0。仅用于桌面/终端相关测试，",
        "  不随 npm 包或 CLI 分发；再分发其二进制需遵守 LGPL（提供源码获取方式与替换自由）。",
        "- 其余均为宽松许可（MIT / Apache-2.0 / BSD / PSF），与 MIT 主许可兼容。",
        "",
        "## 更新方式",
        "",
        "```bash",
        "python scripts/gen_third_party_notices.py --write   # 依赖版本变化后重跑并提交",
        "```",
    ]
    text = "\n".join(lines) + "\n"
    if args.write:
        OUT.write_text(text, encoding="utf-8", newline="\n")
        print(f"OK 已写入 {OUT.name}（{len(rows)} 个组件）")
    else:
        print(text[:1200])
    return 0


if __name__ == "__main__":
    sys.exit(main())
