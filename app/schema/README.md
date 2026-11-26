# app/schema —— APP 契约层单一真源（A0）

> ⛔ 操作指令：本目录是 APP 三端共享格式的**唯一真源**。改任何 schema 前先读 `app/docs/CONTRACT.md` §2–§8；改完必须同步 `app/docs/CLI.md`、`app/fixtures/` 与两处实现（`app/core` Rust / `app/cli` Python），并跑 `python app/gates/run_gates.py`。

## 文件

| 文件 | schema | 说明 |
|---|---|---|
| `nf-pack.schema.json` | `nf-pack/1` | Pack 清单（items/tree/requires/compat） |
| `nf-import.schema.json` | `nf-import/1` | 导入识别（source/detected/structure/suggested/warnings） |
| `nf-protocol-pack.schema.json` | `nf-protocol-pack/1` | 协议包（clauses/fields/rules/examples/compat/migrations） |
| `nf-pipeline-graph.schema.json` | `nf-pipeline-graph/1` | 作者管线图（nodes/edges/weights/params/settings） |
| `nf-md-spec.schema.json` | `nf-md-spec/1` | MD 规范（sections/slots/constraints/acceptance/references） |
| `nf-assembly-plan.schema.json` | `nf-assembly-plan/1` | 装配计划（steps/modules/assets/weights/slots/output/fallback） |
| `nf-validate-report.schema.json` | `nf-validate-report/1` | 校验报告（L0/L1/L2 + issues + verdict） |
| `nf-template.schema.json` | `nf-template/1` | 模板包（内嵌 protocol/spec 快照 + hashes） |
| `nf-pack-update.schema.json` | `nf-pack-update/1` | Pack 更新（changes/impact/merge/conflicts） |
| `nf-overlay.schema.json` | `nf-overlay/1` | 用户覆盖层（clauses/params/presets/custom_assets） |
| `nf-project.schema.json` | `nf-project/1` | 项目引用 + 状态机 + 评审 + history |
| `nf-assemble-result.schema.json` | `nf-assemble-result/1` | 装配元数据（result.meta.json：digest/slots/missing/stage/block） |
| `nf-export-manifest.schema.json` | `nf-export-manifest/1` | 导出清单（format/files/source digest） |
| `nf-backup.schema.json` | `nf-backup/1` | 更新备份清单（本地备份，时间戳仅此处允许） |
| `ccos-task.schema.json` | `ccos-task/1` | CCOS 任务（输入/约束/验收/预算/策略/来源） |
| `ccos-result.schema.json` | `ccos-result/1` | CCOS 结果（artifacts/evidence/report/provenance/人审） |
| `nf-sdir.schema.json` | `nf-sdir/1` | 语义文档 IR（类型化块/关系/可访问性/块级溯源） |
| `nf-build-graph.schema.json` | `nf-build-graph/1` | 内容寻址构建图（节点/边/输出/环境指纹） |
| `nf-evidence.schema.json` | `nf-evidence/1` | 证据随包（产物/输入/校验/谱系/Ed25519 签名） |
| `nf-extension.schema.json` | `nf-extension/1` | 声明式扩展（adapter/renderer/validator/theme/preset） |
| `nf-prefs.schema.json` | `nf-prefs/1` | 单文件设置（模块/UI/语言/动作/校验/工作流） |
| `nf-workflow.schema.json` | `nf-workflow/1` | 工作流预设（只改视图与默认值） |
| `nf-action-policy.schema.json` | `nf-action-policy/1` | 动作策略（AI/合并/Pack/宏） |
| `nf-validation-policy.schema.json` | `nf-validation-policy/1` | 校验策略（off/on_demand/delivery/strict） |
| `limits.json` | `nf-app-limits/1` | 解析/解包上限（实现必须读取，不得散落字面量） |
| `error_codes.json` | `nf-app-error-codes/1` | 错误码登记（code/severity/exit/message/fix） |

## 校验命令

```bash
# 全部正样例过 schema + 反样例按 EXPECTED 被拒（需要 jsonschema）
python -m pytest app/tests/test_schema_valid.py app/tests/test_schema_negative.py -q
# 直接校验单件
python - <<'PY'
import json, jsonschema
schema = json.load(open('app/schema/nf-project.schema.json', encoding='utf-8'))
doc = json.load(open('app/fixtures/schema/valid/nf-project.json', encoding='utf-8'))
jsonschema.Draft202012Validator(schema).validate(doc)
print('OK')
PY
```

## 冻结纪律

- schema 的 `schema` 常量 = 版本；**破坏性变更必须升版本号**并声明 migration。
- 未知版本 fail-closed（`NF-E-001`）；未知 enum/op fail-closed（`NF-E-002`）。
- `additionalProperties: false` 是默认；`x-` 前缀是唯一合法扩展位。
- 确定性：canonical 产物禁时间戳/随机/绝对路径（契约 §7）；`nf-project.history[].at` / `ccos-*.provenance.*_at` 是人读例外，按其 schema 注解从 digest 剔除。