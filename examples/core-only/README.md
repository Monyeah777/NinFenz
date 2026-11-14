# core-only 示例（P00 黄金路径）

> ⛔ 操作指令：本件是 core-only 套件的复现入口（不产正文副本）；路径与命令以仓内实测为准。
> 状态：v1（G5 收口补件）

1. 编译意图 → spec/task：`python scripts/nf.py spec compile --intent spec/intents/sample-document.json --json`
2. 装配 E2E（core-only）：`python scripts/nf.py agent run --adapter mock --intent spec/intents/sample-document.json --assembly --json`
3. 输出校验：产物报告见 `results/output/output-report.json`（`nf-output-report/1`）
4. 交付打包：`python scripts/nf.py agent run --adapter mock --intent spec/intents/sample-document.json --assembly --deliver --sidecar`
   → 包在 `results/delivery/wiki-module-M06/`，报告 `results/delivery/delivery-report.json`
5. 复算：`python -m pytest desktop/tests/test_assembly_runtime_contract.py desktop/tests/test_delivery_contract.py -q`

边界：mock/local-template 是 parity 桩，不是真实外部模型（真实模型接入属 OPEN）。
