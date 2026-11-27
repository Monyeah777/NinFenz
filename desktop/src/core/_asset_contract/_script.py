"""asset_contract 私有子模块 _script：脚本面与包清单面：nf-io 双源、字面路径、链对齐、outputs/INDEX 对账。

门面 core.asset_contract 按原 API 重新导出；本文件只承载实现，不改变对外面。
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

from ._base import _read, _strict_json, resolve
from ._code import _dotted
from ._const import LANGS, _IO_RE



# ---------------------------------------------------------------- 脚本面
def parse_io_header(text: str) -> Optional[Dict[str, List[str]]]:
    """解析脚本自带 nf-io 头 → {"inputs": [...], "outputs": [...]}；没有头返回 None。

    格式（三种语言同一写法，注释符不同）：# nf-io: inputs=a,b outputs=c；- 表示空。
    """
    m = _IO_RE.search(text)
    if not m:
        return None
    out: Dict[str, List[str]] = {"inputs": [], "outputs": []}
    for token in m.group(1).split():
        if "=" not in token:
            continue
        key, val = token.split("=", 1)
        key = key.strip().lower()
        if key not in out:
            continue
        out[key] = [] if val.strip() in ("-", "") else \
            [x.strip() for x in val.split(",") if x.strip()]
    return out



def observed_paths(text: str, lang: str) -> List[str]:
    """脚本里**字面量**形式的文件路径（可证的那部分；变量拼出来的不判）。"""
    out: List[str] = []
    if lang == "python":
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return out
        for n in ast.walk(tree):
            if not isinstance(n, ast.Call):
                continue
            if _dotted(n.func) not in ("open", "Path", "pathlib.Path"):
                continue
            for a in n.args:
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    out.append(a.value)
    elif lang == "bash":
        for m in re.finditer(r">>?[ \t]*([^\s;|&()]+)|<[ \t]*([^\s;|&()]+)", text):
            out.append(m.group(1) or m.group(2) or "")
    elif lang == "powershell":
        # `#` 注释与 bash 同形（parse_io_header 已覆盖）；路径取字面量的重定向/读写 cmdlet。
        for m in re.finditer(r"(?:>>?|Out-File|Set-Content|Add-Content|Get-Content|Import-Csv)"
                             r"[ \t]+([^\s;|&()\[\]$]+)", text):
            out.append(m.group(1))
    elif lang == "vba":
        for m in re.finditer(r'(?i)\bOpen\s+"([^"]+)"', text):
            out.append(m.group(1))
    skip = {"/dev/null", "/dev/stdin", "/dev/stdout", "-"}
    return [p for p in out if p and p not in skip and not p.startswith("$")]



def _check_script(root: str, spec: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any]]:
    sid = str(spec.get("id") or spec.get("path") or "?")
    lang = str(spec.get("lang") or "")
    if lang not in LANGS:
        return (["脚本契约 %s 的 lang=%r 不在词表 %s（修复指引：改用词表内语言）"
                 % (sid, lang, "/".join(LANGS))], {})
    rel = str(spec.get("path") or "")
    if not (Path(root) / rel).is_file():
        return (["脚本契约 %s 的件不在场：%s（修复指引：修正 path）" % (sid, rel)], {"files": 0})
    text, err = _read(root, rel)
    if err:
        return [err], {"files": 1}
    text = text or ""
    issues: List[str] = []
    header = parse_io_header(text)
    if header is None:
        issues.append("脚本 %s 未自带 nf-io 头（修复指引：顶部加一行注释 # nf-io: inputs=a,b "
                      "outputs=c；VBA 用单引号起头——脚本契约必须双源）" % rel)
        header = {"inputs": [], "outputs": []}
    for key in ("inputs", "outputs"):
        declared = list(spec.get(key) or [])
        embedded = list(header.get(key) or [])
        if declared != embedded:
            issues.append("脚本 %s 的 %s 双源不一致：声明=%s / 头=%s（修复指引：让两边逐字一致）"
                          % (rel, key, declared, embedded))
    declared_all = set(spec.get("inputs") or []) | set(spec.get("outputs") or [])
    extra = sorted({x for x in observed_paths(text, lang) if x not in declared_all})
    if extra:
        issues.append("脚本 %s 出现未声明的字面路径 %s（修复指引：补进 inputs/outputs 或去掉硬编码"
            "）"
                      % (rel, ",".join(extra[:3])))
    return issues, {"files": 1, "inputs": len(spec.get("inputs") or []),
                    "outputs": len(spec.get("outputs") or [])}



def _check_index(root: str, spec: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any]]:
    """S1 包自述契约：读包自己的 `outputs/INDEX.json`，与**磁盘实况**双向对账。

    为什么归到「资产契约」：包清单（`nf-output-index/1`）本就是**包自带**的产出面契约
    （path / form / tier / role / schema / inputs）。NF 侧再拿 glob 猜一遍就是两套词表；本判据让
    **声明**与**实况**互相对齐——声明的件必须在场，`outputs/` 下的实况必须都被声明。
    """
    sid = str(spec.get("id") or "?")
    rels = resolve(root, spec)
    if not rels:
        return ["包清单契约 %s 未命中任何清单（修复指引：修正 glob）" % sid], {"files": 0}
    issues: List[str] = []
    declared_total = 0
    for rel in rels:
        text, err = _read(root, rel)
        if err:
            issues.append(err)
            continue
        try:
            doc = _strict_json(text)
        except ValueError as exc:
            issues.append("包清单 %s 不是合法 JSON：%s（修复指引：重跑 nf domain build）"
                          % (rel, exc))
            continue
        base = Path(rel).parent.parent          # <包>/outputs/INDEX.json → <包>
        outs = doc.get("outputs")
        if not isinstance(outs, list) or not outs:
            issues.append("包清单 %s 的 outputs 为空（修复指引：重跑 nf domain build）" % rel)
            continue
        declared = set()
        for item in outs:
            if not isinstance(item, dict):
                continue
            pth = str(item.get("path") or "")
            if not pth:
                issues.append("包清单 %s 有一条无 path 的声明（修复指引：补 path）" % rel)
                continue
            declared.add(pth)
            declared_total += 1
            if not (Path(root) / base / pth).is_file():
                issues.append("包清单 %s 声明的 %s 不在场"
                              "（修复指引：补件或重跑 nf domain build）" % (rel, pth))
            sch = str(item.get("schema") or "")
            if sch and not (Path(root) / base / sch).is_file():
                issues.append("包清单 %s 声明的 schema %s 不在场（修复指引：补件）" % (rel, sch))
            ins = item.get("inputs") or ((item.get("recompute") or {}).get("inputs") or [])
            for inp in ins:
                if not (Path(root) / base / str(inp)).is_file():
                    issues.append("包清单 %s 声明的输入 %s 不在场"
                                  "（修复指引：补件或改声明）" % (rel, inp))
        on_disk = {q.relative_to(Path(root) / base).as_posix()
                   for q in sorted((Path(root) / base / "outputs").rglob("*"))
                   if q.is_file() and not q.is_symlink()}
        self_rel = Path(rel).relative_to(base).as_posix()   # 清单自身不是产出面（它是清单）
        missing = sorted(x for x in on_disk
                         if x not in declared and x != self_rel
                         and not x.startswith("outputs/samples/"))
        if missing:
            issues.append("包清单 %s 未声明 %d 件实况（例 %s）"
                          "（修复指引：重跑 nf domain build 让清单与实况同步）"
                          % (rel, len(missing), "、".join(missing[:3])))
    return issues, {"files": len(rels), "declared": declared_total}



def _check_chain(specs: Dict[str, Dict[str, Any]], chain: Dict[str, Any]
                 ) -> Tuple[List[str], Dict[str, Any]]:
    a_id, b_id = str(chain.get("from") or ""), str(chain.get("to") or "")
    if a_id not in specs or b_id not in specs:
        return (["链 %s→%s 的端点未在脚本面登记（修复指引：先登记两端脚本契约）" % (a_id,
 b_id)],
 {})
    a, b = specs[a_id], specs[b_id]
    ao = [str(x).replace("\\", "/") for x in a.get("outputs") or []]
    bi = [str(x).replace("\\", "/") for x in b.get("inputs") or []]
    issues: List[str] = []
    feeds = chain.get("feeds") or []
    if feeds:
        for f in feeds:
            out_p = str(f.get("output") or "").replace("\\", "/")
            in_p = str(f.get("input") or "").replace("\\", "/")
            if out_p not in ao:
                issues.append("链 %s→%s：上游未声明产物 %s（修复指引：补进上游 outputs）"
                              % (a_id, b_id, out_p))
            if in_p not in bi:
                issues.append("链 %s→%s：下游未声明该输入 %s（修复指引：补进下游 inputs）"
                              % (a_id, b_id, in_p))
            if out_p != in_p:
                issues.append("链 %s→%s：产物路径不对齐（上游 %s vs 下游 %s）（修复指引：统一路径写"
                    "法）"
                              % (a_id, b_id, out_p, in_p))
    elif not set(ao) & set(bi):
        issues.append("链 %s→%s：上游产物与下游输入无交集（上游 %s / 下游 %s）（修复指引："
                      "契约未对齐——A 的输出必须匹配 B 的输入）"
                      % (a_id, b_id, ao[:3], bi[:3]))
    return issues, {"matched": len(set(ao) & set(bi))}
