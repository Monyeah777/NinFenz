"""认知工作台 L0（nf-discourse-state/1）：话语状态 + 15 元动作 + 只追加记录 + 重放。

设计约束（方案 P1 判据）：
- **不依赖契约核**：本包不得 import meta_cockpit / backends / nf.py（依赖方向判据）；
- **动作必须有 frame_delta**：没有「问题/假设/张力/反例」的实际变化的动作 = 仪式，拒绝；
- **只追加 + 可重放**：每步记录带前后 digest，重放必须逐字节复算到最后状态；
- **不动质量分**：本层只记账，不做评分。
"""
from __future__ import annotations

__all__ = ["discourse", "moves", "records", "session"]
