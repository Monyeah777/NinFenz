#!/usr/bin/env python3
# ruff: noqa: E501, UP031
# nf-io: inputs=protocol/check_registry.json,verify.sh,scripts/nf.py,docs/verification-cards.md,protocol/gate_experts.json,docs/meta/VERSION-MATRIX.md outputs=-
"""判据登记册（架构方案 01：判据账本）。

为什么需要
----------
同一批 42 条 check 的清单散在四处、互不引用：`verify.sh`（执行体）、
`gate_engine`（引擎迁移面）、`scripts/nf.py` 的 `CHECK_GUIDE`（修复指引）、
`docs/verification-cards.md`（人读卡册）。2026-10-17 新增 check41/42 后，
**引擎那份漏了两条，4 天没有任何判据发现**。本模块把「判据宇宙」收成一份
单一真源 `protocol/check_registry.json`，并实现三条判据：

- **R1 清单一致**：登记册 id 集合 == 四处清单集合；差集点名到「哪处多/少」。FAIL。
- **R2 活性**：每条 check 的 `module.entry` 可解析（Python 可导入可调用；
  bash/脚本/测试面按在场性判定）；登记册字段必须真被代码读取（AST 反查）。
  灰度：违例先 WARN，累积两版后再升 FAIL。
- **R3 读面合规**：运行期观测到的实际读文件 ⊆ 声明 `reads`。**只在 memo 观测
  模式开启**（`NF_CHECK_REGISTRY_MEMO=1` / `nf verify --memo`），灰度 WARN。
- **#17 改基线须有实验单**：`*_baseline.json` 有改动时，`changes/unreleased/`
  必须有同日实验单，且四行齐全（假设/指标/阈值/回滚点）。FAIL。

纪律：只读（唯 `nf-io` 声明为无输出）；判据只判不写；同输入同输出；
修复指引进每条 issue 文案。判据接线在 `verify.sh` 的 check35（灰度第 1 版不新增
check 号，PASS 基线 76 不变），R3 另由 `nf verify --memo` 暴露。
"""

from __future__ import annotations

import ast
import datetime
import importlib
import json
import re
import subprocess  # nosec B404/B603/B607 —— 只跑只读 git，argv 列表、无 shell
from collections.abc import Sequence
from pathlib import Path
from typing import Any

REGISTRY_REL = "protocol/check_registry.json"
SCHEMA = "nf-check-registry/1"

#: 登记册每条 check 的必填字段（顺序即人读列序）。
FIELDS: tuple[str, ...] = (
    "id",
    "name",
    "module",
    "entry",
    "kind",
    "reads",
    "writes",
    "severity",
    "since",
    "experiment",
)
KINDS = ("prescriptive", "performance")
SEVERITIES = ("fail", "warn")

#: 四处清单名（R1 会逐个点名）。
SOURCES = ("verify_sh", "gate_engine", "check_guide", "cards")
SOURCE_HUMAN = {
    "verify_sh": "verify.sh 的 check 函数",
    "gate_engine": "gate_engine 引擎清单（REGISTRY ∪ PENDING）",
    "check_guide": "scripts/nf.py 的 CHECK_GUIDE",
    "cards": "docs/verification-cards.md 卡片索引",
}

_CHECK_FN = re.compile(r"^check(\d+)\(\)\{", re.M)
_BANNER = re.compile(r"\[(\d+)/(?:(\d+)·([ABCD])|(段[ABCD]))\]")
_TITLE_SEP = "（"
_VERSION_ROW = re.compile(r"verify v(\d+\.\d+) check1-(\d+)")


# ------------------------------------------------------------------ 基础读取


def _text(root: str, rel: str) -> str:
    return (Path(root) / rel).read_text(encoding="utf-8")


def load(root: str = ".") -> dict[str, Any]:
    """读登记册（走本仓唯一 JSON 读点 `core.json_doc`，形状不对即抛）。"""
    from core import json_doc

    return json_doc.load(Path(root) / REGISTRY_REL, dict, what=REGISTRY_REL)


def ids_of(doc: dict[str, Any]) -> set[int]:
    out: set[int] = set()
    for row in doc.get("checks") or []:
        if isinstance(row, dict) and isinstance(row.get("id"), int):
            out.add(int(row["id"]))
    return out


# ------------------------------------------------------------ 四处清单（真实来源）


def verify_sh_ids(root: str = ".") -> set[int]:
    text = _text(root, "verify.sh")
    return {int(m.group(1)) for m in _CHECK_FN.finditer(text)}


