"""core.purity_scan 私有实现分片 1/2（对外只经 core.purity_scan 门面导入）：PROTO_DOCS 等"""

from __future__ import annotations

import ast
import hashlib
import re
from typing import Any, Dict, List

from core import disk_cache
from core import import_graph as _ig

#: 协议真相源 + 导航文档（R1/R2/R3 作用域）
PROTO_DOCS = ("01_核心协议.md", "02_联动注册表.md",
              "06_Agent执行协议.md", "07_官方核心出厂与社区预设导航.md")


_END_SHELL = re.compile(r"(?i)(android|APK|src/ui|Kivy)")


_PRIVATE = re.compile(r"[A-Za-z]:\\|/tmp/|/Users/|/home/|TODO|FIXME|XXX|TBD")


#: R1–R3 的**逐件**事实缓存（键 = 该件正文的 sha256）：`(端壳残留, 私货/可变物, 重复标题)`。
#: 依据（实测 2026-09-29）：R1–R3 每次扫描都要把 4 份协议文档 `splitlines()` **三遍**、逐行跑
#: 三个正则（`01_核心协议.md` 是长文，这笔实测占 `purity_scan._scan_impl` 的一半以上）；而这
#: 三个事实只是**该件正文**的纯函数——改任何别的件（模块库、协议件、文档）时这一整笔应当为零。
#: 纪律同 `layer_model._entry_imports` / 本模块 `_facts_for`：键即内容，值里**不含路径**。
_DOC_FACTS_CACHE: dict = {}


_DOC_FACTS_MAX = 64


#: R5 硬依赖白名单（**登记**的第三方硬 import：允许直接 import）
HARD_ALLOW = {
    "yaml": "PyYAML（仓库既有依赖；check16/28 同源解析，见 CONTRIBUTING §4.2 例外）",
}


#: R5 存量残留（**WARN 挂账**：确有理由保留的存量违规须带裁决/文档指针；不判死但不得隐身）。
#: 本扫描按**文件系统**取件 ⇒ 未入库的本地副本同样会被扫到。2026-09-20：唯一一项残留经作者裁决
#: 删除，登记随之清空（空表即"零残留"）。
IMPORT_RESIDUE: dict = {}


#: 扫描作用域含 `.github/scripts`——那是**唯一处理远程不可信输入**（Issue 标题/正文）
#: 且持有写权限令牌的代码。此前只在 core + scripts 取件，等于把最高风险的入口
#: 排除在 R5/R6 之外（渗透实证：同一份含 os.system / subprocess(shell=True) 的文件
#: 放 scripts/ 被拦、放 .github/scripts/ 命中 0 条）。
IMPORT_SCAN = ("desktop/src/core/*.py", "scripts/*.py", ".github/scripts/*.py")


#: R6 危险 sink（AST 级；键 = 规范化调用名）+ CWE 对齐（外部缺陷类型编码，便于跨工具对账）
DANGEROUS_CALLS = {
    "eval": "CWE-95 动态执行（输入可注入）",
    "exec": "CWE-95 动态执行（输入可注入）",
    "__import__": "CWE-470 动态导入（须证明模块名非用户输入）",
    "os.system": "CWE-78 shell 命令（改用 subprocess 列表参数）",
    "os.popen": "CWE-78 shell 管道（改用 subprocess 列表参数）",
    "pickle.load": "CWE-502 不安全反序列化（可执行任意代码）",
    "pickle.loads": "CWE-502 不安全反序列化（可执行任意代码）",
    "marshal.loads": "CWE-502 不安全反序列化",
    "yaml.load": "CWE-502 非安全 YAML 载入（改用 yaml.safe_load）",
    "shutil.rmtree": "CWE-73 递归删除外部可控路径（须证明落点非主目录/仓库根/盘根）",
    "os.remove": "CWE-73 删除外部可控路径（须证明来源不可被外部左右）",
    "os.rmdir": "CWE-73 删除外部可控目录",
}


#: **方法名类 sink**：`x.unlink()` 与 `os.remove` 同险（都是"删一个文件"），但它们被调者的名字
#: 随接收者变（`old.unlink` / `p.unlink` / `f.unlink` …）——按整串匹配会**整类漏掉**。
#: 故这一类按**方法名**匹配，放行键也用方法名（`<文件基名>:unlink`），不随变量名漂移。
#: 落地依据（2026-09 实测）：本仓 core 里当时有 **6 处 `.unlink()`**，全部一路绿灯穿过 R6——
#: 与 F-10「递归删除面此前不在类目内」是同一类缺口。
METHOD_SINKS = {
    "unlink": "CWE-73 删除外部可控文件（`Path.unlink` 等价 `os.remove`，同样须证明来源不可被外部左"
        "右）",
}


