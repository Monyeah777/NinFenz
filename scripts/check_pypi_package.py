#!/usr/bin/env python3
"""Python 发行包（wheel）构建产物校验：元数据 / 必需件 / 注入面逐字节对账 / 禁入面。

T9.1 判据（全部离线、只读 wheel，不联网、不安装、不发布）：
A **必需件在场**：`ninfenz/scripts/nf.py`、`ninfenz/desktop/src/core/**`、`ninfenz/protocol/
  facts.json`、`ninfenz/protocol/schema/*.schema.json`（与仓库根逐件对应）。
B **入口可执行**：`.dist-info/entry_points.txt` 含 `console_scripts: nf = ninfenz._launcher:main`。
C **元数据自洽**：Name=ninfenz；Version == protocol/facts.json `release.cli_version`；Requires-
  Python == pyproject `requires-python`；License 表达式含 `AGPL-3.0-only` 与
  `LicenseRef-Commercial` 且**不含 MIT**（当前许可不是 MIT；历史 MIT 只对 ≤1.0.5 成立）；
  wheel 文件名版本 == 元数据版本。
D **注入面逐字节对账**：wheel 内 `ninfenz/` 下的注入副本 == 仓库根原件（nf.py / core/** /
  schema/*.json / facts.json），且文件集合完全一致（多一件/少一件都报）——防止「bundle 的是
  旧树」这种构建期漂移。
E **禁入面**：不得含 `.git` / `.worktrees` / `__pycache__` / `.pytest_cache` / `.nf-cache` /
  `node_modules` / `desktop/tests` / `*.pyc`。
F **自证**：zip 可解析、无重复成员、非空。

用法：
  python scripts/check_pypi_package.py                 # 取 dist/ 下最新 wheel
  python scripts/check_pypi_package.py dist/x.whl --json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tomllib
import zipfile
from email.parser import BytesParser
from typing import Any, Dict, Iterable, List, Optional, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FACTS_REL = "protocol/facts.json"
PYPROJECT_REL = "pyproject.toml"
STATIC_PKG_FILES = {"ninfenz/__init__.py", "ninfenz/_launcher.py", "ninfenz/__main__.py"}
PAYLOAD_FILES = ("scripts/nf.py", FACTS_REL)
PAYLOAD_TREES = ("desktop/src/core", "protocol/schema")
FORBIDDEN = ("/.git/", "/.worktrees/", "/__pycache__/", "/.pytest_cache/", "/.nf-cache/",
             "/node_modules/", "/desktop/tests/", "/.rivet/")
FORBIDDEN_SUFFIX = (".pyc", ".pyo")
ENTRY = "nf = ninfenz._launcher:main"
MAX_REPORT = 20


def _h(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_facts(root: str) -> Dict[str, Any]:
    with open(os.path.join(root, FACTS_REL), encoding="utf-8") as fh:
        doc = json.load(fh)
    if not isinstance(doc, dict):
        raise ValueError("facts.json 顶层不是对象：%s" % type(doc).__name__)
    return doc


def _load_pyproject(root: str) -> Dict[str, Any]:
    with open(os.path.join(root, PYPROJECT_REL), "rb") as fh:
        return tomllib.load(fh)


def expected_payload(root: str) -> Dict[str, str]:
    """→ `{wheel 内路径: 仓库根绝对路径}`（注入面真源；与 setup.py 的 PAYLOAD_* 清单同构）。"""
    out: Dict[str, str] = {}
    for rel in PAYLOAD_FILES:
        out["ninfenz/" + rel.replace(os.sep, "/")] = os.path.join(root, rel)
    for rel_dir in PAYLOAD_TREES:
        base = os.path.join(root, rel_dir)
        for dp, dn, fn in os.walk(base):
            dn[:] = sorted(d for d in dn if d not in ("__pycache__", ".pytest_cache", ".git"))
            for f in sorted(fn):
                if f.endswith((".pyc", ".pyo")):
                    continue
                src = os.path.join(dp, f)
                rel = os.path.relpath(src, root).replace(os.sep, "/")
                out["ninfenz/" + rel] = src
    return out


def _dist_info(names: Iterable[str]) -> Optional[str]:
    for n in names:
        if n.endswith(".dist-info/METADATA") and n.startswith("ninfenz-"):
            return n.split("/")[0]
    return None


def _capped(issues: List[str], fmt: str, items: List[str], what: str) -> None:
    for n in items[:MAX_REPORT]:
        issues.append(fmt % n)
    if len(items) > MAX_REPORT:
        issues.append("…另有 %d 个%s（只列前 %d）" % (len(items) - MAX_REPORT, what, MAX_REPORT))


def _check_payload(zf: zipfile.ZipFile, present: Dict[str, Any], root: str,
                   issues: List[str]) -> Dict[str, Any]:
    """判据 A + D：必需件在场、注入面集合一致、逐字节对账。"""
    payload = expected_payload(root)
    missing = sorted(set(payload) - set(present))
    _capped(issues, "缺必需件：%s", missing, "缺失件")
    injected = {n for n in present if n.startswith("ninfenz/")} - STATIC_PKG_FILES
    extra = sorted(injected - set(payload))
    _capped(issues, "wheel 内有注入面之外的文件：%s", extra, "注入面外文件")
    mismatch = 0
    for whl_path, src in sorted(payload.items()):
        if whl_path not in present:
            continue
        try:
            with open(src, "rb") as fh:
                raw = fh.read()
        except OSError as exc:
            issues.append("读不到仓库根原件 %s：%s" % (src, exc))
            continue
        if _h(zf.read(whl_path)) != _h(raw):
            mismatch += 1
            if mismatch <= MAX_REPORT:
                issues.append("%s 与仓库根原件不一致（bundle 旧树 / 构建期漂移）" % whl_path)
    if mismatch > MAX_REPORT:
        issues.append("…另有 %d 件注入副本与仓库根不一致" % (mismatch - MAX_REPORT))
    return {"payload_files": len(payload), "payload_missing": len(missing),
            "payload_extra": len(extra), "payload_mismatch": mismatch}


def _check_metadata(msg: Any, facts: Dict[str, Any], pyproj: Dict[str, Any], wheel: str,
                    issues: List[str]) -> Dict[str, Any]:
    """判据 C：元数据与仓库真源一致（name/version/requires-python/license/文件名）。"""
    proj = pyproj.get("project") or {}
    want_name = str(proj.get("name") or "")
    want_version = str((facts.get("release") or {}).get("cli_version") or "")
    want_py = str(proj.get("requires-python") or "")
    name = str(msg.get("Name") or "")
    version = str(msg.get("Version") or "")
    req_py = str(msg.get("Requires-Python") or "")
    lic = str(msg.get("License-Expression") or msg.get("License") or "")
    if name != want_name:
        issues.append("元数据 Name=%r ≠ pyproject name=%r" % (name, want_name))
    if version != want_version:
        issues.append("元数据 Version=%r ≠ facts.release.cli_version=%r"
                      % (version, want_version))
    if req_py != want_py:
        issues.append("元数据 Requires-Python=%r ≠ pyproject %r" % (req_py, want_py))
    if "AGPL-3.0-only" not in lic or "LicenseRef-Commercial" not in lic:
        issues.append("License 表达式未同时声明 AGPL-3.0-only 与 LicenseRef-Commercial"
                      "（实际：%r）" % lic)
    if "MIT" in lic.upper():
        issues.append("License 表达式仍写 MIT（当前许可是 AGPL/商业；历史 MIT 只对 ≤1.0.5 成立）")
    base = os.path.basename(wheel)
    if want_name and want_version and not base.startswith(
            "%s-%s-" % (want_name.replace("-", "_"), want_version)):
        issues.append("wheel 文件名版本与元数据不一致：%s（期望前缀 %s-%s-）"
                      % (base, want_name.replace("-", "_"), want_version))
    return {"name": name, "version": version, "requires_python": req_py,
            "license_expression": lic}


def _check_entry(zf: zipfile.ZipFile, present: Dict[str, Any], di: str,
                 issues: List[str]) -> None:
    ep = di + "/entry_points.txt"
    if ep not in present:
        issues.append("缺 %s（console_scripts 入口缺失）" % ep)
        return
    eptext = zf.read(ep).decode("utf-8", "replace")
    if "ninfenz._launcher:main" not in eptext:
        issues.append("entry_points 未声明 `%s`（实际：%s）"
                      % (ENTRY, eptext.strip().replace("\n", " | ")[:160]))


def _check_forbidden(names: List[str], issues: List[str]) -> int:
    bad = [n for n in names if any(tok in "/" + n for tok in FORBIDDEN)
           or n.endswith(FORBIDDEN_SUFFIX)]
    _capped(issues, "禁入面文件：%s", bad, "禁入面文件")
    return len(bad)


def inspect_wheel(wheel: str, root: str = ROOT) -> Tuple[List[str], Dict[str, Any]]:
    """只读校验 wheel → (issues, stats)。issues 为空即通过。"""
    issues: List[str] = []
    stats: Dict[str, Any] = {"wheel": wheel}
    if not os.path.isfile(wheel):
        return ["wheel 不存在：%s" % wheel], stats
    try:
        zf = zipfile.ZipFile(wheel)
    except (OSError, zipfile.BadZipFile) as exc:
        return ["wheel 不是合法 zip：%s" % exc], stats
    with zf:
        names = zf.namelist()
        present = {n: None for n in names if not n.endswith("/")}
        if not names:
            return ["wheel 为空（0 个成员）"], stats
        if len(names) != len(set(names)):
            dup = sorted({n for n in names if names.count(n) > 1})
            issues.append("wheel 有重复成员：%s" % ", ".join(dup[:5]))
        try:
            facts = _load_facts(root)
            pyproj = _load_pyproject(root)
        except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
            return ["读不到仓库真源（%s / %s）：%s" % (FACTS_REL, PYPROJECT_REL, exc)], stats
        stats.update(_check_payload(zf, present, root, issues))
        di = _dist_info(names)
        if di is None:
            issues.append("缺 .dist-info/METADATA（wheel 元数据目录不在场）")
        else:
            _check_entry(zf, present, di, issues)
            stats.update(_check_metadata(BytesParser().parsebytes(zf.read(di + "/METADATA")),
                                         facts, pyproj, wheel, issues))
            stats["dist_info"] = di
        bad = _check_forbidden(names, issues)
        stats.update({
            "wheel_bytes": os.path.getsize(wheel),
            "files": len(present),
            "unpacked_bytes": sum(i.file_size for i in zf.infolist()),
            "forbidden": bad,
            "license_files": sorted(n for n in present if "/licenses/" in n.lower()),
        })
    return issues, stats


def _default_wheel(root: str) -> str:
    dist = os.path.join(root, "dist")
    try:
        wheels = [os.path.join(dist, n) for n in os.listdir(dist) if n.endswith(".whl")]
    except OSError:
        return ""
    return max(wheels, key=os.path.getmtime) if wheels else ""


def _print_human(wheel: str, issues: List[str], stats: Dict[str, Any]) -> None:
    print("== check_pypi_package（wheel 构建产物校验）==")
    print("  wheel：%s" % wheel)
    print("  大小：%s B · 文件 %s · 解包 %s B"
          % (format(stats.get("wheel_bytes", 0), ","), stats.get("files", "?"),
             format(stats.get("unpacked_bytes", 0), ",")))
    print("  元数据：%s %s · Requires-Python %s · License %s"
          % (stats.get("name", "?"), stats.get("version", "?"),
             stats.get("requires_python", "?"), stats.get("license_expression", "?")))
    print("  注入面：应 %s 件（缺 %s / 多 %s / 不一致 %s）"
          % (stats.get("payload_files", "?"), stats.get("payload_missing", "?"),
             stats.get("payload_extra", "?"), stats.get("payload_mismatch", "?")))
    print("  禁入面命中：%s · license 文本：%s"
          % (stats.get("forbidden", "?"),
             " / ".join(os.path.basename(p) for p in stats.get("license_files") or [])
             or "（无）"))
    if issues:
        print("  结果：FAIL %d 条" % len(issues))
        for i in issues:
            print("  [FAIL] %s" % i, file=sys.stderr)
    else:
        print("  结果：✓ 全部判据通过")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="check_pypi_package",
                                 description="校验 Python 发行包（wheel）构建产物")
    ap.add_argument("wheel", nargs="?", default=None,
                    help="wheel 路径（缺省 = dist/ 下最新 .whl）")
    ap.add_argument("--root", default=ROOT, help="仓库根（缺省 = 本脚本上一级）")
    ap.add_argument("--json", action="store_true", help="打印机读结果（kind=pypi-wheel-check）")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    wheel = args.wheel or _default_wheel(args.root)
    if not wheel:
        print("✗ 没找到 wheel：先构建 `python -m pip wheel . --no-deps "
              "--no-build-isolation -w dist/`", file=sys.stderr)
        return 2
    issues, stats = inspect_wheel(wheel, args.root)
    if args.json:
        print(json.dumps({"kind": "pypi-wheel-check", "wheel": wheel, "issues": issues,
                          "stats": stats}, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _print_human(wheel, issues, stats)
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
