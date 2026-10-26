# -*- coding: utf-8 -*-
"""门禁引擎 ↔ verify.sh 的**逐 check 判据等价性**差分测试。

为什么必须有它
--------------
`desktop/src/core/gate_engine.py` 声称「只做编排、不改判据」。这个声称不能靠自述成立——
本用例把它变成**可执行的证明**：同一次运行里

1. 用插桩档跑一遍 bash 门禁（`verify_timed.sh`：只加计时、主执行体改为逐 check 计时，
   **每条 check 的 stdout 单独落盘**；check12 的 unittest 换成一个快模块，因为它的耗时
   与本等价性无关，且单跑一次要 23 分钟）；
2. 用引擎跑一遍同样这些 check；
3. 逐 check 比对 **verdict 行**（`[PASS]/[FAIL]/[WARN]` 及其文案）**逐字相同**。

比对口径
--------
只比 verdict 行与条数：banner 也一并比（`== [N/…` 开头那行），但统计行 `[i] …` 不参与
（引擎的统计面是可选的白名单，不属于判据）。**条数不同即失败**——少一条 PASS 也可能是
判据漂移（例如某条断言被吞掉）。

未迁入的 check（仍在 bash 里）由 `gate_engine.PENDING` 如实列出，本用例**只对已迁入的
那些断言等价**，不对未迁入的假装等价。

跑法
----
    python -m unittest tests.test_gate_engine_parity        # 走缓存（快）
    NF_PARITY_FORCE=1 python -m unittest tests.test_gate_engine_parity   # 强制重跑 bash（慢）
"""
from __future__ import annotations

import hashlib
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import gate_engine  # noqa: E402
from core import posix_shell as psh  # noqa: E402

BANNER = re.compile(r"^== \[(\d+)/")
VERDICT = re.compile(r"^\s*\[(PASS|FAIL|WARN)\] (.*)$")
VERIFY_TEXT = (ROOT / "verify.sh").read_text(encoding="utf-8")
BASH = psh.find_posix_shell()

#: 聚合门：失败时必须「N 条子面明细 + 1 条汇总」的四条（工作包 C）。
#: 三条执行体不同（check32 委托 / check33/36 进程内 / check35 仍在 PENDING），
#: 但**失败分支的呈现口径**只由 verify.sh 定义——故本组直接跑 bash 原文取真值。
AGGREGATE_GATES = (32, 33, 35, 36)

#: 探针目录（内部档案：计划期产物不进公开仓库）。缺失即跳过，不假装通过。
PROBE = ROOT / ".rivet" / "private_archive" / "2026-10-15_gate-speedup-probe"
TARGETS = [1, 3, 8, 13, 14, 15, 16, 20, 23, 24, 25, 26, 27, 28, 29, 30,
           31, 32, 33, 34, 35, 36, 37, 39, 40]
#: bash 真值落点：**仓库之外**（放树内会被 check33 的编码卫生扫到自己的临时日志，
#: 形成自指噪声；放 /tmp 又在「每步独立 shell」的工作流里步间不留存）。
PARITY_DIR = ROOT.parent / "_nf_parity"
CACHE = PARITY_DIR / "bash_verdicts.txt"
#: 缓存键前缀。键 = HEAD 提交 + verify.sh sha256：bash 真值既依赖 verify.sh，也依赖
#: 工作树里的源码（如 check40 扫 asset_contract），只校验其中一项都会漏。
CACHE_PREFIX = "# parity truth key "


def _git(*args: str) -> tuple[int, str]:
    """跑只读 git（`core.quotepath=false`：中文路径不转义，指纹才稳定）。"""
    try:
        p = subprocess.run(["git", "-c", "core.quotepath=false", *args],
                           cwd=str(ROOT), capture_output=True, text=True,
                           encoding="utf-8", timeout=120)
    except (OSError, subprocess.SubprocessError):
        return -1, ""
    return p.returncode, p.stdout.strip()


def _truth_key() -> tuple[str, bool] | None:
    """→ (缓存键, 工作树是否干净)；git 不可用 → None（禁用缓存：宁可慢，不复用可疑真值）。

    为什么键里要有 HEAD：真值不只由 verify.sh 决定，还读工作树源码；只看 verify.sh 会漏。
    为什么脏树既不复用也不写缓存：脏树的真值只对那一刻有效（2026-10-19 实测：并发写者
    改 engine/rust 期间生成过一版真值，若落缓存会被之后「看似干净」的树错误复用）。
    """
    rc, head = _git("rev-parse", "HEAD")
    if rc != 0:
        return None
    rc, status = _git("status", "--porcelain")
    if rc != 0:
        return None
    verify_sha = hashlib.sha256(VERIFY_TEXT.encode("utf-8")).hexdigest()
    return (f"{CACHE_PREFIX}head={head} verify={verify_sha}", not status)


