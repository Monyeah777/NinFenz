"""output_forms 私有子模块 _util：渲染侧公共工具：生成器 id / 包内相对路径 / 声明落点越界判据 / 序列化。

门面 core.output_forms 按原 API 重新导出；本文件只承载实现，不改变对外面。
"""
from __future__ import annotations

import json
import os
import re

from core import paths as _paths



def _gen_id(entry: dict) -> str:
    for key in ("recompute", "render"):
        spec = entry.get(key)
        if isinstance(spec, dict) and spec.get("id"):
            return str(spec["id"])
    return ""



def _pkg_rel(entry: dict, rel: str) -> str:
    """包内声明的相对路径 → 仓库相对路径（以本包目录为根）。

    **外来数据面**：社区域包是外来投稿，清单里的 `path` / `inputs` / `graph` / `schema` /
    `dual_source` 都出自投稿者之手。此前这些字段直拼进 `community/<包>/…`——实测把 `path`
    写成 `../../../PWNED.mmd` 再跑 `nf output render --write`，文件**真的落到了仓库外**。
    故此处先过形状判据（`_reject_escape_forms`），越界一律抛 `ValueError`（调用方转成
    「清单越界」问题，不读也不写仓库外的文件）。
    """
    _reject_escape_forms(rel, "清单相对路径")
    pkg = entry.get("_pkg") or ""
    if rel.startswith("community/") or not pkg:
        return rel
    return "community/%s/%s" % (pkg, rel.lstrip("/"))



def _reject_escape_forms(rel: Any, what: str) -> None:
    """外来清单里的路径**形状**判据：越界写法 / 备用数据流 / 控制字符 / 保留设备名抛 `ValueError`。

    词法判据收敛到 `core.paths.path_syntax_issue`（单一出处）：此前本处自写一份（漏了控制字符
    与保留设备名），与账本面/参数面各自为政。产出面**额外严格**：`~` 也当绝对写法拒。
    """
    text = str(rel or "")
    if not text.strip():
        raise ValueError("%s 为空（修复指引：给出包内相对路径，如 outputs/REPORT.json）" % what)
    if text.startswith(("\\", "/")) or re.match(r"^[A-Za-z]:", text) or text.startswith("~"):
        raise ValueError("%s 含绝对/盘符写法 %r（修复指引：改为包内相对路径，如 outputs/x.json）"
                         % (what, text))
    issue = _paths.path_syntax_issue(text)
    if issue:
        raise ValueError("%s %s %r（修复指引：改为包内相对路径，勿用 `..` 段 / 盘符写法 / "
                         "`文件:流` 备用数据流 / 控制字符 / 保留设备名）" % (what, issue, text))



def _declared_out_rel(root: str, pkg: str, rel: Any) -> str:
    """清单声明的产出路径 → 仓库相对路径（形状 + **包内包含性**双判据，越界抛 `ValueError`）。

    包含性收在**声明包自己的目录**内，不只是仓库根：否则「包 A 声明 `community/包 B/outputs/x.json`」
    就能在被渲染时改写包 B 的产物（跨包越权写）。实测存量 1046 条声明路径**全部**以本包
    `outputs/` 开头，`schema` 也全在包内——判据不误伤。
    """
    _reject_escape_forms(rel, "产出路径")
    text = str(rel)
    out_rel = text if text.startswith("community/") else "community/%s/%s" % (pkg, text.lstrip("/"))
    try:
        _paths.validate_path(str(root), out_rel)
    except _paths.PathEscapeError as exc:
        raise ValueError("产出路径越界：%s" % exc) from exc
    if pkg and not _paths.contained(os.path.join(str(root), "community", pkg),
                                    os.path.join(str(root), out_rel)):
        raise ValueError("产出路径越界：%s 不在本包目录内（修复指引：产出面只许落在 "
                         "community/%s/ 下，勿指向其它包）" % (text, pkg))
    return out_rel



def _dump(value: Any) -> str:
    if isinstance(value, str):
        return value if value.endswith("\n") else value + "\n"
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
