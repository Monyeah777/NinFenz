"""conformance_scan 私有子模块 _fence：内容键解析缓存：围栏 YAML、安全 YAML、registry 读取、证据 id 收集。

门面 core.conformance_scan 按原 API 重新导出；本文件只承载实现，不改变对外面。
"""
from __future__ import annotations

import copy
import os
import re
from typing import Any, Dict, Tuple

from core import lazy_yaml as _lyaml
from core import json_doc

from ._read import read_text_cached



FENCE = re.compile(r"(?ms)```yaml\s*(.*?)```")

_T = chr(96) * 3

#: 围栏 YAML 解析缓存：键 = (marker, **文本本身**)，值 = 解析结果或 None（见 `_fence_yaml`）。
#: **负结果（勿重复尝试）**：与 `_BODY_CACHE` 一样**不落盘**；解析器缺席不是文本结果，永不入缓存。
_FENCE_CACHE: Dict[Tuple[str, str], Any] = {}

_FENCE_CACHE_MAX = 4096

_FENCE_CACHE_MAX_BYTES = 64 * 1024 * 1024

_FENCE_CACHE_BYTES = 0

#: 围栏**正文**缓存（键 = 正文本身）：给「自己抽正文」的调用方用（与 `_fence_yaml` 互补）。
_BODY_CACHE: Dict[str, Any] = {}

_BODY_CACHE_MAX = 4096

_BODY_CACHE_MAX_BYTES = 64 * 1024 * 1024

_BODY_CACHE_BYTES = 0



def load_yaml(text: str) -> Any:
    """模块间**共用**的安全 YAML 载入（libyaml 优先；无 PyYAML 即报，不静默降级）。

    新调用点一律走这里，别再各写一份 `yaml.safe_load`——否则「同一个仓库里两套解析器」
    既慢又会有语义分叉。

    注意：这里**直接实例化安全加载器**（`safe_loader()(text)` + `get_single_data()`），与
    `yaml.safe_load()` 逐字同语义，但不写 `yaml.load(...)`——后者是纯度扫描 R6 登记的
    危险 sink（CWE-502 非安全载入），不该为了少写两行把禁用面叫回来。
    """
    loader_cls = _lyaml.safe_loader()
    if loader_cls is None:
        raise RuntimeError("PyYAML 不在（修复指引：pip install pyyaml）")
    loader = loader_cls(text)
    try:
        return loader.get_single_data()
    finally:
        loader.dispose()



def load_yaml_cached(body: str) -> Any:
    """按**正文文本**缓存的安全 YAML 载入（键即内容 ⇒ 文本一变键就变，无陈旧风险）。

    与 `_fence_yaml` 的缓存同一条纪律，只是键更贴近「自己抽正文」的调用方：管道加载器与
    概念图加载器各自用正则抽出正文后直接解析，过去因此**每轮全量重解析**（实测热跑 score
    里仍有 325 次 YAML 解析）。解析失败按原样抛出、不缓存（确定性）。
    """
    global _BODY_CACHE_BYTES
    if body in _BODY_CACHE:
        return _BODY_CACHE[body]
    got = load_yaml(body)
    size = len(body)
    if (len(_BODY_CACHE) >= _BODY_CACHE_MAX
            or _BODY_CACHE_BYTES + size > _BODY_CACHE_MAX_BYTES):
        _BODY_CACHE.clear()
        _BODY_CACHE_BYTES = 0
    _BODY_CACHE[body] = got
    _BODY_CACHE_BYTES += size
    return got



def _read_json(path: str) -> Tuple[Any, str]:
    try:
        # N11/Z1：收敛到单一实现（顶层形状由调用方声明；此处通用读口不限定形状）。
        return json_doc.loads(read_text_cached(path), None, what=str(path)), ""
    except Exception as exc:
        return None, str(exc)



def _parse_fence_yaml(text: str, marker: str) -> Any:
    """真的去扫围栏并交给 PyYAML（未命中缓存时走这里）；未命中 / 解析失败 → None。"""
    for m in FENCE.finditer(text):
        body = m.group(1)
        if marker not in body:
            continue
        try:
            parsed = load_yaml_cached(body) if _lyaml.module() is not None else None
        except Exception:  # 围栏 YAML 不可解析 ⇒ None（等价于「本件无该块」）
            return None  # best-effort 显式忽略（不可读/不可用属预期，由上层门禁另行报出）
        if isinstance(parsed, dict):
            return parsed
    return None



def _fence_yaml_cached(text: str, marker: str) -> Any:
    """`(marker, 文本)` → 解析结果（None = 没找到该围栏或解析失败）。见 `_fence_yaml`。"""
    global _FENCE_CACHE_BYTES
    key = (marker, text)
    if key not in _FENCE_CACHE:
        if _lyaml.module() is None:
            return None
        size = len(text)
        if (len(_FENCE_CACHE) >= _FENCE_CACHE_MAX
                or _FENCE_CACHE_BYTES + size > _FENCE_CACHE_MAX_BYTES):
            _FENCE_CACHE.clear()
            _FENCE_CACHE_BYTES = 0
        _FENCE_CACHE[key] = _parse_fence_yaml(text, marker)
        _FENCE_CACHE_BYTES += size
    return _FENCE_CACHE[key]



def _fence_yaml(text: str, marker: str) -> Dict[str, Any]:
    """取围栏 ```yaml 里含 marker 的第一个块（未命中 → `{}`）；结果按**文本本身**缓存。

    效率（实测）：`nf doctor` 里同一批 **248 份**模块文档被恰好解析**两遍**（496 次
    `yaml.safe_load`，累计 **1.47 s ≈ 体检总时的 74%**）——PyYAML 的扫描器是纯 Python，
    单份 ~3 ms，重复一遍就是纯亏。缓存键取文本本身（不是路径）：文本没变必然同结果，
    文本一变键就变，所以**不存在「改了文件还读到旧值」的陈旧风险**——这正是它敢跨命令
    常驻的原因。返回值一律给**深拷贝**，调用方就地改动不会串味。
    """
    got = _fence_yaml_cached(text, marker)
    return copy.deepcopy(got) if got is not None else {}



def _fence_yaml_opt(text: str, marker: str) -> Optional[Dict[str, Any]]:
    """同 `_fence_yaml`，但「没找到 / 解析失败」返回 None（schema_lint 的既有语义）。

    与 `_fence_yaml` **同一份缓存、同一次解析**——同一段文本被两个模块各解析一遍是纯重复。
    """
    got = _fence_yaml_cached(text, marker)
    return copy.deepcopy(got) if got is not None else None



def _evidence_ids(root: str, reg: Any = None) -> List[str]:
    """官方 registry modules[] + community registry protocols[].module_ids（装配在册证据）。

    `reg` 可由调用方传入（同一次扫描里 registry.json 只该读一次——见 `scan`）。
    """
    if reg is None:
        reg, _ = _read_json(os.path.join(root, "desktop", "src", "core", "registry.json"))
    ids: List[str] = []
    if isinstance(reg, dict):
        for m in reg.get("modules") or []:
            if isinstance(m, dict) and isinstance(m.get("id"), str):
                ids.append(m["id"])
        for p in reg.get("protocols") or []:
            for mid in (p.get("module_ids") or []):
                if isinstance(mid, str):
                    ids.append(mid)
    return ids
