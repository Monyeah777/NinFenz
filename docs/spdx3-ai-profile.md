# SPDX 3.0.1 SBOM + AI Profile

`nf interop --kind sbom` 输出 SPDX 3.0.1 紧凑 JSON-LD。文档根元素是
`software_Sbom`，声明 `core`、`software`、`simpleLicensing`、`ai` 四个
Profile；`rootElement` 指向 `ai_AIPackage` 类型的 NinFenz 包。

## 数据从哪来

- 版本：`verify.sh` 的版本头。
- `CreationInfo.created`：仓内声明日期的最大值，不读墙钟，保证逐字节可复现。
- 依赖：`core.purity_scan.HARD_ALLOW` 与 `SOFT_IMPORTS`；硬依赖关系为
  `dependsOn`，软依赖为 `hasOptionalDependency`。
- 依赖版本：只取 `.github/requirements-*.txt` 或 `pyproject.toml` 中已钉版本；
  没有钉版就写 `NOASSERTION`，不猜测 latest。

## AI Profile 的诚实边界

NinFenz 不捆绑模型权重、训练数据或推理运行时。导出的 `ai_AIPackage` 因此：

- `ai_autonomyType = "no"`；
- `ai_useSensitivePersonalInformation = "no"`；
- 明确写明 “No model training is performed or shipped by this package.”；
- 明确写明不认证下游模型；
- 不填没有测量证据的能量、训练数据或模型指标字段。

## 外部校验边界

SPDX 3.0.1 以 JSON-LD context、模型约束和 SHACL 表述，而不是单一 JSON
Schema。本仓的常驻判据校验 `@id` 唯一性与关系闭合、四 Profile 声明、
AI 根包必填字段、许可证引用、依赖覆盖和确定性。外部工具可用
`spdx-tools` 或 SHACL 验证器进一步验收；本仓不把内部结构校验冒充第三方认证。
