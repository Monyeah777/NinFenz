#!/usr/bin/env python3
"""跨语言契约对拍器（W-10 / P-C0 走通件；P-C1 起真契约向量）。

读向量清单（nf-test-vectors/1），对每条向量跑各语言声明的命令，按 compare_rule 归一后
逐字节比对。纪律（§16.2/§16.8）：

  - 工具链缺席 → 该语言 UNKNOWN，**不下结论**；整条向量若无其他分歧则记 UNKNOWN；
  - 只有「可比且比错」才是 FAIL（偏离方标 FAIL，附期望值）；
  - probe 条目只探工具链在场，不比对输出；
  - 声明的实现**建不起来**（rc != 0 且不是「可执行文件不在」）→ FAIL：那是实现的失败，
    不是环境缺席，两者必须分开，否则「编译不过」会被 UNKNOWN 吞掉。

清单 schema（nf-test-vectors/1）每条向量：

    {
      "id": "...", "spec_clause": "RFC8785/3.2.3", "level": "L1",
      "input": "protocol/generated/test_vectors/xxx.json",
      "compare_rule": "byte" | "jcs",
      "expect": "ok" | "fail",          # fail = 各实现都必须非零退出且无标准输出
      "expected": "<ok 时的期望规范化文本>",
      "langs": {"rust": {"cmd": [...], "build": [...]}, ...}   # build 可省
    }

compare_rule：
  byte —— 先把 CRLF 折成 LF（同一实现在 Windows/Linux 的新行形态不同，是平台噪声不是语义
          分歧，§16.3 要求规则显式，故归一写在规则里），再逐字节比；
  jcs  —— 用 RFC 8785 本体（scripts/jcs.py 的 canonical_jcs，**不是** json.dumps 的近似）
          归一后比。历史上这里用 sort_keys+紧凑分隔冒充 JCS，是错的：那按码点序且用 Python
          的数字形态；D-10 明确 nf-canonical/1 不得充当 JCS，故改为真本体委托。
"""
import argparse
import contextlib
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess  # nosec B404 - 只跑清单里声明过的命令
import sys
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "desktop", "src"))
from core import json_doc  # noqa: E402 - 读 JSON 走仓库唯一读点

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_jcs_spec = importlib.util.spec_from_file_location(
    "nf_jcs_impl", os.path.join(_HERE, "jcs.py"))
_jcs = importlib.util.module_from_spec(_jcs_spec)
sys.modules["nf_jcs_impl"] = _jcs
_jcs_spec.loader.exec_module(_jcs)

#: 语言 → (可执行名, 「可用」探针参数)。探针不是形式主义：Windows 上常见
#: "C:/Program Files/dotnet/dotnet.exe" 这个**有宿主无 SDK** 的壳，shutil.which 会命中它，
#: 但一切构建都会失败。把"在场"收紧成"可用"，才不会让环境问题伪装成实现 FAIL。
#: 「wasm」不是语言而是**实现面**（第 5 部分微内核插件的宿主）：WASI 组件的宿主是 wasmtime。
#: 挂在同一张表里，插件对拍就能复用本器的仲裁与三态口径，无需另起一套。
#: 每个语言给**候选名**而非单名：Linux CI 上只有 python3，Windows 上通常只有 python。
_PROBE_ARGS = {
    "python": (("python", "python3"), ["--version"]),
    "rust": (("cargo",), ["--version"]),
    "csharp": (("dotnet",), ["--list-sdks"]),
    "wasm": (("wasmtime",), ["--version"]),
}
PROBES = {lang: names[0] for lang, (names, _args) in _PROBE_ARGS.items()}
LANGS = tuple(PROBES)

#: 工具链缺席时的兜底搜索目录（本机安装位置，不写进 PATH 也能被发现）。
#: 纪律不变：找不到仍是 UNKNOWN，**不下结论**。
#: NF_TOOLCHAIN_DIRS 是显式逃生口（CI 把工具链装在非标准前缀时用）。
_ENV_DIRS = ("NF_TOOLCHAIN_DIRS",)
_FALLBACK_DIRS = ("~/.cargo/bin", "~/.dotnet", "~/.local/bin")
_NFTOOLS = "~/.nftools"


