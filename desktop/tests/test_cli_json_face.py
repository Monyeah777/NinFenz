"""机器面**面判别键**门禁：每个 `--json` 面成功时都必须是自带类型的对象。

为什么（2026-10-01 取证）：本仓机器面有两种信封——新面（`market-list` / `asset-ls` /
`layers` / `stats`…）顶层带 `kind`（或 `schema`），老面（`doctor` / `conformance` /
`receipts` / `transparency` / `patterns ls`…）什么都不带；全量实跑 64 个可无参运行的
`--json` 面，**只有 17 个带判别键**，47 个不带（其中 7 个还是裸数组——成功回数组、失败回
`{"ok": false, …}` 对象，消费方**无法区分**）。这正是「内外口径统一」要收的那类偏差。

本件两条判据互补：
1. **静态**（快、全覆盖）：`scripts/nf.py` 里所有 `print(json.dumps({…}))` 的字典字面量
   必须带 `kind`/`schema` 键——变量载荷（`**payload` / `doc`）由第 2 条动态判据兜。
2. **动态**（真跑）：声明了 `--json` 的面，无参可跑的那些，成功输出必须是**对象**且带
   `kind` 或 `schema`；豁免面须**逐一点名**并自证（防「悄悄多一个豁免」）。

豁免（注意辨别）：
- `interop`：它导出的是**第三方标准文档**（OpenAPI / AsyncAPI / SPDX / CycloneDX / in-toto /
  VC / C2PA / CID），**不许**加 NF 私键——加了会被官方 meta-schema 判越界（AUD-0010 首轮
  实测：CycloneDX 根级自定义键越界即 FAIL）。它由**自己的规范版本键**自证（`openapi` /
  `asyncapi` / `bomFormat` / `spdxVersion` / `predicateType` / `@context` …）。
- `_machine_fail`：失败信封，契约是 `{"ok": false, "error": …, "exit": N}`，不是面判别。
"""
import ast
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cli_harness  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
NF = str(ROOT / "scripts" / "nf.py")

#: 动态豁免：面 -> 它**自己的**自证键（集合，命中其一即算自描述）
EXEMPT = {"interop": {"openapi", "asyncapi", "bomFormat", "spdxVersion",
                      "predicateType", "@context", "claim_generator", "multihash"}}

#: 静态豁免：这些函数里的 dumps 是失败信封/文件载荷，不是面判别
STATIC_EXEMPT_FUNCS = {"_machine_fail"}


def _enclosing(tree):
    spans = []
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            spans.append((n.lineno, n.end_lineno, n.name))

    def name_of(line):
        best = None
        for a, b, nm in spans:
            if a <= line <= b and (best is None or a > best[0]):
                best = (a, nm)
        return best[1] if best else "?"
    return name_of


def dict_literal_faces(src: str):
    """→ `[(行号, 所在函数, 是否带 kind/schema)]`：所有 `print(json.dumps({…}))` 的字典面。"""
    tree = ast.parse(src)
    name_of = _enclosing(tree)
    out = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "print"):
            continue
        for sub in ast.walk(node):
            if not (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
                    and sub.func.attr == "dumps" and sub.args):
                continue
            first = sub.args[0]
            if not isinstance(first, ast.Dict):
                continue
            keys = {k.value for k in first.keys if isinstance(k, ast.Constant)}
            out.append((sub.lineno, name_of(sub.lineno),
                        bool({"kind", "schema"} & keys)))
    return out


class JsonFaceStaticTest(unittest.TestCase):
    def setUp(self):
        self.src = Path(NF).read_text(encoding="utf-8")

    def test_scanner_is_not_vacuous(self):
        """判据不空转：必须真的扫到面（否则结构变了，本件形同虚设）。"""
        self.assertGreater(len(dict_literal_faces(self.src)), 30)

    def test_dict_faces_carry_a_discriminant(self):
        bad = sorted({"%s:%d" % (fn, ln) for ln, fn, ok in dict_literal_faces(self.src)
                      if not ok and fn not in STATIC_EXEMPT_FUNCS})
        self.assertEqual([], bad, "机器面字典缺面判别键（kind/schema）：%s" % bad[:12])


