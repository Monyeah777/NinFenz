type: test
surface: ccos
note: M2/M3 收口——新增 test_evidence_forms_parity（receipts/attest 双实现 level/root 同判 + 仓外单文件普通/-I 隔离复验）与 test_shell_parity（nf check 与 /api/check 同 sha256/verdict/policy_digest；nf evidence verify 与 /api/verify 同 verdict/root/count/level）；test_ccos_chain 增缺环闭集判据（missing 只允许 cc_label）。abi-v0 补「本季非目标与触发条件」8 条并把未实装差距的阻塞项写成触发口径；check12 权重增量重测两个新模块。判据：96 项相关单测 OK；checks-only PASS=75 WARN=2 FAIL=0；conformance 27/27。
