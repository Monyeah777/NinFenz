"""原子写（labeling 写入器的单一出处）：同目录临时件 + fsync + os.replace。

三个容器写入器（HEIF / GIF·TIFF·WebP / xmind·posm·posf·UOF）此前各抄了一份逐字相同的
`_atomic_write`（死代码门禁的重复体判据）。收敛到这里：写入口唯一、保留原文件权限位、
失败只清理本模块现造的临时件。
"""
from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path


def write_bytes(path, data: bytes) -> None:
    """把 data 原子写到 path（同目录临时件；保留原文件权限位；失败清理）。"""
    p = Path(path)
    try:
        mode = stat.S_IMODE(p.stat().st_mode)
    except OSError as exc:
        raise ValueError("无法读取目标文件状态：%s（%s）" % (path, exc))
    fd, tmp = tempfile.mkstemp(prefix="." + p.name + ".", suffix=".tmp",
                               dir=str(p.parent))
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, p)
    except OSError as exc:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise ValueError("写入失败：%s（%s）" % (path, exc))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
