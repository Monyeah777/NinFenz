#!/usr/bin/env python3
"""nf-label 报告启动器：把 desktop/src 加入 sys.path 后调用 core.labeling.report。

用法（报告 = 客户可直接交付的 HTML/JSON/Markdown）：
  python3 scripts/nf_label_report.py report <file> [--out 目录]
  python3 scripts/nf_label_report.py batch <目录> [--out 目录]
  python3 scripts/nf_label_report.py matrix
  python3 scripts/nf_label_report.py selfcheck

设计：只做启动，报告实现真源始终是 `desktop/src/core/labeling/report.py`。
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core.labeling.report import main  # noqa: E402


if __name__ == "__main__":
    sys.exit(main())
