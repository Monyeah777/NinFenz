"""evidence · _reader（自 evidence.py 拆出；只移动代码，行为/文案不变）。"""
from __future__ import annotations

import os
import zipfile
from typing import Any

from core import json_doc

from ._const import (
    BUNDLE_ENTRY,
    GUIDE,
    MAX_MEMBER_BYTES,
    MAX_TOTAL_BYTES,
    SCHEMA,
)
from ._primitives import (
    _norm,
)

# ------------------------------------------------------------------ 读面

class _Reader:
    """证据包读面：zip 与目录两种落点同一接口（目录形态便于人工检查）。"""

    def __init__(self, path: str):
        self.path = path
        self._zf: zipfile.ZipFile | None = None
        self._dir = ""
        #: 读面发现的结构问题（重名成员 / 超限膨胀）：由 verify 收进判定，不在这里抛
        self.issues: list[str] = []
        self._total = 0
        if os.path.isdir(path):
            self._dir = path
        elif os.path.isfile(path):
            try:
                self._zf = zipfile.ZipFile(path)
            except zipfile.BadZipFile as exc:
                raise ValueError(f"不是证据包（坏 zip）：{exc}（{GUIDE}请用 nf evidence pack "
                                 "产出的 .zip 或解包后的目录，不要喂别的东西）") from exc
            names = self._zf.namelist()
            dup = sorted({n for n in names if names.count(n) > 1})
            if dup:
                self.issues.append(f"包内有重名成员：{'、'.join(dup[:3])}（{GUIDE}重名 zip 的"
                                   "取字节在实现间不一致——判定不可复算，按 invalid 处理）")
            declared = sum(int(getattr(info, "file_size", 0) or 0)
                           for info in self._zf.infolist())
            if declared > MAX_TOTAL_BYTES:
                self.issues.append(f"包声明解压后 {declared} 字节，超过上限 {MAX_TOTAL_BYTES}"
                                   f"（{GUIDE}拒绝按声明膨胀解包——防 zip 炸弹）")
        else:
            raise ValueError(f"证据包不存在：{path}（{GUIDE}请先 nf evidence pack --out "
                             "<包.zip> 生成证据包，再对生成的包执行 verify）")

    def names(self) -> list[str]:
        if self._zf is not None:
            return sorted(self._zf.namelist())
        out: list[str] = []
        for base, _dirs, files in os.walk(self._dir):
            for f in files:
                full = os.path.join(base, f)
                out.append(_norm(os.path.relpath(full, self._dir)))
        return sorted(out)

    def read(self, name: str) -> bytes | None:
        name = _norm(name)
        if self._zf is not None:
            try:
                with self._zf.open(name) as fh:
                    data = fh.read(MAX_MEMBER_BYTES + 1)
            except KeyError:        # 成员不在包里：按「缺件」返回 None，由调用方判 invalid
                return None
            except (zipfile.BadZipFile, RuntimeError, NotImplementedError) as exc:
                # 重叠成员 / 不支持的压缩法（zipfile 自己判成 zip bomb 的形态）：按不可信处理
                self.issues.append(f"成员 {name} 不可安全读取：{exc}"
                                   f"（{GUIDE}容器结构歧义或压缩不受支持——判 invalid，不猜）")
                return None
            if len(data) > MAX_MEMBER_BYTES:
                self.issues.append(f"成员 {name} 超过单件上限 {MAX_MEMBER_BYTES} 字节"
                                   f"（{GUIDE}拒绝解包超限成员——防 zip 炸弹）")
                return None
            self._total += len(data)
            if self._total > MAX_TOTAL_BYTES:
                self.issues.append(f"已解压超过整包上限 {MAX_TOTAL_BYTES} 字节"
                                   f"（{GUIDE}拒绝继续膨胀解包——防 zip 炸弹）")
                return None
            return data
        full = os.path.join(self._dir, *name.split("/"))
        if not os.path.isfile(full):
            return None
        with open(full, "rb") as fh:
            return fh.read()

    def close(self) -> None:
        if self._zf is not None:
            self._zf.close()
            self._zf = None




def _load_meta(rd: _Reader) -> dict[str, Any]:
    raw = rd.read(BUNDLE_ENTRY)
    if raw is None:
        raise ValueError("缺 bundle.json：不是证据包（" + GUIDE + "请用 nf evidence pack 产出，"
                         "不要手工拼 zip）")
    try:
        meta = json_doc.loads(raw.decode(), dict, what="证据文档")
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError(f"bundle.json 不是合法 UTF-8 JSON：{exc}（{GUIDE}请重新 nf evidence "
                         "pack 生成，坏件不要手工修补——补出来的包验不过才是对的）") from exc
    if not isinstance(meta, dict) or meta.get("schema") != SCHEMA:
        got = meta.get("schema") if isinstance(meta, dict) else meta
        raise ValueError(f"证据包 schema 不匹配（期望 {SCHEMA}，实得 {got!r}）（{GUIDE}请用与"
                         "当前 nf 同版本的 nf evidence pack 重新打包）")
    return meta




# ------------------------------------------------------------------ 校验（分段，便于逐段判据）

def _empty_result() -> dict[str, Any]:
    return {"verdict": "invalid", "level": "none", "root": "", "head": "", "count": 0,
            "issues": [], "warnings": [], "created_at": "", "expires_at": "",
            "revoked_by": None, "anchor_ref": None, "anchor_verified": False,
            "decision": None, "decision_status": "absent", "policy_verified": False,
            "revocations_fresh": "unknown", "revocations_source": "none",
            "revocations_basis": "none",
            # 时间可证性（威胁模型 G3）：本仓没有可信时间源，只能如实标注「谁给的时点」
            "time_proof": "none", "time_basis": ""}




def _fill_header(res: dict[str, Any], meta: dict[str, Any]) -> None:
    res["root"] = str(meta.get("root") or "")
    res["head"] = str((meta.get("chain") or {}).get("head") or "")
    res["created_at"] = str(meta.get("created_at") or "")
    res["expires_at"] = str(meta.get("expires_at") or "")
