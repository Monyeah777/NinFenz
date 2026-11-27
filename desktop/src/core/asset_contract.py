"""数字资产契约层：三面验证（数据 / 代码 / 脚本组合 · 声明即契约）。

为什么需要（内部差距实证 2026-10-03）：NF 的门禁此前只守「NF 自己产出的内容资产」——
`export_schema`（5 种产物 shape）、`json_schema`（协议件）、`code_metrics`（AST 度量）、
`purity_scan`（sink 面/纯度）、`sast_check`（bandit + ruff-S 计数棘轮）。而「任何 AI 产出的
数字资产（数据文件 / 生成代码 / 多语言脚本链）」没有统一契约面：数据格式与字段完整性只能
逐件人查，脚本组合的「A 的输出必须匹配 B 的输入」完全没有判据。本模块把这一面做成
**声明即契约 + 只判可证**的机读门禁（真源 `protocol/asset_contracts.json`）。

三面口径：
- **数据面**：JSON（严格 RFC 8259：拒 NaN/Infinity）/ CSV（表头 + 逐行列数）/ Markdown
  （frontmatter + 表格列数）；必填字段；可选 sha256 防篡改；可选 link（某字段是文件路径，
  其行数必须等于另一字段的计数——输入输出一致性）。
- **代码面**：AST 规范符合性（可解析 + 禁用调用面）+ **可证**空指针（同一语句序列内
  `x = None` 之后解引用 x，且期间无重新赋值/无分支并入）+ 测试用例在场（声明的测试件必须
  存在、可解析、且点名被测模块）。**安全漏洞面不另造一套**——SQL 拼接 / 命令注入 / 弱随机等
  由 `scripts/sast_check.py`（bandit + ruff-S 计数棘轮）与 `purity_scan` R6 守着，
  本模块重复造第二套只会造出两套口径。
- **脚本面**：脚本自带的 `nf-io:` 头（Python `#` / Bash `#` / VBA ``` 用同一声明格式）
  是契约双源之一，声明件是另一源；两源必须逐字一致；链（A→B）上「A 的产物」必须落在
  「B 的输入」里且路径对齐。**只判字面路径**——变量拼出来的路径不判（不编造）。
- **测试执行**：`run_tests()` 是**显式开启**面（`nf asset contract --run-tests`），
  默认门禁不执行任何被声明脚本的代码——门禁必须静态可复现。

纪律：纯标准库；只读扫描（唯 `freeze()` 写声明件）；解析不到的面写「未收窄」，不替它
编结论；问题消息带修复指引。
"""

# 读点：声明件读取在 _asset_contract._base 里仍走 json_doc.loads（N11，未改道）。

from __future__ import annotations

# ruff: noqa: F401 — 门面按原模块面重新导出（re-export 是职责，不是未使用）
import sys as _sys
import types as _types

# 依赖面：逐字保留原模块 import 面（含函数内 core import 的边）——
# 耦合图/纯度面按模块级 import 计算，勿删（见 re-export 说明）。
from core import atomic_write, json_doc, repo_face
from core.atoms import hash as hash_atom
from core import json_schema as js
from core import lazy_yaml
from core import conformance_scan as csc

from ._asset_contract._const import (
    DECL_REL,
    EXPORT_REL,
    FACES,
    FORMATS,
    LANGS,
    SCHEMA,
    SCHEMA_REL,
    _IO_RE,
    _MISSING,
    _MMD_KINDS,
)
from ._asset_contract._base import (
    _REPO_FILES,
    _REPO_SCOPE,
    _RESOLVE_MEMO,
    _begin_repo_scope,
    _declaration_doc,
    _declaration_doc_cached,
    _dig,
    _end_repo_scope,
    _read,
    _repo_files,
    _schema_doc,
    _schema_doc_cached,
    _strict_json,
    clear_repo_files_cache,
    digest_of,
    resolve,
)
from ._asset_contract._data import (
    _check_data,
    _csv_rows,
    _data_csv,
    _data_graphml,
    _data_json,
    _data_jsonl,
    _data_link,
    _data_markdown,
    _data_mmd,
    _data_toml,
    _data_yaml,
    _fields_issues,
    _md_tables,
    _schema_issues,
    _schema_of,
)
from ._asset_contract._ast import (
    _always_exits,
    _assigned_names,
    _assigns_none,
    _derefs,
    _guard,
    _head_exprs,
    _is_none,
    _none_deref,
    _scan_block,
    _walk_scope,
)
from ._asset_contract._code import (
    _WARN_RULES,
    _check_code,
    _check_tests,
    _code_structural,
    _code_warns,
    _denied_calls,
    _dotted,
    _is_code_line,
    _line_no,
    _warn_cut,
    _warn_export_no_panic,
    _warn_null_guard,
    _warn_unsafe_safety,
)
from ._asset_contract._script import (
    _check_chain,
    _check_index,
    _check_script,
    observed_paths,
    parse_io_header,
)
from ._asset_contract._aggregate import (
    _FRIENDLY,
    _export_drift,
    _registry_issues,
    _run_test_file,
    _scan_impl,
    _schema_self_check,
    contracts_for_path,
    freeze,
    frictionless_export,
    load,
    run_tests,
    scan,
    write_export,
)
