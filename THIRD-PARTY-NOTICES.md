# 第三方组件声明（THIRD-PARTY NOTICES）

本文件由 `scripts/gen_third_party_notices.py` 从 **PyPI 官方元数据**生成，请勿手改。

## 范围说明

- **运行时**：NinFenz 核心与 npm 包**不依赖任何第三方运行库**（Python stdlib + Node 标准库）。
- **本文所列**：仓库**门禁与开发工具链**依赖（用于跑 `verify.sh` 与 CI 检查，不随产品分发）。
- 各组件按其自身许可证分发；本仓代码/文档为 MIT（见 `LICENSE`）。
- 投稿/社区内容的版权与再分发条款见 `LICENSES/LicenseRef-Community-Submission.txt` 与 `REUSE.toml`。

## 清单

| 组件 | 版本 | 许可证 | 主页 |
|---|---|---|---|
| `boolean-py` | 5.0 | **BSD-2-Clause** | [链接](https://github.com/bastikr/boolean.py) |
| `cachecontrol` | 0.14.4 | **Apache-2.0** | [链接](https://pypi.org/project/CacheControl/) |
| `certifi` | 2026.7.22 | **Mozilla Public License 2.0 (MPL 2.0)** | [链接](https://github.com/certifi/python-certifi) |
| `charset-normalizer` | 3.5.2 | **（查询失败：IncompleteRead）** | — |
| `cyclonedx-python-lib` | 11.12.0 | **Apache Software License** | [链接](https://pypi.org/project/cyclonedx-python-lib/) |
| `defusedxml` | 0.7.1 | **Python Software Foundation License** | [链接](https://github.com/tiran/defusedxml) |
| `filelock` | 4.1.1 | **（查询失败：IncompleteRead）** | — |
| `idna` | 3.20 | **BSD-3-Clause** | [链接](https://pypi.org/project/idna/) |
| `license-expression` | 30.4.4 | **Apache-2.0** | [链接](https://github.com/aboutcode-org/license-expression) |
| `markdown-it-py` | 4.2.0 | **MIT License** | [链接](https://pypi.org/project/markdown-it-py/) |
| `mdurl` | 0.1.2 | **MIT License** | [链接](https://pypi.org/project/mdurl/) |
| `msgpack` | 1.2.3 | **（查询失败：IncompleteRead）** | — |
| `packageurl-python` | 0.17.6 | **（查询失败：URLError）** | — |
| `packaging` | 26.3 | **（查询失败：URLError）** | — |
| `pip-api` | 0.0.35 | **（查询失败：URLError）** | — |
| `pip-audit` | 2.10.1 | **（查询失败：URLError）** | — |
| `pip-requirements-parser` | 32.0.1 | **（查询失败：URLError）** | — |
| `platformdirs` | 4.13.0 | **MIT** | [链接](https://pypi.org/project/platformdirs/) |
| `py-serializable` | 2.1.0 | **（查询失败：URLError）** | — |
| `pygments` | 2.21.0 | **（查询失败：IncompleteRead）** | — |
| `pyparsing` | 3.3.3 | **（查询失败：IncompleteRead）** | — |
| `requests` | 2.34.2 | **（查询失败：IncompleteRead）** | — |
| `rich` | 15.0.0 | **（查询失败：IncompleteRead）** | — |
| `sortedcontainers` | 2.4.0 | **（查询失败：IncompleteRead）** | — |
| `tomli` | 2.5.0 | **（查询失败：IncompleteRead）** | — |
| `tomli-w` | 1.2.0 | **（查询失败：URLError）** | — |
| `typing-extensions` | 4.16.0 | **（查询失败：URLError）** | — |
| `urllib3` | 2.8.0 | **（查询失败：URLError）** | — |
| `pip` | 26.2.1 | **（查询失败：URLError）** | — |
| `attrs` | 26.1.0 | **（查询失败：URLError）** | — |
| `coverage` | 7.16.1 | **（查询失败：URLError）** | — |
| `jsonschema` | 4.26.0 | **（查询失败：URLError）** | — |
| `jsonschema-specifications` | 2025.9.1 | **（查询失败：URLError）** | — |
| `pyside6` | 6.11.2 | **（查询失败：URLError）** | — |
| `pyside6-addons` | 6.11.2 | **（查询失败：URLError）** | — |
| `pyside6-essentials` | 6.11.2 | **（查询失败：URLError）** | — |
| `pyyaml` | 6.0.3 | **（查询失败：URLError）** | — |
| `referencing` | 0.37.0 | **（查询失败：URLError）** | — |
| `rpds-py` | 2026.9.1 | **（查询失败：IncompleteRead）** | — |
| `shiboken6` | 6.11.2 | **（查询失败：URLError）** | — |
| `ruff` | 0.16.8 | **（查询失败：URLError）** | — |
| `bandit` | 1.9.4 | **（查询失败：URLError）** | — |
| `colorama` | 0.4.6 | **（查询失败：URLError）** | — |
| `stevedore` | 5.9.1 | **（查询失败：URLError）** | — |

## 已知注意项

- **PySide6**（若安装 `[dev]` 全量 extras）：LGPL-3.0。仅用于桌面/终端相关测试，
  不随 npm 包或 CLI 分发；再分发其二进制需遵守 LGPL（提供源码获取方式与替换自由）。
- 其余均为宽松许可（MIT / Apache-2.0 / BSD / PSF），与 MIT 主许可兼容。

## 更新方式

```bash
python scripts/gen_third_party_notices.py --write   # 依赖版本变化后重跑并提交
```
