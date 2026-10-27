#!/usr/bin/env python3
"""NinFenz 全链管道 CLI（v2.1.0 B2：retrieve→compose→gate→export 单命令）。

用法：
  python scripts/nf.py run --pipeline <P04管线.md> \
      --modules 通用类:M00,轻混类:M91,轻混类:M92,通用类:M80 \
      [--store <dir>] [--seed] [--fmt ccv3|skill] [--dest <out>] \
      [--no-include-refs] [--force-export]

- 全链 = pipe()：模块选择 → compose（E3 references 并入）→ render_ir
  → quality_gate（三态）→ export（exporter._REGISTRY）。
- --seed：把 04_模块库 + community 组合包模块装载进临时 store（演示/自测用，
  等同 e2e 前置）；缺省要求 --store 指向已含所选模块的工作区。
- 打印 GateResult 摘要（PASS/WARN/FAIL）+ 产物路径；FAIL 且非 --force-export
  → exit 1（CLI 层门禁镜像 verify 铁律）。
- 产物×适配矩阵：skill 拒 narrative（适配器内拒出，warnings 带说明）——
  CLI 原样透传 warnings。
"""
import argparse
import os
import sys
from typing import Optional

# argparse 的每个**内建** help 串都要过一次 `gettext.translation`（本机实测：建一次命令面 **432 次
# → 0.11 s**，每次都去 stat locale 目录），而本 CLI 不做本地化（help 全是中文字面量）。把翻译钩子
# 短路成恒等函数：实测 `_build_parser()` **102.8 → 8.4 ms**，~1900 次 stat 降到近乎零。必须在建面
# 之前打这个补丁（argparse 在 import 期就把 `gettext.gettext` 绑成了模块级 `_`）。
argparse._ = lambda message: message                                     # type: ignore[attr-defined,assignment]
argparse.ngettext = lambda singular, plural, n: singular if n == 1 else plural  # type: ignore[attr-defined]

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
# stderr 同样钉 UTF-8：argparse 的用法错误与中文错误信息走 stderr，若随 locale（Windows 上
# 常为 GBK）落盘/进管道，UTF-8 消费方会解码失败（实测：管道读取方 UnicodeDecodeError）。
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "desktop", "src"))
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)
from core import interp_diet  # noqa: E402 - 紧接路径设定；`-S` 下补回 site-packages（见其 docstring）
from nf_cmds.common import (_file_shape_issue, _portable_path, _machine_fail, _open_store)
from nf_cmds.surfaces import (_cmd_lsp, _cmd_facts, _cmd_license, _cmd_endpoint, _cmd_assertions, _cmd_conformance, _cmd_stats, _cmd_registry, _cmd_model, _cmd_spec, _cmd_ir, _cmd_ops, _cmd_glossary, _cmd_security, _cmd_privacy)  # noqa: F401 - 由 _dispatch_table 经 globals() 解析
from nf_cmds.misc import (_cmd_sig, _cmd_diff, _cmd_telemetry, _cmd_changelog, _cmd_receipts, _cmd_layers, _cmd_attest, _cmd_runtime, _cmd_agent)  # noqa: F401 - 由 _dispatch_table 经 globals() 解析
from nf_cmds.shelf import (_cmd_combine, _cmd_output, _cmd_market)  # noqa: F401 - 由 _dispatch_table 经 globals() 解析
from nf_cmds.domain import _cmd_domain  # noqa: F401 - 由 _dispatch_table 经 globals() 解析
from nf_cmds.knowledge import _cmd_knowledge  # noqa: F401 - 由 _dispatch_table 经 globals() 解析
from nf_cmds.asset import _cmd_asset  # noqa: F401 - 由 _dispatch_table 经 globals() 解析
from nf_cmds.library import _cmd_library  # noqa: F401 - 由 _dispatch_table 经 globals() 解析
from nf_cmds.module import _cmd_module  # noqa: F401 - 由 _dispatch_table 经 globals() 解析
from nf_cmds.forge_ops import (_cmd_register, _cmd_import_ir, _cmd_design, _cmd_pipeline, _seed_store, _demo_pipeline_path, _cmd_demo, _cmd_lint, _cmd_st_validate)  # noqa: F401 - 由 _dispatch_table 经 globals() 解析
from nf_cmds.meta_ops import (_cmd_release, _cmd_worldmodel, _cmd_score, _cmd_nfal, run_cli, run_help, run_completion, run_serve, run_explain)  # noqa: F401 - 由 shims/dispatch 使用
from nf_cmds.assemble import _cmd_assemble  # noqa: F401 - 由 _dispatch_table 经 globals() 解析
from nf_cmds.govern import (_cmd_design_audit, _cmd_approve, _cmd_handover, _cmd_postmortem, _cmd_audit, _cmd_decide, _cmd_decisions, _cmd_review, _cmd_workloop)  # noqa: F401 - 由 _dispatch_table 经 globals() 解析
from nf_cmds.integrate import (_cmd_toolface, _cmd_transparency, _cmd_locales, _cmd_events, _cmd_driver, _cmd_state_front, _cmd_interop, _cmd_render, _cmd_bench)  # noqa: F401 - 由 _dispatch_table 经 globals() 解析
from nf_cmds.library_ops import (_cmd_patterns, _cmd_related, _cmd_impact, _cmd_rename, _cmd_who_refers, _cmd_cognition, _cmd_rfc)  # noqa: F401 - 由 _dispatch_table 经 globals() 解析
interp_diet.restore()





NF_CLI_VERSION = "1.1.0"
NF_CLI_EPILOG = (
    "入门：\n"
    "  nf shell              # 交互终端（能力菜单 + 命令直通；端壳退役后的人机入口）\n"
    "  nf --help             # 全命令总览\n"
    "  nf help <cmd>         # 查看任意子命令帮助\n"
    "  nf doctor             # 环境自检（快速只读体检）\n"
    "  nf completion bash    # 生成 shell 补全（>> ~/.bashrc）\n"
    "  nf run / nf demo      # 作者五分钟上手（README「五分钟快速开始」含逐条示例）\n"
    "退出码：0 成功 · 1 运行/校验失败 · 2 用法错误（argparse 约定）。"
)