def _fallback_dirs():
    dirs = []
    for name in _ENV_DIRS:
        raw = os.environ.get(name) or ""
        dirs.extend(p for p in raw.split(os.pathsep) if p)
    for hint in _FALLBACK_DIRS:
        dirs.append(os.path.expanduser(hint))
    nftools = os.path.expanduser(_NFTOOLS)
    if os.path.isdir(nftools):
        dirs.append(nftools)
        with contextlib.suppress(OSError):  # 目录在但读不了：按「没找到」处理，不打断
            dirs.extend(os.path.join(nftools, sub) for sub in sorted(os.listdir(nftools)))
    return [d for d in dirs if d]


def _candidates(exe):
    """候选路径：PATH 命中优先，其后本机常见安装前缀（去重、保序）。"""
    names = [exe] if isinstance(exe, str) else list(exe)
    out = []
    for name in names:
        found = shutil.which(name)
        if found and found not in out:
            out.append(found)
    wanted = list(names)
    if os.name == "nt":
        wanted += [n + ".exe" for n in names if not n.lower().endswith(".exe")]
    for d in _fallback_dirs():
        for n in wanted:
            p = os.path.join(d, n)
            if os.path.isfile(p) and p not in out:
                out.append(p)
    return out


def resolve_exe(exe, probe_args=None):
    """按名（或候选名列表）解析**可用**的可执行文件；找不到返回 None（→ UNKNOWN）。

    probe_args 给定时逐个候选真跑一次，只认返回 0 且 stdout 非空的——「在场」不等于「可用」。
    """
    for cand in _candidates(exe):
        if probe_args is None:
            return cand
        rc, out = run_cmd([cand] + list(probe_args), ROOT, timeout=60)
        if rc == 0 and out.strip():
            return cand
    return None


def toolchains():
    """→ {语言: 可用可执行路径 或 None}（不可用即 None，由调用方记 UNKNOWN）。"""
    return {lang: resolve_exe(names, args)
            for lang, (names, args) in sorted(_PROBE_ARGS.items())}


def canonical(rule, data):
    """按 compare_rule 归一（见模块串 §compare_rule）。"""
    if rule == "byte":
        return data.replace(b"\r\n", b"\n")
    if rule == "jcs":
        text = data.decode("utf-8")
        return _jcs.canonical_jcs(_jcs.loads_strict(text))
    raise ValueError(f"未知 compare_rule：{rule}（修复指引：用 byte 或 jcs）")


def run_cmd(cmd, cwd, timeout=120, stdin=None):
    """跑一条命令 → (rc, stdout)。找不到可执行文件 rc=-2；超时 rc=-9。

    stdin：向量可声明 stdin 文件（微内核插件的标准输入面——WASI 默认无 fs，输入只能走管道）。
    """
    try:
        proc = subprocess.run([str(x) for x in cmd], cwd=cwd, capture_output=True,  # nosec B603
                              input=stdin, timeout=timeout)
        return proc.returncode, proc.stdout
    except FileNotFoundError:
        return -2, b""
    except subprocess.TimeoutExpired:
        return -9, b""


def _with_exe(cmd, exe):
    """把声明命令的首元素换成**解析到的**可执行文件。

    语言的键（python/rust/csharp）就是工具链的声明；cmd[0] 只是称呼。本机 cargo/dotnet
    常不在 PATH（装在 ~/.cargo/bin、~/.dotnet），若照字面跑会得到 rc=-2 而误判成实现缺席。
    """
    parts = [str(x) for x in cmd]
    return [exe] + parts[1:]


def _stdin_bytes(spec, root):
    """向量声明的 stdin 夹具（相对 root）；没声明返回 None。"""
    rel = spec.get("stdin")
    if not rel:
        return None
    return (Path(root) / str(rel)).read_bytes()


