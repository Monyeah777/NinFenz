# governance 示例（可选治理面）

> ⛔ 操作指令：本件是 governance 套件的复现入口（不产正文副本）；治理面可选，关闭时生产照常（`none` 模式）。
> 状态：v1（G5 收口补件）

1. 契约生命周期与义务：`protocol/contract_lifecycle.json`（`nf-contract-lifecycle/1`）＋ `python -m pytest desktop/tests/test_contract_lifecycle_contract.py -q`
2. 治理 verify 适配（DSSE/cosign/TSA/透明日志）：`python -c "import sys;sys.path.insert(0,'desktop/src');from core import governance_report as g;g.write('.')"`
   → `results/governance/report.json`（T1 可达；T2+ 缺适配器如实 missing）
3. 附件模式（none/observe/require）：`protocol/attachment.json`；require 缺证据即拒（exit 2）
4. 策略判定（默认拒绝）：`python -c "import sys;sys.path.insert(0,'desktop/src');from core import policy_engine as p;print(p.evaluate({'required_level':'T1','contract_status':'active','has_evidence':True}))"`
5. AI 证据链与 AIBOM：`results/ai/{model-card,lineage,human-review}.json`、`results/ai/aibom.cdx.json`
6. 复算：`python -m pytest desktop/tests/test_governance_report_contract.py desktop/tests/test_attachment_contract.py desktop/tests/test_policy_engine_contract.py -q`

边界：外部签名/TSA/透明日志未执行（OPEN）；治理面不声称认证/合规。
