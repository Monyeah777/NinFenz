#!/usr/bin/env python3
"""域包成熟度 M0–M3：从**证据**计算，不接受自报。

为什么需要它（2026-10-26 背景）
------------------------------
111 个社区包在 `protocol.yaml` 里全声明 `conformance: L2`——那是**模块契约级**（协议件/装配可执行），
不是成熟度。真实证据差异很大：多数只有模板 + 机检；techdoc / 合规包有「执行记录」，但 executor
是官方 assembler（工具）而非真实模型。把 L2 当成熟度读，就是拿声明当证据。本模块把成熟度定义成
**四级证据阶梯**，逐级从盘上事实算，证据不足一律降级。

判据（逐级包含：高一级必须满足低一级）
------------------------------------
- **M0 模板**：包目录 + `protocol.yaml` + README（`package.assets.readme`）+ `modules/` 在盘，
  且模块件数 ≥ `package.modules` 声明条数；
- **M1 机检**：check14/15/16/23/29/32 **同源判据**无 FAIL + `outputs/INDEX.json` 在册
  （可解析、`outputs[]` 非空、列出的产出路径逐件在盘、`package` 与包名一致）；
- **M2 真实执行**：`package.outputs` 里有**真实模型**执行记录——executor 是模型标识/版本
  （工具/agent/装配器不算）、date 合法、artifact 在盘为文件、check_rc=0、digest 与 artifact
  现算 sha256 一致；
- **M3 用户签收**：`results/audit/*.md` 里有审计记录（`core.audit.check_doc` 零 issue），
  `accepted_by` + `accepted_at` 双要素齐，且 `subjects` 里有本包内文件的 `路径:sha256`
  （digest 现算一致——被审对象一改，旧签收即失效）。

「同源判据」怎么做到（**不重写门禁**）
------------------------------------
- check14/15/23/29/32：直接走门禁单进程引擎 `core.gate_engine`（与 verify.sh 逐字等价、
  有 parity 差分测试常驻守着）——不在本模块抄第二份判据；
- check16：它在引擎里是 PENDING（判据分两段 heredoc），故从 `verify.sh` **原文取出两段 heredoc**，
  用 `core.gate_inproc.run_inproc` 进程内逐段执行（同一份源码、同一退出码语义，同样不重写）；
- 机检是**整仓判据**（那六条 check 本来就是全仓扫描）：任一 FAIL ⇒ 全部包不计 M1（fail-closed），
  输出里明写 `scope: repo`，不假装逐包归因。

纪律
----
1. **证据不足一律降级**：`missing` 写清下一级缺什么（可执行）；
2. **声明位只作声明**：`package.maturity` 不参与等级计算；声明 > 计算 = 虚标（`misdeclared`）；
3. **确定性输出**：不带时间戳/机器路径——同输入同字节（`--write` 幂等）。

输出（`--write`）
-----------------
- `protocol/domain_maturity.json`（schema `nf-domain-maturity/1`）；
- `desktop/src/core/registry.json` 的 `protocols[].maturity` 投影（**仅新增该字段**）。

用法（CLI 入口在 scripts/nf.py，本模块只做计算与落盘）
-----------------------------------------------------
    nf domain maturity [--json] [--write]
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import date
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

SCHEMA = "nf-domain-maturity/1"
KIND = "domain-maturity"
OUTPUT_REL = "protocol/domain_maturity.json"
REGISTRY_REL = "desktop/src/core/registry.json"
COMMUNITY_REL = "community"
PROTOCOL_REL = "protocol.yaml"
INDEX_REL = "outputs/INDEX.json"

#: 成熟度阶梯（低 → 高）。索引即等级序，供「声明 vs 计算」比较。
LEVELS: Tuple[str, ...] = ("M0", "M1", "M2", "M3")

#: M1 的机检面（task T5.1 点名；**同源**跑法见模块头）。
MACHINE_CHECKS: Tuple[int, ...] = (14, 15, 16, 23, 29, 32)
#: 引擎已迁入的 check（check16 走 verify.sh 内嵌 heredoc，见 `_check16`）。
ENGINE_CHECKS: Tuple[int, ...] = (14, 15, 23, 29, 32)

LEVEL_NOTES: Dict[str, str] = {
    "M0": "模板：包目录 + protocol.yaml + README + modules 在盘（模块件数 ≥ 声明）",
    "M1": "机检：check14/15/16/23/29/32 同源判据无 FAIL + outputs/INDEX.json 在册",
    "M2": "真实执行：真实模型执行记录（executor 模型标识/版本 + date + artifact + check_rc=0 "
          "+ digest 可复算）",
    "M3": "用户签收：results/audit 审计记录 accepted_by+accepted_at 绑定被审对象 digest",
}

_DATED = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DIGEST = re.compile(r"^(?:sha256:)?([0-9a-f]{64})$")
_MODULE_TOKEN = re.compile(r"M\d{2}")

#: executor 的**工具/装配器**信号（命中即不算真实模型执行——这是 M2 的诚实边界）。
_TOOL_MARKERS: Tuple[str, ...] = (
    "python", "scripts/", "script", ".py", "nf ", "nf.py", "assemble", "assembler",
    "装配", "agent", "代理", "脚本", "shell", "bash", "node ", "cli", "tool", "工具",
    "make ", "runner", "执行器", "程序", "pipeline",
)
#: 真实模型标识信号（组织机构/模型名族；与版本号同时出现才算，避免「model」泛词误判）。
_MODEL_MARKERS: Tuple[str, ...] = (
    "gpt", "claude", "qwen", "deepseek", "laya", "llama", "glm", "mistral", "gemma",
    "kimi", "ernie", "minimax", "doubao", "internlm", "baichuan", "phi-", "grok",
    "chatglm", "yi-", "o1", "o3", "模型", "model",
)
_VERSION_RE = re.compile(
    r"(?:@|v)\d{1,3}\b|\b\d{1,4}\.\d{1,4}\b|\b\d{1,6}[bB]\b|instruct|chat|base|mini|turbo|large|flash")


# ---------------------------------------------------------------- 基础读取
def _root(root: Any) -> Path:
    return Path(root)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""


def _load_yaml(path: Path) -> Tuple[Optional[Dict[str, Any]], str]:
    """protocol.yaml → (文档, 错误)。PyYAML 经惰性入口取（缺依赖如实报，不静默当空）。"""
    if not path.is_file():
        return None, "protocol.yaml 缺失"
    from core import lazy_yaml
    yaml = lazy_yaml.module()
    if yaml is None:
        return None, "PyYAML 不可用，无法解析 protocol.yaml"
    try:
        doc = yaml.safe_load(_read_text(path))
    except Exception as exc:                                   # noqa: BLE001 - 坏件如实报
        return None, "protocol.yaml 解析失败：%s" % exc
    if not isinstance(doc, dict):
        return None, "protocol.yaml 顶层非对象"
    return doc, ""


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _pkg_rel(name: str) -> str:
    return "%s/%s" % (COMMUNITY_REL, name)


def discover_packages(root: Any = ".") -> List[str]:
    """→ 全部已登记包名（`community/<包>/protocol.yaml` 在场），按名字排序。"""
    base = _root(root) / COMMUNITY_REL
    if not base.is_dir():
        return []
    return sorted(p.name for p in base.iterdir()
                  if p.is_dir() and (p / PROTOCOL_REL).is_file())


def _package_doc(root: Path, name: str) -> Tuple[Optional[Dict[str, Any]], str]:
    doc, err = _load_yaml(root / COMMUNITY_REL / name / PROTOCOL_REL)
    if err:
        return None, err
    pkg = doc.get("package")
    if not isinstance(pkg, dict):
        return None, "protocol.yaml 缺 package 对象"
    return pkg, ""


# ---------------------------------------------------------------- M0 模板
def m0_evidence(root: Any, name: str, pkg: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """M0：包目录 + protocol.yaml + README + modules 在盘（模块件数 ≥ 声明）。"""
    r = _root(root)
    pkg_dir = r / COMMUNITY_REL / name
    missing: List[str] = []
    module_docs = 0
    declared = 0
    if not pkg_dir.is_dir():
        missing.append("M0：包目录缺失 %s" % _pkg_rel(name))
    elif not (pkg_dir / PROTOCOL_REL).is_file():
        missing.append("M0：protocol.yaml 缺失 %s/%s" % (_pkg_rel(name), PROTOCOL_REL))
    if pkg is not None:
        readme = str(((pkg.get("assets") or {}).get("readme") if isinstance(
            pkg.get("assets"), dict) else "") or "README.md")
        if not (pkg_dir / readme).is_file():
            missing.append("M0：README 缺失 %s/%s" % (_pkg_rel(name), readme))
        mods = pkg.get("modules")
        declared = len(mods) if isinstance(mods, list) else 0
        mdir = pkg_dir / "modules"
        docs = sorted(mdir.glob("*.md")) if mdir.is_dir() else []
        module_docs = len(docs)
        if declared and (not mdir.is_dir() or not docs):
            missing.append("M0：modules/ 缺失或为空 %s/modules" % _pkg_rel(name))
        elif declared and module_docs < declared:
            missing.append("M0：模块件数 %d < 声明 %d（%s/modules）"
                           % (module_docs, declared, _pkg_rel(name)))
        # declared == 0 = 借阅型组合包（无自有模块，references 承载）——无 modules/ 是合法形态
    return {"ok": not missing, "missing": missing,
            "module_docs": module_docs, "modules_declared": declared}


# ---------------------------------------------------------------- M1 机检（同源）
def _heredoc_blocks(text: str) -> List[str]:
    """从一段 check 体里取出**全部** `"$PY3" - <<'PYEOF' … PYEOF` 块（逐字保留源码）。

    只服务于 check16（它的判据分两段 heredoc）；块的闭合行是**顶格**的定界符。
    """
    blocks: List[str] = []
    cur: Optional[List[str]] = None
    delim = ""
    start = re.compile(r"\"\$PY3\"\s+-\s+<<'(\w+)'")
    for line in text.splitlines():
        if cur is None:
            m = start.search(line)
            if m:
                delim = m.group(1)
                cur = []
            continue
        if line == delim or line.startswith(delim + " "):
            blocks.append("\n".join(cur))
            cur = None
        else:
            cur.append(line)
    return blocks


def _check16(root: Path) -> Dict[str, Any]:
    """check16 同源执行：verify.sh 原文两段 heredoc 进程内逐段跑（不重写判据）。"""
    from core import gate_inproc, gate_labels
    text = _read_text(root / "verify.sh")
    if not text:
        return {"status": "ERROR", "source": "verify.sh 缺失", "codes": []}
    body = gate_labels.check_body(text, 16) or ""
    blocks = _heredoc_blocks(body)
    if not blocks:
        return {"status": "ERROR", "source": "check16 heredoc 提取失败", "codes": []}
    codes: List[int] = []
    details: List[str] = []
    for i, src in enumerate(blocks):
        try:
            code, out = gate_inproc.run_inproc(src, root, "domain-maturity-check16-%d" % i)
        except Exception as exc:                               # noqa: BLE001 - 信任门/环境问题如实报
            return {"status": "ERROR", "source": "check16 heredoc 执行失败：%s" % exc,
                    "codes": codes}
        codes.append(int(code))
        details.append(str(gate_inproc.tail(out, 1)))
    ok = all(c == 0 for c in codes)
    out: Dict[str, Any] = {"status": "PASS" if ok else "FAIL",
                           "source": "verify.sh check16 内嵌 heredoc（进程内逐段执行 %d 段）"
                                     % len(blocks),
                           "codes": codes}
    if not ok:                       # 诊断面只在失败时带（成功面保持精简/确定性）
        out["detail"] = " / ".join(d for d in details if d)[:300]
    return out


def _engine_gate(root: Path) -> Dict[str, Any]:
    from core import gate_engine as ge
    ge.build_registry()
    verdicts = ge.run_checks(root, list(ENGINE_CHECKS))
    checks: Dict[str, Any] = {}
    for v in verdicts:
        num = int(str(v.name).replace("check", ""))
        checks[str(num)] = {"status": v.status, "source": "gate_engine（与 verify.sh 判据逐字等价）"}
    return checks


def machine_gate(root: Any = ".",
                 runner: Optional[Callable[[Path], Dict[str, Any]]] = None) -> Dict[str, Any]:
    """M1 的机检面 → {status, checks, source, note, scope}。

    `runner` 注入点：单测用合成 gate（不跑整仓）；缺省走同源执行面。
    """
    r = _root(root)
    checks: Dict[str, Any] = {}
    error = ""
    try:
        checks = runner(r) if runner is not None else _engine_gate(r)
    except Exception as exc:                                   # noqa: BLE001 - 机检环境问题如实报
        error = "机检执行失败：%s" % exc
    if error:
        checks = {str(n): {"status": "ERROR", "source": error} for n in MACHINE_CHECKS}
    else:
        if runner is None:
            checks[str(16)] = _check16(r)
        else:
            for n in MACHINE_CHECKS:
                checks.setdefault(str(n), {"status": "ERROR", "source": "注入 runner 未给该 check"})
    statuses = [str((checks.get(str(n)) or {}).get("status") or "ERROR") for n in MACHINE_CHECKS]
    # 门禁口径：WARN 非致命（verify.sh 只按 FAIL 判死），故 WARN 视为绿并如实记录。
    ok = all(s in ("PASS", "WARN") for s in statuses)
    return {
        "status": "pass" if ok else "fail",
        "scope": "repo",
        "checks": checks,
        "source": ("verify.sh 同源判据（gate_engine 已迁入 %s + check16 内嵌 heredoc 进程内执行）"
                   % "/".join(str(n) for n in ENGINE_CHECKS)),
        "note": ("机检是整仓判据（六条 check 本就是全仓扫描）：任一 FAIL ⇒ 全部包不计 M1"
                 "（fail-closed，不假装逐包归因）"),
    }


def _gate_ok(gate: Optional[Dict[str, Any]]) -> bool:
    return bool(isinstance(gate, dict) and str(gate.get("status") or "") == "pass")


def m1_evidence(root: Any, name: str, gate: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """M1：机检无 FAIL + outputs/INDEX.json 在册（可解析 / 非空 / 路径逐件在盘）。"""
    r = _root(root)
    pkg_dir = r / COMMUNITY_REL / name
    missing: List[str] = []
    stats: Dict[str, Any] = {"index": False, "outputs": 0}
    if not _gate_ok(gate):
        failed = []
        for n in MACHINE_CHECKS:
            rec = ((gate or {}).get("checks") or {}).get(str(n)) or {}
            if str(rec.get("status") or "ERROR") not in ("PASS", "WARN"):
                failed.append(str(n))
        missing.append("M1：机检未全绿（check %s 非绿；同源判据见 nf verify）"
                       % (",".join(failed) or "机器面不可用"))
    idx_path = pkg_dir / INDEX_REL
    if not idx_path.is_file():
        missing.append("M1：outputs/INDEX.json 缺失（%s/%s）" % (_pkg_rel(name), INDEX_REL))
        return {"ok": False, "missing": missing, **stats}
    try:
        doc = json.loads(_read_text(idx_path))
    except ValueError as exc:
        missing.append("M1：outputs/INDEX.json 不可解析：%s" % exc)
        return {"ok": False, "missing": missing, **stats}
    stats["index"] = True
    if not isinstance(doc, dict):
        missing.append("M1：outputs/INDEX.json 顶层非对象")
        return {"ok": False, "missing": missing, **stats}
    want_pkg = str(doc.get("package") or "")
    if want_pkg and want_pkg != name:
        missing.append("M1：outputs/INDEX.json package=%r 与目录名 %r 不一致" % (want_pkg, name))
    rows = doc.get("outputs")
    if not isinstance(rows, list) or not rows:
        missing.append("M1：outputs/INDEX.json 的 outputs[] 缺失或为空")
        return {"ok": False, "missing": missing, **stats}
    stats["outputs"] = len(rows)
    absent = []
    for row in rows:
        rel = str((row or {}).get("path") or "") if isinstance(row, dict) else ""
        if not rel:
            absent.append("<空 path>")
        elif not (pkg_dir / rel).is_file():
            absent.append(rel)
    if absent:
        missing.append("M1：产出面 %d 件不在盘：%s" % (len(absent), "、".join(absent[:3])))
    return {"ok": not missing, "missing": missing, **stats}


# ---------------------------------------------------------------- M2 真实执行
def classify_executor(executor: Any) -> Tuple[str, str]:
    """executor → (kind, reason)；kind ∈ model / tool / unknown。

    判据（诚实边界）：**工具/agent/装配器不算真实模型执行**。结构化写法可显式声明
    `executor: {kind: model, id: ..., version: ...}`（kind 优先于自由文本推断）；字符串按
    「工具信号 / 模型族信号 + 版本」判。任何一侧都无法判定 → unknown（不计 M2）。
    """
    if isinstance(executor, dict):
        kind = str(executor.get("kind") or "").strip().lower()
        ident = str(executor.get("id") or executor.get("name") or "").strip()
        version = str(executor.get("version") or "").strip()
        if kind in ("model", "模型"):
            if not ident:
                return "unknown", "executor.kind=model 但缺 id（模型标识）"
            return "model", "结构化声明：模型 %s%s" % (ident, ("@" + version) if version else "")
        if kind in ("tool", "工具", "agent", "代理", "assembler", "装配器", "script", "脚本"):
            return "tool", "结构化声明：executor.kind=%s（工具/agent，不计 M2）" % kind
        if ident:
            text = ident + (("@" + version) if version else "")
            return classify_executor(text)
        return "unknown", "executor 对象缺 kind/id，无法判定"
    text = str(executor or "").strip()
    if not text:
        return "unknown", "executor 缺失"
    low = text.lower()
    for mark in _TOOL_MARKERS:
        if mark in low:
            return "tool", "executor=%r 命中工具/装配器信号 %r（不计 M2）" % (text, mark)
    has_model = any(m in low for m in _MODEL_MARKERS)
    has_version = bool(_VERSION_RE.search(low))
    if has_model and has_version:
        return "model", "executor=%r 命中模型族 + 版本信号" % text
    if has_model:
        return "unknown", "executor=%r 有模型族信号但缺版本（模型须带标识/版本）" % text
    return "unknown", "executor=%r 未见模型标识/版本（不计 M2）" % text


def _resolve_artifact(root: Path, pkg_dir: Path, artifact: Any) -> Tuple[Optional[Path], str]:
    """执行记录的 artifact → (存在的文件路径, 原因)。只认**单个相对文件路径**（可复算）。"""
    rel = str(artifact or "").strip()
    if not rel:
        return None, "artifact 缺失"
    if os.path.isabs(rel):
        return None, "artifact 须为包内/仓内相对路径（绝对路径不可复算/不可移植）：%r" % rel
    if any(ch in rel for ch in "*?[]") or "（" in rel or "(" in rel:
        return None, "artifact 不是单个文件路径（含通配/说明文字）：%r" % rel
    for base, label in ((pkg_dir, "包内"), (root, "仓内")):
        cand = base / rel
        if cand.is_file():
            return cand, label
    return None, "artifact 不在盘：%r" % rel


def _parse_digest(raw: Any) -> Optional[str]:
    if isinstance(raw, dict):
        raw = raw.get("value")
        if str((raw or "")).strip() == "":
            return None
    text = str(raw or "").strip().lower()
    m = _DIGEST.match(text)
    return m.group(1) if m else None


def m2_evidence(root: Any, name: str, pkg: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """M2：真实模型执行记录（executor/date/artifact/check_rc=0/digest 可复算）。"""
    r = _root(root)
    pkg_dir = r / COMMUNITY_REL / name
    out = (pkg or {}).get("outputs")
    ev: Dict[str, Any] = {"ok": False, "missing": [], "executor": None, "executor_kind": None,
                          "date": None, "artifact": None, "artifact_sha256": None,
                          "check_rc": None, "digest_ok": False}
    if not isinstance(out, dict) or not out:
        ev["missing"].append("M2：缺真实模型执行：package.outputs 执行记录缺失")
        return ev
    executor = out.get("executor")
    ev["executor"] = executor if isinstance(executor, (str, dict)) else None
    kind, why = classify_executor(executor)
    ev["executor_kind"] = kind
    if kind != "model":
        ev["missing"].append("M2：缺真实模型执行：%s" % why)
    when = str(out.get("date") or "").strip()
    ev["date"] = when or None
    if not _DATED.match(when):
        ev["missing"].append("M2：执行日期非法（须 YYYY-MM-DD）：%r" % when)
    else:
        try:
            date.fromisoformat(when)
        except ValueError:
            ev["missing"].append("M2：执行日期不是合法日历日：%r" % when)
    artifact_path, artifact_why = _resolve_artifact(r, pkg_dir, out.get("artifact"))
    ev["artifact"] = str(out.get("artifact") or "") or None
    if artifact_path is None:
        ev["missing"].append("M2：%s" % artifact_why)
    rc = out.get("check_rc")
    ev["check_rc"] = rc
    rc_ok = False
    if isinstance(rc, bool) or rc is None:
        ev["missing"].append("M2：check_rc 缺失或非整数")
    else:
        try:
            rc_ok = int(str(rc).strip()) == 0
        except ValueError:
            rc_ok = False
        if not rc_ok:
            ev["missing"].append("M2：check_rc != 0（%r）——机检未过不算真实执行" % rc)
    digest = _parse_digest(out.get("digest"))
    if artifact_path is not None:
        actual = _sha256(artifact_path)
        ev["artifact_sha256"] = actual
        if digest is None:
            ev["missing"].append("M2：执行记录缺 sha256 digest（artifact 须可复算）")
        elif digest != actual:
            ev["missing"].append("M2：digest 不可复算（记录 %s… vs 实测 %s…）"
                                 % (digest[:12], actual[:12]))
        else:
            ev["digest_ok"] = True
    ev["ok"] = not ev["missing"]
    return ev


# ---------------------------------------------------------------- M3 用户签收
def m3_evidence(root: Any, name: str) -> Dict[str, Any]:
    """M3：审计记录 accepted_by+accepted_at 且 subjects 绑定本包文件 digest（复用 core.audit）。"""
    from core import audit
    r = _root(root)
    ev: Dict[str, Any] = {"ok": False, "missing": [], "entry": None,
                          "accepted_by": None, "accepted_at": None, "subjects": []}
    decl = audit.decl(str(r))
    if str(decl.get("schema") or "") != audit.SCHEMA:
        ev["missing"].append("M3：缺审计协议声明 %s（签收机制未生效，无法机检）" % audit.DECL_REL)
        return ev
    prefix = _pkg_rel(name) + "/"
    try:
        rows = audit.entries(str(r))
    except Exception as exc:                                   # noqa: BLE001 - 读面坏件如实报
        ev["missing"].append("M3：审计件读取失败：%s" % exc)
        return ev
    hit = None
    for ent in rows:
        fm = ent.get("fm") or {}
        if not fm.get("accepted_by") or not fm.get("accepted_at"):
            continue
        if not _DATED.match(str(fm.get("accepted_at") or "")):
            continue
        if str(fm.get("verdict") or "") != "pass":
            continue
        issues, _stats = audit.check_doc(str(r), ent["path"])
        if issues:
            continue
        subs = fm.get("subjects") or []
        if isinstance(subs, str):
            subs = [subs]
        bound = [str(s).rsplit(":", 1)[0].replace("\\", "/") for s in subs
                 if ":" in str(s) and str(s).rsplit(":", 1)[0].replace("\\", "/").startswith(prefix)]
        if not bound:
            continue
        hit = {"entry": ent["path"], "accepted_by": str(fm.get("accepted_by")),
               "accepted_at": str(fm.get("accepted_at")), "subjects": bound}
        break
    if hit is None:
        ev["missing"].append(
            "M3：缺用户签收（%s 需 accepted_by+accepted_at，且 subjects 绑定本包文件 "
            "路径:sha256——digest 现算一致）" % audit.GLOB)
    else:
        ev.update(hit)
        ev["ok"] = True
    return ev


# ---------------------------------------------------------------- 计算
def _rank(level: Optional[str]) -> int:
    return LEVELS.index(level) if level in LEVELS else -1


def _declared(pkg: Optional[Dict[str, Any]]) -> Tuple[Any, bool]:
    raw = (pkg or {}).get("maturity")
    return raw, (raw is None or raw in LEVELS)


def evaluate(root: Any, name: str, gate: Optional[Dict[str, Any]],
             pkg: Optional[Dict[str, Any]] = None, parse_error: str = "") -> Dict[str, Any]:
    """单包证据 → 一行成熟度（纯函数；测试直接调它）。"""
    if parse_error:
        m0 = {"ok": False, "missing": ["M0：%s" % parse_error],
              "module_docs": 0, "modules_declared": 0}
    else:
        m0 = m0_evidence(root, name, pkg)
    evidence: Dict[str, Any] = {"M0": m0}
    level: Optional[str] = None
    next_level: Optional[str] = None
    missing: List[str] = []
    if m0["ok"]:
        m1 = m1_evidence(root, name, gate)
        evidence["M1"] = m1
        if m1["ok"]:
            m2 = m2_evidence(root, name, pkg)
            evidence["M2"] = m2
            if m2["ok"]:
                m3 = m3_evidence(root, name)
                evidence["M3"] = m3
                if m3["ok"]:
                    level = "M3"
                else:
                    level, next_level, missing = "M2", "M3", m3["missing"]
            else:
                level, next_level, missing = "M1", "M2", m2["missing"]
        else:
            level, next_level, missing = "M0", "M1", m1["missing"]
    else:
        missing = m0["missing"]
        next_level = "M0"
    declared, declared_valid = _declared(pkg)
    misdeclared = bool(declared_valid and declared in LEVELS
                       and _rank(declared) > _rank(level))
    return {
        "package": name,
        "path": _pkg_rel(name),
        "declared": declared,
        "declared_valid": declared_valid,
        "maturity": level,
        "misdeclared": misdeclared,
        "next_level": next_level,
        "missing": missing,
        "evidence": evidence,
    }


def compute(root: Any = ".", packages: Optional[Iterable[str]] = None,
            gate: Optional[Dict[str, Any]] = None,
            runner: Optional[Callable[[Path], Dict[str, Any]]] = None) -> Dict[str, Any]:
    """全仓 → 成熟度文档（`nf-domain-maturity/1`）。`gate` 可注入（单测不跑整仓）。"""
    r = _root(root)
    names = list(packages) if packages is not None else discover_packages(r)
    gate_doc = gate if gate is not None else machine_gate(r, runner=runner)
    rows: List[Dict[str, Any]] = []
    for name in names:
        pkg, parse_error = _package_doc(r, name)
        rows.append(evaluate(r, name, gate_doc, pkg=pkg, parse_error=parse_error))
    summary = {lv: sum(1 for row in rows if row["maturity"] == lv) for lv in LEVELS}
    summary["unrated"] = sum(1 for row in rows if row["maturity"] is None)
    summary["total"] = len(rows)
    summary["misdeclared"] = sum(1 for row in rows if row["misdeclared"])
    return {
        "schema": SCHEMA,
        "kind": KIND,
        "note": ("域包成熟度 M0–M3：按证据逐级计算（声明位 package.maturity 不参与计算；"
                 "声明 > 计算 = 虚标）。口径见 core/domain_maturity.py。"),
        "levels": dict(LEVEL_NOTES),
        "machine_checks": list(MACHINE_CHECKS),
        "machine_gate": gate_doc,
        "summary": summary,
        "packages": rows,
    }


# ---------------------------------------------------------------- 落盘
def _registry_update(root: Path, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """registry.protocols[].maturity 投影：**只增/改这一个字段**（锁内重读重并，防丢更新）。"""
    from core import atomic_write
    reg_path = root / REGISTRY_REL
    if not reg_path.is_file():
        return {"path": REGISTRY_REL, "updated": 0, "total": 0,
                "error": "registry.json 缺失"}
    with atomic_write.lock_file(reg_path, what="registry.json（nf domain maturity --write）"):
        doc = json.loads(_read_text(reg_path))
        prots = doc.get("protocols")
        if not isinstance(prots, list):
            return {"path": REGISTRY_REL, "updated": 0, "total": 0,
                    "error": "registry protocols[] 缺失或非列表"}
        by_id = {str(p.get("id")): p for p in prots if isinstance(p, dict)}
        updated = 0
        for row in rows:
            ent = by_id.get(row["package"])
            if ent is None:
                continue
            if ent.get("maturity") != row["maturity"]:
                ent["maturity"] = row["maturity"]
                updated += 1
        missing = sorted(row["package"] for row in rows if row["package"] not in by_id)
        atomic_write.write_text(reg_path,
                                json.dumps(doc, ensure_ascii=False, indent=2) + "\n")
    return {"path": REGISTRY_REL, "updated": updated, "total": len(prots),
            "absent": missing}


def write_outputs(root: Any, doc: Dict[str, Any]) -> Dict[str, Any]:
    """落盘 `protocol/domain_maturity.json` + registry protocols[].maturity 投影（幂等）。"""
    from core import atomic_write
    r = _root(root)
    rel = OUTPUT_REL
    atomic_write.write_text(r / rel, json.dumps(doc, ensure_ascii=False, indent=2,
                                                sort_keys=True) + "\n")
    reg = _registry_update(r, doc.get("packages") or [])
    return {"json": rel, "registry": reg}


# ---------------------------------------------------------------- 人读/机器面
def render_human(doc: Dict[str, Any]) -> str:
    """人读面（稳定顺序：按包名；不含墙钟/机器路径）。"""
    gate = doc.get("machine_gate") or {}
    s = doc.get("summary") or {}
    lines = ["== nf domain maturity（域包成熟度 M0–M3 · 证据计算）==",
             "  机检（check%s 同源）：%s（scope=%s）"
             % ("/".join(str(n) for n in doc.get("machine_checks") or []),
                "PASS" if gate.get("status") == "pass" else "FAIL", gate.get("scope", "-")),
             "  分布：M3 %d · M2 %d · M1 %d · M0 %d · 未达 M0 %d（共 %d）· 虚标 %d"
             % (s.get("M3", 0), s.get("M2", 0), s.get("M1", 0), s.get("M0", 0),
                s.get("unrated", 0), s.get("total", 0), s.get("misdeclared", 0))]
    for row in doc.get("packages") or []:
        level = row.get("maturity") or "—"
        declared = row.get("declared") or ""
        flag = " ⚠虚标" if row.get("misdeclared") else ""
        lines.append("    %-3s ← %-3s %s%s" % (level, declared or "—", row["package"], flag))
        if row.get("missing"):
            lines.append("         · %s" % row["missing"][0])
    lines.append("  → 写盘：nf domain maturity --write（protocol/domain_maturity.json + "
                 "registry protocols[].maturity）")
    return "\n".join(lines)


def run(root: Any = ".", as_json: bool = False, write: bool = False) -> int:
    """CLI 执行体：计算 →（可选）落盘 → 输出。成功返回 0（虚标/降级不是命令失败）。"""
    r = _root(root)
    doc = compute(r)
    if write:
        doc["written"] = write_outputs(r, doc)
    if as_json:
        print(json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    print(render_human(doc))
    if write:
        w = doc.get("written") or {}
        reg = w.get("registry") or {}
        print("  ✓ 已写 %s；registry protocols[].maturity 更新 %d/%d 条%s"
              % (w.get("json"), reg.get("updated", 0), reg.get("total", 0),
                 ("（registry 缺件：%s）" % reg.get("error")) if reg.get("error") else ""))
    return 0