#: 命令面缓存（效率）：argparse 面构建 ≈100 ms/次，而一次终端命令往往要建 3 次以上
#: （索引 + 命令树 + 真正解析）——`--verify --deep` 的全命令扫描更是 64 次。
#: 缓存后同一进程内只建一次；解析器只读复用（构建期之外无人改它）。
_PARSER_CACHE = None
_TREE_CACHE = None
_INDEX_CACHE = None


def _build_parser() -> argparse.ArgumentParser:
    """取命令面（**带缓存**）：首次构建，其后复用同一实例（只读）。"""
    global _PARSER_CACHE
    if _PARSER_CACHE is None:
        _PARSER_CACHE = _make_parser()
    return _PARSER_CACHE


def _make_parser() -> argparse.ArgumentParser:
    """真正构建 argparse 命令面（实现已抽到 scripts/nf_parser/；注册顺序保持不变）。"""
    import importlib.util as _ilu
    _pkg_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nf_parser")
    _spec = _ilu.spec_from_file_location("nf_parser",
                                          os.path.join(_pkg_dir, "__init__.py"),
                                          submodule_search_locations=[_pkg_dir])
    _mod = _ilu.module_from_spec(_spec)
    sys.modules["nf_parser"] = _mod
    _spec.loader.exec_module(_mod)
    return _mod.make_parser(root=ROOT, version=NF_CLI_VERSION, epilog=NF_CLI_EPILOG)
















def _cmd_import(args) -> int:
    """nf import：旧面 + T9.2 导入器（实现见 nf_cmds/import_cmd.py）。"""
    from nf_cmds.import_cmd import run as _import_run
    return _import_run(args, import_ir=_cmd_import_ir)










def _cmd_serve(args):
    return run_serve(args, NF_CLI_VERSION)




















#: `--root` 受闸门的**读类**命令（落点必须是在场目录）。写类（`asset add` 会自建台账目录）
#: 不在此列——它们本来就该能创建落点。
_ROOT_READERS = {
    ("asset", "ls"), ("asset", "verify"), ("asset", "inventory"),
    ("asset", "density"), ("asset", "usage"), ("asset", "thickness"),
    ("asset", "ledger"), ("asset", "baseline"),
    ("module", "ls"), ("module", "verify"),
    ("design", "audit"), ("design", "steelman"),
    ("lsp", ""),
}


def _root_pair(args) -> tuple:
    """→ `(顶层命令, 二级子命令)`（`--root` 落点闸门用的分类键）。"""
    cmd = str(getattr(args, "cmd", "") or "")
    sub = ""
    for att in ("asset_cmd", "module_cmd", "design_cmd", "registry_cmd", "ops_cmd"):
        val = getattr(args, att, None)
        if val:
            sub = str(val)
            break
    return (cmd, sub)

















