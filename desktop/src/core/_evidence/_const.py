"""evidence · _const（自 evidence.py 拆出；只移动代码，行为/文案不变）。"""
from __future__ import annotations

SCHEMA = "nf-evidence/1"


RECEIPTS_SCHEMA = "nf-receipts/1"


ATTEST_SCHEMA = "nf-attest/1"


ATTEST_SET_SCHEMA = "nf-attest-set/1"


REVOCATION_SCHEMA = "nf-revocation/1"


BUNDLE_ENTRY = "bundle.json"


PAYLOAD_DIR = "payload/"


ATTEST_DIR = "attest/"


REVOCATIONS_ENTRY = "revocations.json"



#: 证据强度排序（弱 → 强）：判 level 时取「包内**通过校验**的最强一档」——
#: 不通过的不算，避免「有强信封就算强证据」这种虚假保证。
LEVELS = ("digest_only", "receipts_only", "hmac-sha256", "ssh-sig", "sigstore-keyless")


#: 证据形态（cc_verify 的输入面）：自包含包 / 协议回执 / 信封
KINDS = ("bundle", "receipts", "attest")


#: 判定词表 = EXIT_CODES 的键（单一真源：词表与退出码一一对应，不再各执一份）
#: 判定 → CLI 退出码（稳定面；4 留给「输入不是证据包」这一用法错，不是判定）。
#: 这四个键就是判定词表本身——不再单独维护一份 VERDICTS（两份真源必然漂移）。
EXIT_CODES = {"ok": 0, "invalid": 1, "revoked": 2, "expired": 3}



#: zip 成员固定时间戳：同一输入两次打包**逐字节一致**（可复现构建惯例）。
#: 不用压缩：deflate 输出随 zlib 版本变，跨机器就不再逐字节一致了。
_ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)



GUIDE = "修复指引："




#: 单成员/整包解压上限（防 zip 炸弹）：我们自己打包用 STORED，但**验证器收的是不可信输入**。
MAX_MEMBER_BYTES = 16 * 1024 * 1024


MAX_TOTAL_BYTES = 96 * 1024 * 1024




#: 批处理的默认上限：一次最多验这么多件（防误指 / 防把整盘塞进来）
BATCH_MAX_FILES = 200




# ------------------------------------------------------------------ 复现轨迹（cc_replay）
#
# 把「这条证据是怎么算出来的」摊成确定性 trace：每一步给规则名 + 输入摘要 + 输出摘要。
# 用途不是重新执行生产，而是让第三方**逐步复核**——每一步都能自己重算，错在哪一步一眼可见。
# 稳定性：trace 不含时间戳，同输入两次 replay 逐字节一致（可 diff）。

REPLAY_SCHEMA = "nf-replay/1"



# ------------------------------------------------------------------ 攻击矩阵基准 v0
#
# 目的：把「抓不到篡改的校验器就是摆设」变成**可复跑的数字**。对同一份金丝雀证据包施加
# 25 种已知攻击/退化（改字节、换成员、删证明、改根、改链、改信封、错密钥、良性重排…），
# 逐条比对「期望判定 vs 实际判定」。任何一条不达期望 = 复验器有洞，基准当场红。
#
# 这是**自测基准**，不是安全证明：它证明「这些已知攻击都判得出来」，不证明「所有攻击都
# 判得出来」——不可抵赖与可信时间戳仍需第三方见证，见包内 boundary 声明。

BENCH_SCHEMA = "nf-evidence-bench/1"


BENCH_KEY = b"nf-evidence-bench-key-0123456789"


BENCH_PIN = "2026-01-01T00:00:00Z"
