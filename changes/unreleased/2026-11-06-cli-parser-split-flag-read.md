type: fix
surface: ccos
note: 修两条发布结论真实红（shard 4）。①test_nf_cli 命令树单函数 300 行判据超限（310）——把吊销分发件子命令（sign/verify/merge）注册从 _add_parser_production 拆到新 `_add_parser_revocations`，命令树仍单一构建入口，production 273 行、helper 43 行；②test_no_declared_flag_is_unread——`--require-fresh-revocations` 声明后处理器用 getattr 读、判据只认字面属性读取，改为 `bool(args.require_fresh_revocations)`（引擎行为不变）。判据：test_nf_cli 62 项 OK、test_revocations+test_evidence OK、style 9921=基线；code_metrics 小幅重冻。
