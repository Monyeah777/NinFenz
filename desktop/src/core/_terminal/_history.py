"""terminal · _history（自 terminal.py 拆出；只移动代码，行为/文案不变）。"""
from __future__ import annotations

import os
from pathlib import Path


def default_history_path() -> str:
    """历史文件默认落点：`<NF_HOME>/shell_history`（与 Store 同一 home 约定，不落仓库）。"""
    try:
        from core import storage  # 单源：NF_HOME 约定只在 storage 里定义一次
        home = storage.default_home()
    except Exception:                       # 尽力而为：storage 不可用时退回同样口径的字面约定
        home = Path(os.environ.get("NARRATIVE_FORGE_HOME")
                    or (Path.home() / ".NinFenz"))
    return str(home / "shell_history")




def load_history(path: str, limit: int = 200) -> list:
    """读历史（尾部 limit 条，跳过空行）；文件不存在返回空表（不报错）。"""
    try:
        with open(path, encoding="utf-8") as fh:
            rows = [ln.rstrip("\n") for ln in fh if ln.strip()]
    except OSError:  # 历史文件缺失/坏件 ⇒ 空历史（等价于首次运行）
        return []
    return rows[-int(limit):] if limit else rows




def append_history(path: str, line: str) -> bool:
    """追加一条历史（跳过空行与「与上一条重复」）；返回是否写入。父目录不存在则创建。"""
    text = str(line).strip()
    if not text:
        return False
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        prev = load_history(path, limit=1)
        if prev and prev[-1] == text:
            return False
        with open(path, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(text + "\n")
        return True
    except OSError:  # 历史追加失败 ⇒ False（调用方据此告警；历史是便利面）
        return False
