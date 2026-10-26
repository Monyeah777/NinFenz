"""`python -m ninfenz` 入口（与 console script `nf` 同一实现）。"""
from __future__ import annotations

import sys

from ninfenz._launcher import main

if __name__ == "__main__":
    sys.exit(main())