def _parse_verdicts(text: str) -> dict[int, list[str]]:
    """从门禁 stdout 抽出 {check 号: [verdict 行]}。

    把**连续的 FAIL 行**按空格拼成一条：bash 把 heredoc 的多行 `[FAIL] …`
    分行打印，而进程内路径拿到的是 `tail | tr '\\n' ' '` 的**拼接串**；
    拼接后仍要求**逐字节相同**，不放宽任何判据。
    """
    out: dict[int, list[str]] = {}
    cur: int | None = None
    for line in text.splitlines():
        m = BANNER.match(line)
        if m:
            cur = int(m.group(1))
            out.setdefault(cur, [])
            continue
        v = VERDICT.match(line)
        if v and cur is not None:
            tag, msg = v.group(1), v.group(2)
            if tag == "FAIL" and out[cur] and out[cur][-1].startswith("[FAIL] "):
                out[cur][-1] = "%s %s" % (out[cur][-1], msg)
                continue
            out[cur].append("[%s] %s" % (tag, msg))
    return out


def _read_cache(key: str) -> dict[int, list[str]] | None:
    """读缓存；**只有**键（HEAD + verify.sh 指纹）一致才复用，否则返回 None（→ 重跑真值）。

    首行是键。为什么必须校验：真源/基线一变，旧真值仍然「格式合法」，静默复用要么把
    正确抽取判成假红、要么把真漂移掩盖成假绿——两者都破坏等价性证明。
    """
    if not CACHE.is_file():
        return None
    text = CACHE.read_text(encoding="utf-8")
    first, _, rest = text.partition("\n")
    if first != key:
        return None
    return _parse_verdicts(rest)


