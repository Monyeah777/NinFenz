"""门面活状态转发（facade live-state forwarding）。

拆分后的门面（core.conformance_scan / core.daemon 等）需要把**模块级可变全局**的读取与
赋值转发到真正持有它的私有子模块：测试与调用方仍按原 API 直接读写门面属性（例如
`csc._READ_MEMO`、`dm._WATCHER`、`dm.reset_process_caches = spy`），行为必须与拆分前一致。
唯一实现放这里：各门面只登记「名字 → 持有模块」与可选的惰性 getattr 钩子，不再复制同一段
模块子类样板（审计 D-003：重复 8 行块按文件计，样板复制会跨门面命中）。
"""
from __future__ import annotations

import sys
import types


class LiveFacade(types.ModuleType):
    """按 _LIVE_MODULES 转发活状态（get）与可 patch 面（set）；其余走模块自有属性。"""

    def _owners(self):
        return self.__dict__.get("_LIVE_MODULES") or {}

    def __getattr__(self, name):
        owner = self._owners().get(name)
        if owner is not None:
            return getattr(owner, name)
        hook = self.__dict__.get("_FACADE_GETATTR")
        if hook is not None:
            return hook(name)
        raise AttributeError(name)

    def __setattr__(self, name, value):
        owner = self._owners().get(name)
        if owner is not None:
            setattr(owner, name, value)
            return
        super().__setattr__(name, value)

    def __delattr__(self, name):
        # unittest.mock.patch.object 收尾走 delattr（属性不在门面 __dict__ 时）：
        # 活状态名转发删到持有模块，mock 随后的 hasattr 复查会失败并回填原值——
        # 语义与「在真实模块上打桩→还原」一致。
        owner = self._owners().get(name)
        if owner is not None:
            try:
                delattr(owner, name)
            except AttributeError:
                pass
            return
        super().__delattr__(name)

    def __dir__(self):
        return sorted(set(object.__dir__(self)) | set(self._owners()))


def install(module_name: str, live_modules, getattr_hook=None) -> None:
    """把 module_name 指向的模块换成 LiveFacade 并登记活状态持有者（幂等）。"""
    module = sys.modules[module_name]
    module.__dict__["_LIVE_MODULES"] = dict(live_modules or {})
    if getattr_hook is not None:
        module.__dict__["_FACADE_GETATTR"] = getattr_hook
    module.__class__ = LiveFacade