#: R6 已登记放行（键 = "<文件基名>:<调用名>"；放行须可审计）
SINK_ALLOW = {
    "release_conclusion.py:unlink":
        "快照互斥锁的**自清**：只删 .worktrees/gate-snap/.snapshot.lock 这一个自己写的锁文件，"
        "落点由 snapshot_base 单源决定（仓内 .worktrees，不是外部可控路径），且删除前先核对"
        "锁里的 pid == 本进程（不误删别人接管的锁）；用于并发会话互清 worktree 的实测问题",
    "rust_engine.py:unlink":
        "常驻 worker 状态文件（<NF_HOME>/rust_worker.json）的**自清**：落点由 "
        "core.storage.default_home 单源决定（用户态，不接收外部路径参数），删的是本模块上一轮"
        "自己写的状态文件，用于避免陈旧 port/token 被复用；worker 随后重写该件",
    "regression_score.py:__import__":
        "模块名取自内部常量表 SIGNAL_SPECS（非用户输入），用于按名调用既有扫描器",
    "crosscheck.py:unlink":
        "删除矩阵的**夹具构造**：只对 tempfile.TemporaryDirectory 里 copytree 出来的交付包副本执行"
        "（落点由本模块 mkdtemp 现建，非外部可控路径），目的是验证「删文件后验证器必须报红」；"
        "真实交付包只读，不删仓库内文件",
    "release_conclusion.py:shutil.rmtree":
        "快照门禁的**失败自清**：落点由本模块 tempfile.mkdtemp 现建（前缀 nf-gate-snap-<sha>），"
        "只在 git worktree add 失败时删掉这个刚建的空壳；不接收外部路径参数。成功路径交给 "
        "git worktree remove --force 管，不走这条",
    "e2e_desktop_headless.py:shutil.rmtree":
        "自检专用临时 home 的清理；落点已由 _resolve_test_home 拒绝主目录/仓库根/盘根（见 F-10）",
    "storage.py:shutil.rmtree":
        "模块仓内「同 full_id 旧目录」清理；路径由 Store._safe_name 拼装且限于 modules_root 之下",
    "watch.py:os.rmdir":
        "监听机制自检的临时目录清理：该目录由本模块 tempfile.mkdtemp 现建（路径不来自外部输入），"
        "且**非递归**——真出现意外子树时 rmdir 会拒绝，而不是把它一并抹掉",
    "gate_inproc.py:exec":
        "门禁引擎的**进程内 heredoc 执行面**：源码字符串由 gate_inproc.extract_heredoc 从"
        "本仓 verify.sh 里机械切出（`<<'PYEOF'` 到顶格结束标记），**不来自任何外部输入**；"
        "目的是省掉 heredoc 的解释器启动税（实测全量门禁 42 次 $PY3 启动）。"
        "等价性由 tests/test_gate_engine_parity.py 逐 check 差分守住（verdict 行逐字一致）",
    "disk_cache.py:unlink":
        "缓存裁剪：落点在 <NF_HOME>/cache/<tag>/ 之下，文件名是本模块自己算的 sha256（非外部输入）"
            "，"
        "且只删超出保留份数的旧条目（按 mtime 排序）",
    "scratch.py:unlink":
        "临时区写权限探针的**自清**：探针名含 uuid，落点由 resolve() 裁决（scratch 根），"
        "删的是本模块刚建的那一个文件；不接收外部路径参数",
    "scratch.py:shutil.rmtree":
        "scratch 上下文退出与 TTL GC 的**整目录回收**：落点由 resolve() 裁决（S1：只收养空目录/"
        "带 .nf-scratch 标记的区），且只删 nf-<12hex> 命名的子目录（GC 显式跳过其余条目、"
        "缺标记即拒绝），无法指向仓库根/主目录/盘根",
    "atomic_write.py:unlink":
        "原子写的**失败清理**：临时件由本模块 tempfile.mkstemp 现造（名与落点皆非外部输入），"
        "只删自己刚写的那一个 .tmp；`os.replace` 成功路径不删除任何东西",
    "domain_pack.py:unlink":
        "域包工厂的陈旧件清理：只在目标包自己的 modules/ 与 pipelines/ 内、且文件名令牌匹配该包代码"
            "，"
        "删的是本轮未列入 planned 的旧产物（可复算，删旧即安全）",
    "pack_combo.py:unlink":
        "组合包改号残留清理：只在目标包自己的 pipelines/ 内、且文件名形如 P\\d{2,3} 且不等于本轮管"
            "线号",
    "storage.py:unlink":
        "Preset 删除（remove_preset）：路径由 Store._safe_name 拼装且限于 presets_root 之下",
    "watch.py:unlink":
        "监听机制自检自建临时目录内的探针件（probe.txt）清理；路径不来自外部输入",
}