def _bash_verdicts() -> dict[int, list[str]]:
    """跑**定向** bash 真值（只抽取目标 check 的函数体，不碰 check12 的 3035 个单测）。

    为什么不直接跑 verify.sh：主执行体会连 check12 一起跑，实测 1401 s；等价性证明
    只需要目标这些条。抽取是机械的（`extract_checks.py`，按第 0 列独占 `}` 收尾）。
    """
    runner = PROBE / "bash_targets.sh"
    if not runner.is_file():
        raise unittest.SkipTest("缺定向真值跑法（%s）——无法取得 bash 侧真值" % runner)
    subprocess.run(["bash", str(runner)], cwd=str(ROOT), check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    merged: dict[int, list[str]] = {}
    for n in TARGETS:
        f = PARITY_DIR / ("out_check%d.log" % n)
        if f.is_file():
            merged.update(_parse_verdicts(f.read_text(encoding="utf-8", errors="replace")))
    # 残缺真值是「抽取器坏了」而不是「判据漂移」：不许进缓存、也不许拿去比对。
    # 实测踩坑：check1/3/4/5/6 自 8789d46d 起调 `_decl_check`（定义在 check 体之外），
    # 旧抽取器只抽 check 体 → `command not found` → 这些 check 的 verdict 整条消失。
    missing = [n for n in TARGETS if n not in merged]
    if missing:
        raise RuntimeError(
            f"bash 定向真值缺 check{missing}——抽取器/环境坏了，残缺真值不能进缓存"
            "（修复指引：bash_targets.sh 是否把 check 体之外的 helper 定义一起抽到了？）"
        )
    return merged


class GateEngineParityTest(unittest.TestCase):
    """引擎输出必须与 bash 门禁逐字一致（只看已迁入的那些 check）。"""

    @classmethod
    def setUpClass(cls) -> None:
        force = os.environ.get("NF_PARITY_FORCE")
        keyed = _truth_key()
        clean = bool(keyed and keyed[1])
        cls.bash = None
        if keyed and clean and not force:
            cls.bash = _read_cache(keyed[0])
        if cls.bash is None:
            cls.bash = _bash_verdicts()
            # 只有干净树的真值才是可复用的：脏树的真值不落缓存。
            if clean and keyed is not None:
                try:
                    CACHE.parent.mkdir(parents=True, exist_ok=True)
                    merged = [keyed[0]]
                    for n in sorted(cls.bash):
                        merged.append("== [%d/x] cached ==" % n)
                        merged.extend(cls.bash[n])
                    CACHE.write_text("\n".join(merged), encoding="utf-8")
                except OSError:
                    pass
        gate_engine.build_registry()
        cls.engine = {}
        for v in gate_engine.run_checks(ROOT):
            cls.engine[int(v.name.replace("check", ""))] = [
                "[%s] %s" % (s, m) for s, m in v.verdicts]

    def test_ported_checks_are_covered_by_bash_truth(self) -> None:
        """已迁入的每条 check 都必须在 bash 侧找得到真值（否则等价性无从谈起）。"""
        missing = sorted(set(self.engine) - set(self.bash))
        self.assertEqual([], missing,
                         "引擎已迁入但 bash 侧无对应真值：%s" % missing)

    def test_verdict_lines_match_byte_for_byte(self) -> None:
        """逐 check：verdict 行**逐字 + 条数**相同。"""
        diffs = []
        for num in sorted(self.engine):
            got, want = self.engine[num], self.bash.get(num, [])
            if got != want:
                diffs.append(
                    "check%d：\n  引擎=%s\n  bash=%s" % (num, got, want))
        self.assertEqual([], diffs,
                         "引擎与 bash 判据不一致（%d 条）：\n%s" % (len(diffs), "\n".join(diffs)))

    def test_no_engine_check_is_silently_missing_from_registry(self) -> None:
        """登记表与 PENDING **必须恰好覆盖 check1-42**——不许有 check 从两边都消失。

        这是「check 只增不减」在工程上的牙齿：漏一条会被这里抓住。
        2026-10-26（T2.3）：check41/42 此前两边都不在（覆盖 40/42），已补进 PENDING；
        覆盖面断言随之从 1-40 收紧到 1-42。
        """
        gate_engine.build_registry()
        covered = set(gate_engine.REGISTRY) | set(gate_engine.PENDING)
        self.assertEqual(set(range(1, 43)), covered,
                         "check 覆盖面缺口：%s" % sorted(set(range(1, 43)) - covered))
        overlap = set(gate_engine.REGISTRY) & set(gate_engine.PENDING)
        self.assertEqual(set(), overlap, "同一条 check 既已迁入又标未迁入：%s" % sorted(overlap))

    def test_engine_never_reports_green_for_pending(self) -> None:
        """未迁入的 check 不得出现在引擎结果里充数（不许拿 PENDING 装绿）。"""
        leaked = sorted(set(self.engine) & set(gate_engine.PENDING))
        self.assertEqual([], leaked, "PENDING 的 check 混进了引擎结果：%s" % leaked)

    def test_registry_specs_are_wellformed(self) -> None:
        """每条已迁入的 check 都要有：banner、非空实现、明确 kind。"""
        gate_engine.build_registry()
        bad = []
        for num, spec in sorted(gate_engine.REGISTRY.items()):
            if not spec.title.startswith("== [%d/" % num):
                bad.append("check%d banner 未取自 verify.sh：%r" % (num, spec.title[:40]))
            if spec.kind not in ("native", "delegated", "inproc"):
                bad.append("check%d 未知 kind：%r" % (num, spec.kind))
            if spec.impl is None:
                bad.append("check%d 无实现" % num)
        self.assertEqual([], bad, "\n".join(bad))

    def test_inproc_checks_have_labels(self) -> None:
        """进程内 check **必须**能抽到成功文案——抽不到就会发出空 PASS（实测踩过）。"""
        text = (ROOT / "verify.sh").read_text(encoding="utf-8")
        bad = []
        for num in gate_engine.INPROC_CHECKS:
            labels = gate_engine.gate_labels.parse_labels(text, num)
            if not labels.pass_lines:
                bad.append("check%d 抽取不到成功文案" % num)
            if any(not s.strip() for s in labels.pass_lines):
                bad.append("check%d 含空文案" % num)
        self.assertEqual([], bad, "\n".join(bad))


#: check39 成功文案的回归锚点（真源仍是 verify.sh 里的 `ok` 字面量；这里只判「抽到了没」）。
CHECK39_ANCHORS = ("五分钟入口可跑", "输出确定")


class GateLabelsExtractionTest(unittest.TestCase):
    """抽取层自身的回归：成功文案必须**整条**抽到，不能被 then 空壳 / 引号 / 分支语义吞掉。"""

    def test_check39_success_text_is_fully_extracted(self) -> None:
        """check39 的两条成功文案必须完整抽到（含 quickstart 追加在尾部的判据）。

        为什么单列一条：逐字 parity 依赖 bash 真值缓存，缓存过期时会把**正确的抽取**
        判成假红（2026-10-19 实测）；这条不依赖任何缓存，是抽取层的独立回归锚。
        """
        labels = gate_engine.gate_labels.parse_labels(VERIFY_TEXT, 39)
        joined = "\n".join(labels.pass_lines)
        for anchor in CHECK39_ANCHORS:
            self.assertIn(anchor, VERIFY_TEXT,
                          f"verify.sh 里已没有锚点 {anchor!r}——回归锚点须随真源同步")
            self.assertIn(anchor, joined, f"check39 成功文案漏抽：{anchor!r}")
        self.assertEqual(2, len(labels.pass_lines),
                         f"check39 成功路径文案条数异常：{labels.pass_lines}")

    def test_pass_lines_are_verbatim_ok_literals(self) -> None:
        """抽到的成功文案必须逐字等于体里某条 `ok` 字面量（防截断 / 拼接 / 凭空生成）。"""
        bad = []
        for num in gate_engine.INPROC_CHECKS:
            labels = gate_engine.gate_labels.parse_labels(VERIFY_TEXT, num)
            for s in labels.pass_lines:
                if s not in labels.ok:
                    bad.append(f"check{num}：抽取值不是体里的 ok 字面量：{s[:60]!r}")
        self.assertEqual([], bad, "\n".join(bad))


#: verify.sh 里已升级为逐条透出的聚合门（41/42 是同一口径的先行面）。
UPGRADED_GATES = (32, 33, 35, 36, 41, 42)

#: 汇总句模板（`$_emitted` 是 bash 的计数变量）。测试侧从 verify.sh 现读，不硬编码。
_AGG_SUMMARY_RE = re.compile(r'no\s+"([^"]*?以上\s+\$_emitted\s+条子面失败[^"]*)"')


def _aggregate_summary(num: int) -> str:
    """从 verify.sh 现读该 check 的汇总句模板（不在测试里硬编码——硬编码就是第二份文案）。"""
    body = gate_engine.gate_labels.check_body(VERIFY_TEXT, num)
    m = _AGG_SUMMARY_RE.search(body)
    return m.group(1) if m else ""


def _tail_census(text: str) -> tuple[list[int], list[int]]:
    """扫 verify.sh → (贴整段日志尾部的 check, 把 verdict 压成一行的 check)。

    - `| sed`：失败时把日志尾部贴出来，是**诊断上下文**，不是一行 verdict；
    - `| tr` ：`no "前缀$(tail -N log | tr '\\n' ' ')"` —— 子面明细被压成一行 verdict。
    """
    dump, verdict = set(), set()
    for line in text.splitlines():
        if "tail -" not in line:
            continue
        m = re.search(r"nf_check(\d+)", line)
        if not m:
            continue
        if "| sed" in line:
            dump.add(int(m.group(1)))
        elif "| tr" in line:
            verdict.add(int(m.group(1)))
    return sorted(dump), sorted(verdict)


def _upgraded_gates(text: str) -> list[int]:
    """→ bash 体里已有「遍历日志、逐条透出 [FAIL]」口径的 check（顺序按编号）。"""
    return [n for n in range(1, 43)
            if 'case "$_line" in' in gate_engine.gate_labels.check_body(text, n)]


def _bash_path(p) -> str:
    """Windows 盘符路径 → Git Bash 可执行的 `/c/...`；POSIX 平台原样返回。

    为什么需要：bash 的 `"$PY3"` 要真的 exec 这个假解释器，`C:\\…` 在 Git Bash 里
    不是可执行路径；而 python 的 `tempfile` 只会给 Windows 路径。
    """
    m = re.match(r"^([A-Za-z]):[\\/](.*)$", str(p))
    if not m:
        return str(p)
    return "/" + m.group(1).lower() + "/" + m.group(2).replace("\\", "/")


def _bash_aggregate_fails(num: int, problems: list[str]) -> list[str]:
    """跑**真实 check 的 bash 失败分支**：PY3 换成「只写 N 条 [FAIL] 再退出 1」的假解释器。

    为什么要这样构造：明细条数、`[FAIL] ` 前缀剥离、汇总里的计数都走 verify.sh 原文，
    不是把打印逻辑复制一遍——复制出来的夹具只能证明夹具自洽。
    """
    if not BASH:
        raise unittest.SkipTest("没有 bash：聚合门诊断口径无法验证")
    tmp = Path(tempfile.mkdtemp(prefix="nf-agg-"))
    try:
        stub = tmp / "stub_py"
        lines = ["#!/usr/bin/env bash", "cat >/dev/null 2>&1 || true"]
        for p in problems:
            lines.append("printf '%s\\n' " + shlex.quote("[FAIL] " + p))
        lines += ["printf '统计行\\n'", "exit 1"]
        stub.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        stub.chmod(0o755)
        script = (
            "set -u\nPASS=0; FAIL=0; WARN=0\n"
            "ok(){ PASS=$((PASS+1)); }\n"
            "no(){ FAIL=$((FAIL+1)); printf '  [FAIL] %s\\n' \"$1\"; }\n"
            "wn(){ WARN=$((WARN+1)); }\n"
            "PY3=" + shlex.quote(_bash_path(stub)) + "\n"
            "NFL_TMP=" + shlex.quote(_bash_path(tmp)) + "\n"
            + gate_engine.gate_labels.check_body(VERIFY_TEXT, num) + "\n"
            "check" + str(num) + "\n")
        # 落盘再跑：check33 的整段体超过 Windows 命令行长度上限，`bash -c` 会被截断。
        runner = tmp / "run_check.sh"
        runner.write_text(script, encoding="utf-8", newline="\n")
        proc = subprocess.run([BASH, str(runner)], cwd=str(ROOT),
                              capture_output=True, text=True, encoding="utf-8")
        return [ln[len("  [FAIL] "):] for ln in proc.stdout.splitlines()
                if ln.startswith("  [FAIL] ")]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@unittest.skipUnless(BASH, "没有 bash：聚合门诊断口径无法验证")
class AggregateFailDiagnosticsTest(unittest.TestCase):
    """聚合门失败：N 条子面明细 + 1 条汇总，且汇总句逐字来自 verify.sh。"""

    def test_bash_emits_n_details_plus_one_summary(self):
        """构造 N 个子面失败 → bash 必须输出 N 条明细 + 1 条汇总（N=1/3 都验）。"""
        for num in AGGREGATE_GATES:
            body = gate_engine.gate_labels.check_body(VERIFY_TEXT, num)
            self.assertIn('case "$_line" in', body,
                          f"check{num} 的 bash 体没有逐条透出口径（只剩 tail 压缩？）")
            tmpl = _aggregate_summary(num)
            self.assertTrue(tmpl, f"check{num} 未从 verify.sh 抽到汇总句")
            self.assertIn(tmpl, VERIFY_TEXT, f"check{num} 汇总句不是 verify.sh 的逐字原文")
            for n in (1, 3):
                problems = [f"子面失败{i}" for i in range(1, n + 1)]
                with self.subTest(check=num, n=n):
                    self.assertEqual(
                        problems + [tmpl.replace("$_emitted", str(n))],
                        _bash_aggregate_fails(num, problems))

    def test_no_detail_falls_back_to_one_tail_line(self):
        """日志里没有 [FAIL] 行时不得凭空造汇总：仍是**一条** tail 摘要。"""
        for num in AGGREGATE_GATES:
            with self.subTest(check=num):
                got = _bash_aggregate_fails(num, [])
                self.assertEqual(1, len(got), got)
                self.assertNotIn("条子面失败", got[0])


class AggregateGateCensusTest(unittest.TestCase):
    """模式普查：verify.sh 里 tail 压缩的全量清单（防止“这是个案例”被误读）。"""

    def test_tail_compression_sites(self):
        """23 处 tail：20 处压 verdict（check23-42）+ 3 处贴日志尾部（check12×2/check18）。"""
        total = sum(1 for line in VERIFY_TEXT.splitlines() if "tail -" in line)
        dump, verdict = _tail_census(VERIFY_TEXT)
        self.assertEqual(23, total)
        self.assertEqual([12, 18], dump)
        self.assertEqual(list(range(23, 43)), verdict)

    def test_upgraded_gates_are_exactly_the_six(self):
        """逐条透出口径当前覆盖 32/33/35/36/41/42；其余 14 处仍是模式存量。"""
        self.assertEqual(list(UPGRADED_GATES), _upgraded_gates(VERIFY_TEXT))

    def test_summary_has_single_source(self):
        """汇总句只在 verify.sh 出现一次；生产模块不得内置任何一条具体文案。"""
        for num in AGGREGATE_GATES:
            tmpl = _aggregate_summary(num)
            self.assertTrue(tmpl, f"check{num} 未从 verify.sh 抽到汇总句")
            self.assertEqual(1, VERIFY_TEXT.count(tmpl),
                             f"check{num} 汇总句在 verify.sh 里不是唯一一份")
        for rel in ("desktop/src/core/gate_engine.py", "desktop/src/core/gate_labels.py"):
            src = (ROOT / rel).read_text(encoding="utf-8")
            for text in ("条子面失败", "nf_check32.log", "质量纵深汇总异常"):
                self.assertNotIn(text, src, f"{rel} 内置了汇总句片段：{text}")


if __name__ == "__main__":
    unittest.main()
