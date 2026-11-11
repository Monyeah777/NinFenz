# 第三方组件声明（THIRD-PARTY NOTICES）

本文件由 `scripts/gen_third_party_notices.py` 从 **PyPI 官方元数据**生成，**请勿手改**；
版本真源 = `.github/requirements-*.txt` 的 pin（跨文件去重），机读对照面 = `results/ccos/sbom.json`，新鲜度锚 = 锁文件摘要 `sha256:aa25989a9dec5eab`。
生成失败时脚本**不写盘**（fail-closed），不会把「查询失败」写进本文件。

## 归属声明（Attribution）

本仓自身代码与文档版权归 2026 Monyeah777（MIT，见 `LICENSE`）。
本文件所列第三方组件版权归各自作者，按各组件许可分发；本仓**未修改**上游源码
（Local Modifications: None）——仅以固定版本安装/调用，不 vendored 进产品。

## 范围说明（分发边界）

- **运行时**：NinFenz 核心与 npm 包**不依赖任何第三方运行库**（Python stdlib + Node 标准库）；
  可证：`pyproject.toml` 的 `[project].dependencies` 为空、`packaging/npm/package.json` 无 `dependencies`。
- **本文所列**：仓库**门禁与开发工具链**依赖（用于跑 `verify.sh` 与 CI 检查，不随产品分发）。
- 各组件按其自身许可证分发；本仓代码/文档为 MIT（见 `LICENSE` / `REUSE.toml`）。
- 投稿/社区内容的版权与再分发条款见 `LICENSES/LicenseRef-Community-Submission.txt` 与 `REUSE.toml`。

## 清单