_HEAD = re.compile(r"^#{1,6}\s+(.*?)\s*$")


def _doc_facts(text: str):
    """一份协议文档的 R1–R3 事实：`(端壳命中, 私货命中, 重复标题)`（行号 + 已截断正文 / 标题）。

    等价性由 `test_purity_scan.DocFactsTest` 守着：用**未缓存的参考实现**（原先那三段
    「三遍 `splitlines()` + 逐行正则」原样搬进测试）在真仓库 4 份文档与合成样本上逐字段比对。
    """
    key = hashlib.sha256(text.encode("utf-8")).hexdigest()
    hit = _DOC_FACTS_CACHE.get(key)
    if hit is not None:
        return hit
    shell: List[Any] = []
    private: List[Any] = []
    seen: Dict[str, List[int]] = {}
    for i, ln in enumerate(text.splitlines(), 1):     # `splitlines` 只做一遍（过去三遍）
        if _END_SHELL.search(ln):
            shell.append((i, ln.strip()[:80]))
        if _PRIVATE.search(ln):
            private.append((i, ln.strip()[:80]))
        m = _HEAD.match(ln)
        if m:
            seen.setdefault(m.group(1).strip(), []).append(i)
    got = (tuple(shell), tuple(private),
           tuple((t, tuple(v)) for t, v in seen.items() if len(v) > 1))
    if len(_DOC_FACTS_CACHE) >= _DOC_FACTS_MAX:
        _DOC_FACTS_CACHE.clear()
    _DOC_FACTS_CACHE[key] = got
    return got


_ACTION = re.compile(
    r"(应|须|先|必填|必需|必须|请|建议|参考|查看|运行|执行|使用|改用|替换|修复|"
    r"补齐|重新|重跑|更正|核对|检查|可选|选项|列表|注册|示例|格式|参见|见|按|需|"
    r"选择|可用|如|缺少|缺|期望|修正|§|文档|帮助|重试|再)")


#: R4–R6 的文本预筛：无 raise / import / try / shell / 任一危险调用名 → 三类事实必然为空，
#: 连 parse 都不必做（判据等价：AST 里出现的名字必然在源码文本里出现）。
_NEEDS_AST = re.compile(
    r"raise|import|try|shell|"
    + "|".join(re.escape(c.rsplit(".", 1)[-1]) for c in sorted(DANGEROUS_CALLS)))


def _try_guards_import(node: ast.Try) -> bool:
    """该 try 是否兜住了导入失败（ImportError / ModuleNotFoundError / Exception / 裸 except）。"""
    for h in node.handlers:
        if h.type is None:
            return True
        if isinstance(h.type, ast.Name) and h.type.id in (
                "ImportError", "ModuleNotFoundError", "Exception"):
            return True
        if isinstance(h.type, ast.Tuple):
            names = {e.id for e in h.type.elts if isinstance(e, ast.Name)}
            if names & {"ImportError", "ModuleNotFoundError", "Exception"}:
                return True
    return False


#: AST 事实缓存：键 = **文件文本本身**（内容不变 ⇒ 事实必然相同；内容一改键就变）。
#: 与围栏 YAML 缓存（conformance_scan._FENCE_CACHE）、引用度普查缓存同一条纪律：
#: 键即内容，所以**不存在陈旧风险**，可以放心在常驻进程里长期复用。
_FACTS_CACHE: dict = {}


_FACTS_CACHE_MAX = 4096


#: 持久层未命中的哨兵（`None` 本身是**合法结果**：预筛不中 / 语法错，两者都要能落盘）
_FACTS_READ_MISS = object()


def _pack_facts(facts):
    """事实 → 可 JSON 的载荷（元组/集合统一成列表，并记下「命中与否」）。"""
    if facts is None:
        return {"hit": False, "facts": None}
    raises, guarded, modules, sinks = facts
    return {"hit": True, "facts": [[list(x) for x in raises], sorted(guarded),
                                   [list(x) for x in modules], [list(x) for x in sinks]]}


def _packed_ok(value) -> bool:
    """载荷形状校验：不符即当未命中（半截/串味的文件一律重算）。"""
    return (isinstance(value, dict) and set(value) == {"hit", "facts"}
            and isinstance(value["hit"], bool)
            and (value["facts"] is None
                 or (isinstance(value["facts"], list) and len(value["facts"]) == 4)))


def _unpack_facts(value):
    """载荷 → 事实：**逐类型还原**（元组回元组、集合回集合），保证与现算结果相等。"""
    if not value["hit"]:
        return None
    raises, guarded, modules, sinks = value["facts"]
    return ([(int(a), str(b)) for a, b in raises],
            {int(x) for x in guarded},
            [(str(a), int(b)) for a, b in modules],
            [(int(a), str(b), bool(c)) for a, b, c in sinks])