def _run_declared(spec, key, lang, exe, runner, cache):
    """跑清单声明的命令（build 面按 (lang, cmd) 记忆化）。→ (rc, stdout) 或 None 表「没这步」。"""
    cmd = spec.get(key)
    if not cmd:
        return None
    if key == "build":
        memo = (lang, tuple(str(x) for x in cmd))
        if memo in cache:
            return cache[memo]
    rc, out = runner(_with_exe(cmd, exe), ROOT)
    if key == "build":
        cache[memo] = (rc, out)
    return rc, out


def verify(doc, root=ROOT, runner=run_cmd, tools=None, builds=None):
    """→ 报告：逐向量逐语言三态 + 整条/整体判决（PASS/FAIL/UNKNOWN）。

    builds 是跨调用复用的构建记忆（同一清单里多条向量共享同一次 cargo/dotnet 构建）。
    """
    tools = tools if tools is not None else toolchains()
    cache = builds if builds is not None else {}
    report = {"schema": "nf-cross-lang-report/1", "vectors": [], "verdict": "PASS"}
    for v in doc.get("vectors") or []:
        rule = str(v.get("compare_rule") or "byte")
        expect = str(v.get("expect") or "ok")
        expected = canonical(rule, str(v.get("expected") or "").encode("utf-8"))
        row = {"id": str(v.get("id")), "rule": rule, "expect": expect, "langs": {}}
        missing, mismatch = [], []
        for lang, spec in sorted((v.get("langs") or {}).items()):
            exe = tools.get(lang)
            if spec.get("probe"):
                if not exe:
                    row["langs"][lang] = {"status": "UNKNOWN",
                                          "detail": f"工具链缺席：{PROBES.get(lang, lang)}"}
                    missing.append(lang)
                    continue
                rc, out = runner(_with_exe(spec.get("cmd") or [], exe), root,
                                 stdin=_stdin_bytes(spec, root))
                ok = (rc == 0 and bool(out.strip()))
                row["langs"][lang] = {
                    "status": "PASS" if ok else "UNKNOWN",
                    "detail": (f"工具链探针（rc={rc}，输出 {len(out)} 字节"
                               f"{'' if ok else '：在场但无可用 SDK'}）")}
                if not ok:
                    missing.append(lang)
                continue
            if not exe:
                row["langs"][lang] = {"status": "UNKNOWN",
                                      "detail": f"工具链缺席：{PROBES.get(lang, lang)}"}
                missing.append(lang)
                continue
            built = _run_declared(spec, "build", lang, exe, runner, cache)
            if built is not None and built[0] != 0:
                rc_b, _ = built
                if rc_b == -2:
                    row["langs"][lang] = {"status": "UNKNOWN", "detail": "构建步骤的可执行文件缺席"}
                    missing.append(lang)
                else:
                    row["langs"][lang] = {
                        "status": "FAIL", "rc": rc_b,
                        "detail": f"声明的实现建不起来（rc={rc_b}）"}
                    mismatch.append(lang)
                continue
            rc, out = runner(_with_exe(spec.get("cmd") or [], exe), root,
                             stdin=_stdin_bytes(spec, root))
            if expect == "fail":
                ok = (rc != 0 and not out.strip())
                row["langs"][lang] = {
                    "status": "PASS" if ok else "FAIL", "rc": rc,
                    "detail": f"拒绝语义（rc={rc}，stdout {len(out)} 字节）"}
                if not ok:
                    mismatch.append(lang)
                continue
            try:
                got = canonical(rule, out)
            except (ValueError, UnicodeDecodeError) as exc:
                row["langs"][lang] = {"status": "FAIL", "rc": rc,
                                      "detail": f"输出无法按 {rule} 归一：{exc}"}
                mismatch.append(lang)
                continue
            ok = (rc == 0 and got == expected)
            row["langs"][lang] = {"status": "PASS" if ok else "FAIL", "rc": rc,
                                  "got": got.decode("utf-8", "replace")[:120]}
            if not ok:
                mismatch.append(lang)
        row["verdict"] = "FAIL" if mismatch else ("UNKNOWN" if missing else "PASS")
        report["vectors"].append(row)
    if any(r["verdict"] == "FAIL" for r in report["vectors"]):
        report["verdict"] = "FAIL"
    elif any(r["verdict"] == "UNKNOWN" for r in report["vectors"]):
        report["verdict"] = "UNKNOWN"
    report["toolchains"] = tools
    report["arbitration"] = arbitrate(report["vectors"])
    return report


