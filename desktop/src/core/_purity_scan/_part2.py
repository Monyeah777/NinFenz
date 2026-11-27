"""core.purity_scan 私有实现分片 2/2（对外只经 core.purity_scan 门面导入）：_FILE_FINDINGS 等"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional

from core import conformance_scan as csc

from ._part1 import (
    _ACTION,
    DANGEROUS_CALLS,
    HARD_ALLOW,
    IMPORT_RESIDUE,
    IMPORT_SCAN,
    METHOD_SINKS,
    PROTO_DOCS,
    SINK_ALLOW,
    _doc_facts,
    _facts_for,
)

#: **逐件 findings 缓存**：R4/R5/R6 的结论只是「**该件正文** + 登记表 + 局部模块名集」的纯函数。
#: 依据（实测）：三条规则要遍历 546 份源码、真检查项只 ~81 条 ⇒ 20 ms 里绝大部分是循环开销。
#: 键 = (相对路径, 正文 sha256, **环境指纹**)；判据：`FileFindingsCacheTest`（三态）+ 变异注入用例。
_FILE_FINDINGS: dict = {}


_FILE_FINDINGS_MAX = 4096


def _cache_key(*fps: str) -> str:
    """把若干指纹（各张面 + 环境）拼成派生缓存的键——**键必须覆盖全部输入**，否则回放旧结论。"""
    return hashlib.sha256("\x00".join(fps).encode("utf-8")).hexdigest()


def _is_local(mod: str, root: str) -> bool:
    if mod == "core":
        return True
    for base in (os.path.join(root, "desktop", "src", "core"), os.path.join(root, "scripts"),
                 os.path.join(root, ".github", "scripts")):
        if os.path.exists(os.path.join(base, mod + ".py")):
            return True
    return False


#: R5 软导入登记（第三方可选依赖：必须 try/except ImportError 守卫 + 写明理由）
SOFT_IMPORTS = {
    "numpy": "水印鲁棒性基准（watermark_bench）里按像素构造噪声/亮度攻击；"
        "软导入 + 缺依赖给修复指引，基准以外不依赖",
    "PIL": "标注水印层（label_watermark）读写 PNG 位图；软导入 + 缺依赖给修复指引，"
        "文本载体那条路保持纯标准库",
    "jsonschema": "IDL 标准实现交叉验证（可选对照；缺依赖则跳过该面）",
    "PySide6": "CCV3 卡面占位图写入（缺依赖须给明确修复指引，不得裸 ImportError）",
    "nf_pyengine": "PyO3 扩展（engine/rust/pyo3 构建）为可选进程内原语加速；"
        "缺扩展时 rust_pyext 回退 hashlib/repr，不把 Rust 工具链变成运行前提",
    "laya": "决策层本地服务（scripts/serve_decision_model.py）的模型运行时；软导入 + 缺依赖给修复指"
        "引",
}


def _env_fingerprint(root: str) -> str:
    """R4–R6 的**环境指纹**：局部模块名集 + 六张登记表（任一变，逐件结论都必须重算）。"""
    local = sorted({os.path.basename(p).rsplit(".", 1)[0]
                    for pat in IMPORT_SCAN
                    for p in csc.iter_files(root, pat)})
    blob = json.dumps({"local": local, "hard": HARD_ALLOW, "soft": SOFT_IMPORTS,
                       "residue": IMPORT_RESIDUE, "sink_allow": SINK_ALLOW,
                       "dangerous": DANGEROUS_CALLS, "methods": METHOD_SINKS,
                       "stdlib": sorted(sys.stdlib_module_names)},
                      ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _file_findings(rel: str, text: str, env: str, root: str):
    """单份源码的 R4–R6 findings → `(issues, {"raises":n,"imports":n,"sinks":n,"residue":[…]})`。"""
    key = (rel, hashlib.sha256(text.encode("utf-8")).hexdigest(), env)
    hit = _FILE_FINDINGS.get(key)
    if hit is not None:
        return hit
    out: List[str] = []
    delta: Dict[str, Any] = {"raises": 0, "imports": 0, "sinks": 0, "residue": []}
    facts = _facts_for(text)
    if facts is None:
        hit = (out, delta)
    else:
        raises, guarded, modules, sinks = facts
        fname = os.path.basename(rel)
        for lineno, msg in raises:
            delta["raises"] += 1
            if msg and not _ACTION.search(msg):
                out.append("%s:%d raise 消息缺修复指引：%s" % (fname, lineno, msg[:60]))
        residue = IMPORT_RESIDUE.get(rel)
        for mod, lineno in modules:
            if mod in sys.stdlib_module_names or _is_local(mod, root):
                continue
            delta["imports"] += 1
            if mod in HARD_ALLOW:
                continue
            target = delta["residue"] if residue else out
            if mod in SOFT_IMPORTS:
                if lineno not in guarded:
                    msg = ("%s:%d 第三方 %s 未软导入（须 try/except ImportError 守卫；登记理由：%s"
                        "）"
                           % (rel, lineno, mod, SOFT_IMPORTS[mod]))
                    target.append("%s（%s）" % (msg, residue) if residue else msg)
                continue
            msg = ("%s:%d 第三方 import 未登记：%s（修复指引：改为软导入并在 purity_scan.SOFT_IMPOR"
                "TS "
                   "登记理由，或加入 HARD_ALLOW；端壳残留则登记 IMPORT_RESIDUE）" % (rel,
 lineno,
 mod))
            target.append("%s（%s）" % (msg, residue) if residue else msg)
        for lineno, call, shell_true in sinks:
            flags = []
            if call in DANGEROUS_CALLS:
                flags.append((call, call))
            method = call.rsplit(".", 1)[-1]
            if method in METHOD_SINKS:
                flags.append((method, method))
            if shell_true:
                flags.append(("subprocess(shell=True)", "subprocess"))
            for name, key_name in flags:
                delta["sinks"] += 1
                if "%s:%s" % (fname, key_name) in SINK_ALLOW:
                    continue
                out.append("%s:%d 危险 sink %s（%s）——确需使用须在 purity_scan.SINK_ALLOW "
                           "登记理由（修复指引：改用安全等价物，或登记后写明为何不可注入）"
                           % (rel, lineno, name,
                              DANGEROUS_CALLS.get(call) or METHOD_SINKS.get(method)
                              or "shell=True 命令注入面"))
        hit = (out, delta)
    if len(_FILE_FINDINGS) >= _FILE_FINDINGS_MAX:
        _FILE_FINDINGS.clear()
    _FILE_FINDINGS[key] = hit
    return hit


#: **自有面**（本模块自己读的那些件）：代码 / 协议文档 / 判据脚本。
#: 注意最后几项：**不写 `scripts/**/*`**——它连 `scripts/__pycache__/*.pyc`（Python 自生成）一起收，
#: 会让本面指纹随导入漂移（详见 `disk_cache.CODE_FACE` 的说明）；这里按真读面穷举。
OWN_PATTERNS = ("01_核心协议.md", "02_联动注册表.md", "06_Agent执行协议.md",
                "07_官方核心出厂与社区预设导航.md", "protocol/*.json", "verify.sh",
                "desktop/src/**/*.py", "scripts/**/*.py", "scripts/*.sh",
                "scripts/nf", "scripts/nf.cmd", ".github/scripts/*.py",
                "03_管线库/**/*.md", "04_模块库/**/*.md")


def patterns(root: str = ".") -> tuple:
    """`scan()` 的输入面：自身读的面（代码 / 协议文档 / 判据脚本）+ **R7 阶梯面**。

    为什么带上阶梯面：本函数把 `layer_model.scan()` 的结果并进 issues ⇒ 阶梯的输入也是本函数的
    输入，漏了它就会出现「改资产却不重算纯度」的陈旧。
    """
    own = OWN_PATTERNS
    try:
        from core import layer_model as _lm
        return tuple(dict.fromkeys(own + tuple(_lm.patterns(root))))
    except Exception:                                    # noqa: BLE001 - 面取不全就别缓存
        return own


def _scan_impl(root: str = ".", _layer_fp: Optional[str] = None) -> tuple:
    """真算（未命中缓存时走这里）；`_layer_fp` 由 `scan()` 传下来，避免走两次阶梯面。"""
    issues = []
    stats: Dict[str, Any] = {"docs": 0, "raises": 0, "imports": 0, "import_residue": []}
    # R1/R2/R3：协议层文档
    for name in PROTO_DOCS:
        path = os.path.join(root, name)
        if not os.path.exists(path):
            continue
        text = csc.read_text_cached(path)          # 共享语料读：一次只读调用内同件只读一遍
        stats["docs"] += 1
        shell_hits, private_hits, dup_titles = _doc_facts(text)   # 键即内容：没改就不重扫
        if name in ("01_核心协议.md", "02_联动注册表.md"):
            for i, ln in shell_hits:
                issues.append("%s:%d 端壳/APK 残留：%s" % (name, i, ln))
        for i, ln in private_hits:
            issues.append("%s:%d 私货/可变物：%s" % (name, i, ln))
        for title, lines in dup_titles:
            issues.append("%s 重复标题「%s」：行 %s"
                          % (name, title, ",".join(map(str, lines))))
    # R4：错误信息审计（desktop/src/core/*.py）
    # R4/R5/R6 共用一份「读 + parse + walk」：同一批 core/*.py 过去被 R4 与 R5 各自 parse
    # 一遍、同一棵树被 walk 四遍（见 `_ast_facts`）；现在更进一步——整段「事实 → 结论」
    # 按 `_file_findings`（键 = 路径 + 正文 + 环境指纹）**逐件**缓存，未变的件连循环体都不再进。
    core_dir = os.path.join(root, "desktop", "src", "core")
    env = _env_fingerprint(root)          # R4–R6 逐件缓存的环境指纹（每轮算一次）
    if os.path.isdir(core_dir):
        for fname in sorted(os.listdir(core_dir)):
            if not fname.endswith(".py"):
                continue
            rel = "desktop/src/core/" + fname
            try:
                text = csc.read_text_cached(os.path.join(core_dir, fname))
            except OSError:  # 尽力而为：跳过不可读/不可解析项；该类缺口由对应门禁另行报出（见 AUD-0016）
                continue
            got, delta = _file_findings(rel, text, env, root)
            issues += got
            stats["raises"] += delta["raises"]
            stats["imports"] += delta["imports"]
            stats["sinks"] = stats.get("sinks", 0) + delta["sinks"]
            stats["import_residue"] += delta["residue"]
    # R5：import 面（core + scripts 的第三方依赖须登记；软导入才可免硬依赖）
    import glob as _glob
    for rel_pat in IMPORT_SCAN:
        for f in sorted(_glob.glob(os.path.join(root, rel_pat))):
            rel = os.path.relpath(f, root).replace("\\", "/")
            if rel.startswith("desktop/src/core/"):
                continue                       # R4 那一段已经把这批件算过（同一个逐件缓存）
            try:
                text = csc.read_text_cached(f)
            except OSError:
                continue
            got, delta = _file_findings(rel, text, env, root)
            issues += got
            stats["imports"] += delta["imports"]           # raises 只在 R4（core/*.py）那一段计
            stats["sinks"] = stats.get("sinks", 0) + delta["sinks"]
            stats["import_residue"] += delta["residue"]
    # R6 自洽面（登记表自身的判据）：每个 sink 类目须带 CWE 对齐（跨工具对账用缺陷类型编码），
    # 且 SINK_ALLOW 的每个放行键必须指向一个已登记 sink——放行不能凭空出现。
    for call, desc in sorted({**DANGEROUS_CALLS, **METHOD_SINKS}.items()):
        if not re.match(r"^CWE-\d+ ", desc):
            issues.append("危险 sink 类目缺 CWE 对齐：%s（修复指引：在 purity_scan.DANGEROUS_CALLS "
                          "的说明前加 `CWE-<nnn> `，便于外部扫描器按缺陷类型对账）" % call)
    for key in sorted(SINK_ALLOW):
        sink = key.rsplit(":", 1)[-1]
        if sink not in DANGEROUS_CALLS and sink not in METHOD_SINKS and sink != "subprocess":
            issues.append("SINK_ALLOW 放行键指向未登记 sink：%s（修复指引：删除放行，"
                          "或先在 DANGEROUS_CALLS 登记该 sink 类目）" % key)
    # R7：抽象阶梯归属与越界（真源 protocol/LAYERS.json；语义判据在 core/layer_model.py）
    try:
        from core import layer_model as _lm
        if os.path.isfile(os.path.join(root, _lm.DECL_REL)):
            _ladder_issues, _ladder_stats = _lm.scan(root, _fp=_layer_fp)
            stats["layers"] = _ladder_stats
            issues += _ladder_issues
        else:
            # 合成树（单测）通常无阶梯件：缺件不在这里判死——缺席由断言表
            # `layers-declaration-in-place`（json_value 命中"目标件不存在"）+ 规范性名单
            # （modeling.verify_normative 断言 norm 件存在）+ RECEIPTS 覆盖面三处另判，不静默。
            stats["layers"] = {"skipped": "缺 %s（另由断言表与规范性名单判）" % _lm.DECL_REL}
    except Exception as _exc:
        issues.append("R7 阶梯体检不可用：%s（修复指引：核对 protocol/LAYERS.json 与 "
                      "desktop/src/core/layer_model.py 后可读性）" % _exc)
    # R8：核心文面去叙述（域中立）——实现独立成件（core/domain_neutral.py），守住本件规模上限；
    # 判定归入 check27 同一个门，不新增 check 序号。
    try:
        from core import domain_neutral as _dn
        _dn_issues, _dn_stats = _dn.scan(root)
        issues += _dn_issues
        stats["domain_neutral"] = _dn_stats
    except Exception as _dexc:
        issues.append(
            f"R8 去叙述体检不可用：{_dexc}"
            "（修复指引：核对 desktop/src/core/domain_neutral.py 可读性）"
        )
    return issues, stats


def scan(root: str = ".") -> tuple:
    """纯度体检（R1–R8）。派生结果按**输入内容指纹**缓存（输入面见 `patterns()`，很宽）。

    **冷进程也走这层缓存**（2026-09-29 实测：宽面指纹在同一只读作用域内近乎白拿，而重算这条派生账
    贵得多；见 `quality_depth_scan.scan` 的实测数字）。

    **键的取法（2026-09-29 改，实测）**：把自有面 / 阶梯面 / **六张登记表**（`_env_fingerprint`）
    各自的指纹组合成键，并把阶梯面指纹**传给** `layer_model.scan(_fp=...)`——只枚举一次，
    且「登记表变了」也换键（漏了它就会回放旧结论，由变异注入用例当场抓到）。
    """
    try:
        from core import layer_model as _lm
        layer_fp = _lm.face_fingerprint(root)
    except Exception:                                    # noqa: BLE001 - 取不出就退回整面
        return csc.memo_pair(
            'purity-scan',
            patterns(root),
            _scan_impl,
            root,
            code_modules=('core.purity_scan',),
            opts=csc.MemoOptions(
                fp=_cache_key(csc.face_fingerprint(root, patterns(root)), _env_fingerprint(root)),
            ),
        )
    own_fp = csc.face_fingerprint(root, OWN_PATTERNS)
    fp = _cache_key(own_fp, layer_fp, _env_fingerprint(root))
    return csc.memo_pair(
        'purity-scan',
        patterns(root),
        lambda r: _scan_impl(r, layer_fp),
        root,
        code_modules=('core.purity_scan',),
        opts=csc.MemoOptions(fp=fp),
    )