def gate_engine_ids(root: str = ".") -> set[int]:
    """引擎清单 = REGISTRY（已迁入）∪ PENDING（未迁入）——两条腿都算「引擎知道」。"""
    import sys

    root_p = Path(root).resolve()
    src = str(root_p / "desktop" / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    from core import gate_engine as ge

    ge.build_registry()
    return set(ge.REGISTRY) | set(ge.PENDING)


def check_guide_ids(root: str = ".") -> set[int]:
    """`scripts/nf.py` 的 CHECK_GUIDE（AST 取字面量，不执行 CLI 模块）。"""
    tree = ast.parse(_text(root, "scripts/nf.py"))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == "CHECK_GUIDE" for t in node.targets):
            continue
        value = ast.literal_eval(node.value)
        return {int(k) for k in value}
    return set()


def cards_ids(root: str = ".") -> set[int]:
    """卡册索引表 `| 12 | 段C | … |`（由 verify.sh 生成；只取索引区）。"""
    text = _text(root, "docs/verification-cards.md")
    try:
        head = text.split("## 卡片索引", 1)[1]
    except IndexError:
        return set()
    return {int(m.group(1)) for m in re.finditer(r"^\|\s*(\d+)\s*\|\s*段[ABCD]\s*\|", head, re.M)}


def four_lists(root: str = ".") -> dict[str, set[int]]:
    return {
        "verify_sh": verify_sh_ids(root),
        "gate_engine": gate_engine_ids(root),
        "check_guide": check_guide_ids(root),
        "cards": cards_ids(root),
    }


# ------------------------------------------------------------------ 字段派生


def _verify_text(root: str) -> str:
    return _text(root, "verify.sh")


def _banner_title(text: str, num: int) -> str:
    m = re.search(r"^check%d\(\)\{\s*\n\s*echo '([^']*)'" % num, text, re.M)
    if not m:
        return "check%d" % num
    title = m.group(1).strip()
    seg = re.match(r"^==\s*\[[^\]]+\]\s*(.*?)\s*==$", title)
    body = seg.group(1) if seg else title.strip().strip("=").strip()
    name = body.split(_TITLE_SEP, 1)[0].strip()
    return name or body or title


def _body_of(text: str, num: int) -> str:
    m = re.search(r"^check%d\(\)\{" % num, text, re.M)
    if not m:
        return ""
    nxt = re.search(r"^check\d+\(\)\{", text[m.end() :], re.M)
    end = m.end() + nxt.start() if nxt else len(text)
    return text[m.end() : end]


def _core_imports(body: str) -> list[tuple[str, str]]:
    """从 check 体收集 (module, alias)：覆盖单名 / 别名 / 括号元组 / 子模块导入。"""
    found: list[tuple[str, str]] = []
    for m in re.finditer(r"from core import \(([^)]*)\)", body):
        for piece in m.group(1).split(","):
            bits = piece.strip().split()
            if not bits:
                continue
            mod = bits[0]
            alias = bits[2] if len(bits) >= 3 and bits[1] == "as" else mod
            found.append((mod, alias))
    for m in re.finditer(
        r"from core import ([A-Za-z_][A-Za-z0-9_]*)"
        r"(?: as ([A-Za-z_][A-Za-z0-9_]*))?",
        body,
    ):
        found.append((m.group(1), m.group(2) or m.group(1)))
    for m in re.finditer(
        r"from core\.([A-Za-z_][A-Za-z0-9_]*) import "
        r"([A-Za-z_][A-Za-z0-9_]*)",
        body,
    ):
        found.append((m.group(1), m.group(2)))
    for m in re.finditer(r"import core\.([A-Za-z_][A-Za-z0-9_]*)", body):
        found.append((m.group(1), m.group(1)))
    seen: set[tuple[str, str]] = set()
    out = []
    for item in found:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _module_of(body: str, num: int) -> tuple[str, str]:
    """从 check 体派生实现模块/入口。

    口径（2026-10-22 实测）：
    - **恰一个** core 模块 → 该模块即实现（`core.asset_ledger.verify_root` 一类）；
    - **多个** core 模块 → 该 check 的实现是 verify.sh 里的**聚合编排**（如 check33/34/36），
      模块记为 `verify.sh`，入口 `checkN`（不把聚合体谎报成某一个子模块）；
    - 无 core 导入 → unittest / 独立脚本 / bash 原生三档依次判定。
    """
    imports = _core_imports(body)
    mods = sorted({mod for mod, _ in imports})
    if len(mods) == 1:
        mod = mods[0]
        alias = next(a for m, a in imports if m == mod)
        call = re.search(rf"\b{re.escape(alias)}\.([A-Za-z_][A-Za-z0-9_]*)\(", body)
        if call:
            return "core." + mod, call.group(1)
        direct = re.search(
            rf"from core\.{re.escape(mod)} import ([A-Za-z_][A-Za-z0-9_]*)", body
        )
        return "core." + mod, (direct.group(1) if direct else "scan")
    if len(mods) > 1:
        return "verify.sh", "check%d" % num
    tests = re.findall(r"-m unittest (tests\.[A-Za-z0-9_.]+)", body)
    if tests:
        return tests[0], "unittest"
    scripts = re.findall(r"scripts/([A-Za-z0-9_./-]+\.(?:py|sh))", body)
    if scripts:
        return "scripts/" + scripts[0], "main"
    return "verify.sh", "check%d" % num