CHECK_GUIDE = {
    "1": "缺什么：官方核心目录结构件缺失（01/02/06/07/README/LICENSE + 官方管线 P00/P01/P90）。补什"
        "么：按 07 §7 项1 清单补齐根级文件与 03_管线库 官方管线。",
    "2": "缺什么：重号 ID 未全限定（官方层裸号重复）。补什么：官方核心层模块引用一律全限定（通用:M1"
        "0/事件:M22），07 §7 项5。",
    "3": "缺什么：五条不变式落点缺失或错位。补什么：核对 01 §5 ↔ 07 §7 项6 的逐条落点声明。",
    "4": "缺什么：认知边界断链（06 §4 管线 ↔ M23 认知域不一致）。补什么：对齐执行协议与 M23 的裁剪/"
        "过滤口径。",
    "5": "缺什么：质检门流水线违约（M80 gate_action ↔ 06 §5）。补什么：核对输出生成器的 gate_action"
        " 三态与执行协议一致。",
    "6": "缺什么：入口导航断链（README → 07 → 协议链/官方目录）。补什么：按 07 §7 项6 修 README 路"
        "由。",
    "7": "缺什么：社区两包结构完整度违约。补什么：校园/西幻包 modules/pipelines/protocol.yaml/READM"
        "E 与 02 §8 在册数一致。",
    "8": "缺什么：社区资产外形与基线不一致（文件数 / 行数 / 逐文件摘要）。补什么：核对内容后显式重"
        "签 `nf asset baseline --write`（07 §7 项3）。",
    "9": "缺什么：模块-资产引用不可寻址或社区 README 重号未限定。补什么：资产键真实可寻址 + 社区重"
        "号限定引用。",
    "10": "缺什么：EXT 闭合违约或社区红线未落地。补什么：EXT 实体闭合 + 红线条目对齐 07 §7 项2/8。",
    "11": "缺什么：资产-模块三方对账不一致（02 §8.1 ↔ modules/ ↔ assets/README）。补什么：三方条目"
        "对齐（08 方案 T5 A5）。",
    "12": "缺什么：desktop/src 或 scripts 语法/单测失败。补什么：跑 python -m unittest discover -s desktop/tests 修到全绿；示例：新模块未补测试→先写测试再实现。",
    "13": "缺什么：02 头部与 registry.json 协议版本不一致或迁移记录不全。补什么：版本改动需 02 §9.3"
        " 四步（快照/bump/迁移说明/回读）。",
    "14": "缺什么：社区协议登记缺 protocol.yaml/Schema 12 字段/登记三要件。补什么：01 §6.1 + 02 §8."
        "3 补齐并保持 registry protocols[] 一致。",
    "15": "缺什么：组合引用 references 违约（不在册/闭包未闭合/层冲突/schema 不兼容/双源不一致）。"
        "补什么：按 02 §8.4 五断言核对。",
    "16": "缺什么：machine_contract 机读结构或装配 publish⊆subscribe 违约。补什么：01 §1.1 契约字段"
        " + 运行时寻址授权一致。",
    "17": "缺什么：质量门 unittest 失败。补什么：装配/锚点/资产悬空需过 quality_gate 语义。",
    "18": "缺什么：导出契约 unittest 失败。补什么：ccv3_adapter/exporter 映射层检查锚点与条目。",
    "19": "缺什么：导出产物 shape 与 schema 不符。补什么：对照 export_schema 5 格式自检。",
    "20": "缺什么：模块文档必填项缺失。补什么：按文档完整性清单补必填字段。",
    "21": "缺什么：registry 引用图悬空/裸号重复。补什么：清理 source_package/module_id 引用。",
    "22": "缺什么：导出物规范体检失败（spec_version/name/description 超限）。补什么：按 export_sche"
        "ma 硬约束修正。",
    "23": "缺什么：资产供应链台账违约（不可溯源/不可发现/键孤儿）。补什么：05_资产库/provenance.jso"
        "n + 文件头双源一致。",
    "24": "缺什么：模块状态位异常或 deprecated/retired 被引用。补什么：module deprecate/restore 流"
        "转或移除引用方。",
    "25": "缺什么：01-36 编号方案文档签名不可复现/结构缺标题。补什么：文档须 UTF-8 且含 # 标题，同"
        "一内容重复生成须逐字节一致；示例：nf sig --verify。",
    "26": "缺什么：语义矛盾（techdoc 链订阅事件无发布方 / 挂载点或类别漂移）。补什么：全库补发布方"
        "或修正漂移；示例：nf related 反查 + semantic_conflict.scan。",
    "27": "缺什么：架构纯度违约（端壳残留/私货可变物/重复标题/raise 消息缺修复指引/第三方 import 未"
        "登记）。补什么：purity_scan 五规则逐条修；示例：R1 端壳关键词残留清理、R5 第三方 import 改"
        "软导入并在 SOFT_IMPORTS 登记理由。",
    "28": "缺什么：协议层 IDL 违约（schema 定义缺失或协议件字段漂移）。补什么：protocol/schema 五定"
        "义在场 + 在场 machine_contract/管线/协议包/台账过 schema；示例：nf doctor 看 schema 在场。"
        "",
    "29": "缺什么：Conformance 虚标或声明缺失（声明级别 > 可证级别）。补什么：按 01 §1.2 与 conform"
        "ance_scan 提示降级或补证据。",
    "30": "缺什么：扩展判据缺失或版本字段 bump 无迁移记录。补什么：protocol/EXTENSION.md 判据 + bum"
        "p 变更带 01 §7/02 §9.3 四步迁移记录。",
    "31": "缺什么：生成物过期（protocol/generated 与当前 schema/协议件不一致）。补什么：重跑 protoc"
        "ol_golden.write_golden 并随变更一并提交。",
    "32": "缺什么：质量纵深汇总违约（载荷注册表/资产 ledger/指令审计/资产密度·厚度·零引用/tool_face"
        "/world_model/world_slots 任一缺口）。补什么：跑 nf release 看细分失败项，修复后 verify 全"
        "绿；world_model 契约自查可用 nf worldmodel。",
    "33": "缺什么：新面汇总任一子扫描红（MCP dual-era/stdio 帧纪律、attestation、基线回归评分、机械"
        "修复、正文 lint、编辑器面（能力/诊断定位/didClose/退出码/领域智能/配置生成）、许可证门、遥"
        "测 semconv、编码卫生、互操作导出与入仓面、文档命令面、决策层面、构建回路）。补什么：`nf do"
        "ctor` 先定位，再按面跑 `nf interop --check` / `nf lint` / `nf score` / `nf telemetry` / `n"
        "f conformance`；编码卫生命中按 `docs/text-hygiene.md` 处置（隐形字符/行尾/重复键）。",
    "34": "缺什么：云端图书馆面违约（frontmatter 真源缺字段、INDEX·ALIAS 投影漂移、生命周期状态越表"
        "、文档四型未覆盖、llms.txt 入口缺失、内容分级未声明）。补什么：`nf library verify` 看逐条"
        "失败；改条目 frontmatter 后 `nf library reindex` 重建投影（投影不是真源）。",
    "35": "缺什么：深化面违约（管线抽象执行 GraphSpec、馆藏回执单根、模块边界冻结、内容绑定批准、一"
        "致性报告工件、无效语料）。补什么：按失败项分别跑 `nf pipeline dryrun --all` / `nf library "
        "receipts --write` / `nf module signature --write` / `nf approve --verify` / `nf conformanc"
        "e --write`。",
    "36": "缺什么：治理面违约（一致性声明 CONFORMANCE、RFC 版本史、指令档机器面路由、实践包、跑分台"
        "、端点契约）。补什么：`nf conformance` 看契约面，并用 `nf rfc` / `nf driver` / `nf pattern"
        "s verify` / `nf endpoint` 逐条对；改声明件后重跑。",
    "37": "缺什么：双源知识层违约（权威分层、查询有序、时效、消化可追溯、认知裁剪越权）。补什么：`n"
        "f knowledge lint` 逐条看巡检结论（`nf knowledge order|visible` 可复核顺序与可见性；本子命"
        "令**没有** `--check`）；补 `protocol/knowledge_sources.json` 声明或消化记录后重跑（越权源"
        "不得进入任何 clearance 的查询顺序）。",
    "38": "缺什么：出口自动化违约（自述数字与实算不一致、他证通道缺回填、GEO 出口过期、FDE 样例不过"
        "）。补什么：`nf stats --write` 重写生成区；`docs/standards/index.md` 与 `protocol/geo_expo"
        "rt.json` 重渲染；FDE 样例跑 `python scripts/fde_sample_run.py` 看失败项。",
    "39": "缺什么：端壳残留回潮 / 终端三件缺失 / 菜单指向死命令 / 命令面未策展 / 输出不确定。补什么"
        "：按 `docs/L3_FROZEN.md` 裁决删除残留件；`nf shell --verify` 看终端自检逐项失败；新增命令"
        "要登记进 `core/terminal.py` 的能力族。",
    "40": "缺什么：数字资产契约违约（数据格式/字段完整性/输入输出一致性/防篡改；代码 AST 规范、可证空指针、测试用例在场；脚本 nf-io 头与声明双源不一致、链上 A 输出不匹配 B 输入）。补什么：`nf asset contract` 逐条看；数据件改声明或补字段；脚本补 `# nf-io: inputs=… outputs=…` 头并与 protocol/asset_contracts.json 对齐；sha256 漂移确认后用 `nf asset contract --freeze` 重冻。",
    "41": "缺什么：构建隔离违约（构建入口出现取网/取包命令；Dockerfile 基座未按 @sha256 钉或写了"
          " :latest；engines.node / engine/rust/Cargo.lock 缺位；CI 的 setup-python / setup-node 未给"
          "具体版本号）。补什么：先跑 core.build_isolation.scan 看逐条；构建入口改读仓内既有件、基座"
          "换成 name:tag@sha256:*、工具链把版本写死（不浮动 major）。",
    "42": "缺什么：provenance 校验不过（回执单根形状坏 / 独立子进程验签失败 / 篡改未被检出）。补什么"
          "：nf receipts --scope protocol --write 重建单根；确认 nf attest --key-file 与"
          " core.attest.verify 的口径一致；篡改必须被判否——否则这份证据是摆设。",
    "43": "缺什么：契约语义规则不过（层序闭包/域隔离/门全性 FAIL）。补什么：跑 nf spec check "
          "--core 看 rule/subject/evidence；修注册表或管线声明；不可判定项按 WARN 记录，不假装通过。",
    "44": "缺什么：注册表 CID 与在盘索引不一致（包内文件被改/增删）。补什么："
          "nf registry index --write 重签；确认改动是预期的，否则回滚该包文件。",
    "45": "缺什么：内容供应链扫描出现 critical（可执行内容/明文凭据）。补什么："
          "nf security scan 定位 file:line；删除或转义危险内容；合法安全研究样本走显式白名单。",
    "46": "缺什么：隐私/air-gap 门禁不过（PII/本机绝对路径/凭据 critical，或网络站点静态审计"
          "命中未登记出口）。补什么：跑 nf privacy scan / nf privacy check 看 file:line；"
          "改写绝对路径、删除或掩码凭据、把合法网络出口登记进 allowlist；warn 只报告不判死。",
    "47": "缺什么：CLI IA 生成件与实时重算不一致，或命令覆盖率不闭合（未归族/重复归族/空族/"
          "虚指）。补什么：跑 nf cli map --json/--check 看 coverage；重跑 nf cli map --write；"
          "新命令须在 terminal.FAMILIES 恰好归一族。",
}

