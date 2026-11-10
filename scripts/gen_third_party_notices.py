#!/usr/bin/env python
"""生成 THIRD-PARTY-NOTICES.md：把 CI/开发工具链依赖的真实许可证汇总成一份声明。

为什么需要：本仓**运行时零第三方依赖**（stdlib only），但门禁工具链依赖一批第三方包。
专业仓库对「分发/再分发所含第三方组件」必须有可见的许可声明；CI 与合规审计也需要一份
机器可追溯的清单。许可证信息**取自 PyPI 官方 JSON API**（不手写、不猜）。

纪律（2026-11-10 收紧）：
  * **失败即不写盘**：任一依赖查询失败 → 打印失败清单、返回 2、保持旧文件不动；
    旧版把「（查询失败：URLError）」写进文档，等于把降级当结果（已实测发生过）。
  * 版本真源 = .github/requirements-*.txt 的 pin（不读已安装环境，避免「本机恰好装了」的假象）。
  * 许可解析顺序 = license_expression（PEP 639）→ license → OSI classifier；
    未知写法**原样保留**（宁可显示上游原文，也不编造 SPDX 标识）。
  * 机读对照面 = results/ccos/sbom.json（nf sbom --write），两边组件集由判据对账。

用法：
    python scripts/gen_third_party_notices.py --write
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_PYPI_RESPONSE_BYTES = 8 * 1024 * 1024
sys.path.insert(0, str(ROOT / "desktop" / "src"))

OUT = ROOT / "THIRD-PARTY-NOTICES.md"
PIN_FILES = sorted((ROOT / ".github").glob("requirements-*.txt"))

#: 上游写法 → SPDX 标识（只收无歧义的映射；歧义写法原样保留，不猜条款版本）
LICENSE_MAP = {
    "MIT": "MIT",
    "MIT License": "MIT",
    "Apache-2.0": "Apache-2.0",
    "Apache 2.0": "Apache-2.0",
    "Apache License": "Apache-2.0",
    "Apache Software License": "Apache-2.0",
    "BSD-2-Clause": "BSD-2-Clause",
    "BSD-3-Clause": "BSD-3-Clause",
    "MPL-2.0": "MPL-2.0",
    "Mozilla Public License 2.0 (MPL 2.0)": "MPL-2.0",
    "Python Software Foundation License": "PSF-2.0",
    "PSFL": "PSF-2.0",
    "PSF-2.0": "PSF-2.0",
    "ISC": "ISC",
}
#: 非宽松许可提示词；命中即进「注意项」自动点名
COPYLEFT_HINTS = ("LGPL", "GPL", "AGPL", "MPL", "EPL", "CDDL")
SPDX_EXPR = re.compile(r"^[A-Za-z0-9.+\-() ]+(?:\s(?:AND|OR|WITH)\s[A-Za-z0-9.+\-() ]+)*$")


def lock_digest() -> str:
    """锁文件内容摘要：notices 与「当时的 pin」绑定，pin 一变判据即红（新鲜度）。"""
    h = hashlib.sha256()
    for f in PIN_FILES:
        h.update(f.name.encode("utf-8"))
        h.update(f.read_bytes())
    return h.hexdigest()[:16]


def pins() -> list[tuple[str, str]]:
    """读 pip-compile 产物里的 name==version（忽略带 hashes 的续行；跨文件去重）。"""
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
    from core import json_doc  # 读 JSON 走仓库唯一读点（json_shape_contracts）

    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "pypi.org":
        raise ValueError(
            f"拒绝非 PyPI 官方地址：{url}（修复指引：只允许 https 的 pypi.org —— 本脚本仅取"
            "官方元数据，不访问任意站点）"
        )
    with urllib.request.urlopen(url, timeout=25) as resp:  # nosec B310
        raw = resp.read(MAX_PYPI_RESPONSE_BYTES + 1)
        if len(raw) > MAX_PYPI_RESPONSE_BYTES:
            raise ValueError(f"PyPI 响应超过上限 {MAX_PYPI_RESPONSE_BYTES} 字节"
                             "（修复指引：检查上游是否返回异常大页）")
        return json_doc.loads(raw.decode("utf-8"), dict, what="PyPI " + name)


def _squash(text: str) -> str:
    return " ".join((text or "").split())


def resolve_license(meta: dict) -> str:
    """许可解析：license_expression → license → OSI classifier（无歧义才映射 SPDX）。"""
    expr = _squash(meta.get("license_expression") or "")
    if expr and SPDX_EXPR.match(expr):
        return expr
    lic = _squash(meta.get("license") or "")
    if lic in LICENSE_MAP:
        return LICENSE_MAP[lic]
    # PyPI 的 license 字段可能是整篇许可全文（实测 pip-api 即如此）——短且像 SPDX 才原样收
    if lic and len(lic) <= 80 and SPDX_EXPR.match(lic):
        return lic
    for c in meta.get("classifiers") or []:
        m = re.match(r"License :: OSI Approved :: (.+)$", c)
        if m:
            name = _squash(m.group(1))
            return LICENSE_MAP.get(name, f"{name}（上游 classifier 原文）")
    if lic:
        return "见项目主页（PyPI license 字段为全文，classifier 未声明）"
    raise ValueError(
        "PyPI 元数据未声明任何许可（拒绝猜）"
        "（修复指引：先核对 PyPI 项目页的 license / license_expression / classifiers；"
        "确实缺失时在 notices 判据里加人工核对条目，不要在本脚本里手填）"
    )


def home_of(meta: dict) -> str:
    """主页/源码地址：project_urls → home_page → project_url。"""
    urls = meta.get("project_urls") or {}
    for key in ("Source", "Homepage", "Repository", "Source Code", "Code"):
        if isinstance(urls, dict) and urls.get(key):
            return str(urls[key])
    return str(meta.get("home_page") or meta.get("project_url") or "")


def _pin_stdio() -> None:
    """入口打印中文 ⇒ 钉 UTF-8 stdio（Windows 默认 GBK 会 UnicodeEncodeError）。"""
    for stream in (sys.stdout, sys.stderr):
        with contextlib.suppress(AttributeError, OSError):
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]


def render(rows: list[tuple[str, str, str, str]], digest: str = "") -> str:
    """渲染文档（纯函数，便于测试复用）。"""
    copyleft = sorted({lic for _n, _v, lic, _h in rows
                       if any(h in lic.upper() for h in COPYLEFT_HINTS)})
    unknown = sorted({lic for _n, _v, lic, _h in rows
                      if lic.endswith("（上游 classifier 原文）")})
    lines = [
        "# 第三方组件声明（THIRD-PARTY NOTICES）",
        "",
        "本文件由 `scripts/gen_third_party_notices.py` 从 **PyPI 官方元数据**生成，**请勿手改**；",
        "版本真源 = `.github/requirements-*.txt` 的 pin（跨文件去重），"
        "机读对照面 = `results/ccos/sbom.json`，"
        "新鲜度锚 = 锁文件摘要 `" + ("sha256:" + digest if digest else "（未计算）") + "`。",
        "生成失败时脚本**不写盘**（fail-closed），不会把「查询失败」写进本文件。",
        "",
        "## 归属声明（Attribution）",
        "",
        "本仓自身代码与文档版权归 2026 Monyeah777（MIT，见 `LICENSE`）。",
        "本文件所列第三方组件版权归各自作者，按各组件许可分发；本仓**未修改**上游源码",
        "（Local Modifications: None）——仅以固定版本安装/调用，不 vendored 进产品。",
        "",
        "## 范围说明（分发边界）",
        "",
        "- **运行时**：NinFenz 核心与 npm 包**不依赖任何第三方运行库**"
        "（Python stdlib + Node 标准库）；",
        "  可证：`pyproject.toml` 的 `[project].dependencies` 为空、"
        "`packaging/npm/package.json` 无 `dependencies`。",
        "- **本文所列**：仓库**门禁与开发工具链**依赖"
        "（用于跑 `verify.sh` 与 CI 检查，不随产品分发）。",
        "- 各组件按其自身许可证分发；本仓代码/文档为 MIT（见 `LICENSE` / `REUSE.toml`）。",
        "- 投稿/社区内容的版权与再分发条款见 `LICENSES/LicenseRef-Community-Submission.txt`"
        " 与 `REUSE.toml`。",
        "",
        "## 清单",
        "",
        "| 组件 | 版本（pin） | 许可证 | 主页 |",
        "|---|---|---|---|",
    ]
    for name, version, lic, home in rows:
        home_cell = f"[链接]({home})" if home else "—"
        lines.append(f"| `{name}` | {version} | **{lic}** | {home_cell} |")
    lines += [
        "",
        "## 许可注意项（自动识别）",
        "",
    ]
    dual = sorted({lic for _n, _v, lic, _h in rows if " OR " in lic.upper()})
    if dual:
        lines.append("双许可选择：以下表达式含 OR，本仓使用时应择一履行（当前按最宽松可行项）：")
        lines.append("")
        for lic in dual:
            members = ", ".join(f"`{n}`" for n, _v, x, _h in rows if x == lic)
            lines.append(f"- **{lic}**：{members}")
        lines.append("")
        lines.append("PySide6 系列取 **LGPL-3.0-only**，仅门禁/测试链使用，"
                     "不随 npm 包或 CLI 分发。")
        lines.append("")
    if copyleft:
        lines.append("以下组件带**非宽松许可**条款（仅门禁/测试链，不随产品分发）：")
        lines.append("")
        for lic in copyleft:
            members = ", ".join(f"`{n}`" for n, _v, x, _h in rows if x == lic)
            lines.append(f"- **{lic}**：{members}")
        lines.append("")
        lines.append("再分发其二进制须遵守对应条款（如 LGPL 要求提供源码获取方式与替换自由）。")
    else:
        lines.append("未发现非宽松许可组件。")
    if unknown:
        lines.append("")
        lines.append("以下行只能取到上游 classifier 原文（PyPI 未给 SPDX 标识），"
                     "需人工核对上游 LICENSE：")
        lines.append("")
        for lic in unknown:
            members = ", ".join(f"`{n}`" for n, _v, x, _h in rows if x == lic)
            lines.append(f"- **{lic}**：{members}")
        lines.append("")
    lines += [
        "",
        "## 更新方式",
        "",
        "```bash",
        "python scripts/gen_third_party_notices.py --write   # 依赖版本变化后重跑并提交",
        "```",
    ]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    _pin_stdio()
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="写入 THIRD-PARTY-NOTICES.md")
    args = ap.parse_args(argv)

    rows: list[tuple[str, str, str, str]] = []
    errors: list[tuple[str, str]] = []
    for name, version in pins():
        try:
            meta = pypi(name)["info"]
            rows.append((name, version, resolve_license(meta), home_of(meta)))
        except Exception as exc:  # 失败即整份不写：降级结果不许落盘
            errors.append((name, f"{type(exc).__name__}: {exc}"))
    if errors:
        print(f"✗ {len(errors)} 个依赖的元数据查询失败，未写入 {OUT.name}（fail-closed）：",
              file=sys.stderr)
        for name, msg in errors:
            print(f"  - {name}: {msg}", file=sys.stderr)
        print("修复指引：网络恢复后重跑；不要手改本文件，也不要把失败占位提交。", file=sys.stderr)
        return 2

    text = render(rows, lock_digest())
    if args.write:
        from core import atomic_write  # 落盘走仓库唯一写点（裸写判据）

        atomic_write.write_text(OUT, text)
        print(f"OK 已写入 {OUT.name}（{len(rows)} 个组件）")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
