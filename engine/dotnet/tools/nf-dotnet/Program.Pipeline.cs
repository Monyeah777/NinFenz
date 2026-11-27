using System.Text.Json;
using Nf.Engine;

internal static partial class Program
{
    private static int GovernanceCommand(string family)
    {
        // 治理族三件（handover / postmortem / audit）的 `verify` 与 `ls` 面；`check <path>` 未移植。
        var sub = positional.Count >= 2 ? positional[1] : "ls";
        // 同 Python：`--json` 挂在**子命令**上，缺子命令时 `nf handover --json` 是用法错误（exit 2），
        // 不是"默认 ls + json"。此处不宽容，避免与参考实现的调用面不一致。
        if (json && positional.Count < 2)
            return Fail($"{family} 需要子命令（ls / verify）才能带 --json");
        var (issues, warns, stats, glob, listKeys, kind) = family switch
        {
            "handover" => Wrap(Handover.Scan(root!), "handovers/HO-*.md",
                new[] { "id", "title", "status", "date", "from", "to" }, "handover"),
            "postmortem" => Wrap(Postmortem.Scan(root!), "postmortems/PO-*.md",
                new[] { "id", "title", "status", "date", "trigger" }, "postmortem"),
            _ => Wrap(Audit.Scan(root!), "results/audit/*.md",
                new[] { "id", "date", "scope", "verdict", "auditor" }, "audit"),
        };

        if (sub == "verify")
        {
            if (json)
            {
                Console.WriteLine(JsonFor(new Dictionary<string, object?>
                {
                    ["issues"] = issues.Cast<object?>().ToList(),
                    ["warns"] = warns.Cast<object?>().ToList(),
                    ["stats"] = stats,
                }));
            }
            else
            {
                Console.WriteLine(family switch
                {
                    "handover" => $"== nf handover verify（{stats.GetValueOrDefault("handovers")} 件 · " +
                                  $"未决 {stats.GetValueOrDefault("pending")} 条）==",
                    "postmortem" => $"== nf postmortem verify（{stats.GetValueOrDefault("postmortems")} 件 · " +
                                    $"行动项 {stats.GetValueOrDefault("actions")} 条）==",
                    _ => $"== nf audit verify（{stats.GetValueOrDefault("audits")} 件 · " +
                         $"带审计头 {stats.GetValueOrDefault("with_header")} · legacy {stats.GetValueOrDefault("legacy")}）==",
                });
                foreach (var warn in warns) Console.WriteLine("  [WARN] " + warn);
                foreach (var issue in issues) Console.Error.WriteLine("  [FAIL] " + issue);
                if (issues.Count == 0)
                {
                    Console.WriteLine(family switch
                    {
                        "handover" => "  ✓ 声明与全部交接件一致",
                        "postmortem" => "  ✓ 声明与全部复盘件一致",
                        _ => "  ✓ 声明与全部审计件一致（legacy 只挂账不判死）",
                    });
                }
            }
            return issues.Count == 0 ? 0 : 1;
        }
        if (sub == "check")
        {
            if (positional.Count < 3) return Fail($"{family} check 需要一个件路径");
            var path = positional[2];
            var (docIssues, docStats) = family switch
            {
                "handover" => Handover.CheckDoc(root!, path),
                "postmortem" => Postmortem.CheckDoc(root!, path),
                _ => Audit.CheckDoc(root!, path),
            };
            if (json)
            {
                Console.WriteLine(JsonFor(new Dictionary<string, object?>
                {
                    ["path"] = path,
                    ["issues"] = docIssues.Cast<object?>().ToList(),
                    ["stats"] = docStats,
                }));
            }
            else
            {
                var header = family switch
                {
                    "handover" => $"== nf handover check {path}（未决 {docStats.GetValueOrDefault("pending")} 条）==",
                    "postmortem" => $"== nf postmortem check {path}（行动项 {docStats.GetValueOrDefault("actions")} 条）==",
                    _ => $"== nf audit check {path}" +
                         $"{(docStats.GetValueOrDefault("legacy") is true ? "（legacy：无审计头，按 WARN 挂账）" : "")} ==",
                };
                Console.WriteLine(header);
                foreach (var issue in docIssues) Console.Error.WriteLine("  [FAIL] " + issue);
                if (docIssues.Count == 0)
                {
                    if (family == "handover")
                        Console.WriteLine("  ✓ 五段齐 · 未决非空且每条带判据 · refs 可解析");
                    else if (family == "postmortem")
                        Console.WriteLine("  ✓ 四段齐 · 无指责 · 根因指向机制 · 行动项带负责人与判据");
                    else if (docStats.GetValueOrDefault("legacy") is not true)
                        Console.WriteLine("  ✓ 必填齐 · verdict 在册 · 结论绑定对象 digest · 签收双要素");
                }
            }
            return docIssues.Count == 0 ? 0 : 1;
        }
        if (sub != "ls") return Fail($"{family} 子命令只移植了 `ls` / `verify` / `check <path>`");

        var rows = DocContractIo.Entries(root!, glob);
        if (json)
        {
            Console.WriteLine(JsonFor(rows.Select(r => (object?)listKeys.ToDictionary(
                k => k, k => r.Fm.TryGetValue(k, out var v) ? v : null, StringComparer.Ordinal)).ToList()));
            return 0;
        }
        Console.WriteLine($"== nf {family}（{rows.Count} 件）==");
        foreach (var row in rows)
        {
            if (kind == "audit")
            {
                Console.WriteLine($"  {DocContractIo.PyOr(row.Fm, "id", "(legacy)"),-11} " +
                                  $"{DocContractIo.PyOr(row.Fm, "verdict", "-"),-6} " +
                                  $"{DocContractIo.PyOr(row.Fm, "date", "-"),-11} {row.File}");
            }
            else if (kind == "handover")
            {
                Console.WriteLine($"  {DocContractIo.PyValue(row.Fm, "id"),-9} {DocContractIo.PyValue(row.Fm, "status"),-7} " +
                                  $"{DocContractIo.PyValue(row.Fm, "date"),-10} {DocContractIo.PyValue(row.Fm, "from")} → " +
                                  $"{DocContractIo.PyValue(row.Fm, "to")}");
            }
            else
            {
                Console.WriteLine($"  {DocContractIo.PyValue(row.Fm, "id"),-9} {DocContractIo.PyValue(row.Fm, "status"),-7} " +
                                  $"{DocContractIo.PyValue(row.Fm, "date"),-10} {DocContractIo.PyValue(row.Fm, "title")}");
            }
        }
        return 0;
    }

