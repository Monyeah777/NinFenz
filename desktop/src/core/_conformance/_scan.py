"""conformance_scan 私有子模块 _scan：一致性分级扫描真算（模块 mc / 协议包 / 导出 manifest 三面）。

门面 core.conformance_scan 按原 API 重新导出；本文件只承载实现，不改变对外面。
"""
from __future__ import annotations

import copy

from core import import_graph as _ig

from core import conformance_scan as _dm



def scan(root: str = ".") -> Tuple[List[str], Dict[str, int]]:
    """检查（外层）：派生结果按**输入内容指纹**跨调用缓存（输入面见 `SCAN_INPUTS`，已穷举）。

    依据（实测）：本函数一次调用约 0.4 s，而它只依赖那 6 类输入——守护逐请求清空按 root 的
    缓存时，这些派生账会被白交一遍。键即内容 ⇒ 输入一变指纹就变，故不需要随请求清空。

    再叠一层**持久**缓存（`core.disk_cache`：键里还含**代码面 + 运行时**）：新进程也能免付
    这笔派生账。读回时按 `result_pair_ok` 校验形状，不可信即重算。

    「读到的文件必须全部落在输入面内」有判据守着（test_conformance_scan.DerivedResultCacheTest）：
    将来给本函数加新读取，判据会先红、逼着把新输入补进来——不会悄悄读到陈旧结果。
    """
    fp = _dm.face_fingerprint(root, _dm.SCAN_INPUTS)
    hit = _dm._SCAN_CACHE.get(fp)
    if hit is None:
        from core import disk_cache
        dkey = disk_cache.key("scan", fp, root=root,
                              code_scope=_ig.code_scope_fingerprint(root,
 ("core.conformance_scan",
)))
        cached = disk_cache.load("scan", dkey, validate=_dm.result_pair_ok)
        if cached is None:
            got = _dm._scan_impl(root)
            cached = disk_cache.canonical({"issues": list(got[0]), "stats": got[1]})
            disk_cache.store("scan", dkey, cached)
        # 命中与未命中必须**逐字节一致**：落盘是 `sort_keys` 规范化过的，新算的那份也要过同一道
        # 规范化（否则首跑/次跑换序——见 `disk_cache.canonical` 的取证）。
        hit = _dm._SCAN_CACHE[fp] = (list(cached["issues"]), dict(cached["stats"]))
    return copy.deepcopy(hit[0]), copy.deepcopy(hit[1])
