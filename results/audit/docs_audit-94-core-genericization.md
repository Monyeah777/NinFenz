---
id: AUD-0046
title: 官方核心语义通用化（03/04/05 去叙述、域中立；协议层与门禁同步）
date: 2026-10-13
scope: 作者指令「把管线/模块/资产牵扯到叙述的全部删除，按 NF 定位改成通用，工业级回炉重造」，并确认「语义通用化」方案 A（保留 id、语义通用化）。方法沿用本会话五阶段逆向流程。硬不变量：13 个模块 id、文件路径、事件名、inputs/outputs/interfaces 一律冻结，保 107 社区包依赖闭包不破。机读面逐件等价证明：机器边界逐键相同、contract.schema/pipeline.schema PASS、模块边界签名 digest 不变、world_model slot 仍可寻址。
verdict: pass
auditor: 本轮执行者
subjects:
  - 01_核心协议.md:73f550896c9fa3185be72139adfed1277bf193bad7a363fab207d7bc3cdf0969
  - 02_联动注册表.md:686e91e8bbb6055f7dfeea8cd9beae064dc941d7b31263909cc159e58447e3ba
  - 06_Agent执行协议.md:849503effd94f1d7da1d5aab2c9dc2bc6113bb3ea8de4f6fa18446695ba8fd52
  - 07_官方核心出厂与社区预设导航.md:c7c522fd4f0370674cc2c191855c2fe14849fba04f7a5d8b2c68b437d8c34233
  - 03_管线库/P00_通用文档生成管线.md:e3acba0c5111b7e67094c4d82d815cd941bd2ebf6b36d5b71f8574241c2e06a2
  - 03_管线库/P01_标准管线.md:45176d7415faa9b63055892717f8262538e6ead83fff2d3ee83c11ad6df375ee
  - 03_管线库/P90_结构装配管线.md:b44562314643a042781a22f50a609785d339642c41c57db7ab134a732720b0dc
  - 04_模块库/通用类/M00_数据槽总线.md:dd9a95691343370a880b4aad605716901d7cb794859094da62c4099eac5795c9
  - 04_模块库/通用类/M10_节拍推进.md:d5e92a58ce3c0d5d144366828f919f3ce6eb7e2cc3234ad62a1c98535d77aacb
  - 04_模块库/通用类/M23_可见性边界.md:9635fe2d9f74a8f1d7e5060bfac3c44dc3545f81c9de515aae134205bb51f007
  - 04_模块库/通用类/M24_规则组合.md:1e5429032ca392f703c8123da4c4d0877bca0b60e1ad4b73744245a0329bc494
  - 04_模块库/通用类/M50_调度器.md:ddb590f6af181c677caccc39190a5a65b04751e9b0aec4bf5fb5ec27c6a9d524
  - 04_模块库/通用类/M80_输出质检门.md:b2dad838246b0f6287729131cd1aae464843691c1ede95bdcfb412a6eaf2cd48
  - 04_模块库/事件类/M06_流程状态机.md:321bd9492a6d5f6390e00542c4de2dc1914fdd3ddf5e35e0da9cb3981f9ebdcd
  - 04_模块库/事件类/M12_模板检索库.md:e927b0b1fc3d04b435fab672db4b92962ea28cb1ea8d2457c808ad377137006c
  - 04_模块库/事件类/M13_实体交互.md:9fa11d50e132082e55522cd56a3f7f3e84403f24ab6ee90f84a3805af6868d64
  - 04_模块库/事件类/M20_知识条目库.md:6178afdd65522494ba7fd9fe060d5b220269c0b4e893ec50ac631f4d0685e924
  - 04_模块库/事件类/M22_事件编排.md:b9b9d9728621912f954a67ae5d5ce80dc5ee7ec7945441a6b602b37fbfc9ad1a
  - 04_模块库/世界类/M08_环境状态.md:eb27707703c93a787150a8f32ecb0d5a2a273d56a8e93d2b4789def281c5fb81
  - 04_模块库/技术文档类/M90_结构装配.md:7ed8a8435be582e59aa070a10d5d6a6b234dfc127a0613507bd5842bf5a876a4
  - 05_资产库/README.md:7f8d241a8e6ce0f2b65a8e37b7708fa260044aec78b44f1efa986f7b57bf49bb
  - 05_资产库/provenance.json:293d3d3dfd1bf25e0fdeaa32e4b14cc817ed974b4209fda45619c65a1473ab93
  - 05_资产库/用户自定义/README.md:03068b5931dba4a0ae92020f9eddcb058bba27a852b0cf9ea015413607374dbf
  - 05_资产库/用户自定义/STYLE_DNA.md:b7ebed51132f13d4f42d6b3e8b6c425a653e947531e5952d65aa49df8e0a4381
  - protocol/asset_keys.json:59d9fcfb03e4da3c21c1b23bc83c2c0518c6e0c94147b3a6aa3915700e2bd33f
  - desktop/src/core/registry.json:cdcb852579785d8817451398021e55441e635a857e0acd3557af9a86b030e7ca
  - verify.sh:58a495db6a5eff2c49a39c0e3f34f2ca62d570700732fdfbdbb9e9d316baf8ad

