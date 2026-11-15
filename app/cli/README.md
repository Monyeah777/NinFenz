# app/cli —— Python 控制面 nf_app

用户流入口（不是内部 op 堆砌）：import / map / project / author / assemble / validate /
export / share / pack / ccos / selftest。内部统一经 subprocess 调 Rust 参考实现
`nf-app-core`（CLI/JSON 面，见 `app/docs/CLI.md`）。

## 复跑（仓库根）

bash：

    export PYTHONPATH=app/cli
    python -m nf_app --help
    python -m nf_app --json import app/fixtures/sample-pack/docs/sample.md --out /tmp/import.nfimport.json
    python -m nf_app --json selftest        # 核心 op 冒烟，输出 nf-app-selftest/1，exit 0/1

PowerShell：

    $env:PYTHONPATH = "app/cli"
    python -m nf_app --help

核心定位顺序：`NF_APP_CORE` 环境变量（显式指定必须存在，找不到即 NF-E-005/exit 4，不静默回落）
→ `app/core/target/release/nf-app-core[.exe]` → `app/core/target/debug/...` → PATH。
找不到核心一律 fail-closed（NF-E-005 + 明确修复指引），Python 侧绝不伪造结果。

## 目录

    app/cli/
      nf_app/
        __main__.py      python -m nf_app 入口
        cli.py           argparse：用户流子命令 + 统一 --json 信封 + 错误/退出码出口
        core.py          subprocess 桥（--in -；信封校验；exit 一致性；ABI 探活）
        errors.py        AppError / 错误码注册表（单一真源 app/schema/error_codes.json）
        canonical.py     nf-canonical/1 + digest + 严格 JSON 解析（禁 float/重复键/超深）
        schemas.py       app/schema/*.schema.json 本地结构校验（pre-flight，语义面归核心）
        security.py      zip slip/bomb/symlink、YAML alias bomb、JSON 深度、路径穿越、分享脱敏
        io_utils.py      UTF-8 stdio / 原子写 / 严格读 / 相对 POSIX 路径
        pack.py          pack 目录 → items/tree（与核心同口径，夹具生成与测试用）
        commands/        子命令实现（common/import/project/author/flow/share/pack/ccos/selftest）
      tools/
        gen_fixtures.py      生成 app/fixtures/schema/{valid,invalid} + sample-pack / sample-pack-v2
        bless_golden.py      用 release 核心生成 golden 期望（--bless / --check）

## 子命令与产物

| 子命令 | 产物 / 作用 | 退出码 |
|---|---|---|
| import FILE 或 - | nf-import/1（--out）；`-` 读 stdin 剪贴板（source.kind=clipboard） | 0；低置信 warn 仍 0（NF-IMP-002） |
| map IMPORT [--spec] | 映射建议（heading→section / paragraph→slot / code_block→example / table→structured） | 0；无候选 warn（NF-MAP-001） |
| project init | nf-project/1，只存引用；`--force` 对已有项目 = 刷新引用（保留状态/history，追加 refs:refresh） | 2 用法/IO |
| project status / set | 状态机 draft→authoring→assembled→validated→exported→reviewed；回退必须 `--force` 且写 history | 2 非法回退 |
| author protocol 或 graph 或 spec | 条款开关/字段默认值；节点·边·权重增删改（先删后加）；槽位约束/预算。每次编辑后跑核心校验，失败不落盘 | 1 校验失败 |
| assemble PROJECT | 核心 graph-compile + assemble；写 result.md / result.meta.json / plan.nfplan.json，刷新 assembly 引用并推进状态 | 1 摘要不符/必填缺失 |
| validate --level L0 或 L1 | nf-validate-report/1（默认项目目录 report-LEVEL.nfreport.json）；`--record` 通过时推进到 validated | 1 fail；4 L2 不可用 |
| export --format md 或 zip 或 json | 核心 export；manifest 输出件摘要+来源 digest；zip 逐字节确定（mtime 1980、0644、path 升序） | 4 docx/pdf（NF-EXP-004，OPEN） |
| share prompt 或 markdown 或 json | 分享文本/文件；绝对路径/家目录/用户名/邮箱/密钥模式脱敏，脱敏后仍命中则 fail-closed（NF-E-002） | 2 |
| pack update 或 apply 或 rollback | diff → 冲突（默认 defer，未裁决 NF-PCK-006/exit 1）→ decisions 应用；`--backup` 本地备份；回滚校验摘要/目标（NF-PCK-007/exit 2）；apply 前后复算 base tree（base 只读，变了 NF-PCK-004/exit 3） | 1/2/3 |
| ccos task 或 import-result 或 review | ccos-task/1（项目必须 validated）；结果回钉 task_digest；人审 pending→approved/rejected，approve 必须 reviewer+note，绑定 subject_digest | 1 回钉不符/未人审 |
| selftest | 核心 op 冒烟，输出 nf-app-selftest/1（ops/summary），exit 0/1；核心缺失 exit 4 | 0/1/4 |

## 输出与错误契约

- 任意子命令支持 `--json`（可放在子命令前或后）：stdout 单行 JSON 信封
  {"ok":bool,"exit":int,"result":obj|null,"error":{code,message,fix,path?}|null}。
  成功 ok=true 且 exit=0；校验失败 exit=1 时 result=report。
- 非 `--json`：人类可读摘要到 stdout，错误摘要到 stderr（含修复指引）。
- 错误码只来自 `app/schema/error_codes.json`；exit 语义 0 成功 / 1 校验失败 / 2 用法·IO / 3 拒绝 / 4 环境缺失。
- 输入文档解析失败 → NF-E-004（exit 2）；未知枚举/格式 fail-closed → NF-E-002（exit 3）。

## 与 core / schema 的边界

- schema = 结构真源：本地只做 pre-flight（schemas.py），语义校验（引用/拓扑/预算/规则/verdict）以核心 validate 类 op 为权威。
- core = 语义与格式真源：CLI 不重写装配/导出/合并；只编排用户流、持久化产物、做安全护栏与脱敏。
- 内容真源仍是仓库根（01–07/管线库/模块库/资产库/protocol）：CLI 只按 ID+digest 引用，不复制内容。
- 确定性：canonical 产物禁时间戳/随机/绝对路径；唯一例外 nf-project.history[].at（digest 计算剔除 history）与本地备份目标指针 sidecar（nf-backup.target）。
- 产物 schema 自检：assemble meta（nf-assemble-result/1）、export manifest（nf-export-manifest/1）、backup（nf-backup/1）均先按 app/schema 校验再落盘（核心为本原则，CLI 兜底归一）。
- 核心产物（assemble meta、export manifest）以核心输出为准，CLI 按 app/schema/nf-assemble-result/1、nf-export-manifest/1 校验并落盘；核心版本暂不满足 schema 时 CLI 按同一 schema 归一兜底（升级核心后自动回到"核心为准"）。

## 测试

见 `app/tests/README.md`。快速自检：

    python -m pytest app/tests -q          # 全量（含 E2E；需要可用核心）
    python app/cli/tools/gen_fixtures.py --check
    python app/cli/tools/bless_golden.py --check

## OPEN（明确未实现，不冒充）

1. export --format docx 或 pdf：导出器未接入 → NF-EXP-004 / exit 4（不生成伪文件）。
2. assemble --block SEC-##：需要既有 result.md 作为 base_markdown（核心只替换该节、保留其余字节，缺失 → NF-ASM-004）；块编辑后建议重跑 validate L0。
3. assemble --stage：spec section 与 plan stage 无冻结映射字段，核心按可用信息尽力过滤（OPEN，测试只断言可调用/产物结构）。
4. ccos 的 QR/本地桥传输：文件/zip 默认，QR 未实现。
5. 环境注记 ENV-01：本机 DSH 沙箱下"工作区内可执行文件"外写受限（核心写 result.md 报 os error 5）；
   测试通过 conftest.core_in_tmp 把核心复制到临时目录绕过；真实 APP/CI 不受此限。