_CACHE: dict = {}


def _face_rows():
    """声明 --json 的面清单（只枚举、不跑）——便宜的半个探针。"""
    if "rows" not in _CACHE:
        p = cli_harness.run_cli_proc([sys.executable, NF, "shell", "--commands", "--json"],
                                     cwd=str(ROOT))
        doc = json.loads(p.stdout)
        _CACHE["rows"] = [r for r in (doc.get("commands") or doc.get("rows") or [])
                          if "--json" in (r.get("flags") or [])]
    return _CACHE["rows"]


def _probe_faces(index: int = 0, total: int = 1):
    """枚举声明 `--json` 的面，并**真跑无参形态**（rc=2 = 缺必填参数，本判据跑不到）。

    按切片缓存（index/total 只决定"跑哪一份面"，判据不变）：分片器可以把同一条判据
    切成多份并行，单条地板从 ~90 s 降到 ~25 s。total=1 即历史全量口径。
    """
    rows = _face_rows()
    chunk = rows[index::total] if total > 1 else rows
    key = (index, total)
    if key in _CACHE.get("runs", {}):
        return chunk, _CACHE["runs"][key]
    runs, raw = {}, {}
    for r in chunk:
        path = r["path"]
        q = cli_harness.run_cli_proc([sys.executable, NF] + path.split() + ["--json"],
                                     cwd=str(ROOT))
        if q.returncode == 2:
            continue
        raw[path] = q.stdout or ""
        try:
            runs[path] = json.loads((q.stdout or "").strip())
        except ValueError:
            runs[path] = None
    _CACHE.setdefault("runs", {})[key] = runs
    _CACHE.setdefault("raw", {}).update(raw)
    return chunk, runs


class JsonFaceDynamicTest(unittest.TestCase):
    def _assert_self_describing_slice(self, index: int, total: int = 4):
        """自描述判据的分片版：每片只跑自己的 1/4 面，断言内容与原判据逐条相同。"""
        _, runs = _probe_faces(index, total)
        missing = []
        for path, data in sorted(runs.items()):
            if data is None:
                missing.append("%s（stdout 非 JSON）" % path)
                continue
            top = path.split()[0]
            if top in EXEMPT:
                keys = set(data) if isinstance(data, dict) else set()
                if not (keys & EXEMPT[top]):
                    missing.append("%s（豁免面缺自证键）" % path)
                continue
            if not isinstance(data, dict) or not ({"kind", "schema"} & set(data)):
                missing.append("%s（%s）" % (path, type(data).__name__))
        self.assertGreater(len(runs), 8, "分片内可跑面不足（%d）——判据形同虚设" % len(runs))
        self.assertEqual([], missing, "缺少面判别键的 --json 面：%s" % missing)
        if index == 0:
            # 豁免面集合与实测一致（全量口径）：用面清单（便宜）判，不再为它跑全量探针。
            tops = {r["path"].split()[0] for r in _face_rows()}
            self.assertEqual(set(EXEMPT), {t for t in EXEMPT if t in tops},
                             "豁免面集合与实测不一致（防悄悄新增/失效豁免）")

    def test_every_runnable_json_face_is_self_describing_chunk0(self):
        self._assert_self_describing_slice(0)

    def test_every_runnable_json_face_is_self_describing_chunk1(self):
        self._assert_self_describing_slice(1)

    def test_every_runnable_json_face_is_self_describing_chunk2(self):
        self._assert_self_describing_slice(2)

    def test_every_runnable_json_face_is_self_describing_chunk3(self):
        self._assert_self_describing_slice(3)


#: 预设面的**隔离 NF_HOME**：预设库在用户态，判据不许碰真实 `~/.NinFenz`
#: （也保证面里那两条 `preset show/apply` 有真件可查，走的是**成功**分支）。
_PRESET_STATE: dict = {}


