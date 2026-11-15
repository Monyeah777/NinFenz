"""nf_app 命令行入口：按用户流组织子命令；全部支持 --json（单行 JSON 信封）。

用法（仓库根，app/cli 在 PYTHONPATH）：
    set PYTHONPATH=app/cli   # Windows
    export PYTHONPATH=app/cli
    python -m nf_app --help
"""

from __future__ import annotations

import argparse
import sys

from . import __version__
from .canonical import canonical_text
from .commands import author_cmd, ccos_cmd, flow_cmd, import_cmd, pack_cmd, project_cmd, selftest_cmd, share_cmd
from .commands.common import STATE_ORDER, json_pretty
from .errors import AppError, ok_envelope
from .io_utils import configure_stdio


class NfParser(argparse.ArgumentParser):
    """用法错误统一为 NF-E-003（exit 2），不再让 argparse 直接 sys.exit。"""

    def error(self, message: str):  # type: ignore[override]
        raise AppError("NF-E-003", message=f"用法错误: {message}", fix="运行 nf-app --help 查看用法")


def _add_json_flag(parser: argparse.ArgumentParser) -> None:
    # default=SUPPRESS：子命令未显式给 --json 时不覆盖父级（根）的 --json 取值
    parser.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help=argparse.SUPPRESS)