    private static int PipelineCommand()
    {
        // 只移植了 `nf pipeline dryrun`（全仓 `--all` 与单条管线两个面）。
        if (positional.Count >= 2 && positional[1] == "dryrun")
        {
            if (pipelineAll)
            {
                var (issues, tot) = PipelineDryrun.Sweep(root!);
                if (json)
                {
                    Console.WriteLine(JsonFor(new Dictionary<string, object?>
                    {
                        ["issues"] = issues.Cast<object?>().ToList(),
                        ["stats"] = tot,
                    }));
                }
                else
                {
                    Console.WriteLine("== nf pipeline dryrun --all ==");
                    Console.WriteLine($"  管线 {tot["pipelines"]} · 模块 {tot["modules"]} · " +
                                      $"官方核心基座 {tot["core_base"]} · advisory {tot["notes"]}");
                    var buckets = tot.GetValueOrDefault("advisory_buckets") as Dictionary<string, object?>
                                  ?? new Dictionary<string, object?>(StringComparer.Ordinal);
                    foreach (var (category, count) in buckets.OrderBy(kv => kv.Key, StringComparer.Ordinal))
                        Console.WriteLine($"    · {category,-14} {count}");
                    foreach (var issue in issues) Console.Error.WriteLine("  [FAIL] " + issue);
                    if (issues.Count == 0)
                        Console.WriteLine("  ✓ 全仓管线零 hard 缺陷（advisory 为同层序/跨包事件，不作判死）");
                }
                return issues.Count == 0 ? 0 : 1;
            }
            if (pipelineName is null) return Fail("pipeline dryrun 需要管线路径（或用 --all）");
            PipelineDryrun.GraphResult graph;
            try
            {
                graph = PipelineDryrun.Graph(pipelineName, root!);
            }
            catch (Exception exc)
            {
                Console.Error.WriteLine("  ✗ " + exc.Message);
                return 1;
            }
            if (json)
            {
                Console.WriteLine(JsonFor(new Dictionary<string, object?>
                {
                    ["schema"] = "nf-graphspec/1",
                    ["pipeline"] = new Dictionary<string, object?>
                    {
                        ["id"] = graph.PipelineId, ["name"] = graph.PipelineName,
                        ["structure_type"] = graph.StructureType,
                        ["path"] = pipelineName.Replace('\\', '/'),
                    },
                    ["steps"] = graph.Steps.Select(s => (object?)new Dictionary<string, object?>
                    {
                        ["index"] = s.Index, ["layer"] = s.Layer, ["layer_name"] = s.LayerName,
                        ["optional"] = s.Optional,
                        ["modules"] = s.Modules.Select(m => (object?)new Dictionary<string, object?>
                        {
                            ["id"] = m.Id, ["path"] = m.Path, ["has_contract"] = m.HasContract,
                        }).ToList(),
                        ["missing"] = s.Missing.Cast<object?>().ToList(),
                    }).ToList(),
                    ["edges"] = graph.Edges.Select(e => (object?)new Dictionary<string, object?>
                    {
                        ["from"] = e.From, ["to"] = e.To, ["kind"] = e.Kind,
                    }).ToList(),
                    ["tokens"] = graph.Tokens.Cast<object?>().ToList(),
                    ["events"] = new Dictionary<string, object?>
                    {
                        ["published"] = graph.Published.Cast<object?>().ToList(),
                    },
                    ["issues"] = graph.Issues.Cast<object?>().ToList(),
                    ["notes"] = graph.Notes.Select(n => (object?)new Dictionary<string, object?>
                    {
                        ["category"] = n.Category, ["detail"] = n.Detail,
                    }).ToList(),
                    ["stats"] = graph.Stats,
                }));
                return graph.Issues.Count == 0 ? 0 : 1;
            }
            Console.WriteLine($"== nf pipeline dryrun：{graph.PipelineId}（{graph.PipelineName}）==");
            Console.WriteLine($"  层 {graph.Stats["layers"]} · 模块 {graph.Stats["modules"]} · " +
                              $"token {graph.Stats["tokens"]} · 事件 {graph.Stats["events_published"]} · " +
                              $"hard {graph.Stats["issues"]} · advisory {graph.Stats["notes"]}");
            foreach (var step in graph.Steps)
            {
                var mods = step.Modules.Count == 0 ? "（空）" : string.Join("、", step.Modules.Select(m => m.Id));
                var layerName = step.LayerName.Length <= 12 ? step.LayerName : step.LayerName[..12];
                Console.WriteLine($"  {step.Index,2}. {step.Layer,-4} {layerName,-14} {mods}");
            }
            foreach (var issue in graph.Issues) Console.Error.WriteLine("  [FAIL] " + issue);
            foreach (var note in graph.Notes.Take(6)) Console.WriteLine("  [note] " + note.Detail);
            return graph.Issues.Count == 0 ? 0 : 1;
        }
        return Fail("pipeline 子命令只移植了 `dryrun`（--all / <管线路径>）；其余（new/dryrun --write-advisory）未移植");
    }