def _reads_of(root: str, body: str, module: str) -> list[str]:
    """声明读面：优先用 gate_experts 的观测派生清单，否则从 check 体路径字面量推断。"""
    if module.startswith("core."):
        stem = module.split(".", 1)[1]
        try:
            experts = json.loads(_text(root, "protocol/gate_experts.json"))["experts"]
        except (OSError, ValueError, KeyError):
            experts = []
        for e in experts:
            if e.get("id") == stem:
                return sorted(str(x) for x in (e.get("reads") or []))
    base = Path(root)
    dirs: set[str] = set()
    #: 路径字面量切词：只许「ASCII 标识符 / 汉字 / . _ - * /」；遇到全角标点、反引号、
    #: 引号、括号即截断（实测 check20 的正文里 "04_模块库）：机读完备…" 会被吞进读面）。
    _bad = set("）)：；，、。！？（）【】「」《》`'\"“”‘’<>|,;")
    pat = re.compile(
        r"(?<![\w/.-])((?:0[1-9]_[^\s\"'()<>|,;]+|community|desktop|docs|"
        r"engine|integrations|library|packaging|protocol|results|scripts|"
        r"site|skills|tui)(?:/[^\s\"'()<>|,;]+){0,3})"
    )
    for m in pat.finditer(body):
        tok = m.group(1).strip("/")
        while tok and tok[-1] in _bad:
            tok = tok[:-1].strip("/")
        if not tok:
            continue
        stop = min((tok.find(ch) for ch in _bad if tok.find(ch) >= 0), default=-1)
        if stop >= 0:
            tok = tok[:stop].strip("/")
        parts = [p for p in tok.split("/") if p not in ("", ".", "..")]
        if not parts:
            continue
        candidate = "/".join(parts)
        full = base / candidate
        if full.is_file():
            dirs.add(candidate)
        elif full.is_dir():
            dirs.add(candidate + "/**")
        elif len(parts) > 1 and ("." in parts[-1]):
            dirs.add("/".join(parts[:-1]) + "/**")
        else:
            dirs.add(candidate + "/**")
        if len(dirs) >= 8:
            break
    return sorted(dirs)


def _since_map(root: str = ".") -> list[tuple[str, int]]:
    """从 VERSION-MATRIX 取 (verify 版本, 覆盖到第 N 条) 的阶梯表（按覆盖数升序）。"""
    try:
        text = _text(root, "docs/meta/VERSION-MATRIX.md")
    except OSError:
        return []
    rows = [(v, int(n)) for v, n in _VERSION_ROW.findall(text)]
    return sorted(rows, key=lambda r: r[1])


def _since_of(num: int, ladder: Sequence[tuple[str, int]], fallback: str) -> str:
    for ver, upto in ladder:
        if num <= upto:
            return "v" + ver
    return fallback


def _verify_version(root: str = ".") -> str:
    m = re.search(r"# 版本 : (v\d+\.\d+)", _verify_text(root))
    return m.group(1) if m else "?"


def category_of(body: str) -> str:
    """prescriptive = 静态结构断言；performance = 真跑代码/测试/脚本的结果断言。"""
    if "unittest" in body or re.search(r"scripts/[A-Za-z0-9_./-]+\.(?:py|sh)", body):
        return "performance"
    return "prescriptive"


