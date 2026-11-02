#!/usr/bin/env python3
"""nf-labeling 薄启动器：把 desktop/src 加入 sys.path 后调用 core.labeling.cli。

用法（等价于 `python3 scripts/nf.py labeling ...`）：
  python3 scripts/nf_labeling.py check <file>
  python3 scripts/nf_labeling.py selfcheck

只做启动：命令面真源始终是 `desktop/src/core/labeling/cli.py`。
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core.labeling.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