def arbitrate(vectors):
    """多实现仲裁（P-C2）：**规范是权威**，多数票只作定位线索。

    可比值 = status ∈ {PASS, FAIL}（UNKNOWN 不参与投票）。
      - 无偏离 ⇒ PASS；
      - 单一偏离 ⇒ FAIL，该实现为首要嫌疑（规范为权威，不因多数而改判）；
      - 多数偏离 ⇒ **SPEC-GAP**：先怀疑规范/判据本身，禁止用多数票裁定"实现对"。
    """
    available, deviants = [], []
    for row in vectors:
        for lang, st in sorted((row.get("langs") or {}).items()):
            status = st.get("status")
            if status == "PASS":
                available.append("{}/{}".format(row.get("id"), lang))
            elif status == "FAIL":
                available.append("{}/{}".format(row.get("id"), lang))
                deviants.append("{}/{}".format(row.get("id"), lang))
    if not available:
        return {"outcome": "UNKNOWN", "clue": "无可比实现（工具链缺席）——不下结论"}
    if not deviants:
        return {"outcome": "PASS", "comparable": len(available),
                "clue": "所有可比实现与规范一致"}
    # N=2 时单一偏离就占 50%：照搬「多数偏离」会把它误判成 SPEC-GAP——那是把「无从分辨」
    # 说成「规范有缺口」。故 SPEC-GAP 需要**至少 2 个偏离方**（≈3 个可比实现里的多数）。
    # 期望值本身由规范导出，所以 N=2 下的偏离方仍然是确定的偏离方，判 FAIL 名正言顺。
    if len(deviants) >= 2 and len(deviants) * 2 >= len(available):
        return {"outcome": "SPEC-GAP", "suspects": deviants, "comparable": len(available),
                "clue": "多数可比实现偏离规范 ⇒ 先怀疑规范/判据本身；"
                        "多数票**不得**用作改判依据（INV-6：规范 > 实现）"}
    return {"outcome": "FAIL", "suspects": deviants, "comparable": len(available),
            "clue": "单一实现偏离规范 ⇒ 该实现为首要嫌疑；多数票仅作定位线索"}


def toolchain_versions(tools=None, runner=run_cmd):
    """各语言工具链自述版本（工具链 digest 的人读面；缺席记 UNKNOWN）。"""
    tools = tools if tools is not None else toolchains()
    args = {"python": ["--version"], "rust": ["--version"], "csharp": ["--version"]}
    out = {}
    for lang, exe in sorted(tools.items()):
        if not exe:
            out[lang] = None
            continue
        rc, stdout = runner([exe] + args.get(lang, ["--version"]), ROOT)
        text = stdout.decode("utf-8", "replace").strip()
        out[lang] = text if rc == 0 and text else f"rc={rc}"
    return out


#: 视为「可复核产物」的后缀（清单声明到的脚本 / 二进制 / 工程件）。
_ARTIFACT_SUFFIXES = (".exe", ".dll", ".wasm", ".pyd", ".py", ".csproj", ".toml")


def _candidate_paths(doc):
    """向量清单里声明到的、可能是在场文件的字面量（去重排序）。"""
    out = []
    for v in doc.get("vectors") or []:
        for spec in (v.get("langs") or {}).values():
            for key in ("cmd", "build"):
                for token in (spec.get(key) or []):
                    if str(token).endswith(_ARTIFACT_SUFFIXES):
                        out.append(str(token))
    return sorted(set(out))


def collect_digests(doc, tools=None, root=ROOT):
    """→ 工具链自述版本 + 声明产物的 sha256（§16.6「toolchain digest 记录在场」的本地可复核面）。

    容器密封跑不了时，**这一份**就是「输入可枚举、结果可哈希」的替代载体：
    换工具链或换产物，digest 必变，可与上次报告逐字节对照。
    """
    tools = tools if tools is not None else toolchains()
    artifacts = {}
    for rel in _candidate_paths(doc):
        path = Path(rel)
        if not path.is_absolute():
            path = Path(root) / rel
        if path.is_file():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            artifacts[rel] = f"sha256:{digest}（{path.stat().st_size} B）"
    return {"schema": "nf-cross-lang-digest/1", "tools": toolchain_versions(tools),
            "artifacts": artifacts}


