# audit/tools

第三方/重型审计工具的配置与接入说明。**离线环境全部未接入**，在 audit/rules.json 中对应规则
（tool 类型）记为 not-run：不扣分、不写成 pass，报告单列。

| 工具 | 配置文件 | 对应规则 | 何时跑 | 说明 |
|---|---|---|---|---|
| detekt | detekt.yml | C-003/C-004/C-007/C-008 | CI | 需 detekt-cli jar，离线无 jar |
| ktlint | ktlint.editorconfig | B-007/C-011 风格面 | CI | 需 ktlint 可执行文件 |
| Konsist | konsist/NfArchitectureTest.kt | ARCH-001..004、B-004/B-010 | CI（接入 app/android 后） | 骨架，需先接入 Gradle 源集 |
| jscpd | 无（命令行参数） | D-001 | CI | 需 node/npm 依赖 |
| jacoco | 无（Gradle 插件） | J-001 | CI | 需 app/android Gradle 可解析 |
| PIT | 无（Gradle 插件） | J-013 | CI | 需 app/android Gradle 可解析 |
| CodeQL | 复用 .github/workflows/codeql.yml | H-014 | CI | GitHub 托管 |
| pip-audit | 复用 .github/workflows/dependency-audit.yml | H-013 | CI | PyPI 漏洞库需联网 |
| cargo-audit | 复用 .github/workflows/dependency-audit.yml | K-015 | CI | RustSec 需联网 |
| gitleaks | 无（命令行参数） | H-015 | CI | 需 gitleaks 二进制 |
| cyclonedx | SBOM.md | K-014 | CI | 需联网解析依赖元数据 |
| macrobenchmark | 无（Android 测试模块） | I-001/I-008 | 真机 CI | 被测试 APK 混淆冲突阻断 |

纪律：
- 工具未接入时，规则在报告里必须显示 not-run，不得手填 pass；
- 接入后把对应规则从 tool 改为可复现命令，并在 audit/evidence/<commit>/meta.json 留下运行记录；
- 阈值统一放 audit/ci/thresholds.json，禁止在工具配置里另设与门禁冲突的宽松阈值。
