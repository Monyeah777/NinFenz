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
- **M1 机检**：check14/15/16/23/29/32 **同源判据**无 FAIL + **至少一件可验收产物证据**
  （二选一，均须机器可核验，不得人工白名单）：
  a) `outputs/INDEX.json` 在册（可解析、`outputs[]` 非空、`package` 与包名一致、列出的产出
     路径逐件在盘）**且每件通过 `nf output check`**（同源：`core.output_forms.detect` +
     `_FORM_CHECK` 逐件机检）；
  b) 官方样本产物在场且可追溯：`library/NF-*.md` 在 `library/INDEX.md` 台账行里指认本包
     （行内声明本包管线 / 包名或类别）或 `docs/完整版样本_*.md` 明确声明本包管线，且样本路径
     被 provenance/协议台账（`protocol/*.json` 溯源字段）指认；样本须通过 `nf assemble --check`
     （同源：`core.assemble_plan.plan/check`，含跨域门——声明管线与本包管线不一致即 FAIL）；
  手工编写但有可验收产物的官方包（techdoc/校园/西幻）因此不被错误压到 M0，机检门槛不降低。
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
#: M1 分支 b 的候选样本面（**glob 发现**，不写包名单=不搞人工白名单）。
SAMPLE_LIBRARY_GLOB = "library/NF-*.md"
SAMPLE_DOCS_GLOB = "docs/完整版样本_*.md"
LIBRARY_INDEX_REL = "library/INDEX.md"
PROTOCOL_GLOB = "protocol/*.json"
#: 管线 id 的独立 token 匹配（避免把层位/正文里的长串数字误当管线声明）。
_PIPELINE_TOKEN = re.compile(r"(?<![A-Za-z0-9])P[0-9]{2,3}(?![0-9])")

#: 成熟度阶梯（低 → 高）。索引即等级序，供「声明 vs 计算」比较。
LEVELS: Tuple[str, ...] = ("M0", "M1", "M2", "M3")

#: M1 的机检面（task T5.1 点名；**同源**跑法见模块头）。
MACHINE_CHECKS: Tuple[int, ...] = (14, 15, 16, 23, 29, 32)
#: 引擎已迁入的 check（check16 走 verify.sh 内嵌 heredoc，见 `_check16`）。
ENGINE_CHECKS: Tuple[int, ...] = (14, 15, 23, 29, 32)