def _cmd_preset(args):
    """nf preset：预设配置（实现见 nf_cmds/preset.py）。"""
    from nf_cmds.preset import run as _preset_run
    return _preset_run(args)























































#: 收路径的旗标 dest（`--out` / `--dest` / `--store` / `--key-file` / `--trace` …）——写法闸门
#: 只扫这些，**不扫自由文本参数**（`--note` / 需求描述 / 问题陈述里出现 `..` 是正常写法）。
#: 名单由「argparse 面里 help 含路径类词」运行时枚举得到，再逐条人工剔除非路径项。
_PATH_FLAG_DESTS = ("out", "dest", "build_dest", "save_path", "store", "trace", "session_path",
                    "state", "state_path", "key_file", "ssh_key", "ssh_allowed_signers",
                    "registry", "root", "case", "exceptions", "check_file", "check_md",
                    "artifact", "verify", "ledger", "history", "template", "dst", "script_file",
                    "baseline", "pipeline", "questions", "plan", "record", "replay")


def _path_writing_issue(args) -> str:
    """收路径旗标的**写法闸门** → 问题描述（合规返回空串）。

    口径（2026-10-01，与 `core.paths.validate_path` 同源）：**绝对路径按原样**（落到 CI 产物目录 /
    临时导出是设计面），**相对路径一律相对仓库根**且不得含 `..` 段 / 盘符相对写法——后者看着像
    仓内相对路径，实际会静默逃出仓库（实测 `nf interop --kind openapi --out ../x.json` 写到仓外，
    且报成「内部错误」）。集中一处判 ⇒ 覆盖全部收路径命令，错误也框成用户问题。
    """
    from core import paths as _p
    for dest in _PATH_FLAG_DESTS:
        val = getattr(args, dest, "")
        if not isinstance(val, str) or not val.strip() or os.path.isabs(val):
            continue
        try:
            _p.validate_path(ROOT, val)
        except _p.PathEscapeError as exc:
            return ("路径写法越界：--%s %s（修复指引：相对路径一律相对**仓库根**，不得含 `..` 段 / "
                    "盘符相对写法；确实要落到仓库外请给**绝对路径**）（%s）"
                    % (dest.replace("_", "-"), val, exc))
    return ""


#: **读进来当文本**的参数（旗标 + 位置参数）→ 过编码闸。名单口径（2026-10-01 三批后的最终态）：
#: **从 argparse 面运行时枚举**（help 里自称「文件 / 路径 / JSON / md / 信封 / 快照 / 规则 / 脚本 /
#: 台账 / 清单」的非布尔参数），再减去两类：
#:   ① **二进制输入**：`--key-file` / `--ssh-key`（HMAC/SSH 密钥是**字节**，不是文本）；
#:   ② **写侧落点**：`--out` / `--dest` / `--to` / `--session` / `--write`（那些是**目标**，
#:      不是被读的内容；把目标也拦会把「覆盖一个已有二进制文件」误判成输入错误）。
#: 为什么不再手写名单：二批普查抓到 5 处漏网，根因就是「同一概念换了个参数名（`path` / `paths`）
#: 就漏出闸门」——所以改成**枚举为准**，并由 `test_cli_error_framing.PathFlagCoverageTest`
#: 的对账判据保证「枚举到的文本类参数都在这里，或写明为什么豁免」。
_UTF8_BINARY_EXEMPT = {"key_file": "HMAC 密钥是字节", "ssh_key": "SSH 私钥是字节",
                       "fmt": "导出格式枚举（md/ccv3/skill/…，ASCII，非文本件）"}
