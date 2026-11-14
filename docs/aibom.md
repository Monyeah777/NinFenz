# AIBOM / Model Card 导出（WP-41，G4）

> ⛔ 操作指令：本件是 WP-41 AIBOM 导出的人读说明；机读真源 `protocol/aibom.json`（`nf-aibom/1`），判据 `desktop/tests/test_aibom_contract.py`，实现 `desktop/src/core/aibom_export.py`，导出件 `results/ai/aibom.cdx.json` + `results/ai/aibom.spdx.json`。导出只是清单，不声称认证/合规。
> 状态：v1（G4 · 2026-11-15）· 依据：G4 WP-41（AIBOM/Model Card 导出 CycloneDX/SPDX）

## 导出

| 格式 | 文件 | 关键字段 |
|---|---|---|
| CycloneDX 1.5（AI-BOM） | `results/ai/aibom.cdx.json` | bomFormat/specVersion/serialNumber、metadata.component（machine-learning-model + SHA-256 model_digest）、components（context-lineage head）、properties（model/eval/lineage/review） |
| SPDX 2.3 风格 | `results/ai/aibom.spdx.json` | spdxVersion/dataLicense/SPDXID/namespace/creationInfo/packages（checksum=model_digest）/relationships（DESCRIBES） |

## 纪律

- **确定性**：serialNumber/documentNamespace 由模型身份摘要派生；created/timestamp 用固定样例时间（不读时钟）→ 同输入逐字节一致；
- **闭合**：hash == 模型卡 model_digest；properties 的 eval digest / lineage head / review decision+subject 必须与 `results/ai` 三件一致；
- **无秘密**：导出串扫描私钥/令牌/密码形状；
- **不引第三方运行时**：纯标准库，CycloneDX/SPDX 只作字段口径。

## 复核命令

```bash
python -c "import sys;sys.path.insert(0,'desktop/src');from core import aibom_export as a;a.write('.')"
python -m pytest desktop/tests/test_aibom_contract.py -q
```

## 边界

导出是清单（最小闭合集），**不构成官方认证/供应商合规声明**；全量规范字段映射不追。