def _preset_env() -> dict:
    """→ 带隔离 NF_HOME 的环境（首次调用时建一条预设）。"""
    if not _PRESET_STATE:
        home = tempfile.mkdtemp(prefix="nf_preset_gate_")
        env = dict(os.environ, NARRATIVE_FORGE_HOME=home)
        cli_harness.run_cli_proc([sys.executable, NF, "preset", "save", "门禁用例预设",
                                  "--pipeline", "P01", "--modules", "通用类:M00"],
                                 cwd=str(ROOT), env=env)
        _PRESET_STATE["env"] = env
    return _PRESET_STATE["env"]


def _fixtures() -> dict:
    """→ 需参面用的**真夹具**（首次调用时造；全在临时目录，不落仓库）。

    为什么要造而不是跳过（2026-10-01）：`bench compare|report` / `decide` /
    `knowledge frequency` 此前挂在判据的 `SKIP` 里（「仓内无正式夹具」），只有静态口径兜着。
    其实它们都能用**文档已声明的输入形状**现造：`bench run --out` 产的 run 记录、`decide` 的
    `--questions` JSON（形状见 `docs/decision-layer.md`）、知识层的 trace（JSONL，源 id 取
    `protocol/knowledge_sources.json` 在册项）。造出来就真跑，判据从「静态」升到「动态」。
    """
    if _PRESET_STATE.get("fixtures"):
        return _PRESET_STATE["fixtures"]
    env = _preset_env()
    tmp = tempfile.mkdtemp(prefix="nf_face_fix_")
    trace = os.path.join(tmp, "trace.jsonl")
    with open(trace, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"knowledge_source": "nf-protocol"}) + "\n")
    qfile = os.path.join(tmp, "questions.json")
    with open(qfile, "w", encoding="utf-8") as fh:
        json.dump({"pipeline": {"type": "choice", "instructions": "选择装配管线",
                                "options": ["P02 校园情感流", "P03 西幻生存流"]}},
                  fh, ensure_ascii=False)
    sfile = os.path.join(tmp, "state.txt")
    with open(sfile, "w", encoding="utf-8") as fh:
        fh.write("西幻生存题材，需要多语输出。\n")
    for i in (1, 2):                      # 两份 run 记录：bench compare 才有可比面
        cli_harness.run_cli_proc([sys.executable, NF, "bench", "run", "--case",
                                  "desktop/tests/fixtures/benchmark/suite/p03-western-cross",
                                  "--model", "gate-%d" % i,
                                  "--out", os.path.join(tmp, "run%d.json" % i)],
                                 cwd=str(ROOT), env=env)
    _PRESET_STATE["fixtures"] = {"env": env, "trace": trace, "questions": qfile,
                                 "state": sfile, "runs_glob": os.path.join(tmp, "run*.json")}
    return _PRESET_STATE["fixtures"]


def _canon_argv(name: str) -> list:
    """`CANON` 里 `@key` 占位 → 真夹具路径（夹具惰性创建，只在真跑到时付代价）。"""
    argv = list(CANON[name])
    if not any(isinstance(a, str) and a.startswith("@") for a in argv):
        return argv
    fx = _fixtures()
    return [fx[a[1:]] if isinstance(a, str) and a.startswith("@") else a for a in argv]


