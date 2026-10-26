"""质量门公共类型（Issue / GateResult）——从 `quality_gate` 拆出的稳定接口层。

拆出原因（2026-10-26）：S4/S5 结构门实现放在 `techdoc_gate`，它需要构造 `Issue`；
若它反向 import `quality_gate` 会形成模块级环（coupling 判据 FAIL）。故把两个
dataclass 放到本模块：`quality_gate` 与 `techdoc_gate` 都依赖它，依赖方向单向。
`quality_gate` 继续 re-export 这两个名字（对外导入面不变）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class Issue:
    level: str       # "pass" / "warn" / "fail"
    message: str
    #: B1 可解释化（v2.1.0）：actionable 修复指引——缺省空串向后兼容
    #: （现有构造 Issue(level, message) 两参仍成立）。
    suggestion: str = ""


@dataclass
class GateResult:
    n_pass: int = 0
    n_warn: int = 0
    n_fail: int = 0
    issues: List[Issue] = field(default_factory=list)

    def ok(self) -> bool:
        """可信任度不变量：fail 阻断通过。"""
        return self.n_fail == 0

    def report_text(self) -> str:
        """可解释报告（B1）：三态汇总 + 逐条 [LEVEL] 原因 → 修复建议。

        fail 优先列出（阻断项，须修复）；warn 次之（可行动项）；pass 不列
        （无问题无需展示）。无 issues 且 ok → 通过说明。
        """
        if not self.issues and self.ok():
            return "质量门通过：无质量问题。"
        lines = [
            f"质量门：PASS {self.n_pass} · WARN {self.n_warn}"
            f" · FAIL {self.n_fail}（{'可产出' if self.ok() else '存在 FAIL，须修复'}）",
            "",
        ]
        # fail 优先，再 warn
        for level, tag in (("fail", "FAIL"), ("warn", "WARN")):
            hits = [i for i in self.issues if i.level == level]
            if not hits:
                continue
            for i in hits:
                lines.append(f"[{tag}] {i.message}")
                if i.suggestion:
                    lines.append(f"    建议：{i.suggestion}")
        return "\n".join(lines)
