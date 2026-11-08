"""判据的时钟纯度：测试里读「此刻」必须登记理由（防跨日假红）。

依据（第 64 轮实测）：`test_build_is_deterministic` 比较「已提交报告」与「实时重算」的 root digest，
而 digest 含 `built_for_date`；快照恰好跨午夜 → 次日重算必然不同 → 每日 00:00 后必红一次。
同类风险是「判据输入里混进了此刻或环境」。

本判据不禁止读时钟（有些测试确实要构造「今天/30 天前」的样本），而是要求**每个读法显式登记理由**：
新增一处未登记的 `date.today()` / `datetime.now()` / `time.time()` → 红。
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TESTS = ROOT / "desktop" / "tests"

PATTERNS = (
    ("date.today", re.compile(r"date\.today\(\)")),
    ("datetime.now", re.compile(r"datetime\.now\(")),
    ("utcnow", re.compile(r"utcnow\(")),
    ("time.time", re.compile(r"time\.time\(\)")),
    ("localtime", re.compile(r"localtime\(")),
)

#: 文件 → 为什么必须读此刻（**只登记「构造样本」与「计时」两类**，不许写「反正没事」）
ALLOW = {
    "test_daemon.py": "守护进程超时判定，需要真实单调时间",
    "test_disk_cache_bounds.py": "缓存 TTL 过期，需要推进真实时间",
    "test_gate_faces.py": "门禁面的耗时测量",
    "test_instruction_evidence.py": "构造「今天 / 30 天前」的指令证据样本",
    "test_intake_quota.py": "构造「今日配额 / 昨日已用」样本",
    "test_interop_export.py": "互操作样本自带 today 说明（文件头已标注该风险）",
    "test_launcher.py": "启动器等待/超时的真实计时",
    "test_perf_budget.py": "构造「今日实测 / 30 天前实测」性能预算样本",
    "test_scratch.py": "临时目录清理的 mtime 推进",
    "test_session_watch.py": "会话监看的真实计时",
    "test_watch.py": "文件监看的真实计时",
}


#: 本判据自身源码必然含这些模式串——扫描时跳过自身（自指处理）
SELF = Path(__file__).name


def scan(root: Path = TESTS) -> dict[str, list[str]]:
    """→ {文件名: [命中的模式名…]}（只读）。"""
    out: dict[str, list[str]] = {}
    for path in sorted(root.glob("test_*.py")):
        if path.name == SELF:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        found = [name for name, rx in PATTERNS if rx.search(text)]
        if found:
            out[path.name] = found
    return out


class JudgeClockPurityTest(unittest.TestCase):
    def test_every_clock_reader_is_registered(self):
        hits = scan()
        unregistered = sorted(set(hits) - set(ALLOW))
        self.assertEqual(unregistered, [],
                         f"这些测试读了「此刻」但没登记理由：{unregistered}（跨日可能假红）")

    def test_allowlist_has_no_stale_entries(self):
        hits = scan()
        stale = sorted(set(ALLOW) - set(hits))
        self.assertEqual(stale, [], f"登记了但已不读时钟：{stale}（删掉，别留死条目）")

    def test_allowlist_reasons_are_specific(self):
        for name, why in ALLOW.items():
            self.assertGreaterEqual(len(why.strip()), 8, name + " 的理由太短")


if __name__ == "__main__":
    unittest.main()