#: 需要必填参数、但**只读**的面 -> 仓储内可复现的调用（本判据真跑它们）。
CANON = {
    "approve": ["approve", "--verify"],
    "audit check": ["audit", "check", "results/audit/docs_audit-73-layers.md"],
    # --dry-run 是只读面（实测跑完 git status 无新件）；重绑的真写面另有 test_audit_rebind 覆盖。
    "audit rebind": ["audit", "rebind", "--note", "canon 只读面", "--dry-run"],
    "bench compare": ["bench", "compare", "@runs_glob"],
    "bench report": ["bench", "report", "@runs_glob"],
    "bench run": ["bench", "run", "--case",
                  "desktop/tests/fixtures/benchmark/suite/p03-western-cross"],
    "combine plan": ["combine", "plan", "--packs", "大语言模型域包,视觉模型域包"],
    # 复核纠正之二（2026-10-01）：`combine materialize` 此前被我按「写面」挂进 SKIP——**也不对**：
    # 它只在带 `--write` 时落盘，不带旗标是**只读**派生（实测 rc=0、跑完 `git status` 无新件）。
    "combine materialize": ["combine", "materialize", "--packs", "大语言模型域包,视觉模型域包"],
    "decisions show": ["decisions", "show", "ADR-0001"],
    "decide": ["decide", "--state", "@state", "--questions", "@questions",
               "--adapter", "stub"],
    # 复核纠正（2026-10-01）：这两张此前被我按「仓内 0 件」挂进 SKIP，**是错的**——
    # 仓内本来就有 `handovers/HO-9000-示例-接力模板.md` 与 `postmortems/PO-9000-示例-复盘模板.md`
    # （`test_handover` / `test_postmortem` 的 RealRepo 用例一直断言 ≥1 件）。直接指真件真跑。
    "handover check": ["handover", "check", "handovers/HO-9000-示例-接力模板.md"],
    "postmortem check": ["postmortem", "check", "postmortems/PO-9000-示例-复盘模板.md"],
    # T7.2 内容 IR：节点级检查面（只读；报告带 schema 面判别键）。
    "ir check": ["ir", "check", "docs/terminal.md"],
    # T9.2 导入面：旧面 SKILL 导入的 --json 机器面（docx/dita 导入器见
    # test_import_docx_dita.py；此面真跑，报告带 schema 判别键）。
    "import": ["import", "desktop/tests/fixtures/external/anthropic-official/docx.SKILL.md"],
    # T12.2 英文术语层：校验面（只读；报告带 schema 面判别键）。
    "glossary check": ["glossary", "check"],
    "diff": ["diff", "01_核心协议.md", "01_核心协议.md"],
    "domain build": ["domain", "build", "--spec", "A01"],
    "library search": ["library", "search", "验收"],
    "library show": ["library", "show", "NF-1"],
    "market": ["market", "--list"],
    "output check": ["output", "check", "docs/terminal.md"],
    "patterns for": ["patterns", "for", "04_模块库/通用类"],
    "patterns show": ["patterns", "show", "error-message-guidance"],
    "preset show": ["preset", "show", "门禁用例预设"],
    "preset apply": ["preset", "apply", "门禁用例预设"],
    "related": ["related", "M90"],
    "st-validate": ["st-validate", "desktop/tests/fixtures/external/chara.json"],
    "state-front": ["state-front", "docs/examples/state-front/nf1_front.md"],
    "knowledge frequency": ["knowledge", "frequency", "--trace", "@trace"],
}

#: 明确**不跑**的面 -> 理由（覆盖式点名：新面若不进 CANON 也不在这里，判据会红）。
SKIP = {
    # 写面与交互面不在「只读面真跑」这条判据里；各自的**功能覆盖**另有专件（逐条点名，
    # 免得「跳过」被读成「没人管」）。
    "library attest": "写盘面（改馆藏 frontmatter）——见 test_library.py",
    "library deprecate": "写盘面（生命周期流转）——见 test_library.test_lifecycle_flow_deprecate_sup"
        "ersede_restore",
    "library restore": "写盘面（生命周期流转）——见 test_library.py",
    "library supersede": "写盘面（生命周期流转）——见 test_library.py",
    "preset export": "写盘面（导出到文件）——全链见 test_preset_cli.py",
    "preset import": "写盘面（改本机预设库）——全链见 test_preset_cli.py",
    "preset rm": "写盘面（删本机预设）——全链见 test_preset_cli.py",
    "preset save": "写盘面（同名须 --force）——全链见 test_preset_cli.py",
    "shell": "交互面（接 TTY；非 TTY 阻塞）——覆盖见 test_terminal.py",
    "terminal": "交互面（shell 别名）——见 test_terminal.test_terminal_alias_works",
    # T7.3：参考运行时 run 需 --plan/--trace（无参跑 rc=2），且 trace/fixture 是用户命名落点；
    # 确定性 / record→replay / fixture 篡改与缺失 fail-closed 全链见 test_runtime.py。
    "runtime run": "写盘面（需要 --plan/--trace；trace/fixture 为用户落点）——全链见 test_runtime.py",
}