def _ast_facts(tree: ast.AST) -> tuple:
    """**一次** `ast.walk` 取齐 R4–R6 全部事实（判据与分次遍历逐条等价）。

    效率（实测）：同一棵树过去被 walk **四遍**——R4 的 raise 消息 1 遍、R5 的守卫 import
    行号 1 遍、R5 的顶层模块 1 遍、R6 的危险 sink 1 遍；`nf conformance` 里 AST 面因此
    独占约 **7.7 s**（约 210 万次节点访问）。合流后每份文件只 walk 一遍。

    返回 `(raise 消息, 守卫 import 行号集, 顶层模块, 危险调用节点)`；各自的**产出顺序**
    与原来那次独立遍历完全一致（同一次 walk 顺序）。
    """
    raises: list = []
    guarded: set = set()
    modules: list = []
    sinks: list = []
    for node in ast.walk(tree):
        raises += _raise_facts(node)
        modules += _import_facts(node)
        guarded |= _guarded_imports(node)
        sinks += _sink_facts(node)
    return raises, guarded, modules, sinks


def _raise_facts(node) -> list:
    """Raise 节点的消息事实（R4）。"""
    if not (isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call) and node.exc.args):
        return []
    arg = node.exc.args[0]
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        return [(node.lineno, arg.value)]
    if isinstance(arg, ast.JoinedStr):
        parts = [v.value for v in arg.values
                 if isinstance(v, ast.Constant) and isinstance(v.value, str)]
        return [(node.lineno, "".join(parts))]
    return []


def _import_facts(node) -> list:
    """Import/ImportFrom 节点的顶层模块事实（R5）。"""
    if isinstance(node, ast.Import):
        return [(a.name.split(".")[0], node.lineno) for a in node.names]
    if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
        return [(node.module.split(".")[0], node.lineno)]
    return []


def _guarded_imports(node) -> set:
    """try 守卫内的 import 行号（R5）。"""
    if not (isinstance(node, ast.Try) and _try_guards_import(node)):
        return set()
    out: set = set()
    for sub in node.body:
        for n2 in ast.walk(sub):
            if isinstance(n2, (ast.Import, ast.ImportFrom)):
                out.add(n2.lineno)
    return out


def _sink_facts(node) -> list:
    """危险 sink 事实（R6）：(行号 / 被调名 / 是否 shell=True)。"""
    if not isinstance(node, ast.Call):
        return []
    # 危险 sink 候选在这里就**摘成可序列化的三元组**：判据与原来"拿着 AST 节点到 R6 再
    # unparse"逐条等价（有等价性判据守着），但结果成了纯数据 ⇒ 整份事实可以按内容落盘。
    return [(node.lineno, ast.unparse(node.func),
             any(kw.arg == "shell" and isinstance(kw.value, ast.Constant)
                 and kw.value.value is True for kw in node.keywords))]


def _facts_for(text: str):
    """文本 → R4–R6 事实（预筛不中即 None）；**两层**按内容缓存（进程内 + 持久）。

    持久层（`core.disk_cache`，键里还含代码面 + 运行时）：一次冷进程 `evaluate` 里 AST 解析
    134–235 份 core/scripts 源码约 **0.98 s**，新进程从此免付。键＝文本的 sha256 ⇒ 键即内容，
    无陈旧面；读回按 `_packed_ok` 校验形状并把元组/集合**还原成原类型**（保证与现算逐位相等，
    有往返判据守着）。
    """
    if text in _FACTS_CACHE:
        return _FACTS_CACHE[text]
    dkey = disk_cache.key("ast-facts", hashlib.sha256(text.encode("utf-8")).hexdigest(),
                              code_scope=_ig.code_scope_fingerprint(".", ("core.purity_scan",)))
    packed = disk_cache.load("ast-facts", dkey, validate=_packed_ok)
    got = _unpack_facts(packed) if packed is not None else _FACTS_READ_MISS
    if got is _FACTS_READ_MISS:
        got = None
        if _NEEDS_AST.search(text):
            try:
                got = _ast_facts(ast.parse(text))
            except SyntaxError:
                got = None
        # 每份源码一条 ⇒ 上限按「进程内事实缓存」同一量级给（默认 16 会让它反复抖动）
        disk_cache.store("ast-facts", dkey, _pack_facts(got), keep=_FACTS_CACHE_MAX)
    if len(_FACTS_CACHE) >= _FACTS_CACHE_MAX:
        _FACTS_CACHE.clear()
    _FACTS_CACHE[text] = got
    return got