def build_parser() -> argparse.ArgumentParser:
    parser = NfParser(prog="nf-app", description="NF APP 控制面（Python nf_app）；内部统一调 nf-app-core")
    parser.add_argument("--json", action="store_true", default=False, help="输出单行 JSON 信封 {ok,exit,result,error}")
    parser.add_argument("--version", action="version", version=f"nf-app {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, parser_class=NfParser)

    def leaf(parent, name: str, help_text: str, func):
        sp = parent.add_parser(name, help=help_text, description=help_text)
        _add_json_flag(sp)
        sp.set_defaults(func=func)
        return sp

    # ---------------------------------------------------------------- import / map
    p = leaf(sub, "import", "导入文件或 stdin（剪贴板文本）→ nf-import/1", import_cmd.cmd_import)
    p.add_argument("file", help="输入文件路径；- 表示 stdin")
    p.add_argument("--name", help="来源名（默认文件名；stdin 默认 clipboard.md）")
    p.add_argument("--source-kind", choices=import_cmd.SOURCE_KINDS, help="来源类型（默认 file / clipboard）")
    p.add_argument("--out", help="输出 *.nfimport.json")

    p = leaf(sub, "map", "补映射建议（供映射向导）", import_cmd.cmd_map)
    p.add_argument("import_path", metavar="import.json")
    p.add_argument("--spec", help="nf-md-spec/1（补槽位候选）")
    p.add_argument("--out")

    # ---------------------------------------------------------------- project
    project = sub.add_parser("project", help="项目引用 + 状态机（draft→authoring→assembled→validated→exported→reviewed）")
    _add_json_flag(project)
    project_sub = project.add_subparsers(dest="project_cmd", required=True, parser_class=NfParser)
    p = leaf(project_sub, "init", "初始化 nf-project/1（只存引用）", project_cmd.cmd_project_init)
    p.add_argument("project_file", metavar="project.nfproject.json")
    p.add_argument("--id", help="项目 id（小写字母开头；默认取文件名）")
    p.add_argument("--title")
    p.add_argument("--base-pack", help="基础 pack 根目录或 nf-pack.json")
    p.add_argument("--overlay", help="nf-overlay/1")
    p.add_argument("--protocol", help="nf-protocol-pack/1")
    p.add_argument("--graph", help="nf-pipeline-graph/1")
    p.add_argument("--spec", help="nf-md-spec/1")
    p.add_argument("--force", action="store_true", help="覆盖已存在的项目文件 / 刷新引用（保留状态与 history）")
    p.add_argument("--at", help="history 时间（确定性测试用）")
    p = leaf(project_sub, "status", "查看项目状态与校验报告", project_cmd.cmd_project_status)
    p.add_argument("project_file", metavar="project.nfproject.json")
    p = leaf(project_sub, "set", "改项目状态（回退必须 --force 且写 history）", project_cmd.cmd_project_set)
    p.add_argument("project_file", metavar="project.nfproject.json")
    p.add_argument("--status", required=True, choices=STATE_ORDER)
    p.add_argument("--force", action="store_true", help="允许状态回退（写 history）")
    p.add_argument("--at", help="history 时间（确定性测试用；默认当前 UTC）")

    # ---------------------------------------------------------------- author
    author = sub.add_parser("author", help="受控编辑作者对象（编辑后跑核心校验，失败不落盘）")
    _add_json_flag(author)
    author_sub = author.add_subparsers(dest="author_cmd", required=True, parser_class=NfParser)
    p = leaf(author_sub, "protocol", "协议包：条款开关 / 字段默认值", author_cmd.cmd_author_protocol)
    p.add_argument("file", help="nf-protocol-pack/1")
    p.add_argument("--clause", help="条款 id（C-###）")
    toggle = p.add_mutually_exclusive_group()
    toggle.add_argument("--enable", action="store_true", help="启用条款")
    toggle.add_argument("--disable", action="store_true", help="停用条款")
    p.add_argument("--field", help="字段 id（F-###）")
    p.add_argument("--default", help="字段默认值（JSON 字面量；解析失败按字符串）")
    required_group = p.add_mutually_exclusive_group()
    required_group.add_argument("--required", dest="required", action="store_const", const=True, default=None)
    required_group.add_argument("--optional", dest="required", action="store_const", const=False)
    p.add_argument("--out", help="输出文件（默认原地写 canonical JSON）")

    p = leaf(author_sub, "graph", "管线图：节点/边/权重增删改（拓扑重排）", author_cmd.cmd_author_graph)
    p.add_argument("file", help="nf-pipeline-graph/1")
    p.add_argument("--mode", choices=["simple", "pro", "expert"])
    p.add_argument("--add-node", action="append", metavar="N##:kind:标题[:module_ref]")
    p.add_argument("--del-node", action="append", metavar="N##")
    p.add_argument("--add-edge", action="append", metavar="E##:from:to:from_port:to_port[:type]")
    p.add_argument("--del-edge", action="append", metavar="E##")
    p.add_argument("--weight", action="append", metavar="N##=0..100")
    p.add_argument("--del-weight", action="append", metavar="N##")
    p.add_argument("--required-stage", action="append", metavar="N##")
    p.add_argument("--out")

    p = leaf(author_sub, "spec", "md spec：槽位约束/必填/预算", author_cmd.cmd_author_spec)
    p.add_argument("file", help="nf-md-spec/1")
    p.add_argument("--slot", metavar="SLT-##")
    required_group = p.add_mutually_exclusive_group()
    required_group.add_argument("--required", dest="required", action="store_const", const=True, default=None)
    required_group.add_argument("--optional", dest="required", action="store_const", const=False)
    p.add_argument("--min-chars", type=int)
    p.add_argument("--max-chars", type=int)
    p.add_argument("--max-tokens", type=int)
    p.add_argument("--add-constraint", action="append", metavar="op[:value]")
    p.add_argument("--remove-constraint", action="append", metavar="op")
    p.add_argument("--out")

    # ---------------------------------------------------------------- assemble / validate / export
    p = leaf(sub, "assemble", "编译 plan 并装配（写 result.md + result.meta.json）", flow_cmd.cmd_assemble)
    p.add_argument("project", metavar="project.nfproject.json")
    p.add_argument("--inputs", help="槽位取值 JSON：{slot: 字符串}")
    p.add_argument("--out", help="输出目录（默认项目目录/out）")
    p.add_argument("--stage", metavar="N##", help="只渲染该阶段（OPEN：核心按 step stage 过滤）")
    p.add_argument("--block", metavar="SEC-##", help="块级编辑（OPEN：核心返回该节片段）")
    p.add_argument("--at", help="history 时间（确定性测试用）")

    p = leaf(sub, "validate", "校验 L0/L1（写 nf-validate-report/1）", flow_cmd.cmd_validate)
    p.add_argument("project", metavar="project.nfproject.json")
    p.add_argument("--level", required=True, choices=flow_cmd.VALID_LEVELS)
    p.add_argument("--markdown", help="待校验 Markdown（默认项目 out/result.md）")
    p.add_argument("--out", help="报告输出路径（默认项目目录 report-<level>.nfreport.json）")
    p.add_argument("--record", action="store_true", help="通过时把项目状态推进到 validated 并写 history")

    p = leaf(sub, "export", "导出 md/zip/json（docx/pdf → NF-EXP-004 exit 4，OPEN）", flow_cmd.cmd_export)
    p.add_argument("project", metavar="project.nfproject.json")
    p.add_argument("--format", required=True, choices=flow_cmd.EXPORT_FORMATS)
    p.add_argument("--out", help="导出目录（默认项目目录/export）")
    p.add_argument("--markdown", help="待导出 Markdown（默认项目 out/result.md）")

    # ---------------------------------------------------------------- share
    share = sub.add_parser("share", help="生成脱敏分享文本/文件（绝对路径/用户名/邮箱/密钥全遮）")
    _add_json_flag(share)
    share_sub = share.add_subparsers(dest="share_cmd", required=True, parser_class=NfParser)
    for kind, help_text in (
        ("prompt", "分享给执行面的任务提示词"),
        ("markdown", "分享用 Markdown（含结果时脱敏后内嵌）"),
        ("json", "分享用 JSON 包"),
    ):
        p = leaf(share_sub, kind, help_text, share_cmd.cmd_share)
        p.set_defaults(share_kind=kind)
        p.add_argument("--project", help="project.nfproject.json")
        p.add_argument("--result", help="result.md（脱敏后内嵌）")
        p.add_argument("--text", help="补充说明文本")
        p.add_argument("--out", help="输出文件（默认 stdout）")

    # ---------------------------------------------------------------- pack
    pack = sub.add_parser("pack", help="Pack 更新：diff → 冲突裁决 → 应用/备份/回滚（base 只读）")
    _add_json_flag(pack)
    pack_sub = pack.add_subparsers(dest="pack_cmd", required=True, parser_class=NfParser)
    p = leaf(pack_sub, "update", "生成 nf-pack-update/1（base vs new）", pack_cmd.cmd_pack_update)
    p.add_argument("--base", required=True, help="旧 pack 根目录")
    p.add_argument("--new", required=True, help="新 pack 根目录")
    p.add_argument("--projects", action="append", metavar="project.json", help="受影响项目（impact.projects）")
    p.add_argument("--out", help="输出 *.nfupdate.json（默认 update.nfupdate.json）")
    p = leaf(pack_sub, "apply", "应用更新（冲突未裁决 → NF-PCK-006 exit 1）", pack_cmd.cmd_pack_apply)
    p.add_argument("update", metavar="*.nfupdate.json")
    p.add_argument("--base", required=True)
    p.add_argument("--new", required=True)
    p.add_argument("--out", required=True, help="应用目标目录")
    p.add_argument("--overlay", help="nf-overlay/1")
    p.add_argument("--decisions", help="冲突裁决 JSON：{CFL-01: keep_mine|take_new|defer}")
    p.add_argument("--backup", help="应用前快照到该目录（本地备份指针）")
    p = leaf(pack_sub, "rollback", "从本地备份回滚（摘要不符 → NF-PCK-007 exit 2）", pack_cmd.cmd_pack_rollback)
    p.add_argument("--backup", required=True, help="备份目录（含 nf-backup.json）")
    p.add_argument("--target", required=True, help="回滚目标目录（必须与备份记录一致）")

    # ---------------------------------------------------------------- ccos
    ccos = sub.add_parser("ccos", help="CCOS 交接：task / import-result / review（人审恒必需）")
    _add_json_flag(ccos)
    ccos_sub = ccos.add_subparsers(dest="ccos_cmd", required=True, parser_class=NfParser)
    p = leaf(ccos_sub, "task", "生成 ccos-task/1（项目必须 validated）", ccos_cmd.cmd_ccos_task)
    p.add_argument("project", metavar="project.nfproject.json")
    p.add_argument("--task-id", required=True, help="调用方生成（确定性；小写字母数字-，长度>=8）")
    p.add_argument("--created-at", help="创建时间（确定性测试用；默认当前 UTC）")
    p.add_argument("--max-tokens", type=int, default=1000)
    p.add_argument("--max-chars", type=int, default=4000)
    p.add_argument("--max-seconds", type=int, default=600)
    p.add_argument("--variables", help="变量 JSON 文件")
    p.add_argument("--out", help="输出 *.ccos-task.json")
    p = leaf(ccos_sub, "import-result", "导入 CCOS 回传结果（回钉 task_digest）", ccos_cmd.cmd_ccos_import_result)
    p.add_argument("--task", required=True)
    p.add_argument("--result", required=True)
    p.add_argument("--project", help="更新项目 review.state=pending")
    p.add_argument("--out", help="结果落盘路径")
    p = leaf(ccos_sub, "review", "人审状态机：approve/reject（必须 reviewer + note）", ccos_cmd.cmd_ccos_review)
    p.add_argument("result", metavar="*.ccos-result.json")
    decision = p.add_mutually_exclusive_group()
    decision.add_argument("--approve", action="store_true")
    decision.add_argument("--reject", action="store_true")
    p.add_argument("--reviewer")
    p.add_argument("--note")
    p.add_argument("--project")
    p.add_argument("--task", help="给定时校验 task_digest 回钉")
    p.add_argument("--force", action="store_true", help="已审过再改判")

    # ---------------------------------------------------------------- selftest
    leaf(sub, "selftest", "核心 op 冒烟（输出 nf-app-selftest/1；exit 0/1）", selftest_cmd.cmd_selftest)

    return parser


def _print_json(obj) -> None:
    sys.stdout.write(canonical_text(obj) + "\n")
    sys.stdout.flush()


def _emit_error(exc: AppError, json_mode: bool) -> int:
    if json_mode:
        _print_json(exc.to_envelope())
    else:
        sys.stderr.write(f"错误 {exc.code}: {exc.message}\n")
        if exc.fix:
            sys.stderr.write(f"修复: {exc.fix}\n")
        if exc.path:
            sys.stderr.write(f"位置: {exc.path}\n")
        if exc.result is not None:
            sys.stdout.write(json_pretty(exc.result) + "\n")
    return int(exc.exit or 0)


def main(argv: list[str] | None = None) -> int:
    configure_stdio()
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    try:
        args = parser.parse_args(raw_argv)
    except AppError as exc:
        return _emit_error(exc, "--json" in raw_argv)
    try:
        outcome = args.func(args)
    except AppError as exc:
        return _emit_error(exc, bool(args.json))
    envelope = ok_envelope(outcome.result, int(outcome.exit or 0))
    if args.json:
        _print_json(envelope)
    elif outcome.human:
        sys.stdout.write(outcome.human + "\n")
    return int(outcome.exit or 0)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
