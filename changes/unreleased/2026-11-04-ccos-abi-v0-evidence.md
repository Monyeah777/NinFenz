type: feat
surface: ccos
note: CCOS ABI v0（7 调用 · cc_verify 先行，其余如实标注实装状态）+ 证据复验器（三种可验形态——自包含包、协议回执、信封集；判定 ok|revoked|expired|invalid，退出码 0/1/2/3/4；25 条攻击矩阵基准逐条比对判定）+ 零依赖单文件复验器（scripts/nf_verify.py --evidence，纯标准库、不 import NF，与 core 版判据一致性由单测硬钉；37 项单测 + --selfcheck 机制体检）
