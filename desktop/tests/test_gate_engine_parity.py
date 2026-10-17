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

import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import gate_engine  # noqa: E402

BANNER = re.compile(r"^== \[(\d+)/")
VERDICT = re.compile(r"^\s*\[(PASS|FAIL|WARN)\] (.*)$")

#: 探针目录（内部档案：计划期产物不进公开仓库）。缺失即跳过，不假装通过。
PROBE = ROOT / ".rivet" / "private_archive" / "2026-10-15_gate-speedup-probe"
TARGETS = [1, 3, 8, 13, 14, 15, 16, 20, 23, 24, 25, 26, 27, 28, 29, 30,
           31, 32, 33, 34, 35, 36, 37, 39, 40]
#: bash 真值落点：**仓库之外**（放树内会被 check33 的编码卫生扫到自己的临时日志，
#: 形成自指噪声；放 /tmp 又在「每步独立 shell」的工作流里步间不留存）。
PARITY_DIR = ROOT.parent / "_nf_parity"
CACHE = PARITY_DIR / "bash_verdicts.txt"


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
    return merged


class GateEngineParityTest(unittest.TestCase):
    """引擎输出必须与 bash 门禁逐字一致（只看已迁入的那些 check）。"""

    @classmethod
    def setUpClass(cls) -> None:
        force = os.environ.get("NF_PARITY_FORCE")
        if CACHE.is_file() and not force:
            cls.bash = _parse_verdicts(CACHE.read_text(encoding="utf-8"))
        else:
            cls.bash = _bash_verdicts()
            try:
                CACHE.parent.mkdir(parents=True, exist_ok=True)
                merged = []
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
        """登记表与 PENDING **必须恰好覆盖 check1-40**——不许有 check 从两边都消失。

        这是「check 只增不减」在工程上的牙齿：漏一条会被这里抓住。
        """
        gate_engine.build_registry()
        covered = set(gate_engine.REGISTRY) | set(gate_engine.PENDING)
        self.assertEqual(set(range(1, 41)), covered,
                         "check 覆盖面缺口：%s" % sorted(set(range(1, 41)) - covered))
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


if __name__ == "__main__":
    unittest.main()