_UTF8_TEXT_DESTS = ("a", "action", "artifact", "b", "baseline", "check", "check_file",
                    "check_md", "entry", "exceptions", "face", "file", "history", "key", "ledger",
                    "mode", "name", "package", "path", "paths", "pipeline", "pkg",
                    "questions", "registry", "root", "runs", "script_file", "snapshot",
                    "source", "ssh_allowed_signers", "state", "state_path", "subject",
                    "target", "template", "tier", "trace", "verify", "plan", "record", "replay")


def _utf8_text_issue(args) -> str:
    """输入件必须是 UTF-8 文本 → 问题描述（合规 / 不在场 / 超限一律返回空串）。

    依据（2026-10-01 探针）：把**非 UTF-8** 文件喂给 `nf attest` / `nf lint` / `nf import` /
    `nf run --pipeline` / `nf decide --state`，此前要么冒「✗ 内部错误：'utf-8' codec can't
    decode…（重跑 NF_DEBUG=1 看堆栈）」，要么只回裸解码错——**用户输入问题被框成内部故障**，
    且零指引。读盘在各命令里分散，故在入口集中判一次：**文本件一律 UTF-8**（本仓编码卫生口径），
    不合即 clean 拒 + 可执行指引。密钥等二进制输入**不在此列**（那类是字节，不是文本）。
    """
    for dest in _UTF8_TEXT_DESTS:
        raw = getattr(args, dest, "")
        # 位置参数可以是**列表**（`nf lint a.md b.md` 的 `target` 是 `nargs="*"`）——两条形态都判。
        values = raw if isinstance(raw, (list, tuple)) else [raw]
        for val in values:
            if not isinstance(val, str) or not val.strip():
                continue
            path = val if os.path.isabs(val) else os.path.join(ROOT, val)
            if not os.path.isfile(path):
                continue
            # T9.2 二进制导入面：.docx/.doc 是 zip/二进制，不由 UTF-8 文本闸判（各自导入器
            # fail-closed 判 zip/XML 形状）。
            if path.lower().endswith((".docx", ".docm", ".doc")):
                continue
            try:
                if os.path.getsize(path) > 8 * 1024 * 1024:  # 超大件交各命令自己的体量闸门
                    continue
                with open(path, "rb") as fh:
                    fh.read().decode("utf-8")
            except UnicodeDecodeError as exc:
                label = ("--%s" % dest.replace("_", "-") if dest in _PATH_FLAG_DESTS
                         else "<%s>" % dest)
                return ("输入件不是 UTF-8 文本：%s %s（%s）（修复指引：本仓文本面一律 UTF-8；"
                        "其它编码先转换（如 `iconv -f gbk -t utf-8`），二进制请换文本件）"
                        % (label, val, exc))
            except OSError:
                continue
    return ""





























def _cmd_explain(args):
    return run_explain(args, CHECK_GUIDE)



def _cmd_help(args):
    return run_help(args, _build_parser)


def _cmd_doctor(args):
    """nf doctor：环境自检（实现见 nf_cmds/doctor.py）。"""
    from nf_cmds.doctor import run as _doctor_run
    return _doctor_run(args, NF_CLI_VERSION)


#: 终端检索索引里单行摘要的截断长度（列出命令面时保持一行一条）
_SHELL_SUMMARY_MAX = 100


#: 终端可用的着色模式（与 core/terminal.resolve_color 同词表）
_SHELL_COLOR_MODES = ("auto", "always", "never")




def _shell_command_index() -> list:
    """终端检索索引：从 argparse 面派生（命令真源 = CLI 面，终端不留第二份）。

    每条 = {path, summary, flags}；path 含二级（如 `asset ls`）。check39 断言索引覆盖
    **全部**顶层命令——「最全功能」在终端侧的可机检形态就是「每个命令都能被检索到」。
    """
    global _INDEX_CACHE
    if _INDEX_CACHE is not None:
        return _INDEX_CACHE
    def _flags(parser):
        out = []
        for act in parser._actions:
            if isinstance(act, argparse._SubParsersAction):
                continue
            out += list(act.option_strings)
        return sorted(set(out))

    def _summary(parser):
        text = (parser.description or "").strip()
        if not text:
            return ""
        first = text.splitlines()[0].strip()
        return first if len(first) <= _SHELL_SUMMARY_MAX \
            else first[:_SHELL_SUMMARY_MAX - 1] + "…"

    root = _build_parser()
    out = []
    for act in root._actions:
        if not isinstance(act, argparse._SubParsersAction):
            continue
        for name, sp in act.choices.items():
            out.append({"path": name, "summary": _summary(sp), "flags": _flags(sp)})
            for act2 in sp._actions:
                if isinstance(act2, argparse._SubParsersAction):
                    for n2, sp2 in act2.choices.items():
                        out.append({"path": "%s %s" % (name, n2),
                                    "summary": _summary(sp2), "flags": _flags(sp2)})
    _INDEX_CACHE = sorted(out, key=lambda e: e["path"])
    return _INDEX_CACHE








def _cmd_shell(args) -> int:
    """nf shell（别名 nf terminal）：终端交互入口（实现见 nf_cmds/shell.py）。"""
    from nf_cmds.shell import run as _shell_run
    return _shell_run(args, main=main, collect_cli_tree=_collect_cli_tree,
                      shell_command_index=_shell_command_index)


