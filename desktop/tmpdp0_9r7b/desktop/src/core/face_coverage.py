"""门禁覆盖度反向：每个受管面必须被至少一个 check 指到（机制借鉴 objectui 覆盖度反向 / falcone 契约×校验器）。

judgement_coverage 判「判据须有消费者」（正向）；本模块补反向：**面须有判据**，
否则「有这个面但没人管」是静默的。
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List


def uncovered_faces(faces: Iterable[str], checks: List[Dict[str, Any]]) -> List[str]:
    covered = set()
    for c in checks:
        for f in (c.get("covers") or []):
            covered.add(str(f))
    return [str(f) for f in faces if str(f) not in covered]


def orphan_checks(faces: Iterable[str], checks: List[Dict[str, Any]]) -> List[str]:
    have = {str(f) for f in faces}
    return ["check %s 指向不存在的面 %s（修复指引：补面登记或改 covers）" % (c.get("id"), f)
            for c in checks for f in (c.get("covers") or []) if str(f) not in have]