---
> 重审（2026-10-17）：门禁提速收口：check39 剪枝定为 target/obj（刻意不剪 bin——实测零收益且可能承载入库脚本）；check39 7.15s→4.06s，差分 6/6

> 重审（2026-10-17）：门禁提速：check39 遍历再剪构建产物目录（target/bin/obj）——engine/rust/target 一处 22454 目录（gitignore），只含产物不含源；实测目录 24712→1949、遍历 4.36s→0.28s（15.5×），判定逐项等价（禁名命中与 desktop/src/ui 在场性一致），差分 6/6 通过；nf verify 冷跑 17.8s→16.3s

> 重审（2026-10-16）：门禁提速（收口）：修 check30 批量化引入的两处路径归一缺陷（git quotepath 非ASCII转义 + Windows glob 反斜杠）——被 test_check30_bump 当场抓出；另打破 gate_engine↔subcheck_cache 模块环（依赖倒置，只回稳定字段字典），并补两处静默兜底理由

> 重审（2026-10-16）：门禁提速：check30 的 127 次 git diff 合并为一次全量调用后按块取（实测 2.016s→0.196s，42 件逐字节等价）；连同 check39 遍历优化，22 条已迁入合计 30.6s→19.1s、nf verify 冷跑 28.7s→17.8s

> 重审（2026-10-16）：门禁提速：check39 遍历由 os.walk 换单遍 os.scandir（同层剪枝 + follow_symlinks=False，省掉每条目一次 lstat 与整棵被排除子树）；实测 10.34s→6.70s，结果集逐字段一致（24712 目录/7221 py），差分 6/6 通过

> 重审（2026-10-16）：L-D 并行结论：默认保持串行（并行结论不稳定：共享守护单例 + 派生面可写），verify_parallel.py 保留为开发侧工具；verify.sh 字节已变，重绑 digest

> 重审（2026-10-16）：L-D 并行收尾：check12 默认按核数并行（上限 16）+ 守护卫生；相关派生面重冻后重绑

> 重审（2026-10-16）：L-D 并行接线：check12 改走 scripts/verify_parallel.py（模块级并行，8 路实测 1255→409 s）+ 守护卫生（只收本次拉起的）；verify.sh 字节已变，重绑 digest


> 重审（2026-10-14 · 核心文档改名/路径迁移）：被审对象随本波改名或引用替换而变，subjects 依「重审并更新 digest」机械重绑；本轮不主张新的语义审计。

## 一、做了什么

- **04_模块库 13/13 语义通用化**：M00 数据槽总线 / 通用:M10 节拍推进 / M23 可见性边界 / M24 规则组合 / M50 调度器 / M80 输出质检门 / 事件:M22 事件编排 / M06 流程状态机 / M12 模板检索库 / M13 实体交互 / M20 知识条目库 / M08 环境状态 / M90 结构装配。
- **03_管线库 3/3**：P01 九层名通用化（装载/语境推进/实体状态/内容生产/决策/装配/一致性/素材/输出）；P00 骨架示例去叙述；P90 去叙事表述。
- **05_资产库**：README 改「机制资产 / 域包资产」两分；STYLE_DNA 去文学 DNA、改域中立 profile；provenance 三条 source 去域化；并补 STYLE_DNA 供应链登记（键词表 + 台账 + 文件头）。
- **协议层同步**：01 tags、02 模块表/挂载层名/执行序、06 §4 改可见性四层管线 + §5 改 profile 质检门、07、registry.json 名称三源一致。
- **门禁同步**：verify.sh check4/check5 判据键集随之泛化。
- **派生面重生成**：golden、LSP 逐字节夹具、verification-cards、verify_report、conformance_report、RECEIPTS、receipt_chain、interop×12、自包含样本（library/NF-TECHDOC-* 与 docs/examples/state-front/techdoc_front）与 library 回执。

## 二、验证

- 落定后 `bash verify.sh`：PASS=70 / FAIL=1——唯一失败为**并发会话的新增未跟踪件** `desktop/src/core/workflow_hardening.py`（引用不存在的 `nf verify-report` 子命令），不属本波范围，未改动。
- 本波范围内用例全绿：test_selfcontained_rebuild / test_lsp_transcript / test_audit / test_verification_cards / test_verify_report 共 30 例 OK；conformance 27/27 conformant。
- 12 份 pin 了旧 verify.sh digest 的审计件按仓规「重审并更新 digest」机械重绑（附重审说明），既有结论不变。

## 三、遗留

- 并发会话的 workflow_hardening 相关项由其自身收口。
- 标识符（narrative_event、quest_state、cognition.filter 等）迁移属 Phase 2，未在本次执行。
