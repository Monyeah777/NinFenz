"""内容外挂签名 / attestation（内部差距实证：knowledge_sig 只证明「两遍算得出一样」，
即自证一致，**不能证明这份内容没被第三方换过**——仓库全域实测 sigstore/attestation/
cosign/gpg 命中 0）。

本模块把内容摘要升级为**可对外验证的 attestation envelope**，三级信任，逐级 fail-closed：

1. `digest_only` —— 可复现内容摘要（sha256/字节数/行数 + 信封摘要）。
   证明「内容与信封一致」；**不证明诚实性**（任何人都能重算）。
2. `hmac-sha256` —— 本地密钥 HMAC（**纯标准库** hashlib/hmac，不引第三方）。
   持有密钥者可在离线环境验证「信封确由持钥方签发且未被改动」。
3. `sigstore-keyless` —— 外挂锚（Sigstore/cosign）。
   本模块**不实现密码学**：只检测外部验证器（`cosign`）并调用；验证器缺失即
   **拒绝**（不静默降级成 digest_only）——缺锚 = 不可信，而非「默认通过」。

纪律（对齐 core 零第三方依赖红线）：stdlib-only；外部锚是可选外挂，装不装由消费方裁决。
"""

# ruff: noqa: F401 — 门面按原模块面重新导出（re-export 是职责，不是未使用），实现在私有子包。
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import shutil
import subprocess  # nosec B404/B603/B607 —— 调用 ssh-keygen/git/hf（argv 列表、无 shell、路径经 which 解析）
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

# 实现分片：原模块逻辑在私有子包 _attest/，本门面按原模块面显式再导出（API 不变）。
from ._attest._part1 import (
    DECISION_FIELDS,
    DEFAULT_SUBJECTS,
    SCHEMA,
    SCHEME_HMAC,
    SCHEME_SIGSTORE,
    SCHEME_SSH,
    SSH_NAMESPACE,
    SSH_PAYLOAD_PREFIX,
    TOOL_TIMEOUT_S,
    _sha256,
    _which,
    build,
    canonical,
    decision_issues,
    envelope_digest,
    have_external_verifier,
    issue_stamp,
    sign_digest_hmac,
    sign_hmac,
    ssh_payload,
    subject_of,
    verify,
    verify_external,
)
from ._attest._part2 import (
    dumps,
    read_key_file,
    sign_digest_ssh,
    verify_digest_anchor,
    verify_ssh_anchor,
)