def _collect_cli_tree():
    """自省 argparse 命令面：命令 × 顶层 flags × 二级子命令（供 completion 生成）。"""
    global _TREE_CACHE
    if _TREE_CACHE is not None:
        return _TREE_CACHE
    root = _build_parser()

    def flags(parser):
        out = []
        for act in parser._actions:
            if isinstance(act, argparse._SubParsersAction):
                continue
            out += list(act.option_strings)
        return sorted(set(out))

    tree = {}
    for act in root._actions:
        if not isinstance(act, argparse._SubParsersAction):
            continue
        for name, sp in act.choices.items():
            nested = {}
            for act2 in sp._actions:
                if isinstance(act2, argparse._SubParsersAction):
                    for n2, sp2 in act2.choices.items():
                        nested[n2] = flags(sp2)
            tree[name] = {"flags": flags(sp), "nested": nested}
    _TREE_CACHE = {
        "commands": sorted(tree),
        "root_flags": flags(root),
        "tree": tree,
    }
    return _TREE_CACHE


def _cmd_completion(args):
    return run_completion(args, _collect_cli_tree)
























def _cmd_verify(args) -> int:
    """nf verify：门禁单进程引擎入口（实现见 nf_cmds/verify.py）。"""
    from nf_cmds.verify import run as _verify_run
    return _verify_run(args)


def _cmd_daemon(args) -> int:
    """nf daemon：执行层常驻守护（实现见 nf_cmds/daemon.py）。"""
    from nf_cmds.daemon import run as _daemon_run
    return _daemon_run(args)








def _rust_engine_argv(args) -> Optional[list]:
    """**已实测为净收益**的面才映射成 nf-rs argv；其余返回 None（走 Python 真源）。

    热进程内对照（2026-10-22，同机同语料，median of 6）：
      - layers 626ms → 229ms（2.73×）→ 接管；
      - stats 11.5ms → 49ms（0.23×）/ receipts 18ms → 30ms（0.60×）/
        conformance 2.0s → 3.2s（0.63×）/ purity 0.73× / schema 0.94× / depth 0.04×
        → **不接管**（Rust 快线仍可由 nf-rs 直接调用，但不得拖慢默认热路径）。
    写面（--write）与人类可读面永远留在 Python 真源。
    """
    if args.cmd == "layers":
        if (getattr(args, "write", False) or not getattr(args, "verify", False)
                or not getattr(args, "json", False)):
            return None
        return ["layers", "--root", ROOT, "--verify", "--json"]
    return None


def _try_rust_face(args) -> Optional[int]:
    """opt-in 只读快线：--engine rust|auto 时把已对账的 JSON 读面交给 nf-rs，失败回退 Python。

    返回 None = 未接管（调用方继续走 Python 真源）；返回 int = 已接管（作为 main 的退出码）。
    只读纪律：只加速 exit==0 且字节已对账的面；快线退出非零（有 issue/异常）时回退 Python
    以保留完整诊断面——绝不静默丢掉诊断。
    """
    engine = str(getattr(args, "engine", None) or os.environ.get("NF_ENGINE", "") or "").strip().lower()
    if engine not in ("rust", "auto"):
        return None
    argv = _rust_engine_argv(args)
    if argv is None:
        return None
    from core import rust_engine as re
    if re.disabled():
        return None
    res = re.run_face(argv, root=ROOT)
    if res is None:
        if engine == "rust":
            print("  [WARN] NF_ENGINE=rust 但 nf-rs 不可用（回退 Python 真源）", file=sys.stderr)
        return None
    code, out = res
    if code != 0:
        if engine == "rust":
            print("  [WARN] nf-rs 退出 %d（回退 Python 真源保留诊断面）" % code, file=sys.stderr)
        return None
    sys.stdout.buffer.write(out)
    sys.stdout.buffer.flush()
    return 0










def _preflight(args):
    """入口闸门：--root / --key-file / --registry / 路径逃逸 / 编码 / Rust 面。"""
    # `--root` 落点闸门（2026-09-30）：读类命令的 `--root` 语义是「对**另一棵树**做同一套
    # 体检」。落点不在场 / 是文件时，此前照样吐**肯定结论**（实测：`nf asset verify --root
    # README.md` → 「✓ 台账闭合」、`nf module verify --root <不存在>` → 「✓ 引用门禁全绿」）——
    # 对**没有载体**的树下结论是错的事实（同 `drill_fidelity`「标准不得无载体」）。
    _root_arg = str(getattr(args, "root", "") or "")
    if _root_arg and _root_pair(args) in _ROOT_READERS:
        _rp = _root_arg if os.path.isabs(_root_arg) else os.path.join(ROOT, _root_arg)
        if not os.path.isdir(_rp):
            return _machine_fail(
                args, "--root 落点不是在场目录：%s（修复指引：`--root` 给**在场目录**"
                      "（相对仓库根或绝对皆可）——本命令按它扫树，落点不在场或为文件时"
                      "没有载体可体检；只想跑本仓库就别传 `--root`，空树体检请先建空目录）"
                      % _root_arg, 2)
    # 同族形状闸门（2026-09-30）：`--registry` / `--key-file` 是**输入文件**，落点不在场
    # 或是目录时，此前照样一路走到读盘 ⇒ 冒成「内部错误 + Errno」（实测 who-refers /
    # impact / library verify / attest 等 7 处）。集中判一次，覆盖全部声明点。
    _key_issue = _file_shape_issue(
        getattr(args, "key_file", ""), "--key-file",
        "修复指引：给 HMAC 密钥**文件**路径（`~` 会展开到家目录；不给就按 digest_only 级走）")
    if _key_issue:
        return _machine_fail(args, _key_issue, 1)
    # `--registry` 有 7 个声明点（market / spec / register / who-refers / impact / related /
    # release）：在**入口**判一次「在场 + 是文件 + 是合法 JSON」，覆盖全部声明点——此前
    # 目录落点报「内部错误 + Errno」，非 JSON 件报「内部错误：Expecting value…」（零指引）。
    _reg_arg = getattr(args, "registry", None)
    _reg_guide = ("修复指引：给 registry.json 的**文件**路径（缺省 = "
                  "desktop/src/core/registry.json；`nf doctor` 可体检）")
    if _reg_arg:
        _reg_issue = _file_shape_issue(_reg_arg, "--registry", _reg_guide)
        if _reg_issue:
            return _machine_fail(args, _reg_issue, 1)
        _reg_path = next((c for c in (_reg_arg, os.path.join(ROOT, _reg_arg))
                          if os.path.isfile(c)), "")
        try:
            import json as _json_probe
            with open(_reg_path, encoding="utf-8") as _fh:
                _json_probe.loads(_fh.read())
        except (OSError, ValueError) as exc:
            return _machine_fail(args, "--registry 不是合法 JSON：%s（%s）"
                                 % (exc, _reg_guide), 1)
    # 收路径旗标的**写法闸门**（2026-10-01）：相对路径的语义是「相对**仓库根**」，而 `..` 写法
    # 会让它静默逃出仓库（实测 `nf interop --kind openapi --out ../x.json` 写到了仓外，且报成
    # 「内部错误」）。口径与 `core.paths.validate_path` 同源：相对写法拒 `..` / 盘符，
    # **绝对路径按原样**（落地到 CI 产物目录、临时导出是设计面，写清楚即可）。
    _escape = _path_writing_issue(args)
    if _escape:
        return _machine_fail(args, _escape, 1)
    # 输入件编码闸门（2026-10-01）：非 UTF-8 文本件此前在 5 条命令上冒「内部错误」或裸解码错。
    _coding = _utf8_text_issue(args)
    if _coding:
        return _machine_fail(args, _coding, 2)
    _rust_rc = _try_rust_face(args)
    if _rust_rc is not None:
        return _rust_rc
    return None


