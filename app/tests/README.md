# app/tests —— pytest 契约/安全/Oracle/首闭环

依赖：Python 3.11、pytest、jsonschema（2020-12）、PyYAML。全部用 python -m pytest，cwd=仓库根。

## 复跑

    python -m pytest app/tests -q                                   # 全量
    python -m pytest app/tests/test_schema_valid.py app/tests/test_schema_negative.py -q
    python -m pytest app/tests/test_security_negative.py -q
    python -m pytest app/tests/test_oracle_parity.py app/tests/test_golden.py -q
    python -m pytest app/tests/test_cli_contract.py -q
    python -m pytest app/tests/test_e2e_first_loop.py -q            # 首闭环（需可用核心）
    NF_REQUIRE_CORE=1 python -m pytest app/tests -q                 # 核心缺失时失败而不是挂起（门禁用）

## 文件地图

| 文件 | 覆盖 |
|---|---|
| conftest.py | 路径/子进程 CLI 工具/错误码/核心探活；core_in_tmp 把核心复制到临时目录（ENV-01 沙箱外写限制）并设 NF_APP_CORE |
| helpers.py | sample-pack 工作区、项目/overlay/ccos-result 夹具（不实现校验语义） |
| oracle.py | 独立重写 canonical / tree / 拓扑序 / verdict（不 import nf_app） |
| test_schema_valid.py | fixtures/schema/valid/<schema>/*.json 通过对应 schema（16 个 schema：A0 13 + 首闭环 3，各 ≥1） |
| test_schema_negative.py | invalid 夹具被拒 + 与 invalid/EXPECTED.json 映射一致（每个 schema ≥2 反例、码已登记） |
| test_security_negative.py | zip slip / zip bomb / symlink / 嵌套 / YAML alias bomb / JSON 深度 / 路径穿越 / 分享脱敏（tmp_path 真实构造 zip） |
| test_oracle_parity.py | 本地层：oracle vs nf_app 实现 vs 入仓 manifest；对账层：canonical / pack tree / 拓扑序 / plan steps / verdict 与核心逐项对账 |
| test_golden.py | app/fixtures/golden/<op>/*.json 与核心输出逐字节比对（expected_sha256 钉原始 stdout） |
| test_cli_contract.py | 子命令参数契约 / --json 信封 / 错误码+退出码 / 缺核心 NF-E-005 / 状态机回退 / pack 备份回滚 / share 脱敏 / selftest |
| test_e2e_first_loop.py | §18.2 首闭环：装 pack→import→map→协议/管线重排/权重→装配→块级编辑→L0/L1→导出 md+zip→v2 diff/冲突/回滚→ccos task/result/人审；每步断言 schema 与 digest 确定性 |
| test_text_hygiene.py | app/cli、app/tests、app/fixtures 文本必须 UTF-8 无 BOM + LF（对齐全仓 text_hygiene 门禁） |

## 夹具与 golden

- schema 正反样例与 sample-pack 由 app/cli/tools/gen_fixtures.py 生成（唯一来源；--check 只校验）。
  手工改夹具前先改生成器，否则 gen_fixtures --check / 测试会红。
- golden 期望只由 release 核心生成（不是手写）：app/cli/tools/bless_golden.py --bless
  重生成后必须人工审 git diff app/fixtures/golden/ops 再入仓；--check 核对核心输出字节摘要。
  本仓 Python 侧 golden 放 app/fixtures/golden/ops/<op>/*.json（与 core 的 fixtures/、golden/ 分目录，互不覆盖）。
- EXPECTED.json 约定：每个 invalid 夹具登记 {schema, codes, violated}；
  codes 必须登记于 app/schema/error_codes.json（结构类 → 域错误码，未知枚举 → NF-E-002）。

## 核心依赖与 xfail 政策

- 需要核心的测试用 core fixture：文件存在 + --abi-version 返回 {abi,...} 才算可用
  （空实现 exe 不算）。核心不可用时以 xfail 显式报告阻塞（owner: rust-core）；NF_REQUIRE_CORE=1 下直接失败。
- 首闭环（test_e2e_first_loop.py）不允许 skip/xfail：必须真跑；两条 E2E 用例都直接执行。
- 安全负例与 schema 测试不依赖核心，恒可跑。

## 与 core/schema 的边界

- 不 import Rust；不复制核心实现来"自证"（oracle 是独立算法实现，故意与 nf_app 走不同代码路径）。
- 校验类断言以核心报告为准；本地只核对结构 schema 与文档约定字段。
- 测试不写仓库内夹具（golden 除外，仅 bless 工具在人工审后写）；所有临时产物进 tmp_path。

## 当前基线（2026-11-15）

    python -m pytest app/tests -q   →  485 passed / 0 failed / 0 skipped / 0 xfailed（约 2m08s）
    release 核心：app/core/target/release/nf-app-core.exe（abi nf-app-core/1，0.1.0）

覆盖：schema 正 16 / 反 41（EXPECTED 映射齐）；golden 15 case（逐字节）；安全负例 47；
首闭环 6 条用例（复合闭环 1 + 独立步骤 5）真跑 release 核心；CLI 契约 60（含 CLI.md op 表逐 op 协议负例）；oracle 对账 15；
text_hygiene 按文件计数（238 个文本文件）。