class JsonFaceCanonicalArgsTest(unittest.TestCase):
    """需参面的**真跑**判据 + 覆盖点名（每张声明 `--json` 的面都要有去处）。"""

    def _run(self, argv):
        return cli_harness.run_cli_proc([sys.executable, NF] + list(argv) + ["--json"],
                                        cwd=str(ROOT), env=_preset_env())

    def test_canonical_faces_are_self_describing(self):
        bad = []
        for name in CANON:
            p = self._run(_canon_argv(name))
            try:
                data = json.loads((p.stdout or "").strip())
            except ValueError:
                bad.append("%s（rc=%d，stdout 非 JSON）" % (name, p.returncode))
                continue
            if not isinstance(data, dict):
                bad.append("%s（顶层非对象）" % name)
                continue
            # 本判据管「**成功时**自带类型」（见模块头）。rc≠0 有两种合规形态：面判据**部分
            # 命中**仍回面载荷（如 audit check 已带 kind 但发现失效）→ 判别键照收；否则须是
            # 失败信封 {"ok": false, …}（模块头明写「不是面判别」）。
            if {"kind", "schema"} & set(data):
                continue
            if p.returncode != 0 and data.get("ok") is False:
                continue
            bad.append("%s（rc=%d，%s）" % (
                name, p.returncode,
                "缺面判别键" if p.returncode == 0 else "既非面载荷也非失败信封"))
        self.assertEqual([], bad, "需参面缺面判别键：%s" % bad)

    def test_every_json_face_has_a_destination(self):
        """覆盖点名：每张声明 --json 的面要么无参可跑、要么在 CANON、要么在 SKIP 有理由。

        P2（2026-10-18 实测）：原实现先把**所有**面真跑一遍再算 `faces - (runs ∪ CANON ∪ SKIP)`，
        单条白付 ~90 s。判据等价改写：`orphan = {f ∉ CANON/SKIP : 无参跑 rc=2}`——只跑
        「尚未被点名」的那些面（正常为 0，异常时才多跑几条），结果集与旧式**逐项相同**。
        """
        rows, runs = _probe_faces()
        faces = {r["path"] for r in rows}
        known = set(CANON) | set(SKIP)
        orph = sorted(faces - (set(runs) | known))
        self.assertEqual([], orph, "既不在 CANON 也不在 SKIP 的 --json 面（无处安放）：%s" % orph)
        self.assertTrue(SKIP, "跳过面必须逐条写理由（防悄悄不跑）")
        stale = sorted(known - faces)
        self.assertEqual([], stale, "CANON/SKIP 里列了不存在（或已改名）的面：%s" % stale)

    # ── 分片版（2026-10-19）：把同一条判据按面切成 4 份，让分片器能并行它 ──
    # 判据本身不变：仍是「每张面要么无参可跑、要么被 CANON/SKIP 点名」，只是不再由一条
    # 测试独占 ~90 s（实测那是全量档的头部地板之一）。
    def _face_chunk(self, index: int, total: int = 4):
        rows = _face_rows()
        chunk = rows[index::total]
        self.assertTrue(chunk, "面切片 %d/%d 为空（判据形同虚设）" % (index, total))
        return rows, chunk

    def _assert_face_slice(self, index: int, total: int = 4):
        rows, chunk = self._face_chunk(index, total)
        known = set(CANON) | set(SKIP)
        paths = [r["path"] for r in chunk]
        runs = _probe_faces(index, total)[1]
        orph = sorted(p for p in paths if p not in (set(runs) | known))
        self.assertEqual([], orph,
                         "既不在 CANON 也不在 SKIP 的 --json 面（无处安放）：%s" % orph)
        if index == 0:
            all_faces = {r["path"] for r in rows}
            self.assertTrue(SKIP, "跳过面必须逐条写理由（防悄悄不跑）")
            stale = sorted(known - all_faces)
            self.assertEqual([], stale, "CANON/SKIP 里列了不存在（或已改名）的面：%s" % stale)

    def test_every_json_face_has_a_destination_chunk0(self):
        self._assert_face_slice(0)

    def test_every_json_face_has_a_destination_chunk1(self):
        self._assert_face_slice(1)

    def test_every_json_face_has_a_destination_chunk2(self):
        self._assert_face_slice(2)

    def test_every_json_face_has_a_destination_chunk3(self):
        self._assert_face_slice(3)

    def test_skip_reasons_point_at_real_coverage(self):
        """`SKIP` 理由里点名的覆盖专件**必须真的碰过这张面**（防「按记忆填理由」）。

        依据（2026-10-01 连续两次自纠）：我先把 `handover check` / `postmortem check` 写成
        「仓内当前 0 件」（其实各有一件），又把 `combine materialize` 写成「写面，覆盖见
        test_pack_combo.py」（其实它不带 `--write` 就是只读；而 `test_pack_combo` 里根本没有
        materialize）。自由文本理由不会让任何检查变红，却会把读者引向错结论——本件把它变成
        可核事实：理由里出现 `test_*.py` 的，该文件必须含**这张面的关键词**。
        """
        tests_dir = ROOT / "desktop" / "tests"
        bad = []
        for face, reason in SKIP.items():
            m = re.search(r"(test_[a-z0-9_]+\.py)", reason or "")
            if not m:
                continue
            p = tests_dir / m.group(1)
            if not p.is_file():
                bad.append("%s → 覆盖件不存在：%s" % (face, m.group(1)))
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            token = face.split()[-1] if " " in face else face      # 如 library deprecate → deprecate
            if token not in text:
                bad.append("%s → %s 里没有 `%s`" % (face, m.group(1), token))
        self.assertEqual([], bad, "SKIP 理由里的覆盖声明与证据不符：%s" % bad)


