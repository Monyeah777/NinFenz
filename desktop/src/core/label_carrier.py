"""标注载体 v0：把 nf-label/1 真正**写进** PNG iTXt 块 / JPEG APP15 段。

覆盖两种常见格式（2026-11-06）：
- PNG → iTXt（keyword=AIGC，UTF-8）；
- JPEG → APP15 私有段（"AIGC\0" + JSON）。
两者都是公开规范 + 纯字节可逆的载体，纯标准库可写且可读回自证；其它格式（MP4/PDF/…）
各自有一套嵌入规则，没有实测就不宣称，走 sidecar 回退。

承诺（逐格式有判据）：
1. 写入后**能被自己读回**（同 IR、JSON 语义等价）；IR.object.digest 必须等于「去掉本件
   标签后的内容摘要」——不符 fail-closed（写入前绑定，防「标签声明的是另一个文件」）；
2. 写入**不改内容面**：PNG 所有 IDAT 块拼接 sha256 一致；JPEG 从 SOS 到 EOF 的原始字节一致；
3. 写入后文件**结构合法**：PNG 块 CRC/签名/IHDR 首/IEND 尾；JPEG 段边界与长度合法、SOI 起、
   含 SOF 与 SOS。

不承诺：抗裁剪/抗转码/抗截屏（那是水印，不在本件）；不承诺未覆盖的格式。
"""

# ruff: noqa: F401 — 门面按原模块面重新导出（re-export 是职责，不是未使用），实现在私有子包。
from __future__ import annotations

import base64
import hashlib
import json
import os
import struct
import zlib
from typing import Any

from core import atomic_write, json_doc, label_ir

# 实现分片：原模块逻辑在私有子包 _label_carrier/，本门面按原模块面显式再导出（API 不变）。
from core._label_carrier._part1 import (
    _JPEG_STANDALONE,
    _SOF_MARKERS,
    APP15,
    GUIDE,
    JPEG_PREFIX,
    JPEG_SOI,
    KEYWORD,
    MAX_INPUT_BYTES,
    PNG_SIG,
    SCHEMA,
    CarrierError,
    _chunk,
    _embed_png,
    _iter_chunks,
    _itxt_body,
    _itxt_text,
    _jpeg_seg,
    _jpeg_split,
    _jpeg_structure_issues,
    _read_png,
    _structure_issues,
    content_digest,
    jpeg_content_digest,
    jpeg_scan_digest,
    pixel_digest,
)
from core._label_carrier._part2 import (
    MP4_BOX,
    PDF_COMMENT,
    WEBP_CHUNK,
    WEBP_RIFF,
    WEBP_TAG,
    _embed_jpeg,
    _embed_mp4,
    _embed_pdf,
    _embed_webp,
    _read_jpeg,
    _read_mp4,
    _read_pdf,
    _read_webp,
    _webp_media_digest,
    embed,
    embed_file,
    read,
)
