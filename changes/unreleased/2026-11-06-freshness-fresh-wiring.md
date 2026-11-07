type: fix
surface: ccos
note: 吊销新鲜度词表 FRESH 接入生产面（修死代码判据）。_apply_freshness 对来源给出的状态做词表校验（state not in revoc.FRESH → 按 unknown 处理），既消掉 test_dead_code 的零引用常量告警，也把「词表外状态一律按未知、绝不因错误状态放行」写成 fail-safe 规则。判据：test_dead_code/test_revocations/test_evidence 115 项 OK；style 9921=基线；code_metrics 小幅重冻。
