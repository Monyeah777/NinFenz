"""集成面（integrations）：把 NF 的**接入面**做成可机检的目录（真源 + 人读投影）。

为什么需要（内部差距实证 2026-10-05）：NF 的接入面已有一批（MCP / LSP / CLI / TUI / 图书馆 raw /
Agent Skill / AGENTS 规则出口 / CCV3 出口 / npm 启动器 / Rust 快线 / .NET 引擎 / A2A 卡片），
但它们散在 README 表、docs/*、各子目录 README 与导出物里——**没有一处能回答「NF 现在有哪些
接入面、各自入口是什么、件还在不在」**。本模块把接入面做成三件可证的事：

1. 真源 integrations/<id>/integration.json（描述件：kind / status / 入口 / 文档 / 证据）；
2. 人读投影 integrations/README.md 的生成区（nf:integrations 标记，逐字对账）；
3. 判据（check38 子扫描）：描述件可解析 / id 唯一且与目录同名 / 词表封闭 / 入口与文档与证据件
   **真实在场** / 投影 == 实时渲染 / 无孤儿目录。

纪律：纯标准库；只读；无网络；同输入同输出；缺件/空根如实报 issue 不裸崩。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Tuple
from core import json_doc

DIR = "integrations"
INDEX_REL = "integrations/README.md"
BEGIN = "<!-- nf:integrations:begin -->"
END = "<!-- nf:integrations:end -->"
SCHEMA = "nf-integration/1"
KINDS = ("server", "client", "cli", "library", "editor", "package", "export", "collection")
STATUSES = ("active", "proposed", "deprecated")
REQUIRED = ("schema", "id", "title", "kind", "status", "version", "codeowner", "tier",
            "entry", "docs", "evidence")
SCHEMA_ID = "https://ninfenz.dev/schema/integration.schema.json"
STRINGS_SCHEMA_ID = "https://ninfenz.dev/schema/integration_strings.schema.json"
STRINGS_NAME = "strings.json"
#: 多字符类 + 必需字面量：**必须带「不在类内」的负向后顾**（2026-10-10 ReDoS 扫描扫出）——
#: 否则在长 token 上每个起点各回溯一遍 ⇒ O(n²)（实测 64 KB 纯字母数字 3.2 s）。后顾只让
#: 起点落在 token 首字符，匹配结果与「取最大 token」等价。
_PATH_TOKEN = re.compile(
    r"(?<![A-Za-z0-9_./\\-])[A-Za-z0-9_./\\-]+\\.(?:py|sh|ps1|cmd|mjs|js|json|md|csproj|toml)")
#: entry.command 里的 `nf <子命令>`（`python scripts/nf.py <子>` 与裸 `nf <子>` 两种形态）
_NF_SUBCMD = re.compile(r"(?:\bpython\s+scripts/nf\.py|\bnf)\s+([a-z][a-z0-9-]*)")


def _nf_subcommand(command: str) -> str:
    """→ command 里的第一个 nf 子命令；没有（或只是 --flag）返回空串。"""
    m = _NF_SUBCMD.search(command or "")
    return m.group(1) if m else ""


def entries(root: str = ".") -> List[Dict[str, Any]]:
    """在场接入面描述件（按目录名排序；坏件也返回，由 check 如实报）。"""
    d = Path(root) / DIR
    out: List[Dict[str, Any]] = []
    if not d.is_dir():
        return out
    for sub in sorted(p for p in d.iterdir() if p.is_dir()):
        f = sub / "integration.json"
        if not f.is_file():
            out.append({"id": sub.name, "rel": DIR + "/" + sub.name, "_missing": True})
            continue
        rec: Dict[str, Any] = {"rel": DIR + "/" + sub.name}
        try:
            rec.update(json_doc.load(f, dict, what=f.name))
        except (OSError, ValueError) as exc:
            rec["_bad"] = str(exc)
        out.append(rec)
    return out


def render_index(root: str = ".") -> str:
    """人读投影（生成区内容）：接入面一张表，逐条给入口与文档。"""
    rows = ["| id | 面 | 类型 | 状态 | 版本 | 责任方 | 入口 | 文档 |",
            "|---|---|---|---|---|---|---|---|"]
    for e in entries(root):
        if e.get("_missing") or e.get("_bad"):
            rows.append("| " + str(e.get("id", "?")) + " | — | — | — | （坏件/缺件） | — |")
            continue
        entry = e.get("entry") or {}
        cmd = entry.get("command") or entry.get("path") or ""
        docs = e.get("docs") or []
        rows.append("| " + str(e.get("id", "?")) + " | " + str(e.get("title", ""))
                    + " | " + str(e.get("kind", "")) + " | " + str(e.get("status", ""))
                    + " | " + str(e.get("version", "")) + " | " + str(e.get("codeowner", ""))
                    + " | " + cmd + " | " + " · ".join(str(d) for d in docs) + " |")
    return "\n".join(rows)


def _schema_gate(root: str, schema_id: str, hint: str, label: str):
    schema = None
    issues: List[str] = []
    try:
        from core import schema_lint as _sl
        schema = _sl.load_schema(root, schema_id)
        if schema is None:
            issues.append("缺%s（%s；修复指引：%s）" % (label, schema_id, hint))
    except Exception as exc:
        issues.append("%s 校验不可用：%s" % (label, exc))
    return schema, issues


def _record_issues(rel: str, e: Dict[str, Any], seen: Dict[str, str]) -> List[str]:
    issues: List[str] = []
    if e["schema"] != SCHEMA:
        issues.append(rel + " schema 应为 " + SCHEMA + "（实为 " + str(e["schema"]) + "）")
    if str(e["id"]) != Path(rel).name:
        issues.append(rel + " id=" + str(e["id"]) + " 与目录名不一致（修复指引：id 即目录名）")
    if e["id"] in seen:
        issues.append("接入面 id 重复：" + str(e["id"]) + "（" + seen[e["id"]] + " 与 " + rel + "）")
    if e["kind"] not in KINDS:
        issues.append(rel + " kind 越出词表：" + str(e["kind"]) + "（词表：" + "/".join(KINDS) + "）")
    if e["status"] not in STATUSES:
        issues.append(rel + " status 越出词表：" + str(e["status"])
                      + "（词表：" + "/".join(STATUSES) + "）")
    return issues


def _schema_subset_issues(rel: str, e: Dict[str, Any], schema: Any) -> List[str]:
    from core import schema_lint as _sl2
    desc = {k: v for k, v in e.items() if k != "rel" and not k.startswith("_")}
    return ["%s 越出 integration schema：%s" % (rel, _v)
            for _v in _sl2.subset_validate(desc, schema, rel)]


def _subcommand_issues(r: Path, rel: str, command: str) -> List[str]:
    sub = _nf_subcommand(command)
    if not sub:
        return []
    try:
        from core import prose_lint
        known = prose_lint.cli_commands(str(r))
    except Exception:
        known = set()
    if known and sub not in known:
        return [rel + " entry.command 的 nf 子命令未注册：" + sub
                + "（修复指引：核对 scripts/nf.py 的 argparse 面）"]
    return []


def _entry_issues(r: Path, rel: str, e: Dict[str, Any]) -> List[str]:
    issues: List[str] = []
    entry = e["entry"] if isinstance(e["entry"], dict) else {}
    if not (entry.get("command") or entry.get("path")):
        issues.append(rel + " entry 缺 command/path（修复指引：给可跑的入口或路径锚）")
    if entry.get("path") and not (r / str(entry["path"])).exists():
        issues.append(rel + " entry.path 不在场：" + str(entry["path"]))
    for tok in _PATH_TOKEN.findall(str(entry.get("command") or "")):
        if not (r / tok).exists():
            issues.append(rel + " entry.command 引用的件不在场：" + tok)
    # 命令里的 **nf 子命令**也要在册（2026-10-08 补）：此前只查「引用的件在不在场」——
    # 子命令名**拼错一个字母**时件仍都在场、判据全绿，用户照卡敲才发现命令不存在。
    issues += _subcommand_issues(r, rel, str(entry.get("command") or ""))
    return issues


def _ref_issues(r: Path, rel: str, e: Dict[str, Any]) -> List[str]:
    issues: List[str] = []
    for key in ("docs", "evidence"):
        vals = e[key] if isinstance(e[key], list) else [e[key]]
        for v in vals:
            if not str(v).strip():
                issues.append(rel + " " + key + " 含空项")
            elif not (r / str(v)).exists():
                issues.append(rel + " " + key + " 不在场：" + str(v))
    return issues


def _rec_issues(r: Path, rel: str, e: Dict[str, Any], schema: Any,
                seen: Dict[str, str], kinds: List[str]) -> List[str]:
    if e.get("_missing"):
        return [rel + " 缺 integration.json（修复指引：补齐描述件，或删掉该目录）"]
    if e.get("_bad"):
        return [rel + " integration.json 不可解析：" + e["_bad"]]
    miss = [k for k in REQUIRED if k not in e]
    if miss:
        return [rel + " 缺字段：" + "、".join(miss)]
    issues: List[str] = _record_issues(rel, e, seen)
    seen[e["id"]] = rel
    kinds.append(str(e["kind"]))
    if schema is not None:
        issues += _schema_subset_issues(rel, e, schema)
    issues += _entry_issues(r, rel, e)
    issues += _ref_issues(r, rel, e)
    return issues


def _recs_issues(root: str, recs: List[Dict[str, Any]], schema: Any,
                 seen: Dict[str, str], kinds: List[str]) -> List[str]:
    r = Path(root)
    issues: List[str] = []
    for e in recs:
        issues += _rec_issues(r, e["rel"], e, schema, seen, kinds)
    return issues


def _locales_want(root: str) -> set:
    try:
        from core import locales as _lc
        reg, _ = _lc.registry(root)
        return {str(x.get("id", "")).lower() for x in ((reg or {}).get("locales") or [])}
    except Exception:
        return set()


def _locale_diff_issues(sid: str, missing: set, extra: set) -> List[str]:
    issues: List[str] = []
    if missing:
        issues.append(DIR + "/" + sid + " strings 缺语言：" + "、".join(sorted(missing)))
    if extra:
        issues.append(DIR + "/" + sid + " strings 多出未注册语言：" + "、".join(sorted(extra))
                      + "（修复指引：与 protocol/locales.json 对齐）")
    return issues


def _strings_data_issues(sid: str, sdata: Dict[str, Any], str_schema: Any,
                         want: set) -> List[str]:
    issues: List[str] = []
    if str_schema is not None:
        from core import schema_lint as _sl3
        for _v in _sl3.subset_validate(sdata, str_schema, DIR + "/" + sid + "/" + STRINGS_NAME):
            issues.append(DIR + "/" + sid + " strings 越界：" + _v)
    got = {str(k).lower() for k in (sdata.get("locales") or {})}
    if want and got != want:
        issues += _locale_diff_issues(sid, want - got, got - want)
    return issues


def _strings_issues(root: str, e: Dict[str, Any], str_schema: Any, want: set) -> List[str]:
    if e.get("_missing") or e.get("_bad") or "id" not in e:
        return []
    sid = str(e["id"])
    sf = Path(root) / DIR / sid / STRINGS_NAME
    if not sf.is_file():
        return [DIR + "/" + sid + " 缺 " + STRINGS_NAME
                + "（修复指引：逐语言 title/summary；语言集见 protocol/locales.json）"]
    try:
        sdata = json_doc.load(sf, dict, what=sf.name)
    except (OSError, ValueError) as exc:
        return [DIR + "/" + sid + " " + STRINGS_NAME + " 不可解析：" + str(exc)]
    return _strings_data_issues(sid, sdata, str_schema, want)


def _index_issues(root: str) -> List[str]:
    idx = Path(root) / INDEX_REL
    if not idx.is_file():
        return ["缺接入面人读投影 " + INDEX_REL + "（修复指引：加 " + BEGIN + " / " + END
                + " 生成区）"]
    txt = idx.read_text(encoding="utf-8")
    m = re.search(re.escape(BEGIN) + r"\n(.*?)\n" + re.escape(END), txt, re.S)
    if not m:
        return [INDEX_REL + " 缺生成区标记（" + BEGIN + " / " + END + "）"]
    if m.group(1).strip() != render_index(root).strip():
        return [INDEX_REL + " 生成区与实时渲染不一致（修复指引：按 render_index 重出该区）"]
    return []


def check(root: str = ".") -> Tuple[List[str], Dict[str, Any]]:
    """接入面机检（check38 子扫描口径）。缺根如实报 issue，不裸崩。"""
    r = Path(root)
    if not (r / "verify.sh").is_file():
        return (["读不到仓库根（缺 verify.sh）——接入面须在 NF 仓库根运行"], {})
    issues: List[str] = []
    recs = entries(root)
    if not recs:
        issues.append("缺接入面目录 " + DIR + "/（修复指引：每个接入面一个子目录 + integration.json"
                      "；字段见 core/integrations.py::REQUIRED）")
    seen: Dict[str, str] = {}
    kinds: List[str] = []
    # 配置即契约：描述件必须过 protocol/schema/integration.schema.json（缺 schema 即红）。
    _schema, schema_issues = _schema_gate(
        str(r), SCHEMA_ID, "protocol/schema/integration.schema.json", "接入面 schema")
    issues += schema_issues
    issues += _recs_issues(root, recs, _schema, seen, kinds)
    # 每接入面的本地化字符串（HA strings.json 同型）：在场 + 过 schema + 语言集 == 注册语言
    _want = _locales_want(root)
    _str_schema, strings_schema_issues = _schema_gate(
        str(r), STRINGS_SCHEMA_ID,
        "protocol/schema/integration_strings.schema.json", "接入面字符串 schema")
    issues += strings_schema_issues
    for e in recs:
        issues += _strings_issues(root, e, _str_schema, _want)
    issues += _index_issues(root)
    return issues, {"count": len([x for x in recs
                                  if not x.get("_missing") and not x.get("_bad")]),
                    "ids": sorted(seen), "kinds": sorted(set(kinds))}


def localized(root: str = ".", integration_id: str = "", locale: str = "zh") -> Dict[str, str]:
    """取某接入面某语言的字符串（缺件缺语言返回空 dict——调用方自行兜底，不臆造）。"""
    p = Path(root) / DIR / integration_id / STRINGS_NAME
    try:
        data = json_doc.load(p, dict, what=p.name)
    except (OSError, ValueError):
        return {}
    loc = (data.get("locales") or {}).get(locale) or {}
    return {k: str(v) for k, v in loc.items()}


#: 扫描器统一入口名（与 repo_stats / release_gate / locales 一致）。
scan = check
