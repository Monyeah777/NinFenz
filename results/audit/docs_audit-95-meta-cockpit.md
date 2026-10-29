---
id: AUD-0047
title: 元认知生产驾驶舱主仓融合
date: 2026-10-29
scope: 将元原子运行时、动态驾驶、事件溯源、上下文预算、A/B 与正式协议融合进主仓；不调用外部模型，不伪造 HR-001。
verdict: pass
auditor: 本轮执行者
subjects:
  - desktop/src/core/cli_bridge.py:846d3097297b24cf10d83925adeaac98085083bd4ce4524699b23fcdc9e79e49
  - desktop/src/core/meta_cockpit/runtime_executor.py:204a67ec93855257323887011395b0866ac8d5ae1c485362e89eb058ffe64bfb
  - desktop/src/core/meta_cockpit/cockpit_service.py:18280c6966dd618a8b09daa058b461fa43f89e99f11c797ca884338ff5c13bbf
  - desktop/src/core/meta_cockpit/cockpit_ab.py:ae7a62ad3d3040c750a4b8a07794ae350bc5660e7f19679cb9330646cf32d04f
  - desktop/src/core/terminal.py:200c9ba8661ad8cf7b182c45d86aa94f4fcc0a6a5b9d2867b719f5c447305a25
  - desktop/tests/test_meta_cockpit.py:624f21f1e3bbb7bd40cb48bd028114b034e829d720020f2dd159c49d47ccc3af
  - desktop/tests/test_nf_cli.py:3544e66fa9081d201c47f59b15376d16abaa2eeba50491a9e69e1fd3d3aa239f
  - scripts/nf.py:a8d4e2f6170d01cfe63387bc1a58c368ead723bc874d15a8db445813e89b8ec6
  - tui/_surface.py:6b688fcd5c75248dbc5a496bb9c66a8e1c612d339392afaafa488a0cfe843ec9
  - protocol/check12_weights.json:744258fe3a1da9ed6e071618f4d9916d6107b1404b6489f55630cf3431f65397
  - protocol/coupling_baseline.json:c77bf864d3191b2364ff184168fc4978162e33c46853bfcb65987a62e54c9cc5
  - docs/meta-cockpit/README.md:fa04c0f21d01dbbfa96149190a76bd43aa44be22ca1e806662c3789296ff4518
  - results/meta-cockpit-manifest.json:dfb177bd9cfc8afda01544305c73852224ca2bd790c1fd213d715a33ff6ba87d

---

# 元认知生产驾驶舱主仓融合审计

> 日期：2026-10-29
> 范围：`desktop/src/core/meta_cockpit/`、CLI 桥、终端命令族与自动化测试
> Machine digest：`e2efe89661c386cd7b282992cdf833776d0840925f27152b44dbac5a1b0219c9`
> Manifest digest：`234905086b2c7dfb76ccf254b304a4ea7f3d06a1983f18bd23731b585aeeebda`

## 结果

- 33/33 原子执行器在场，14 个方法节点、10 节点内容管线与 5 节点元管线可加载执行。
- 元管线好样本 PASS：5 节点、17 个原子轨迹全部 PASS。
- 六类 fail-closed 突变均被抓：缺执行器、无效方法路由、预算耗尽、缺判据、未知任务类型、输出类型不匹配。
- 动态驾驶验证：不同任务/注入产生不同 need 序列，状态完成且轨迹无 `score`。
- 事件账本验证：提交后可加载、哈希链校验通过、确定性重放与当前状态一致。
- A/B 验证：预注册、盲包、功效分析、强效应、重复 ballot 拒绝、bundle/store 往返均通过。
- 发布清单验证：运行代码、契约、协议与正式说明纳入统一 digest；HR-001 保持 `PENDING`。
- CLI 入口验证：`nf cockpit` 与 `nf cockpit-ab` 可发现、可帮助、可执行；终端能力族与生成投影同步。

## 验证证据

| 检查 | 结果 |
|---|---|
| `tests.test_meta_cockpit` | 11/11 PASS |
| 最终受影响合并集 | 292/292 PASS |
| 终端/TUI/代码度量/权重/文本卫生受影响集 | 233/233 PASS |
| CLI/JSON 形状/耦合/模块命名受影响集 | 79/79 PASS |
| Ruff | PASS |
| 风格棘轮 | 10022 ≤ 基线 10032 |
| 代码规模 | 310 文件；最大行数 7643；最长函数 1262；最大复杂度 116 |
| 耦合 | 0 未登记环；258 模块；SDP 10/10 登记 |
| 元管线运行 | `PENDING-REVIEW`，机器层 PASS |

## 遗留边界

- HR-001 必须由作者或指定复核人签字，本审计未生成 approve 记录。
- 真实跨模型、多 seed A/B 未运行；不宣称已测得质量增量。
- 语义真伪仍由人工复核兜底。
- 工作区存在本次任务前已有的并发修改；本轮未执行 stash、reset、restore 或清理。

## 设计偏差

- 内部原型使用扁平模块导入与 `D:\\NinFenz` 绝对路径；主仓版本改为 `core.meta_cockpit` 包、相对导入和仓库根推导。
- 内部一次性 spike 脚本未直接入库；高价值断言已转为主仓 unittest 契约。
- `jsonschema` 作为可选标准实现使用；缺失时退回主仓确定性 JSON Schema 子集并 fail-closed。