def derive(root: str = ".") -> list[dict[str, Any]]:
    """从四处清单 + verify.sh 现文派生 42 条登记册条目（不手抄）。"""
    text = _verify_text(root)
    ids = sorted(verify_sh_ids(root))
    ladder = _since_map(root)
    fallback = _verify_version(root)
    out = []
    # experiment 是**人工预注册挂载点**（方案 01 §2.3）：生成器保留已填值，不重置；
    # 其余字段一律由四处清单/verify.sh 现文派生（不手抄）。`--check` 因此稳定。
    kept: dict[int, str] = {}
    try:
        for row in load(root).get("checks") or []:
            if (
                isinstance(row, dict)
                and isinstance(row.get("experiment"), str)
                and row.get("experiment")
            ):
                kept[int(row["id"])] = row["experiment"]
    except (OSError, ValueError):
        kept = {}
    for num in ids:
        body = _body_of(text, num)
        module, entry = _module_of(body, num)
        if module == "verify.sh":  # bash 原生判据：入口就是 verify.sh 的 checkN()
            entry = "check%d" % num
        out.append(
            {
                "id": num,
                "name": _banner_title(text, num),
                "module": module,
                "entry": entry,
                "kind": category_of(body),
                "reads": _reads_of(root, body, module),
                "writes": [],
                "severity": "fail",
                "since": _since_of(num, ladder, fallback),
                "experiment": kept.get(num),
            }
        )
    return out


# ------------------------------------------------------------------ R1 清单一致


def consistency(
    root: str = ".", doc: dict[str, Any] | None = None
) -> tuple[list[str], dict[str, Any]]:
    """R1：登记册 id 集合必须与四处清单逐一相等（差集点名到具体缺/多）。

    `doc` 仅供变异测试注入（生产路径恒为 None ⇒ 读在盘登记册）。
    """
    issues: list[str] = []
    try:
        doc = load(root) if doc is None else doc
    except (OSError, ValueError) as exc:
        return (
            [
                f"判据账本 R1：读不到登记册 {REGISTRY_REL}（{exc}）——修复指引：python "
                "scripts/gen_check_registry.py --write"
            ],
            {},
        )
    problems = validate(doc)
    if problems:
        return (["判据账本 R1：登记册不合 schema——" + "；".join(problems[:4])], {})
    target = ids_of(doc)
    try:
        lists = four_lists(root)
    except Exception as exc:
        return (
            [
                f"判据账本 R1：四处清单读取失败（{type(exc).__name__}: {exc}）——修复指引：核对 verify.sh / "
                "gate_engine / nf.py CHECK_GUIDE / 卡册"
            ],
            {},
        )
    stats = {"registry": len(target)}
    for name in SOURCES:
        got = lists[name]
        stats[name] = len(got)
        missing = sorted(target - got)  # 登记册有、该处没有
        extra = sorted(got - target)  # 该处有、登记册没有
        if missing or extra:
            bits = []
            if missing:
                bits.append("少 {}".format(",".join(map(str, missing))))
            if extra:
                bits.append("多 {}".format(",".join(map(str, extra))))
            issues.append(
                "判据账本 R1：{}与登记册不一致（{}）——修复指引：对齐后重跑 "
                "python scripts/gen_check_registry.py --write".format(
                    SOURCE_HUMAN[name], "；".join(bits)
                )
            )
    return issues, stats


# ------------------------------------------------------------------ R2 活性