LEVEL_NOTES: Dict[str, str] = {
    "M0": "模板：包目录 + protocol.yaml + README + modules 在盘（模块件数 ≥ 声明）",
    "M1": "机检：check14/15/16/23/29/32 同源判据无 FAIL + 可验收产物证据（a：outputs/INDEX.json "
          "在册且逐件过 nf output check；b：关联官方样本产物过 nf assemble --check）",
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


def _output_check_issues(root: Path, repo_rel: str) -> List[str]:
    """单件产出面机检（**与 `nf output check` 同源**：detect + _FORM_CHECK）。"""
    from core import output_forms as of
    try:
        form, _tier = of.detect(str(root), repo_rel)
        checker = of._FORM_CHECK.get(form)
        return list(checker(str(root), repo_rel)) if checker else []
    except Exception as exc:                                   # noqa: BLE001 - 坏件如实报
        return ["产出面机检异常：%s" % exc]


def _index_evidence(root: Path, name: str) -> Dict[str, Any]:
    """M1 分支 a：`outputs/INDEX.json` 在册且列出的产出面逐件过机检。"""
    pkg_dir = root / COMMUNITY_REL / name
    ev: Dict[str, Any] = {"ok": False, "missing": [], "present": False, "outputs": 0,
                          "checked": 0, "issues": []}
    idx_path = pkg_dir / INDEX_REL
    if not idx_path.is_file():
        ev["missing"].append("M1a：outputs/INDEX.json 缺失（%s/%s）"
                             % (_pkg_rel(name), INDEX_REL))
        return ev
    try:
        doc = json.loads(_read_text(idx_path))
    except ValueError as exc:
        ev["missing"].append("M1a：outputs/INDEX.json 不可解析：%s" % exc)
        return ev
    ev["present"] = True
    if not isinstance(doc, dict):
        ev["missing"].append("M1a：outputs/INDEX.json 顶层非对象")
        return ev
    want_pkg = str(doc.get("package") or "")
    if want_pkg and want_pkg != name:
        ev["missing"].append("M1a：outputs/INDEX.json package=%r 与目录名 %r 不一致"
                             % (want_pkg, name))
    rows = doc.get("outputs")
    if not isinstance(rows, list) or not rows:
        ev["missing"].append("M1a：outputs/INDEX.json 的 outputs[] 缺失或为空")
        return ev
    ev["outputs"] = len(rows)
    absent: List[str] = []
    for row in rows:
        rel = str((row or {}).get("path") or "") if isinstance(row, dict) else ""
        if not rel or not (pkg_dir / rel).is_file():
            absent.append(rel or "<空 path>")
            continue
        ev["checked"] += 1
        issues = _output_check_issues(root, "%s/%s" % (_pkg_rel(name), rel))
        if issues:
            ev["issues"].append({"path": rel, "issues": issues[:3]})
            ev["missing"].append("M1a：产出面未过 nf output check：%s（%s）"
                                 % (rel, "；".join(issues[:2])))
    if absent:
        ev["missing"].append("M1a：产出面 %d 件不在盘：%s"
                             % (len(absent), "、".join(absent[:3])))
    ev["ok"] = not ev["missing"]
    return ev


def _candidate_samples(root: Path) -> List[str]:
    """M1 分支 b 的候选样本面（glob 发现，按路径排序；不写包名单）。"""
    out: List[str] = []
    for pattern in (SAMPLE_LIBRARY_GLOB, SAMPLE_DOCS_GLOB):
        for p in sorted(root.glob(pattern)):
            if p.is_file():
                out.append(p.relative_to(root).as_posix())
    return out


def _requirement_for(pkg: Dict[str, Any], name: str) -> Tuple[str, Dict[str, Any]]:
    """从**包自身声明**推装配需求 → (requirement, plan)。

    只用类别/包名（不读外部白名单）；要求 plan 命中本包且管线与 `protocol.yaml` 一致，
    否则视为「定不出允许集」（分支 b 不可用，fail-closed）。
    """
    from core import assemble_plan as ap
    pipe = str(pkg.get("pipeline") or "")
    cats = [str(c) for c in (pkg.get("categories") or []) if str(c).strip()]
    stem = re.sub(r"(领域包|域包|组合包)$", "", name)
    for req in cats + [name, stem]:
        if not req:
            continue
        try:
            plan = ap.plan(req)
        except Exception:                                      # noqa: BLE001 - 单候选失败不致死
            continue
        if (plan.get("matched") and plan.get("package") == name
                and str(plan.get("pipeline") or "") == pipe):
            return req, plan
    return "", {}


def _library_row(root: Path, sample_rel: str) -> str:
    """library 样本 → `library/INDEX.md` 台账里对应该条目 id 的表格行（空 = 未在册）。"""
    entry = Path(sample_rel).stem
    text = _read_text(root / LIBRARY_INDEX_REL)
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("|") and entry in s:
            return s
    return ""


def _provenance_hits(root: Path, sample_rel: str) -> List[Dict[str, str]]:
    """`protocol/*.json`（协议台账/溯源字段）里逐值指认该样本路径的登记点。

    **排除本模块的落盘件** `protocol/domain_maturity.json`：它是本判据的产出，不是溯源
    ｜台账——不排除会形成自指（自己的输出把自己算成"被指认"）。
    """
    hits: List[Dict[str, str]] = []
    for p in sorted(root.glob(PROTOCOL_GLOB)):
        if p.relative_to(root).as_posix() == OUTPUT_REL:
            continue
        try:
            doc = json.loads(_read_text(p))
        except ValueError:
            continue

        def walk(node: Any, path: str) -> None:
            if isinstance(node, dict):
                for k, v in node.items():
                    walk(v, path + "/" + str(k))
            elif isinstance(node, list):
                for i, v in enumerate(node):
                    walk(v, path + "/" + str(i))
            elif isinstance(node, str) and node.strip() == sample_rel:
                hits.append({"ledger": p.name, "field": path.lstrip("/")})

        walk(doc, "")
    return hits


def _sample_evidence(root: Path, name: str, pkg: Dict[str, Any],
                     planner: Optional[Callable[..., Tuple[str, Dict[str, Any]]]] = None,
                     checker: Optional[Callable[..., Tuple[List[str], Dict[str, Any]]]] = None,
                     ) -> Dict[str, Any]:
    """M1 分支 b：关联官方样本产物通过 `nf assemble --check`（同源 plan/check）。

    `planner`/`checker` 是单测注入点（合成 plan / 合成 check 结果）；缺省走
    `core.assemble_plan.plan/check`（与 CLI `nf assemble --check` 同一份判据）。
    """
    ev: Dict[str, Any] = {"ok": False, "missing": [], "sample": None, "sample_kind": None,
                          "association": None, "check": None}
    plan_fn = planner or _requirement_for
    req, plan = plan_fn(pkg, name)
    pipe = str((plan or {}).get("pipeline") or pkg.get("pipeline") or "")
    if not plan:
        ev["missing"].append("M1b：分支 b 不可用——无法从包声明推出装配计划/允许集")
        return ev
    from core import assemble_plan as ap
    check_fn = checker or ap.check
    near: List[str] = []
    for rel in _candidate_samples(root):
        text = _read_text(root / rel)
        if not text:
            continue
        if rel.startswith("library/"):
            kind = "library"
            row = _library_row(root, rel)
            cats = [str(c) for c in (pkg.get("categories") or [])]
            if not row:
                near.append("%s：未在 %s 在册" % (rel, LIBRARY_INDEX_REL))
                continue
            if pipe and pipe not in row:
                near.append("%s：台账行未声明本包管线 %s" % (rel, pipe))
                continue
            if name not in row and not any(c and c in row for c in cats):
                near.append("%s：台账行未指认本包（包名/类别）" % rel)
                continue
            assoc = {"ok": True, "ledger": LIBRARY_INDEX_REL, "field": "条目 %s 的表格行"
                     % Path(rel).stem}
        else:
            kind = "docs"
            tokens = set(_PIPELINE_TOKEN.findall(text))
            if not pipe or pipe not in tokens:
                near.append("%s：样本未明确声明本包管线 %s" % (rel, pipe or "（未声明）"))
                continue
            hits = _provenance_hits(root, rel)
            if not hits:
                near.append("%s：provenance/协议台账未指认该样本路径" % rel)
                continue
            assoc = {"ok": True, "ledger": hits[0]["ledger"], "field": hits[0]["field"],
                     "hits": hits}
        try:
            issues, stats = check_fn(text, plan, expected_pipeline=pipe)
        except Exception as exc:                               # noqa: BLE001 - 同源执行异常如实报
            near.append("%s：assemble --check 执行异常：%s" % (rel, exc))
            continue
        if issues:
            near.append("%s：未过 assemble --check（%s）" % (rel, "；".join(issues[:2])))
            continue
        ev.update({"ok": True, "sample": rel, "sample_kind": kind, "association": assoc,
                   "check": {"issues": [], "segments": (stats or {}).get("segments")}})
        return ev
    if not ev["missing"]:
        ev["missing"].append(
            "M1b：无可验收产物证据（a) outputs/INDEX.json 缺失/未过机检；b) 无与包关联且通过 "
            "nf assemble --check 的官方样本%s）"
            % ("；候选：" + "；".join(near[:2]) if near else ""))
    return ev


def m1_evidence(root: Any, name: str, gate: Optional[Dict[str, Any]],
                pkg: Optional[Dict[str, Any]] = None,
                sample_probe: Optional[Callable[..., Dict[str, Any]]] = None,
                ) -> Dict[str, Any]:
    """M1：机检无 FAIL + 可验收产物证据（a: INDEX 在册并逐件过 output check；b: 样本过
    assemble --check）。两分支任一成立即算有证据，机检门槛不降。"""
    r = _root(root)
    missing: List[str] = []
    if not _gate_ok(gate):
        failed = []
        for n in MACHINE_CHECKS:
            rec = ((gate or {}).get("checks") or {}).get(str(n)) or {}
            if str(rec.get("status") or "ERROR") not in ("PASS", "WARN"):
                failed.append(str(n))
        missing.append("M1：机检未全绿（check %s 非绿；同源判据见 nf verify）"
                       % (",".join(failed) or "机器面不可用"))
    index_ev = _index_evidence(r, name)
    sample_ev: Optional[Dict[str, Any]] = None
    branch: Optional[str] = None
    if index_ev["ok"]:
        branch = "index"
    else:
        sample_ev = (sample_probe(r, name, pkg or {}) if sample_probe is not None
                     else _sample_evidence(r, name, pkg or {}))
        if sample_ev.get("ok"):
            branch = "sample"
    ok = bool(_gate_ok(gate) and branch)
    if not ok:
        missing += list(index_ev.get("missing") or [])
        if sample_ev is not None:
            missing += list(sample_ev.get("missing") or [])
    ev: Dict[str, Any] = {"ok": ok, "branch": branch, "missing": missing,
                          "index": bool(index_ev.get("present")),
                          "outputs": int(index_ev.get("outputs") or 0),
                          "outputs_checked": int(index_ev.get("checked") or 0),
                          "index_evidence": index_ev,
                          "sample_evidence": sample_ev}
    if branch == "sample" and sample_ev:
        ev["sample"] = sample_ev.get("sample")
        ev["sample_kind"] = sample_ev.get("sample_kind")
        ev["association"] = sample_ev.get("association")
        ev["sample_check"] = sample_ev.get("check")
    return ev



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
             pkg: Optional[Dict[str, Any]] = None, parse_error: str = "",
             sample_probe: Optional[Callable[..., Dict[str, Any]]] = None) -> Dict[str, Any]:
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
        m1 = m1_evidence(root, name, gate, pkg=pkg, sample_probe=sample_probe)
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
            runner: Optional[Callable[[Path], Dict[str, Any]]] = None,
            sample_probe: Optional[Callable[..., Dict[str, Any]]] = None) -> Dict[str, Any]:
    """全仓 → 成熟度文档（`nf-domain-maturity/1`）。

    `gate` / `runner` / `sample_probe` 都是注入点（单测不跑整仓、不依赖真实样本）；
    缺省走同源判据。
    """
    r = _root(root)
    names = list(packages) if packages is not None else discover_packages(r)
    gate_doc = gate if gate is not None else machine_gate(r, runner=runner)
    rows: List[Dict[str, Any]] = []
    for name in names:
        pkg, parse_error = _package_doc(r, name)
        rows.append(evaluate(r, name, gate_doc, pkg=pkg, parse_error=parse_error,
                             sample_probe=sample_probe))
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