# ---------------------------------------------------------------- 覆盖棘轮（§16.3）
#: 向量清单位置（棘轮与对拍器读同一组面）
VECTOR_DIR = "protocol/generated/test_vectors"
MANIFESTS = ("jcs_conformance.json", "jcs_reject.json", "jcs_basic.json", "harness.json")


def coverage(docs):
    """→ {语言: [该语言**真实现**（非 probe）参与的 spec_clause，去重排序]}。

    probe 条目只探工具链在场，不构成实现覆盖，故不计入棘轮（否则加一条探针就能刷覆盖）。
    """
    out = {}
    for doc in docs:
        for v in (doc.get("vectors") or []):
            clause = str(v.get("spec_clause") or "")
            if not clause:
                continue
            for lang, spec in (v.get("langs") or {}).items():
                if spec.get("probe"):
                    continue
                out.setdefault(lang, set()).add(clause)
    return {lang: sorted(v) for lang, v in sorted(out.items())}


def ratchet_regressions(current, frozen):
    """当前覆盖**缺**了冻结基线里的哪条（返回人读描述；空表 = 没退化）。"""
    bad = []
    for lang, clauses in sorted((frozen.get("clauses") or {}).items()):
        have = set(current.get(lang) or [])
        for clause in clauses:
            if clause not in have:
                bad.append(f"{lang} 少覆盖 {clause}")
    return bad


def load_manifests(root=ROOT, names=MANIFESTS):
    """按名读在场清单（缺件跳过，不裸崩）。"""
    docs = []
    for name in names:
        p = Path(root) / VECTOR_DIR / name
        if p.is_file():
            docs.append(json_doc.loads(p.read_text(encoding="utf-8"), dict, what=name))
    return docs


# ---------------------------------------------------------------- self-test
#: 可执行名 → 语言键（命令首元素是 exe，不是语言名）。
_EXE_LANG = {"python": "python", "cargo": "rust", "dotnet": "csharp"}


def _fake(expected_by_lang, missing=()):
    tools = {lang: (None if lang in missing else "/fake/" + lang) for lang in LANGS}
    by_exe = {v: k for k, v in tools.items() if v}
    def runner(cmd, cwd, timeout=120, stdin=None):
        first = str(cmd[0])
        lang = by_exe.get(first, _EXE_LANG.get(first, first))
        return 0, expected_by_lang.get(lang, b"")
    return tools, runner


