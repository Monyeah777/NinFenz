type: feat
surface: ccos
note: ABI v0 错误面落登记（protocol/error_codes.json 从空表到 14 条 cc.* 码；error_codes.py 词法新增 cc.<syscall>.<reason> 一类，保留大写码兼容）；新增 docs/ccos 一致性判据 test_ccos_abi_docs（7 调用 id/status、声明码必登记、文档单测项数==实测、maps_to 顶层命令可达、禁用废止的 L0–L5 词汇）；修 5 处结果面漂移（abi-v0 的 L0–L5 错引与「当前空表」口径、evidence-bundle 37→52、local-api 12→18、release-conclusion 10→22）；check12 权重增量重测新模块