    private static int ModuleCommand()
    {
        // 只移植了 `nf module types --backlog`（类型积压台账）；默认面（io_types）未移植——明确报错。
        if (positional.Count >= 2 && positional[1] == "types" && backlogOnly)
        {
            var (issues, stats) = TypeBacklog.VerifyBacklog(root!);
            Console.WriteLine("== nf module types --backlog ==");
            Console.WriteLine($"  不可推断的 untyped：{stats["untyped"]} 项");
            foreach (var issue in issues) Console.Error.WriteLine("  [FAIL] " + issue);
            return issues.Count == 0 ? 0 : 1;
        }
        if (positional.Count >= 2 && positional[1] == "types")
        {
            // `nf module types`（I/O 类型面）：可证不匹配/越词表 → FAIL 走 stderr；未收窄/L0 只 WARN。
            var (issues, warns, stats) = IoTypes.Scan(root!);
            var coverage = IoTypes.Coverage(root!);
            if (json)
            {
                Console.WriteLine(JsonFor(new Dictionary<string, object?>
                {
                    ["issues"] = issues.Cast<object?>().ToList(),
                    ["warns"] = warns.Cast<object?>().ToList(),
                    ["stats"] = coverage,
                }));
            }
            else
            {
                Console.WriteLine("== nf module types（I/O 类型面）==");
                var total = (int)(coverage["typed_fields"] ?? 0) + (int)(coverage["untyped_fields"] ?? 0);
                var percent = ((double)(coverage["coverage"] ?? 0.0))
                    .ToString("F1", System.Globalization.CultureInfo.InvariantCulture);
                Console.WriteLine($"  机读契约模块 {coverage["modules_with_contract"]} · L0 未承载 {coverage["l0_modules"]} · " +
                                  $"已标注 {coverage["typed_fields"]}/{total} 字段（{percent}%）");
                foreach (var issue in issues) Console.Error.WriteLine("  [FAIL] " + issue);
                foreach (var warn in warns) Console.WriteLine("  [WARN] " + warn);
                if (issues.Count == 0) Console.WriteLine("  ✓ 无可证类型不匹配（untyped 为如实缺口，不判死）");
            }
            return issues.Count == 0 ? 0 : 1;
        }
        if (positional.Count >= 2 && positional[1] == "signature")
        {
            // `nf module signature`（边界冻结）：漂移 → FAIL 走 stderr；新增/撤签 → WARN。
            var (issues, warns, stats) = ModuleSignature.Verify(root!);
            if (json)
            {
                Console.WriteLine(JsonFor(new Dictionary<string, object?>
                {
                    ["issues"] = issues.Cast<object?>().ToList(),
                    ["warns"] = warns.Cast<object?>().ToList(),
                    ["stats"] = stats,
                }));
            }
            else
            {
                Console.WriteLine("== nf module signature（边界冻结）==");
                Console.WriteLine($"  模块 {stats.GetValueOrDefault("modules")} · 已签 {stats.GetValueOrDefault("signed")}");
                foreach (var issue in issues) Console.Error.WriteLine("  [FAIL] " + issue);
                foreach (var warn in warns) Console.WriteLine("  [WARN] " + warn);
                if (issues.Count == 0) Console.WriteLine("  ✓ 全部模块边界与基线一致（改边界须显式重签）");
            }
            return issues.Count == 0 ? 0 : 1;
        }
        if (positional.Count >= 2 && positional[1] == "verify")
        {
            var (issues, stats) = ModuleLifecycle.VerifyModules(root!);
            Console.WriteLine("== nf module verify ==");
            Console.WriteLine($"  统计：模块 {PyS(stats["modules"])} / active {PyS(stats["active"])} / "
                              + $"deprecated {PyS(stats["deprecated"])} / retired {PyS(stats["retired"])}");
            if (issues.Count > 0)
            {
                foreach (var issue in issues) Console.Error.WriteLine($"  [FAIL] {issue}");
                return 1;
            }
            Console.WriteLine("  ✓ 无 deprecated/retired 模块被引用（引用门禁全绿）");
            return 0;
        }
        if (positional.Count >= 2 && positional[1] == "ls")
        {
            var rows = ModuleLifecycle.Rows(root!, assetStatus);
            if (json)
            {
                Console.WriteLine(PythonJson.Indented(new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["kind"] = "module-ls",
                    ["status"] = assetStatus.Length > 0 ? assetStatus : null,
                    ["rows"] = rows.OrderBy(r => r.Status, StringComparer.Ordinal)
                        .ThenBy(r => r.File, StringComparer.Ordinal)
                        .Select(r => (object?)new Dictionary<string, object?>(StringComparer.Ordinal)
                        {
                            ["status"] = r.Status, ["file"] = r.File,
                        }).ToList(),
                }));
                return 0;
            }
            Console.WriteLine("== nf module ls ==");
            foreach (var (status, file) in rows)
                Console.WriteLine("  " + PadCp(status, 10) + " " + file);
            Console.WriteLine($"  合计 {rows.Count}");
            return 0;
        }
        if (positional.Count >= 2 && positional[1] == "status")
        {
            if (positional.Count < 3) return Usage("module status 需要一个模块 md 路径");
            var fpath = positional[2];
            if (!File.Exists(fpath)) return Fail($"文件不存在：{fpath}");
            var before = ModuleLifecycle.GetStatus(
                KnowledgeSig.Norm(new System.Text.UTF8Encoding(false, true).GetString(File.ReadAllBytes(fpath)))).Status;
            Console.WriteLine("== nf module status ==");
            Console.WriteLine($"  {fpath} → {before}");
            return 0;
        }
        if (positional.Count >= 2 && positional[1] is "deprecate" or "restore")
            return Fail($"module {positional[1]} 是写面（改模块文件状态位）——本引擎是只读门，不提供写命令");
        return Fail("module 子命令只移植了 `types`（含 --backlog）/ `signature` / `ls` / `status` / `verify`；"
                    + "其余（deprecate/restore/contract）属写面或未移植");
    }

    private static int LintCommand()
    {
        // 只移植了 `nf lint --kinds`（四型写法判据）；默认面（autofix 规则 + 正文 lint）未移植——
        // 未移植就明确报错，不静默给"通过"。
        if (!kindsOnly)
        {
            return Fail("lint 默认面未移植（autofix 机械规则 + 正文 lint）：本引擎只实现 `nf lint --kinds`");
        }
        var warns = DocHygiene.KindRulesFor(root!);
        Console.WriteLine("== nf lint --kinds（四型写法判据）==");
        foreach (var warn in warns) Console.WriteLine("  [WARN] " + warn);
        if (warns.Count == 0) Console.WriteLine("  ✓ 四型写法齐（每型都有该型必备的结构块）");
        return 0;
    }

    private static int ConformanceCommand()
    {
        var report = Conformance.Run(root!);
        var failed = report.Contracts.Where(c => !c.Ok).ToList();
        if (json)
        {
            Console.WriteLine(PythonJson.Indented(new Dictionary<string, object?>
            {
                // 诚实标注：本引擎只落地了部分契约，**不输出 conformant / non-conformant**
                ["verdict"] = "partial",
                ["coverage"] = $"{report.Contracts.Count}/{Conformance.AllContractIds.Length}",
                ["ported"] = report.Contracts.Select(c => (object?)new Dictionary<string, object?>
                {
                    ["id"] = c.Id, ["ok"] = c.Ok, ["detail"] = c.Detail, ["digest"] = c.Digest,
                    ["description"] = c.Description,
                }).ToList(),
                ["unported"] = report.Unported.Cast<object?>().ToList(),
                ["passed"] = report.Passed,
                ["root_of_ported"] = report.RootOfPorted,
            }));
        }
        else
        {
            Console.WriteLine("== nf-dotnet conformance（一致性报告 · 部分实现）==");
            foreach (var c in report.Contracts)
                Console.WriteLine($"  {(c.Ok ? "✓" : "✗")} {c.Id,-28} {c.Detail}");
            Console.WriteLine($"  —— 已移植 {report.Contracts.Count}/{Conformance.AllContractIds.Length} 契约 · " +
                              $"通过 {report.Passed} · root(已移植叶子)={report.RootOfPorted[..Math.Min(16, report.RootOfPorted.Length)]}");
            Console.WriteLine($"  —— 未移植 {report.Unported.Count} 条（不参与判定，不伪造 verdict）：" +
                              string.Join("、", report.Unported));
        }
        return failed.Count == 0 ? 0 : 1;
    }

    private static int Usage(string? error)
    {
        if (error is not null) Console.Error.WriteLine("错误：" + error);
        Console.Error.WriteLine("""
nf-dotnet 0.1.0 · NF 工业引擎 CLI（只读子集，输出面与 Python 侧 nf 对齐）

用法：nf-dotnet [--root <dir>] [--json] <命令>

命令：
  verify                                            聚合校验（协议回执 + 馆藏回执 + 透明链 + 组合证书）
  assertions                                        数据化断言表求值（14 条 · 4 种 kind）
  decisions [verify]                                决策记录门禁（ADR 编号/状态/取代链/证据/回执锚定/投影）
  cognition                                         认知族门禁（术语表真源逐字命中 + 执行分档结构块）
  library                                           馆藏门（frontmatter + 签名锚漂移 + INDEX/ALIAS 投影）
  bench [--baseline <f>] [--write-baseline <f>]     性能基线：测量关键操作，可对基线做回归门
  serve                                             MCP stdio 服务器（JSON-RPC 2.0 · dual-era · 只读 15 工具）
  receipts [--scope protocol|library]               回执复算（默认 protocol）
  transparency                                      透明链复算
  combine verify                                    组合证书 T4 复算
  combine plan --packs a,b [--extra-modules x,y] [--strict-coherence]  组合一个并打印证书
  combine breadth [--pairs-only] [--samples <json>] 广度证明（默认自足：两两全集 + 定种子抽样）
  selftest                                          负例 / 健壮性自检（撞号·深链·未知包·悬空·未桥接 + 篡改检测）
  patterns ls|show|for|verify [--json]              实践包（读面子集；reindex 属写面，不提供）
  rfc [--json]                                      协议件 RFC 索引与 supersede 链自检
  endpoint [--json]                                 服务端点契约自检（proposed；契约不指向空气）
  events [--json]                                   全仓事件背书核对（订阅是否真有发布方）
  toolface [--json]                                 模块工具面浏览（machine_contract.tool_face 建议层）
  st-validate <path> [--out <p>] [--json]           ST 制卡校验器（卡 / 世界书 / MVU 变量 → 可自动化项报告）
  stats [--check] [--json]                          自述数字实算（README/README.en/llms.txt 生成区 == 实算）
  telemetry <trace.json> [--otlp]                   遥测 semconv 映射（trace 记录 → OTel GenAI 属性 / OTLP 形状）
  driver [工作流] [--json]                          指令档机器面路由（有 MCP 走 MCP；派发失败即停、不回退文本）
  interop --list | --kind K [--out P] [--check]     互操作导出面（12/12 形状已移植；--check 跑门禁）
  impact <target> [--check] [--registry P]          变更影响面预检（拟删除 module/protocol 前查破坏性）
  related <target> [--json] [--registry P]          See-Also 关联（引用了谁 / 谁引用我 / 模块互见）
  market --list [--tier T] [--json]                 市场目录视图（官方核心 + 社区包，各带分级徽章）
  asset verify|inventory|ls|baseline|density|usage|thickness|ledger [--assets-root P]  资产供应链台账（verify = check23 同语义闭合门禁；baseline 只读比对）
  model [vocab|normative|contracts] [--json]        内容建模三件（词表 / 规范件 / 数据契约）
  sig [verify] [--json]                             知识签名（根文档结构化签名 + 两遍一致）
  worldmodel [--json]                               世界模型面（JEPA-inspired 确定性抽象状态契约 · check32 硬门）
  conformance [--json]                              一致性报告（部分实现：只报已移植契约 · verdict=partial）
  corpus [--json]                                   语料身份指纹（导出态比金标 · 工作区态只报模式）
  lint --kinds [--json]                             文档 lint 只读子集（autofix / 正文 lint 未移植）
  module types|signature|ls|status|verify [--json]  模块面（写面 deprecate/restore/contract 不提供）
  pipeline dryrun [--all] [--json]                  管线抽象执行（--write-advisory 属写面，不提供）
  handover [--json]                                 交接待办清单（HO 编号 / 状态 / 承接人）
  postmortem [--json]                               复盘登记（PO 编号 / 状态 / 一句话教训）
  audit [--check] [--json]                          审计面（登记册与对象锁回执）
  state-front <产物 md> [--json]                    前端状态（--out 属写面，不提供）
  knowledge [order|visible|transform|lint|frequency] [--json]  双源知识层（缺省即 status；写面不提供）
  who-refers <模块 id> [--json]                     反向引用（谁提到这个模块）
  diff <a> <b> [--json]                             两文档结构化差分
  explain <check 编号|all> [--json]                 判据说明（编号 → 该 check 在查什么）
  output [list|render|verify|check|meter] [--json]  产出面（写面不提供；list 为形态清单）
  domain-closure [--target X|--list|--gaps|--check] 概念前置闭包求值器（真源是 scripts/ 下独立脚本 · 只读）
  workloop [--list] [--top N] [--source S] [--json] 构建回路：工单扫描与能力缺口（写面不提供）
  license [--json]                                  图书馆许可证门（登记 / 声明 / 内联 / 双源一致）
  score [--baseline <f>] [--tolerance X] [--json]   基线相对回归评分（purity_clean 为声明边界）
  decide --questions <f> [--state-text S|--state <f>] [--dry-run] [--json]  决策层（choice/score/noul；端点适配器不外呼）
  doctor [--json]                                   环境自检（文件在场 / 注册表 / schema / 基线自述 / 机器面）
  spec [ls] [--json]                                注册表面（registry 版本 + 官方核心模块数 + 逐协议包）
  review [--limit N] [--scope S] [--batch B] [--json]  逐行缺口审查（机械预筛 + 确定性证据复核）
  extension [--diff <文件|->] [--json]              扩展策略面（结构 bump 待迁移记录；diff 由调用方提供）
  assemble "<需求>" [--answer X ...] [--check <成品 md>]  需求 → 装配计划（--check 对成品做机器验收）
  daemon                                            执行层常驻守护（真源有）——**本引擎只读，不提供**（调用即显式拒绝）
  shell    → 执行层·交互层（真源有）——**本引擎只读，不提供**（调用即显式拒绝）
  terminal → 执行层·交互层（真源有）——**本引擎只读，不提供**（调用即显式拒绝）
  lsp      → 执行层·交互层（真源有）——**本引擎只读，不提供**（调用即显式拒绝）
  completion → 执行层·交互层（真源有）——**本引擎只读，不提供**（调用即显式拒绝）
  demo     → 执行层·交互层（真源有）——**本引擎只读，不提供**（调用即显式拒绝）
  run      → 执行层·交互层（真源有）——**本引擎只读，不提供**（调用即显式拒绝）
  help     → 执行层·交互层（真源有）——**本引擎只读，不提供**（用法见 --help）
  register → 写面·工厂（真源有）——**本引擎只读，不提供**（调用即显式拒绝）
  rename   → 写面·工厂（真源有）——**本引擎只读，不提供**（调用即显式拒绝）
  import   → 写面·工厂（真源有）——**本引擎只读，不提供**（调用即显式拒绝）
  approve  → 写面·工厂（真源有）——**本引擎只读，不提供**（调用即显式拒绝）
  attest   → 写面·工厂（真源有）——**本引擎只读，不提供**（调用即显式拒绝）
  design   → 写面·工厂（真源有）——**本引擎只读，不提供**（调用即显式拒绝）
  domain   → 写面·工厂（真源有）——**本引擎只读，不提供**（调用即显式拒绝）
  layers   → 读面未移植（真源 protocol/LAYERS.json · 与 check27 R7 同源）
  release  → 读面未移植（verify + doctor 组合）

全局：--root <dir> 指定仓库根；--json 输出结构化 JSON（键排序 + 2 空格缩进，与 nf 一致）
退出码：0 通过 / 1 存在问题 / 2 用法或 IO 错误
""");
        return error is null ? 0 : 2;
    }

    private static int Fail(string message)
    {
        Console.Error.WriteLine("错误：" + message);
        return 2;
    }

}
