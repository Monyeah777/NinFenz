"""nf-labelcheck 并入 NF：AI 生成合成内容标识体检（GB 45438 / TC260）。

作者：impl（DSH agent）· 2026-11-02
来源：`/root/workspace/nf-labelcheck/nf_labelcheck/`（原型 160 测试全绿后并入）。

纪律：
- 纯标准库；包内子模块只用相对 import（`from . import sm`），不依赖 NF core 其它模块；
- 命令面在 `core.labeling.cli`，NF 侧入口是 `scripts/nf_labeling.py` 与
  `python3 scripts/nf.py labeling ...`（薄壳，不复制业务逻辑）。
"""

__all__ = [
    "sm",
    "der",
    "metadata",
    "security_data",
    "checker",
    "tsa",
    "x509",
    "cli",
]