#: 本机绝对路径形状（隐私 + 换机不可解释）。口径同 `_no_machine_paths` / `_c_public_surface`
#: / `test_leak_surface`——那边管**失败消息**与**入仓文件**，这里管**成功面**。
MACHINE_PATH = re.compile(r"C:[\\/]Users[\\/]|/Users/[A-Za-z]|/home/[a-z]"
                          r"|[A-Za-z]:\\\\[A-Za-z0-9_$&+.\-]+\\\\")


class JsonFaceNoMachinePathTest(unittest.TestCase):
    """成功面不得回吐本机绝对路径（2026-10-01 取证：`doctor` / `toolface` / `daemon status`
    三处机器面把 `C:\\\\Users\\\\<user>\\\\…` 原样写进 `--json`，而同一份纪律此前只覆盖失败
    消息与入仓文件）。跳过的 11 张面（见 `SKIP`，每条都点名了自己的覆盖专件）未纳入本判据。"""

    def test_success_faces_are_portable(self):
        _probe_faces()
        texts = dict(_CACHE["raw"])                      # 无参可跑的面（同一批已跑过）
        for name, argv in CANON.items():
            p = cli_harness.run_cli_proc([sys.executable, NF] + _canon_argv(name) + ["--json"],
                                         cwd=str(ROOT), env=_preset_env())
            texts[name] = p.stdout or ""
        # 面表之外的**人读面**（不带 `--json`、需要子旗标才看得到的那几处），
        # 2026-10-01 取证：`nf shell --verify` 会把 `<NF_HOME>/shell_history` 绝对路径打出来。
        for argv in (["shell", "--verify"], ["shell", "--baseline"],
                     ["shell", "--commands", "--json"], ["daemon", "status", "--json"]):
            p = cli_harness.run_cli_proc([sys.executable, NF] + argv, cwd=str(ROOT))
            texts[" ".join(argv)] = (p.stdout or "") + (p.stderr or "")
        pats = (MACHINE_PATH, re.compile(re.escape(os.path.expanduser("~")), re.I))
        bad = []
        for name, out in sorted(texts.items()):
            for pat in pats:
                m = pat.search(out)
                if m:
                    bad.append("%s → …%s…"
                               % (name, out[max(0, m.start() - 20):m.end() + 20]
                                  .replace("\n", " ")))
        self.assertEqual([], bad, "机器面回吐本机绝对路径（改走仓库相对 / `_portable_path`）：%s"
                         % bad[:6])


if __name__ == "__main__":
    unittest.main()
