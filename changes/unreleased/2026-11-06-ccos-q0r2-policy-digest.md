type: feat
surface: ccos
note: Q0-r2 期望策略比对（--policy-digest）——nf evidence verify / nf_verify.py 增可选期望策略摘要：与包内 decision.policy_digest 比对，不符判 invalid（policy_verified=false）；包内无 decision 时只 warning 不判死。四词判定/退出码稳定面不变；旧包无 decision 仍 ok。evidence.verify/verify_any 增 expected_policy_digest 参数（向后兼容），nf.py 与零依赖单文件同口径。新增 4 条判据（吻合/不符/无 decision 仅 warning/双实现同判），test_evidence 58→62；文档 abi-v0 + evidence-bundle 同步。说明：源码随并发会话 9688c92f 入库（共享工作树被宽 git add 卷走，第三次同类）；本条补 change note 与审计口径。