def _importable(module: str, entry: str, root: str = ".") -> tuple[bool, str]:
    """module.entry 是否可解析可调用（Python 导入；脚本/测试/bash 按在场性判定）。"""
    import sys

    root_p = Path(root).resolve()
    if module == "verify.sh":
        fn = re.search(rf"^{re.escape(entry)}\(\)\{{", _verify_text(root), re.M)
        return (bool(fn), "" if fn else f"verify.sh 里缺 {entry}()")
    if module.startswith("scripts/"):
        p = root_p / module
        return (p.is_file(), "" if p.is_file() else f"缺 {module}")
    if module.startswith("tests."):
        p = root_p / "desktop" / "tests" / (module.split(".", 1)[1] + ".py")
        return (
            p.is_file(),
            "" if p.is_file() else "缺 desktop/tests/{}.py".format(module.split(".", 1)[1]),
        )
    src = str(root_p / "desktop" / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    try:
        mod = importlib.import_module(module)
    except Exception as exc:
        return (False, f"import 失败：{type(exc).__name__}: {exc}")
    fn = getattr(mod, entry, None)
    if not callable(fn):
        return (False, f"{module} 里没有可调用入口 {entry}")
    return (True, "")


def _field_reads(root: str) -> dict[str, int]:
    """AST 反查：登记册字段名在代码面（desktop/src / scripts / tools）出现次数。"""
    counts = dict.fromkeys(FIELDS, 0)
    paths: list[Path] = []
    for rel in ("desktop/src", "scripts", "tools"):
        base = Path(root) / rel
        if base.is_dir():
            paths.extend(base.rglob("*.py"))
    for p in paths:
        try:
            tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in counts:
                counts[node.attr] += 1
            elif isinstance(node, ast.Subscript):
                sl = node.slice
                if (
                    isinstance(sl, ast.Constant)
                    and isinstance(sl.value, str)
                    and sl.value in counts
                ):
                    counts[sl.value] += 1
            elif (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and node.value in counts
            ):
                counts[node.value] += 1
    return counts


def activity(
    root: str = ".", doc: dict[str, Any] | None = None
) -> tuple[list[str], dict[str, Any]]:
    """R2：module.entry 可解析 + 字段真被读。灰度：违例 WARN。"""
    warns: list[str] = []
    try:
        doc = load(root) if doc is None else doc
    except (OSError, ValueError) as exc:
        return ([f"判据账本 R2：读不到登记册（{exc}）"], {})
    rows = [r for r in (doc.get("checks") or []) if isinstance(r, dict)]
    bad_impl, bad_field = 0, []
    for row in rows:
        module, entry = str(row.get("module") or ""), str(row.get("entry") or "")
        ok, why = _importable(module, entry, root)
        if not ok:
            bad_impl += 1
            warns.append(
                "判据账本 R2：check{} 的 {}.{} 不可用（{}）".format(
                    row.get("id"), module, entry, why
                )
            )
    counts = _field_reads(root)
    for f in FIELDS:
        if counts.get(f, 0) <= 0:
            bad_field.append(f)
            warns.append(
                f"判据账本 R2：字段 {f!r} 无任何代码读取（死字段）——修复指引：接线或"
                "从 schema 删除"
            )
    return warns, {
        "entries": len(rows),
        "bad_impl": bad_impl,
        "dead_fields": bad_field,
        "field_reads": counts,
    }


# ------------------------------------------------------------------ R3 读面合规


def read_surface(
    root: str = ".", doc: dict[str, Any] | None = None
) -> tuple[list[str], dict[str, Any]]:
    """R3：运行期观测读面 ⊆ 声明 reads（观测源 = subcheck_cache 的先验读面表）。

    只在 memo 观测模式开启：没有观测就如实报「未观测」，不假装合规。
    """
    from core import gate_faces as gf
    from core import subcheck_cache as sc

    warns: list[str] = []
    observed = 0
    skipped: list[int] = []
    try:
        doc = load(root) if doc is None else doc
    except (OSError, ValueError) as exc:
        return ([f"判据账本 R3：读不到登记册（{exc}）"], {})
    for row in [r for r in (doc.get("checks") or []) if isinstance(r, dict)]:
        num = row.get("id")
        decl = [str(x) for x in (row.get("reads") or [])]
        face = sc.read_face(root, f"check{num}")
        if not face or not face.get("files"):
            skipped.append(int(num) if isinstance(num, int) else -1)
            continue
        observed += 1
        if not decl:
            warns.append(
                "判据账本 R3：check%s 有运行期读面但未声明 reads（%d 件）"
                % (num, len(face["files"]))
            )
            continue
        out = [rel for rel in face["files"] if not gf.covered(rel, decl)]
        if out:
            warns.append(
                "判据账本 R3：check%s 读到声明读面之外 %d 件：%s"
                % (num, len(out), "、".join(out[:5]))
            )
    return warns, {"observed": observed, "skipped": len(skipped)}


# --------------------------------------------------------- #17 改基线须有实验单

#: 实验单四行（缺一行即 FAIL；回滚点必须可执行）。
EXP_LINES = ("假设", "指标", "阈值", "回滚点")


def _changed_baselines(root: str) -> list[str]:
    """工作树里相对 HEAD 改动的 `*_baseline.json`（只读 git；git 不可用即空）。"""
    try:
        p = subprocess.run(  # nosec B603/B607 —— argv 列表、无 shell
            [
                "git",
                "-c",
                "core.quotepath=false",
                "diff",
                "--name-only",
                "HEAD",
                "--",
                "*_baseline.json",
            ],
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if p.returncode != 0:
        return []
    return [ln.strip() for ln in (p.stdout or "").splitlines() if ln.strip()]


def _today() -> str:
    return datetime.date.today().isoformat()


def experiment_guard(
    root: str = ".", changed: Sequence[str] | None = None
) -> tuple[list[str], dict[str, Any]]:
    """#17：改基线必须附同日实验单（四行齐备），且登记册里存在 experiment 条目。"""
    paths = list(changed) if changed is not None else _changed_baselines(root)
    if not paths:
        return ([], {"changed": 0})
    issues: list[str] = []
    today = _today()
    base = Path(root) / "changes" / "unreleased"
    sheets = sorted(base.glob("*.md")) if base.is_dir() else []
    same_day = [p for p in sheets if p.name.startswith(today)]
    if not same_day:
        issues.append(
            "#17 改基线无同日实验单：{} 有改动，但 changes/unreleased/ 无 "
            "{}-*.md（修复指引：补四行实验单）".format("、".join(paths), today)
        )
    else:
        text = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in same_day)
        lacking = [label for label in EXP_LINES if label not in text]
        if lacking:
            issues.append(
                "#17 实验单缺行：{} 缺 {}（四行：假设/指标/阈值/回滚点）".format(
                    "、".join(p.name for p in same_day), "/".join(lacking)
                )
            )
    try:
        doc = load(root)
        if not any(
            isinstance(r.get("experiment"), str) and r.get("experiment")
            for r in (doc.get("checks") or [])
            if isinstance(r, dict)
        ):
            issues.append(
                "#17 判据账本缺预注册：改基线时登记册须有 experiment 非空的条目"
                "（修复指引：把实验单 id 填进对应 check 的 experiment）"
            )
    except (OSError, ValueError):
        pass
    return issues, {"changed": len(paths), "sheets": len(same_day)}


# ------------------------------------------------------------------ schema 校验


def validate(doc: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    if doc.get("schema") != SCHEMA:
        problems.append("schema 应为 {}，实为 {!r}".format(SCHEMA, doc.get("schema")))
    rows = doc.get("checks")
    if not isinstance(rows, list) or not rows:
        return problems + ["checks 必须是非空数组"]
    seen: set[int] = set()
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            problems.append("checks[%d] 不是对象" % i)
            continue
        lack = [f for f in FIELDS if f not in row]
        if lack:
            problems.append("checks[%d] 缺字段 %s" % (i, ",".join(lack)))
            continue
        num = row["id"]
        if not isinstance(num, int) or num <= 0:
            problems.append("checks[%d].id 必须是正整数" % i)
            continue
        if num in seen:
            problems.append("id 重复：%d" % num)
        seen.add(num)
        if row["kind"] not in KINDS:
            problems.append("check%d.kind 非法：%r" % (num, row["kind"]))
        if row["severity"] not in SEVERITIES:
            problems.append("check%d.severity 非法：%r" % (num, row["severity"]))
        if not isinstance(row["reads"], list) or not isinstance(row["writes"], list):
            problems.append("check%d.reads/writes 必须是数组" % num)
        if row["experiment"] is not None and not isinstance(row["experiment"], str):
            problems.append("check%d.experiment 只能是 null 或字符串" % num)
    return problems


# ------------------------------------------------------------------ 聚合入口


def scan(root: str = ".", memo: bool = False) -> tuple[list[str], list[str], dict[str, Any]]:
    """聚合判据：issues（FAIL）· warns（WARN，灰度）· stats（[i] 行）。

    R1 与 #17 违例 = FAIL（方案写明第一步即判死）；R2 违例先 WARN；R3 只在 memo
    模式跑（灰度），其余情况如实记账「未观测」。
    """
    issues, stats = consistency(root)
    r1_ok = not issues
    warns, r2 = activity(root)
    stats.update({"r2_entries": r2.get("entries", 0)})
    exp_issues, exp = experiment_guard(root)
    issues.extend(exp_issues)
    r3: dict[str, Any] = {"observed": 0, "skipped": -1, "note": "仅 --memo 模式开启"}
    if memo:
        r3_warns, r3 = read_surface(root)
        warns.extend(r3_warns)
    return (
        issues,
        warns,
        {
            "r1": "四份清单 %s" % ("一致" if r1_ok else "有差集"),
            "r2": "%d 条（坏实现 %d / 死字段 %d）"
            % (stats.get("r2_entries", 0), r2.get("bad_impl", 0), len(r2.get("dead_fields") or [])),
            "r3": ("观测 %d 条" % r3["observed"]) if memo else str(r3.get("note")),
            "exp": "无基线改动" if not exp.get("changed") else "改基线 %d 件" % exp["changed"],
        },
    )