_DISPATCH_CACHE = None


def _dispatch_table():
    """cmd → handler 的可调用表（首次调用时解析，避免前向定义问题）。"""
    global _DISPATCH_CACHE
    if _DISPATCH_CACHE is None:
        from nf_cmds.dispatch import COMMANDS
        _DISPATCH_CACHE = {name: globals()[fn] for name, fn in COMMANDS.items()}
    return _DISPATCH_CACHE


def _run_pipeline(args) -> int:
    """nf run：管线装配 + 质量门 + 导出（main 的兜底分支）。"""
    from core.pipeline import pipe
    from core.pipeline_loader import load_pipeline_file

    # --pipeline 收「管线 md 路径」**或**「在场管线编号」（极端渗透 D8 实证：此前只当路径，
    # 传最自然的编号 `--pipeline P01` 会报「管线解析失败：P01」——P01 明明是合法管线，
    # 属**错误归因**且无修复指引；`nf pipeline dryrun` 的同类参数则明写「管线 md 路径」）。
    import glob as _glob
    _pl_arg = str(args.pipeline)
    _pl_path = _pl_arg if os.path.isfile(_pl_arg) else ""
    _dirs = [os.path.join(ROOT, "03_管线库")] + sorted(
        _glob.glob(os.path.join(ROOT, "community", "*", "pipelines")))
    _avail = [os.path.basename(p)[:-3] for d in _dirs
              for p in sorted(_glob.glob(os.path.join(d, "*.md")))]
    if not _pl_path:
        for _d in _dirs:
            for _p in sorted(_glob.glob(os.path.join(_d, "*.md"))):
                _base = os.path.basename(_p)[:-3]
                if _base.split("_", 1)[0] == _pl_arg or _base == _pl_arg:
                    _pl_path = _p
                    break
            if _pl_path:
                break
    pipeline = load_pipeline_file(_pl_path or _pl_arg)
    if pipeline is None:
        print("✗ 管线解析失败：%s" % _pl_arg, file=sys.stderr)
        print("  修复指引：--pipeline 收**管线 md 路径**（如 03_管线库/P01_标准管线.md）"
              "或在场的管线编号；当前可用：%s"
              % ("（文件在场但解析失败：检查 frontmatter 与结构）" if _pl_path and not _avail
                 else "、".join(_avail) or "（未发现任何管线）"), file=sys.stderr)
        return 1

    store, err = _open_store(args, args.store)   # 落点不可用 ⇒ 干净拒绝（含 OSError：盘/权限）
    if err is not None:
        return err
    if args.seed:
        stats = _seed_store(store)
        print(f"  seed 装载：官方核心 {stats['core']} 件"
              f" + 轻混组合包 {stats['combo']} 件 → {_portable_path(store.home)}")
    else:
        print(f"  store：{_portable_path(store.home)}")

    selected = [m.strip() for m in args.modules.split(",") if m.strip()]
    # B2 变体：--variant-add/--variant-remove 经 apply_variant 变换 selected
    if args.variant_add or args.variant_remove:
        from core.variants import apply_variant
        v = apply_variant(selected, {
            "add": [x.strip() for x in args.variant_add.split(",") if x.strip()],
            "remove": [x.strip() for x in args.variant_remove.split(",") if x.strip()],
        })
        selected = v.selected
        print(f"  [变体] selected {args.modules.split(',')} → {selected}"
              + (f"（移除 {args.variant_remove}）" if args.variant_remove else ""))
    dest = args.dest
    r = pipe(store, pipeline, selected,
             include_references=not args.no_include_refs,
             fmt=args.fmt, dest_dir=dest,
             fail_on_gate=not args.force_export,
             doc_semantics=args.doc_semantics)

    print(f"\n== 质量门 ==\n  PASS {r.gate.n_pass} · WARN {r.gate.n_warn}"
          f" · FAIL {r.gate.n_fail}" + ("（可产出）" if r.ok else "（存在 FAIL）"))
    # B1 可解释化：逐条含修复建议（quality_gate 报告样式，warn/fail 都 actionable）
    for issue in r.gate.issues:
        if issue.level in ("fail", "warn"):
            print(f"  [{issue.level.upper()}] {issue.message}")
            if issue.suggestion:
                print(f"      建议：{issue.suggestion}")
    for w in r.warnings:
        print(f"  [INFO] {w}")
    if r.export is not None:
        print("\n== 导出 ==")
        if r.export.files:
            for f in r.export.files:
                print(f"  ✓ {f}")
        if r.export.warnings:
            for w in r.export.warnings:
                print(f"  [导出] {w}")
    if not r.ok:
        print("\n✗ 质量门 FAIL（可信任度不变量）"
              + ("；已按 --force-export 导出诊断产物" if args.force_export
                 else "——修复装配后重跑或加 --force-export 看坏产物"), file=sys.stderr)
        return 1
    print("\n★ 全链管道 PASSED ✓")
    return 0

