"""terminal · _session_io（自 terminal.py 拆出；只移动代码，行为/文案不变）。"""
from __future__ import annotations

import json
import os

from core import json_doc

from ._const import (
    SESSION_SCHEMA,
)


def load_session_state(path: str):
    """读会话文件 → (state, warn)：缺件返回空态；坏件给理由但不抛（终端不该被状态文件拖死）。"""
    if not path:
        return {}, ""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json_doc.loads(fh.read(), dict, what=path)
    except FileNotFoundError:
        return {}, ""
    except OSError as exc:
        return {}, "会话文件不可读（%s）：%s" % (path, exc)
    except ValueError as exc:   # json_doc 抛 ValueError（含 JSONDecodeError/顶层形状）
        return {}, "会话文件不是合法 JSON（%s）：%s（修复指引：删除该文件或改成合法 JSON）" \
            % (path, exc)
    if str(data.get("schema")) != SESSION_SCHEMA:
        return {}, "会话文件 schema 不匹配（期望 %s；修复指引：删除后重开）" % SESSION_SCHEMA
    return data, ""




def save_session_state(path: str, session) -> bool:
    """把会话状态落盘（视图设置 + 上次分区）：父目录不存在则建；失败返回 False（不抛）。"""
    data = {"schema": SESSION_SCHEMA,
            "settings": {"color": str(session.color_mode),
                         "width": int(session.width or 0),
                         "limit": int(session.limit or 0)},
            "last_zone": str(session.last_zone or "")}
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        from core import atomic_write
        atomic_write.write_text(
            path, json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        return True
    except OSError:  # 会话落盘失败 ⇒ False（调用方据返回值告警）
        return False
