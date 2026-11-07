type: fix
surface: ccos
note: 修 --snapshot 模式两条真实假红。①快照临时目录改到「盘根 .nf-gate-tmp/<run>/tmp」：原实现放在仓库树内（<run>/tmp），npm 包 findRepoRoot 会从 %TEMP% 向上命中活树 → 不触发解包，test_payload_is_extracted_to_cache_and_runs 假红；现在同盘且不在任何仓库树的祖先链上，并随快照一起清理（_snapshot_remove_tmp）。②docs/ccos/release-conclusion.md 的 test_release_conclusion 项数 44→47（对方 a7451e74 增测试后未同步）。另：上一轮已修的 <NF_HOME> 可移植前缀使 daemon status/preset 的机器面在快照里不再回吐绝对路径。判据：test_ccos_abi_docs OK、style 9921=基线、code_metrics 小幅重冻；快照全量待重跑验证。