def main(argv=None) -> int:
    # 效率：`--version` 是最常被调用的探测命令，而构建 argparse 面 ≈100 ms——
    # 它不需要命令面，直接短路（输出与 argparse 的 version 动作逐字一致）。
    if argv is not None and list(argv) == ["--version"]:
        print("nf %s" % NF_CLI_VERSION)
        return 0
    args = _build_parser().parse_args(argv)
    if args.cmd is None:
        _build_parser().print_help()
        return 0
    rc = _preflight(args)
    if rc is not None:
        return rc
    if args.cmd == "design":
        if args.design_cmd == "audit":
            # 注意：这里必须指向 **design audit** 实现——此前与 `nf audit`
            # 的同名函数冲突（flake8 F811），`nf design audit ls` 实际打到 nf audit 那套
            # （实测输出「== nf audit（26 件）==」），已重命名为 _cmd_design_audit 修正。
            return _cmd_design_audit(args)
        return _cmd_design(args)
    _handler = _dispatch_table().get(args.cmd)
    if _handler is not None:
        return _handler(args)
    if args.cmd == "run":
        return _run_pipeline(args)
    _build_parser().print_help()
    return 2






def _cmd_cli(args):
    return run_cli(args, _build_parser)


def guarded_main(argv=None) -> int:
    """`main()` 的异常兜底 —— **CLI 与常驻守护共用的同一条错误面**。

    为什么单独抽出来（2026-10-10 全仓审计 X0，P0）：守护 `core.daemon.execute()` 此前直接调
    `main()`、只兜 `SystemExit`，于是任何未捕获异常都穿透守护循环、**杀死常驻进程**——实测
    `nf receipts` 在 `protocol/RECEIPTS.json` 被截断时必抛 `json.JSONDecodeError`，18/18
    条 protocol JSON 都如此；客户端拿 rc=1 + 零输出。兜底是仓库既有的正确实现，只是**写在了
    `cli()` 里而没有到守护那条路径上**。抽到这里 ⇒ 同一语义只有一份实现，两条执行路径
    （终端直跑 / 守护内跑）的 (退出码, stderr 文本) 逐字一致。

    纪律：只兜 `Exception`（`SystemExit` 照旧上抛，由调用方按 argparse 语义归一；`KeyboardInterrupt`
    与 `BrokenPipeError` 各自归一为 130 / 0）；`NF_DEBUG` 在场时透出原始堆栈（排障用）。
    """
    try:
        code = main(argv)
    except BrokenPipeError:
        try:
            devnull = os.open(os.devnull, os.O_WRONLY)
            os.dup2(devnull, sys.stdout.fileno())
        except Exception:  # nosec B110 —— 尽力而为：终端重定向失败即沿用默认（见 AUD-0016）
            pass
        code = 0
    except KeyboardInterrupt:
        code = 130
    except Exception as exc:
        if os.environ.get("NF_DEBUG"):
            raise
        print("  ✗ 内部错误：%s（重跑 NF_DEBUG=1 nf ... 看堆栈）" % exc,
              file=sys.stderr)
        code = 1
    return code if isinstance(code, int) else 0


def cli(argv=None) -> int:
    """CLI 运行时封装：SIGPIPE 语义 + 断管/中断兜底 + 退出码归一。

    - POSIX：恢复 SIGPIPE 默认动作（`nf ... | head` 静默截断，无 traceback）；
    - 断管兜底（Windows 无 SIGPIPE 场景）；
    - Ctrl-C → 130；返回非 int（如 None）按 0 处理。
    - 未预期异常：默认一句错误 + 提示（NF_DEBUG=1 时透出堆栈），不裸刷 traceback。

    兜底实现只在 `guarded_main()`（上）一处：本函数只做「进程级」准备（SIGPIPE 动作），
    其余转交共用实现——**别在这里再写一份 try/except**（两处实现就会分叉，历史教训见审计 §0.3）。
    """
    try:
        import signal
        # Windows 无 SIGPIPE：取不到即跳过（原写法在该平台靠 except 兜住，行为等价）。
        _sigpipe = getattr(signal, "SIGPIPE", None)
        if _sigpipe is not None:
            signal.signal(_sigpipe, signal.SIG_DFL)
    except Exception:  # 尽力而为：跳过不可读/不可解析项（该类缺口由对应门禁与 AUD-0016 静默跳过清单另行报出）  # nosec B110 —— 尽力而为：跳过不可读/不可解析项（对应门禁另报；见 AUD-0016）
        pass
    return guarded_main(argv)


if __name__ == "__main__":
    # 必须**把 argv 显式递进去**：`main()` 的 `--version` 短路判据是「argv 就是 ['--version']」，
    # 而 `cli()` 原样转 `main(None)` 时该判据永远为假 ⇒ 为打印一行版本号白建整个 argparse 命令面
    # （实测 **99 ms**，65 条子命令）。传 argv 与 `parse_args(None)` 取的是同一份 sys.argv[1:]。
    sys.exit(cli(sys.argv[1:]))