def self_test():
    doc = {"schema": "nf-test-vectors/1", "vectors": [
        {"id": "t", "compare_rule": "byte", "expected": "ok\n",
         "langs": {"python": {"cmd": ["python"]}, "rust": {"cmd": ["cargo"]},
                   "csharp": {"cmd": ["dotnet"]}}}]}
    # 1) 三语言一致 → PASS
    tools, runner = _fake({"python": b"ok\n", "rust": b"ok\n", "csharp": b"ok\n"})
    assert verify(doc, runner=runner, tools=tools)["verdict"] == "PASS"  # nosec B101
    # 2) 一语言偏离 → FAIL
    tools, runner = _fake({"python": b"ok\n", "rust": b"bad\n", "csharp": b"ok\n"})
    rep = verify(doc, runner=runner, tools=tools)
    assert rep["verdict"] == "FAIL" and rep["vectors"][0]["langs"]["rust"]["status"] == "FAIL"  # nosec B101
    # 3) 工具链缺席且其余一致 → UNKNOWN（不下结论）
    tools, runner = _fake({"python": b"ok\n", "csharp": b"ok\n"}, missing=("rust",))
    rep = verify(doc, runner=runner, tools=tools)
    assert rep["verdict"] == "UNKNOWN", rep  # nosec B101
    # 4) probe 只探在场：缺席即 UNKNOWN
    pdoc = {"schema": "nf-test-vectors/1", "vectors": [
        {"id": "p", "compare_rule": "byte", "expected": "",
         "langs": {"rust": {"cmd": ["cargo"], "probe": True}}}]}
    assert verify(pdoc, runner=runner, tools=tools)["verdict"] == "UNKNOWN"  # nosec B101
    # 5) probe 在场但输出为空（有 exe 无 SDK）→ 仍 UNKNOWN
    all_tools = {lang: "/fake/" + lang for lang in LANGS}
    def empty(cmd, cwd, timeout=120, stdin=None):
        return 0, b""
    assert verify(pdoc, runner=empty, tools=all_tools)["verdict"] == "UNKNOWN"  # nosec B101
    # 6) 构建失败（非「exe 缺席」）→ FAIL，不被 UNKNOWN 吞
    bdoc = {"schema": "nf-test-vectors/1", "vectors": [
        {"id": "b", "compare_rule": "byte", "expected": "ok\n",
         "langs": {"rust": {"build": ["cargo", "build"], "cmd": ["cargo", "run"]}}}]}
    def broke(cmd, cwd, timeout=120, stdin=None):
        return (1, b"") if str(cmd[1]) == "build" else (0, b"ok\n")

    rep = verify(bdoc, runner=broke, tools=all_tools)
    assert rep["verdict"] == "FAIL", rep  # nosec B101
    # 7) 构建步骤 exe 缺席 → UNKNOWN（环境事实）
    tools_gone = dict.fromkeys(LANGS)
    tools_gone["rust"] = "/fake/rust"
    assert verify(bdoc, runner=lambda c, w, t=120, stdin=None: (-2, b""),
                  tools=tools_gone)["verdict"] == "UNKNOWN"  # nosec B101
    # 8) expect=fail：非零退出 + 空 stdout 才算各实现都拒绝
    fdoc = {"schema": "nf-test-vectors/1", "vectors": [
        {"id": "f", "compare_rule": "byte", "expect": "fail", "expected": "",
         "langs": {"python": {"cmd": ["python"]}, "rust": {"cmd": ["cargo"]}}}]}
    tools3, _ = _fake({})
    def okall(cmd, cwd, timeout=120, stdin=None):
        return 1, b""
    assert verify(fdoc, runner=okall, tools=tools3)["verdict"] == "PASS"  # nosec B101
    def bad(cmd, cwd, timeout=120, stdin=None):
        return (1, b"") if "python" in str(cmd[0]) else (0, b"{}")

    rep = verify(fdoc, runner=bad, tools=tools3)
    assert rep["verdict"] == "FAIL" and rep["vectors"][0]["langs"]["rust"]["status"] == "FAIL"  # nosec B101
    # 9) jcs 规则走真 JCS 本体（不是 json.dumps 近似）：星平面键序
    astral = b'{"\\ud83d\\ude00":1,"\\ue000":2}'
    got = canonical("jcs", astral)
    assert got == '{"\U0001F600":1,"\ue000":2}'.encode("utf-8"), got  # nosec B101
    # 12) digest 面：同清单同产物必得同摘要，且缺席产物不入表（不编路径）
    probe = {"schema": "nf-test-vectors/1", "vectors": [
        {"id": "d", "compare_rule": "byte", "expected": "ok",
         "langs": {"python": {"cmd": ["python", "scripts/jcs.py", "--file", "x"]}}}]}
    dig = collect_digests(probe, tools={})
    assert dig["artifacts"].get("scripts/jcs.py", "").startswith("sha256:"), dig
    assert "no/such/file.py" not in dig["artifacts"]
    assert collect_digests(probe, tools={})["artifacts"] == dig["artifacts"], "摘要必须可复算"
    # 10) 工具链解析：PATH 命中优先；找不到即 None（不自造）
    assert resolve_exe("definitely-not-a-real-exe-xyz") is None  # nosec B101
    # 11) 两个可比实现里的单一偏离 → FAIL（不是 SPEC-GAP）：N=2 根本没有「多数」可言。
    #     实测由 512 MiB 插件对拍抓到：当时 wasm 一侧偏离，却被 N=2 的旧规则判成 SPEC-GAP。
    two = [{"id": "v", "langs": {"python": {"status": "PASS"}, "wasm": {"status": "FAIL"}}}]
    got2 = arbitrate(two)
    assert got2["outcome"] == "FAIL" and got2["suspects"] == ["v/wasm"], got2  # nosec B101
    three = [{"id": "v", "langs": {"python": {"status": "FAIL"}, "rust": {"status": "FAIL"},
                                   "csharp": {"status": "PASS"}}}]
    assert arbitrate(three)["outcome"] == "SPEC-GAP"  # nosec B101
    print("self-test OK（一致=PASS / 偏离=FAIL / 缺席=UNKNOWN / probe 三态 / 空 SDK=UNKNOWN / "
          "构建失败=FAIL / 构建 exe 缺席=UNKNOWN / 拒绝语义 / jcs 真本体 / 解析兜底）")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="跨语言契约对拍器（只读）")
    ap.add_argument("--manifest", default="")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--versions", action="store_true", help="附工具链自述版本")
    ap.add_argument("--coverage", action="store_true",
                    help="打印各实现覆盖的 spec_clause 并核对覆盖棘轮（退化即 exit 1）")
    ap.add_argument("--digest", action="store_true",
                    help="报告里附工具链版本 + 声明产物的 sha256（密封跑不了时的可复核替代）")
    ap.add_argument("--require-full", action="store_true",
                    help="full 模式：任一处 UNKNOWN 即 exit 1（§16.5：full 要求 UNKNOWN=0）")
    args = ap.parse_args(argv)
    if args.self_test:
        return self_test()
    if args.coverage:
        cur = coverage(load_manifests(ROOT))
        frozen_path = Path(ROOT) / VECTOR_DIR / "ratchet.json"
        frozen = (json_doc.loads(frozen_path.read_text(encoding="utf-8"), dict, what="ratchet")
                  if frozen_path.is_file() else {})
        bad = ratchet_regressions(cur, frozen)
        print(json.dumps({"kind": "nf-cross-lang-coverage", "clauses": cur,
                          "frozen": frozen.get("clauses") or {}, "regressions": bad},
                         ensure_ascii=False, indent=2, sort_keys=True))
        return 1 if bad else 0
    if not args.manifest:
        print("  ✗ 缺 --manifest（修复指引：给向量清单路径）", file=sys.stderr)
        return 2
    doc = json_doc.loads(Path(args.manifest).read_text(encoding="utf-8"), dict,
                         what="向量清单")
    tools = toolchains()
    rep = verify(doc, root=ROOT, tools=tools)
    if args.versions or args.digest:
        rep["versions"] = toolchain_versions(tools)
    if args.digest:
        rep["digest"] = collect_digests(doc, tools)
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("== 跨语言对拍（{}）==".format(rep["verdict"]))
        arb = rep.get("arbitration") or {}
        print("  仲裁：{}（{}）".format(arb.get("outcome"), arb.get("clue")))
        for s in arb.get("suspects") or []:
            print(f"    嫌疑：{s}")
        if rep.get("digest"):
            dig = rep["digest"]
            print("  工具链：" + " · ".join(f"{k}={v}" for k, v in sorted(dig["tools"].items())))
            print(f"  产物摘要：{len(dig['artifacts'])} 件（sha256 见 --json 报告）")
        for row in rep["vectors"]:
            print("  {} [{}]".format(row["id"], row["verdict"]))
            for lang, st in sorted(row["langs"].items()):
                note = st.get("detail") or st.get("got", "")
                print(f"    {lang:<7} {st['status']:<8} {note}")
    if args.require_full and rep["verdict"] != "PASS":
        print(f"full 模式要求 UNKNOWN=0：当前 {rep['verdict']}"
              "（修复指引：装齐三工具链，或改跑 local 模式）", file=sys.stderr)
        return 1
    return 1 if rep["verdict"] == "FAIL" else 0


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        if hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8")
    raise SystemExit(main())