| 组件 | 版本（pin） | 许可证 | 主页 |
|---|---|---|---|
| `boolean-py` | 5.0 | **BSD-2-Clause** | [链接](https://github.com/bastikr/boolean.py) |
| `cachecontrol` | 0.14.4 | **Apache-2.0** | [链接](https://github.com/psf/cachecontrol) |
| `certifi` | 2026.10.23 | **MPL-2.0** | [链接](https://github.com/certifi/python-certifi) |
| `charset-normalizer` | 3.5.2 | **MIT** | [链接](https://github.com/jawah/charset_normalizer) |
| `cyclonedx-python-lib` | 11.12.0 | **Apache-2.0** | [链接](https://github.com/CycloneDX/cyclonedx-python-lib/#readme) |
| `defusedxml` | 0.7.1 | **PSF-2.0** | [链接](https://github.com/tiran/defusedxml) |
| `filelock` | 4.2.9 | **MIT** | [链接](https://github.com/tox-dev/filelock) |
| `idna` | 3.20 | **BSD-3-Clause** | [链接](https://github.com/kjd/idna) |
| `license-expression` | 30.4.4 | **Apache-2.0** | [链接](https://github.com/aboutcode-org/license-expression) |
| `markdown-it-py` | 4.2.0 | **MIT** | [链接](https://github.com/executablebooks/markdown-it-py) |
| `mdurl` | 0.1.2 | **MIT** | [链接](https://github.com/executablebooks/mdurl) |
| `msgpack` | 1.2.3 | **Apache-2.0** | [链接](https://msgpack.org/) |
| `packageurl-python` | 0.17.6 | **MIT** | [链接](https://github.com/package-url/packageurl-python) |
| `packaging` | 26.3 | **Apache-2.0 OR BSD-2-Clause** | [链接](https://github.com/pypa/packaging) |
| `pip-api` | 0.0.35 | **Apache-2.0** | [链接](https://github.com/di/pip-api) |
| `pip-audit` | 2.10.1 | **Apache-2.0** | [链接](https://github.com/pypa/pip-audit) |
| `pip-requirements-parser` | 32.0.1 | **MIT** | [链接](https://github.com/nexB/pip-requirements-parser) |
| `platformdirs` | 4.13.0 | **MIT** | [链接](https://github.com/tox-dev/platformdirs) |
| `py-serializable` | 2.1.0 | **Apache-2.0** | [链接](https://github.com/madpah/serializable#readme) |
| `pygments` | 2.21.0 | **BSD-2-Clause** | [链接](https://github.com/pygments/pygments) |
| `pyparsing` | 3.3.3 | **MIT** | [链接](https://github.com/pyparsing/pyparsing.git) |
| `requests` | 2.34.2 | **Apache-2.0** | [链接](https://github.com/psf/requests) |
| `rich` | 15.0.0 | **MIT** | [链接](https://github.com/Textualize/rich) |
| `sortedcontainers` | 2.4.0 | **Apache-2.0** | [链接](http://www.grantjenks.com/docs/sortedcontainers/) |
| `tomli` | 2.5.0 | **MIT** | [链接](https://github.com/hukkin/tomli) |
| `tomli-w` | 1.2.0 | **MIT** | [链接](https://github.com/hukkin/tomli-w) |
| `typing-extensions` | 4.16.0 | **PSF-2.0** | [链接](https://github.com/python/typing_extensions) |
| `urllib3` | 2.8.0 | **MIT** | [链接](https://github.com/urllib3/urllib3) |
| `pip` | 26.2.1 | **MIT** | [链接](https://github.com/pypa/pip) |
| `attrs` | 26.1.0 | **MIT** | [链接](https://pypi.org/project/attrs/) |
| `coverage` | 7.16.1 | **Apache-2.0** | [链接](https://github.com/coveragepy/coveragepy) |
| `jsonschema` | 4.26.0 | **MIT** | [链接](https://github.com/python-jsonschema/jsonschema) |
| `jsonschema-specifications` | 2025.9.1 | **MIT** | [链接](https://github.com/python-jsonschema/jsonschema-specifications) |
| `pyside6` | 6.11.2 | **LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only** | [链接](https://pyside.org) |
| `pyside6-addons` | 6.11.2 | **LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only** | [链接](https://pyside.org) |
| `pyside6-essentials` | 6.11.2 | **LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only** | [链接](https://pyside.org) |
| `pyyaml` | 6.0.3 | **MIT** | [链接](https://pyyaml.org/) |
| `referencing` | 0.37.0 | **MIT** | [链接](https://github.com/python-jsonschema/referencing) |
| `rpds-py` | 2026.9.1 | **MIT** | [链接](https://github.com/crate-py/rpds) |
| `shiboken6` | 6.11.2 | **LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only** | [链接](https://pyside.org) |
| `ruff` | 0.16.8 | **MIT** | [链接](https://docs.astral.sh/ruff) |
| `bandit` | 1.9.4 | **Apache-2.0** | [链接](https://bandit.readthedocs.io/) |
| `colorama` | 0.4.6 | **BSD License（上游 classifier 原文）** | [链接](https://github.com/tartley/colorama) |
| `stevedore` | 5.9.1 | **Apache-2.0** | [链接](https://docs.openstack.org/stevedore) |

## 许可注意项（自动识别）

双许可选择：以下表达式含 OR，本仓使用时应择一履行（当前按最宽松可行项）：

- **Apache-2.0 OR BSD-2-Clause**：`packaging`
- **LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only**：`pyside6`, `pyside6-addons`, `pyside6-essentials`, `shiboken6`

PySide6 系列取 **LGPL-3.0-only**，仅门禁/测试链使用，不随 npm 包或 CLI 分发。

以下组件带**非宽松许可**条款（仅门禁/测试链，不随产品分发）：

- **LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only**：`pyside6`, `pyside6-addons`, `pyside6-essentials`, `shiboken6`
- **MPL-2.0**：`certifi`

再分发其二进制须遵守对应条款（如 LGPL 要求提供源码获取方式与替换自由）。

以下行只能取到上游 classifier 原文（PyPI 未给 SPDX 标识），需人工核对上游 LICENSE：

- **BSD License（上游 classifier 原文）**：`colorama`


## 更新方式

```bash
python scripts/gen_third_party_notices.py --write   # 依赖版本变化后重跑并提交
```
