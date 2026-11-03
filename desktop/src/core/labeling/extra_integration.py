"""额外容器接进主判定（不改冻结文件的补丁层）。

标准依据：TC260-PG-202511A 附录 A.2 的 `DFT` 口径（除隐式标识外的全部字节）；
实现与补丁逻辑在 `extra_dft.py`，本模块只保留薄接口，避免顶破 code_metrics 行数棘轮。

用法：
    from core.labeling import extra_integration
    rep = extra_integration.build_report("a.pptx")   # 主 sniffer 不认时返回 dict
"""

from __future__ import annotations

from . import metadata, metadata_extra, report as report_mod
from .extra_dft import (container_label, mark_note,  # noqa: F401
                        patched_metadata, recount,
                        selfcheck as _selfcheck)


def build_report(path, title=None, generated_at=None):
    """额外容器也走主判定；主 sniffer 已认得或无扩展读取器时返回 None。"""
    container = metadata_extra.sniff_extra(path)
    if not container or metadata.sniff(path) != "unknown":
        return None
    with patched_metadata(path) as info:
        rep = report_mod.build_report(path, title=title,
                                      generated_at=generated_at)
    rep["container"] = container
    rep["container_label"] = container_label(container)
    rep["extra"] = {
        "reader": "metadata_extra",
        "container": container,
        "entries": info["entries"],
        "cntsel": "DFT",
        "excluded_ranges": info["excluded"],
        "note": ("标识块为明文，已按 DFT 扣除" if info["excluded"]
                 else "标识块非明文（压缩/编码），DFT 退化为整文件；报告已标注"),
    }
    mark_note(rep, container, info["excluded"])
    rep["counts"] = recount(rep)
    return rep


def build_or_main(path, title=None, report_module=None):
    """pipeline 的一行式委托：能接管就接管，否则回退主 report。"""
    module = report_module or report_mod
    if metadata.sniff(path) == "unknown":
        rep = build_report(path, title=title)
        if rep is not None:
            return rep
    return module.build_report(path, title=title)


def selfcheck():
    return _selfcheck()
