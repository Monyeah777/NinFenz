using System.Text.Json;
using Nf.Engine;

internal static partial class Program
{
    // 需求 → 澄清漏斗 → 装配计划（真源 `nf assemble` · core/assemble_plan.py）。
    // **读面**：clarify / plan / dossier / check。**写面与未移植面明确拒绝**：`--session-path`（会话档读写）·
    // `--save-path`（需求档案落盘）· `--trace-path`（工具轨迹落盘）· `--rounds`（需 core/round_drill，未移植）。
    private static int AssembleCommand()
    {
        if (assembleSessionPath.Length > 0 || assembleSavePath.Length > 0 || assembleTracePath.Length > 0
            || assembleRounds)
        {
            Console.Error.WriteLine("错误：--session-path / --save-path / --trace-path 是写面，"
                                    + "--rounds 依赖未移植的 core/round_drill —— 只读门不落盘、不冒充，均不提供");
            return 2;
        }
        if (positional.Count < 2)
        {
            Console.Error.WriteLine("错误：assemble 需要一句话需求（nf assemble \"题材+主轴+尺度\"）");
            return 2;
        }
        var requirement = positional[1];
        var answers = assemblyAnswers;
        var reqText = answers.Count > 0 ? requirement + "（" + string.Join("；", answers) + "）" : requirement;
        var funnel = AssemblePlan.Clarify(root!, reqText);
        var plan = funnel.GetValueOrDefault("plan") as Dictionary<string, object?>
                   ?? AssemblePlan.Plan(root!, reqText);
        if (PyS(funnel.GetValueOrDefault("status")) == "clarify")
        {
            Console.WriteLine("== nf assemble（需求澄清）==");
            Console.WriteLine("  你的需求信息还不够直接编排，先补三点（缺一不可）：");
            foreach (var q in (funnel.GetValueOrDefault("questions") as List<object?> ?? new List<object?>()))
                Console.WriteLine("  · " + PyS(q));
            Console.WriteLine("  补充后再跑：nf assemble \"题材+主轴+尺度的一句话\" --check <out.md>");
            return 0;
        }
        if (assembleCheck)
        {
            if (positional.Count < 3)
            {
                Console.Error.WriteLine("错误：assemble --check 需要成品 md 路径（位置参数）");
                return 2;
            }
            string outMd;
            try
            {
                outMd = File.ReadAllText(positional[2], new System.Text.UTF8Encoding(false, true));
            }
            catch (Exception exc)
            {
                Console.Error.WriteLine($"  ✗ 读取成品失败：{exc.Message}（修复指引：给出仓库内完整版 md 路径）");
                return 1;
            }
            var hasSegments = System.Text.RegularExpressions.Regex.IsMatch(
                outMd, @"^##\s+[0-7]\.", System.Text.RegularExpressions.RegexOptions.Multiline);
            List<string> issues;
            Dictionary<string, object?> stats;
            if (hasSegments)
            {
                (issues, stats) = AssemblePlan.Check(outMd, plan);
            }
            else
            {
                issues = new List<string>();
                stats = new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["segments"] = 0L, ["modules_mentioned"] = 0L,
                    ["allowed"] = (long)(plan.GetValueOrDefault("allowed_module_ids") as List<object?>
                                         ?? new List<object?>()).Count,
                };
            }
            Console.WriteLine("== nf assemble --check（需求 → 成品机器验收）==");
            Console.WriteLine($"  需求：{requirement} → {PyOr(plan.GetValueOrDefault("package"), "？")}"
                              + $"/{PyOr(plan.GetValueOrDefault("pipeline"), "？")}"
                              + $"（模块提及 {PyS(stats["modules_mentioned"])} · 允许集 {PyS(stats["allowed"])}）");
            foreach (var issue in issues) Console.Error.WriteLine("  [FAIL] " + issue);
            if (issues.Count == 0)
                Console.WriteLine("  ✓ 成品通过自组装机器验收（八段骨架 + 编号允许集 + 决策引用）");
            return issues.Count > 0 ? 1 : 0;
        }
        Console.WriteLine("== nf assemble（需求 → 装配计划）==");
        var pipelineFiles = (plan.GetValueOrDefault("pipeline_files") as List<object?> ?? new List<object?>())
            .Select(PyS).ToList();
        if (plan.GetValueOrDefault("matched") is true)
        {
            Console.WriteLine($"  匹配预设：{PyS(plan.GetValueOrDefault("package"))}"
                              + $" · 管线 {PyS(plan.GetValueOrDefault("pipeline"))}");
            Console.WriteLine($"  管线件：{(pipelineFiles.Count > 0 ? string.Join("、", pipelineFiles) : "—")}");
            Console.WriteLine("  取件模块："
                              + string.Join("、", (plan.GetValueOrDefault("fetch_modules") as List<object?> ?? new List<object?>()).Select(PyS)));
            Console.WriteLine("  装配允许集（官方核心 + 包模块）："
                              + PyS((plan.GetValueOrDefault("allowed_module_ids") as List<object?> ?? new List<object?>()).Count));
            Console.WriteLine($"  下一步：读 docs/agent/agent_组装指令包_v0.2.md → 取件 → 输出完整版 → "
                              + $"nf assemble \"{requirement}\" --check <out.md> 验收");
        }
        else
        {
            Console.WriteLine("  未命中预设 → 用户自定义流（custom）");
            var known = (plan.GetValueOrDefault("known_packages") as List<object?> ?? new List<object?>())
                .Select(PyS).ToList();
            Console.WriteLine($"  可借用已登记包：{(known.Count > 0 ? string.Join("、", known) : "—")}");
            Console.WriteLine("  装配允许集（官方核心 + 全部已登记社区模块）："
                              + PyS((plan.GetValueOrDefault("allowed_module_ids") as List<object?> ?? new List<object?>()).Count));
            Console.WriteLine("  自定义预留槽位：模块 M91-M99 或 <本包独占类别>:Mxx 类内段 · 资产 900+ 命名空间 · "
                              + "新管线 Pxx（避让层位 id P00-P80 与官方/既有管线，见 02 §8.3）");
            Console.WriteLine("  建件：按 community/模板制作指令包.md 做自定义模块/资产 → "
                              + "protocol.yaml 登记（nf register）→ 成品里即可引用 → 验收");
            Console.WriteLine($"  验收：nf assemble \"{requirement}\" --check <out.md>");
        }
        return 0;
    }

    private static string PyOr(object? value, string fallback) => value is null || (value is string s && s.Length == 0)
    ? fallback : PyS(value);

    private static int InteropCommand()
    {
        // 片内推进：`--list` 全 12 形状可用；`--kind` 仅对已移植形状可用（未移植明确拒绝）；
        // `--check` / `--all` 需要全部形状，未移植前明确拒绝——不提供半个门禁。
        if (interopList)
        {
            foreach (var (id, label) in Interop.Kinds)
                Console.WriteLine($"  {PadCp(id, 9)} {PadCp(label, 38)} 消费者：外部标准工具链");
            return 0;
        }
        if (interopCheck)
        {
            var (checkIssues, checkStats) = Interop.Verify(root!);
            if (json)
            {
                Console.WriteLine(JsonFor(new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["issues"] = checkIssues.Cast<object?>().ToList(),
                    ["stats"] = checkStats,
                }));
            }
            else
            {
                foreach (var i in checkIssues) Console.Error.WriteLine($"  [FAIL] {i}");
                if (checkIssues.Count == 0) Console.WriteLine($"  ✓ 导出面一致（{Interop.Summary(checkStats)}）");
            }
            return checkIssues.Count > 0 ? 1 : 0;
        }
        if (interopAll)
        {
            if (outPath is null)
                return Fail("interop --all 缺省落仓内 results/interop/（仓库写面）——本引擎只写调用者显式指定的路径，" +
                            "请加 --out <目录>");
            var dir = Path.IsPathRooted(outPath) ? outPath : Path.Combine(root!, outPath);
            Directory.CreateDirectory(dir);
            foreach (var (id, _) in Interop.Kinds)
            {
                var dest = Path.Combine(dir, $"{id}.json");
                File.WriteAllBytes(dest, Interop.Render(id, root!));
                Console.WriteLine($"written: {dest}");
            }
            Console.WriteLine("  （入仓面须与实时派生逐字节一致——由 verify check33 断言；改声明件后重跑本命令）");
            return 0;
        }

        var kind = interopKind ?? "openapi";
        if (!Interop.Kinds.Any(k => k.Id == kind))
            return Usage($"interop 的 --kind 取值须为：{string.Join(" / ", Interop.Kinds.Select(k => k.Id))}");
        byte[] blob;
        try
        {
            blob = Interop.Render(kind, root!);
        }
        catch (InvalidOperationException exc)
        {
            return Fail(exc.Message);
        }
        if (outPath is not null)
        {
            var outp = Path.IsPathRooted(outPath) ? outPath : Path.Combine(root!, outPath);
            var parent = Path.GetDirectoryName(outp);
            if (!string.IsNullOrEmpty(parent)) Directory.CreateDirectory(parent);
            File.WriteAllBytes(outp, blob);
            Console.WriteLine($"written: {outPath}（{blob.Length} 字节，纯派生，勿手改）");
        }
        else
        {
            Console.Out.Write(System.Text.Encoding.UTF8.GetString(blob));
            Console.Out.Flush();
        }
        return 0;
    }

    private static int StatsCommand()
    {
        if (writeRequested)
            return Usage("stats --write 是写面（重写三处生成区与 protocol/repo_stats.json）——本引擎是只读门，不提供写命令");

        var (issues, stats) = RepoStats.Check(root!);
        long N(string key) => stats.TryGetValue(key, out var v) && v is not null
            ? Convert.ToInt64(v, System.Globalization.CultureInfo.InvariantCulture) : 0L;
        var pipes = (stats.TryGetValue("core_pipelines", out var p) ? p as List<object?> : null) ?? new List<object?>();

        if (json)
        {
            // 有意分歧（已登记）：Python 侧 `nf stats --json` 因缺 `import json` 抛 NameError 崩栈；
            // 引擎侧给出正确的机读面——这是修好，不是等价差，故不进「逐字节对账面」。
            Console.WriteLine(PythonJson.Indented(stats));
        }
        else
        {
            Console.WriteLine("== nf stats（自述数字实算 · 真源 protocol/repo_stats.json）==");
            Console.WriteLine($"  官方核心：模块 {N("core_modules")} · 管线 {string.Join(" / ", pipes.Select(PyS))}");
            Console.WriteLine($"  社区规模：登记包 {N("registered_packs")} · 资产档 {N("pack_assets")} · " +
                              $"概念图 {N("concept_graphs")} · 域包 {N("domain_packs")}/{N("subdivisions_total")} 细分");
            Console.WriteLine($"  标准目录：{N("standards_total")} 条（可达 {N("standards_reachable")} / " +
                              $"不可达 {N("standards_unreachable")} · 机构 {N("standards_bodies")} · " +
                              $"{N("standards_edges")} 边） · 绑定 {N("standard_bindings")} 条");
            Console.WriteLine($"  质量凭证：verify check1-{N("baseline_checks")} 常驻（脚本 " +
                              $"v{PyS(stats.GetValueOrDefault("verify_version"))}） · 馆藏 {N("library_items")} 件");
            Console.WriteLine("  模式：check（只校验）");
            foreach (var i in issues) Console.Error.WriteLine($"  [FAIL] {i}");
        }
        return issues.Count > 0 ? 1 : 0;
    }

    /// <summary>
    /// <c>nf driver [工作流] [--json]</c>——指令档机器面路由（有 MCP 走 MCP；派发失败即停、不回退文本步骤）。
    /// 与真源逐字节对齐：文本面的列宽（<c>%-12s</c> / <c>%-28s</c>）、warns 走 stdout 的 <c>[note]</c>、
    /// issues 走 **stderr** 的 <c>[FAIL]</c>、以及 JSON 面的 <c>indent=2, sort_keys=True</c>；退出码 1 当有 issues。
    /// </summary>
    private static int DriverCommand()
    {
        var workflow = positional.Count >= 2 ? positional[1] : "";
        var scan = Driver.Scan(root!);
        if (workflow.Length > 0)
        {
            var resolved = Driver.Resolve(root!, workflow);
            if (json)
            {
                Console.WriteLine(JsonFor(new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["resolve"] = resolved,
                    ["issues"] = scan.Issues.Cast<object?>().ToList(),
                    ["warns"] = scan.Warns.Cast<object?>().ToList(),
                }));
            }
            else
            {
                Console.WriteLine($"== nf driver {workflow} ==");
                var mode = S(resolved.GetValueOrDefault("mode"));
                Console.WriteLine($"  路径：{(mode == "mcp" ? "MCP（机器面）" : mode)}");
                var prompt = S(resolved.GetValueOrDefault("prompt"));
                if (prompt.Length > 0) Console.WriteLine($"  提示：{prompt}");
                var tools = resolved.GetValueOrDefault("tools") as List<object?> ?? new List<object?>();
                if (tools.Count > 0) Console.WriteLine("  工具：" + string.Join("、", tools.Select(PyS)));
                var fallback = S(resolved.GetValueOrDefault("fallback"));
                Console.WriteLine($"  文本 fallback：{(fallback.Length > 0 ? fallback : "-")}");
                var onFailure = S(resolved.GetValueOrDefault("on_dispatch_failure"));
                Console.WriteLine($"  派发失败：{(onFailure.Length > 0 ? onFailure : "-")}");
                foreach (var issue in scan.Issues) Console.Error.WriteLine($"  [FAIL] {issue}");
            }
            return scan.Issues.Count > 0 ? 1 : 0;
        }

        var document = Driver.Load(root!);
        if (json)
        {
            Console.WriteLine(JsonFor(new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["driver"] = document,
                ["issues"] = scan.Issues.Cast<object?>().ToList(),
                ["warns"] = scan.Warns.Cast<object?>().ToList(),
                ["stats"] = scan.Stats,
            }));
        }
        else
        {
            Console.WriteLine("== nf driver（指令档机器面路由）==");
            var workflows = document.GetValueOrDefault("workflows") as Dictionary<string, object?>
                            ?? new Dictionary<string, object?>();
            foreach (var name in workflows.Keys.OrderBy(x => x, StringComparer.Ordinal))
            {
                var wf = workflows[name] as Dictionary<string, object?> ?? new Dictionary<string, object?>();
                var tools = wf.GetValueOrDefault("mcp_tools") as List<object?> ?? new List<object?>();
                var toolText = tools.Count > 0 ? string.Join("、", tools.Select(PyS)) : "-";
                var fallback = S(wf.GetValueOrDefault("fallback"));
                Console.WriteLine($"  {Pad(name, 12)} MCP：{Pad(toolText, 28)} fallback：{(fallback.Length > 0 ? fallback : "-")}");
            }
            foreach (var warn in scan.Warns) Console.WriteLine($"  [note] {warn}");
            foreach (var issue in scan.Issues) Console.Error.WriteLine($"  [FAIL] {issue}");
            if (scan.Issues.Count == 0)
                Console.WriteLine("  ✓ 工作流映射/工具名/fallback/文档声明块全部一致（fail-closed 已声明）");
        }
        return scan.Issues.Count > 0 ? 1 : 0;
    }

    /// <summary>Python <c>%-Ns</c>：按**码点**左对齐补空格（不足才补，超长不截）。</summary>
    private static string Pad(string text, int width)
    {
        var length = text.EnumerateRunes().Count();
        return length < width ? text + new string(' ', width - length) : text;
    }

    /// <summary>
    /// Python <c>.get(key, "-")</c> / 真值跳过的口径：**缺键与 None 都当作空**（渲染成空串，由调用方补 "-"）。
    /// 注意不能直接用 <c>PyS</c>——它把 null 渲染成 <c>"None"</c>（那是 <c>str(None)</c> 的口径，用在这里会多出三个字节）。
    /// </summary>
    private static string S(object? value) => value is null ? "" : PyS(value);

    /// <summary>
    /// 列表强制：引擎各 Stats 字典里的数组类型不统一（`List&lt;object?&gt;` / `List&lt;string&gt;` / …），
    /// `as List&lt;object?&gt;` 对后者**静默返回 null**（实测踩过：license 文本面把「未声明 1」打成 0，
    /// 而 JSON 面因渲染器吃 IEnumerable 仍逐字节一致——只有文本面照得出来）。
    /// </summary>
    private static List<object?> AsObjList(object? value) => value switch
{
    List<object?> list => list,
    System.Collections.IEnumerable seq when value is not string => seq.Cast<object?>().ToList(),
    _ => new List<object?>(),
};

    /// <summary>
    /// <c>nf telemetry &lt;trace.json&gt; [--otlp]</c>——trace 记录 → OTel GenAI semconv 属性 / OTLP 形状。
    /// 文本面与真源逐字节对齐（含属性名左对齐 28 列与 <c>json.dumps</c> 默认分隔符）；错误面与真源同向：
    /// 打一行可读错误到 stderr + 退出码 1，不打栈。
    /// </summary>
    private static int TelemetryCommand()
    {
        if (positional.Count < 2) return Usage("telemetry 需要一个 trace JSON 路径（单条记录或 {records:[...]}）");
        var tracePath = positional[1];
        List<Dictionary<string, object?>> records;
        try
        {
            records = TelemetrySemconv.LoadTrace(tracePath);
        }
        catch (Exception exc) when (exc is IOException or System.Text.Json.JsonException
                                    or InvalidOperationException or UnauthorizedAccessException or ArgumentException)
        {
            Console.Error.WriteLine($"  ✗ {exc.Message}");
            return 1;
        }
        if (records.Count == 0)
        {
            Console.Error.WriteLine("  ✗ trace 为空或格式不识别（支持单条记录或 {records:[...]}）");
            return 1;
        }
        if (flags.Contains("--otlp"))
        {
            var exported = TelemetrySemconv.ToExport(records);
            if (exported is Dictionary<string, object?> doc)
                exported = new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["kind"] = "telemetry-otlp",
                }.Concat(doc).ToDictionary(kv => kv.Key, kv => kv.Value, StringComparer.Ordinal);
            Console.WriteLine(PythonJson.IndentedUnsorted(exported));
            return 0;
        }
        Console.WriteLine($"== nf telemetry（{records.Count} 记录 → semconv 属性）==");
        foreach (var record in records)
        {
            Console.WriteLine("  " + TelemetrySemconv.ToolNameOf(record));
            foreach (var kv in TelemetrySemconv.AttributesFor(record).OrderBy(k => k.Key, StringComparer.Ordinal))
            {
                var pad = kv.Key.EnumerateRunes().Count();
                var padding = pad < 28 ? new string(' ', 28 - pad) : "";
                Console.WriteLine($"    {kv.Key}{padding} {PythonJson.UnsortedWithSpaces(kv.Value)}");
            }
        }
        return 0;
    }

    private static int StValidateCommand()
    {
        if (positional.Count < 2) return Usage("st-validate 需要一个被校验对象的路径");
        var target = positional[1];
        Dictionary<string, object?> rep;
        try
        {
            rep = StValidate.Validate(target);
        }
        catch (Exception exc) when (exc is IOException or System.Text.Json.JsonException or InvalidOperationException)
        {
            // 与 Python 同向：`except (OSError, ValueError)` → 打一行可读错误 + 退出码 1（不打栈）
            Console.Error.WriteLine($"  ✗ {exc.Message}");
            return 1;
        }

        if (outPath is not null)
        {
            var outp = Path.IsPathRooted(outPath) ? outPath : Path.Combine(root!, outPath);
            var parent = Path.GetDirectoryName(outp);
            if (!string.IsNullOrEmpty(parent)) Directory.CreateDirectory(parent);
            File.WriteAllText(outp, StValidate.ReportMarkdown(rep), new System.Text.UTF8Encoding(false));
        }

        if (json)
        {
            Console.WriteLine(PythonJson.Indented(rep));
        }
        else
        {
            var counts = rep.GetValueOrDefault("counts") as Dictionary<string, object?> ?? new Dictionary<string, object?>(StringComparer.Ordinal);
            long N(string key) => counts.TryGetValue(key, out var v) && v is not null
                ? Convert.ToInt64(v, System.Globalization.CultureInfo.InvariantCulture) : 0;
            Console.WriteLine($"== nf st-validate {target}（{PyS(rep.GetValueOrDefault("kind"))}：" +
                              $"fail {N("fail")} · warn {N("warn")} · info {N("info")}）==");
            var issues = rep.GetValueOrDefault("issues") as List<object?> ?? new List<object?>();
            foreach (var node in issues)
            {
                var issue = (Dictionary<string, object?>)node!;
                Console.WriteLine($"  [{PyS(issue["severity"]).ToUpperInvariant()}] {PyS(issue["rule"])} {PyS(issue["detail"])}");
            }
            if (issues.Count == 0) Console.WriteLine("  ✓ 可自动化项全部通过（R1/R3/R4）");
            if (outPath is not null) Console.WriteLine($"  报告已写入：{outPath}");
        }

        var fails = rep.GetValueOrDefault("counts") is Dictionary<string, object?> c
                    && c.TryGetValue("fail", out var f) && f is not null
            ? Convert.ToInt64(f, System.Globalization.CultureInfo.InvariantCulture) : 0;
        return fails > 0 ? 1 : 0;
    }

    private static int EventsCommand()
    {
        var (issues, warns, stats) = EventBacking.Scan(root!);
        if (json)
        {
            Console.WriteLine(JsonFor(new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["issues"] = issues.Cast<object?>().ToList(),
                ["warns"] = warns.Cast<object?>().ToList(),
                ["stats"] = stats,
            }));
        }
        else
        {
            var cross = stats.TryGetValue("cross_pkg", out var c) && c is List<object?> list ? list : new List<object?>();
            Console.WriteLine("== nf events（全仓事件背书）==");
            Console.WriteLine($"  事件 {StatOr(stats, "events")} · 跨包 {cross.Count} · 无发布方挂账 {warns.Count - cross.Count}");
            foreach (var i in issues) Console.Error.WriteLine($"  [FAIL] {i}");
            foreach (var w in warns.Take(10)) Console.WriteLine($"  [note] {w}");
            if (issues.Count == 0) Console.WriteLine("  ✓ 每个被订阅的事件都有发布方（外部通道已显式挂账）");
        }
        return issues.Count > 0 ? 1 : 0;
    }

    private static int ToolFaceCommand()
    {
        var (issues, stats) = ToolFace.Scan(root!);
        if (json)
        {
            Console.WriteLine(JsonFor(new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["kind"] = "toolface",
                ["issues"] = issues.Cast<object?>().ToList(),
                ["stats"] = stats,
            }));
        }
        else
        {
            Console.WriteLine("== nf toolface（模块工具面 · AI 裁量不入门禁）==");
            Console.WriteLine($"  模块 {StatOr(stats, "modules")} · 条目 {StatOr(stats, "entries")} · " +
                              $"候选工具链接 {StatOr(stats, "candidates")}");
            var faces = stats.TryGetValue("faces", out var f) && f is List<object?> list ? list : new List<object?>();
            foreach (var face in faces)
            {
                var row = face as Dictionary<string, object?>;
                if (row is null) continue;
                Console.WriteLine($"  · {StatOr(row, "module")}（{StatOr(row, "source")} · {StatOr(row, "entries")} 条目）");
            }
            foreach (var i in issues) Console.Error.WriteLine($"  [FAIL] {i}");
        }
        return issues.Count > 0 ? 1 : 0;
    }

    private static int RfcCommand()
    {
        var (issues, warns, stats) = Rfc.Scan(root!);
        var idx = Rfc.IndexDoc(root!);
        if (json)
        {
            Console.WriteLine(JsonFor(new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["index"] = idx,
                ["issues"] = issues.Cast<object?>().ToList(),
                ["warns"] = warns.Cast<object?>().ToList(),
                ["stats"] = stats,
            }));
        }
        else
        {
            Console.WriteLine("== nf rfc（协议件版本史）==");
            var docs = idx.GetValueOrDefault("docs") as List<object?> ?? new List<object?>();
            foreach (var item in docs)
            {
                var row = item as Dictionary<string, object?>;
                var rel = row is null ? "" : PyS(row.GetValueOrDefault("path"));
                var text = KnowledgeSig.Norm(new System.Text.UTF8Encoding(false, true)
                    .GetString(File.ReadAllBytes(Path.Combine(root!, rel))));
                var head = Rfc.ParseHead(text);
                string Get(string key) => head.TryGetValue(key, out var v) ? v : "-";
                Console.WriteLine($"  {PadCp(row is null ? "" : PyS(row.GetValueOrDefault("rfc")), 9)} {PadCp(rel, 34)} " +
                                  $"{PadCp(Get("cat"), 16)} {PadCp(Get("status"), 9)} {Get("date")}");
            }
            foreach (var i in issues) Console.Error.WriteLine($"  [FAIL] {i}");
            if (issues.Count == 0) Console.WriteLine($"  ✓ {stats.GetValueOrDefault("docs")} 件 RFC 头齐备且链可解析");
        }
        return issues.Count > 0 ? 1 : 0;
    }

    private static int EndpointCommand()
    {
        var (issues, warns, stats) = EndpointContract.Scan(root!);
        var doc = EndpointContract.Load(root!);
        if (json)
        {
            Console.WriteLine(JsonFor(new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["contract"] = doc,
                ["issues"] = issues.Cast<object?>().ToList(),
                ["warns"] = warns.Cast<object?>().ToList(),
                ["stats"] = stats,
            }));
        }
        else
        {
            Console.WriteLine($"== nf endpoint（服务端点契约 · {StatOr(stats, "status")}）==");
            var endpoints = doc.GetValueOrDefault("endpoints") as List<object?> ?? new List<object?>();
            foreach (var item in endpoints)
            {
                var ep = item as Dictionary<string, object?>;
                if (ep is null) continue;
                var streaming = ep.TryGetValue("streaming", out var sv) && PyTruthy(sv) ? "SSE" : "单发";
                Console.WriteLine($"  {PadCp(PyS(ep.GetValueOrDefault("method")), 8)} " +
                                  $"{PadCp(PyS(ep.GetValueOrDefault("path")), 22)} {PadCp(streaming, 9)} " +
                                  $"{PyS(ep.GetValueOrDefault("maps_to"))}");
            }
            foreach (var i in issues) Console.Error.WriteLine($"  [FAIL] {i}");
            foreach (var w in warns) Console.WriteLine($"  [note] {w}");
            if (issues.Count == 0)
                Console.WriteLine("  ✓ 每个端点都映射到现存 CLI 子命令或 MCP 工具（契约不指向空气）");
        }
        return issues.Count > 0 ? 1 : 0;
    }

    /// <summary>Python 真值判定（用于 <c>"SSE" if ep.get("streaming") else "单发"</c>）。</summary>
    private static bool PyTruthy(object? v) => v switch
{
    null => false,
    bool b => b,
    string s => s.Length > 0,
    long l => l != 0,
    double d => d != 0,
    List<object?> list => list.Count > 0,
    Dictionary<string, object?> map => map.Count > 0,
    _ => true,
};

    /// <summary>Python <c>dict.get(k, "?")</c> 语义：缺键才给默认值（有键即使是空串也照印）。</summary>
    private static string StatOr(Dictionary<string, object?> stats, string key) => stats.TryGetValue(key, out var v) ? PyS(v) : "?";

    private static int SigCommand()
    {
        var verifyOnly = positional.Count >= 2 && positional[1] == "verify";
        if (verifyOnly)
        {
            var (issues, stats) = KnowledgeSig.VerifyReproducible(root!);
            if (json)
            {
                Console.WriteLine(JsonFor(new Dictionary<string, object?>
                {
                    ["issues"] = issues.Cast<object?>().ToList(),
                    ["stats"] = stats,
                }));
            }
            else
            {
                Console.WriteLine($"== nf-dotnet sig verify（check25 同语义）==  文档 {stats["docs"]} · 可复现 {stats["reproducible"]}");
                foreach (var issue in issues) Console.WriteLine("  ✗ " + issue);
                if (issues.Count == 0) Console.WriteLine("  ✓ 01-36 全量签名两遍一致（知识指纹稳定）");
            }
            return issues.Count == 0 ? 0 : 1;
        }

        var scan = KnowledgeSig.Scan(root!);
        if (json)
        {
            Console.WriteLine(JsonFor(scan.Records));
        }
        else
        {
            Console.WriteLine($"== nf-dotnet sig（{scan.Count} 文档）==");
            foreach (var row in scan.Records.Cast<Dictionary<string, object?>>())
            {
                var sig = (Dictionary<string, object?>)row["sig"]!;
                var refs = (List<object?>)sig["refs"]!;
                Console.WriteLine($"  {((string)row["digest"]!)[..12]}  {sig["path"],-14} {sig["doc_id"],-8} refs={refs.Count}");
            }
        }
        return 0;
    }

}
