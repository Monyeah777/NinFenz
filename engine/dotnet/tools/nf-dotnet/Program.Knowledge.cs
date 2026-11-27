using System.Text.Json;
using Nf.Engine;

internal static partial class Program
{
    private static int ModelCommand()
    {
        var part = positional.Count >= 2 ? positional[1] : "";
        if (part is not ("" or "vocab" or "normative" or "contracts"))
            return Usage("model 的子命令须为 vocab / normative / contracts");
        var result = Modeling.Run(root!, part);
        if (json)
        {
            Console.WriteLine(JsonFor(new Dictionary<string, object?>
            {
                ["issues"] = result.Issues.Cast<object?>().ToList(),
                ["stats"] = result.Stats,
                ["warns"] = result.Warns.Cast<object?>().ToList(),
            }));
        }
        else
        {
            Console.WriteLine($"== nf-dotnet model{(" · " + part)} ==");
            foreach (var kv in result.Stats)
            {
                Console.WriteLine($"  {kv.Key,-10} {PythonJson.CanonicalizeGraph(kv.Value)}");
            }
            foreach (var warn in result.Warns) Console.WriteLine("  ! " + warn);
            foreach (var issue in result.Issues) Console.WriteLine("  ✗ " + issue);
            if (result.Issues.Count == 0)
                Console.WriteLine("  ✓ 词表与真源一致 · 规范件皆有主 · 说明件未被当规范 · 契约 quality_rule 全部解析");
        }
        return result.Issues.Count == 0 ? 0 : 1;
    }

    private static int BenchCommand()
    {
        var measurements = Bench.Run(root!);

        if (benchWritePath is not null)
        {
            var ops = measurements.ToDictionary(
                m => m.Name,
                m => (object?)new Dictionary<string, object?> { ["ms"] = m.Milliseconds, ["detail"] = m.Detail },
                StringComparer.Ordinal);
            File.WriteAllText(benchWritePath,
                PythonJson.Indented(new Dictionary<string, object?>
                {
                    ["schema"] = "nf-net-bench/1",
                    ["ops"] = ops,
                }) + "\n", new System.Text.UTF8Encoding(false));
            Console.WriteLine("已写入基线：" + benchWritePath);
        }

        var rows = new List<object?>();
        var regressed = 0;
        Dictionary<string, double>? baseline = null;
        if (benchBaselinePath is not null)
        {
            using var doc = JsonIo.ReadFile(benchBaselinePath);
            baseline = new Dictionary<string, double>(StringComparer.Ordinal);
            if (doc.RootElement.TryGetProperty("ops", out var ops))
            {
                foreach (var op in ops.EnumerateObject())
                {
                    if (op.Value.TryGetProperty("ms", out var ms) && ms.TryGetDouble(out var value))
                        baseline[op.Name] = value;
                }
            }
        }

        foreach (var m in measurements)
        {
            double? baseMs = baseline is not null && baseline.TryGetValue(m.Name, out var b) ? b : null;
            var ratio = baseMs is > 0 ? m.Milliseconds / baseMs.Value : (double?)null;
            // 判据：允许 tolerance 倍，且给 50 ms 绝对地板（小操作噪声不判红）
            var ok = baseMs is null || m.Milliseconds <= baseMs.Value * tolerance + 50;
            if (!ok) regressed++;
            rows.Add(new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["name"] = m.Name,
                ["ms"] = m.Milliseconds,
                ["baseline_ms"] = baseMs is null ? null : Math.Round(baseMs.Value, 2),
                ["ratio"] = ratio is null ? null : Math.Round(ratio.Value, 2),
                ["ok"] = ok,
                ["detail"] = m.Detail,
            });
        }

        var overall = regressed == 0;
        if (json)
        {
            Console.WriteLine(PythonJson.Indented(new Dictionary<string, object?>
            {
                ["ok"] = overall,
                ["tolerance"] = tolerance,
                ["ops"] = rows,
            }));
        }
        else
        {
            Console.WriteLine("== nf-dotnet bench（性能基线）==");
            foreach (var row in rows.Cast<Dictionary<string, object?>>())
            {
                var name = (string)row["name"]!;
                var ms = (double)row["ms"]!;
                var baseText = row["baseline_ms"] is null ? "—" : row["baseline_ms"] + " ms";
                var ratioText = row["ratio"] is null ? "" : $" · ×{row["ratio"]}";
                Console.WriteLine($"  {(row["ok"] is true ? "✓" : "✗")} {name,-14} {ms,7:0.00} ms · 基线 {baseText}{ratioText} —— {row["detail"]}");
            }
            Console.WriteLine(overall ? "  —— 无回归" : $"  —— 回归 {regressed} 项（容差 ×{tolerance}）");
        }
        return overall ? 0 : 1;
    }

    private static int LibraryCommand()
    {
        var result = Library.Verify(root!);
        var failed = result.Issues.Count + result.Projection.Count;
        if (json)
        {
            Console.WriteLine(JsonFor(new Dictionary<string, object?>
            {
                ["issues"] = result.Issues.Cast<object?>().ToList(),
                ["projection"] = result.Projection.Cast<object?>().ToList(),
                ["stats"] = result.Stats,
                ["warns"] = result.Warns.Cast<object?>().ToList(),
            }));
        }
        else
        {
            Console.WriteLine($"== nf-dotnet library verify（图书馆门）==  条目 {result.Stats["entries"]} · 在役 {result.Stats["active"]} · WARN {result.Warns.Count}");
            foreach (var issue in result.Issues.Concat(result.Projection)) Console.WriteLine("  ✗ " + issue);
            foreach (var warn in result.Warns) Console.WriteLine("  ! " + warn);
            if (failed == 0) Console.WriteLine("  ✓ frontmatter 真源 + INDEX/ALIAS 投影一致");
        }
        return failed == 0 ? 0 : 1;
    }

    private static int CognitionCommand()
    {
        var result = Cognition.Run(root!);
        if (json)
        {
            Console.WriteLine(JsonFor(new Dictionary<string, object?>
            {
                ["issues"] = result.Issues.Cast<object?>().ToList(),
                ["stats"] = result.Stats,
                ["warns"] = result.Warns.Cast<object?>().ToList(),
            }));
        }
        else
        {
            Console.WriteLine("== nf-dotnet cognition（术语表 + 执行分档）==");
            var glossary = (Dictionary<string, object?>)result.Stats["glossary"]!;
            var modes = (Dictionary<string, object?>)result.Stats["modes"]!;
            Console.WriteLine($"  术语 {glossary["terms"]} 条 · 被使用 {glossary["uses"]} 处 · 分档 {modes["modes"]} 档 · 合格实例 {modes["instances_ok"]}");
            foreach (var issue in result.Issues) Console.WriteLine("  ✗ " + issue);
            if (result.Issues.Count == 0) Console.WriteLine("  ✓ 术语真源逐字命中 / 分档实例含全部必备结构块");
        }
        return result.Issues.Count == 0 ? 0 : 1;
    }

    private static int KnowledgeCommand()
    {
        // 只读面：status（缺省）/ order / visible / transform / lint / frequency（--trace 复算，不落盘）。写面（frequency --write、transform add|promote）未移植。
        var sub = positional.Count >= 2 ? positional[1] : "status";
        // 同 Python：`--json` 只挂在子命令上，且**没有 `status` 子命令**（缺省即 status）——
        // 故 `nf knowledge --json` 与 `nf knowledge status` 都是用法错误（exit 2），此处不宽容。
        if (json && positional.Count < 2)
            return Fail("knowledge 需要子命令（order / visible / transform / lint）才能带 --json");
        if (positional.Count >= 2 && sub is not ("order" or "visible" or "transform" or "lint" or "frequency"))
            return Fail($"knowledge 没有子命令：{sub}（可选 order / visible / transform / lint / frequency；缺省即 status）");
        if (sub == "frequency")
        {
            if (writeRequested)
                return Fail("knowledge frequency --write 是写面（写 protocol/knowledge_usage.json）——本引擎只做只读面");
            if (string.IsNullOrEmpty(tracePath))
                return Fail("knowledge frequency 需要 --trace <file>（trace 文件：JSON / JSONL）");
            Dictionary<string, object?> counts;
            try
            {
                counts = KnowledgeSources.HarvestFrequency(tracePath);
            }
            catch (Exception exc) when (exc is IOException or UnauthorizedAccessException)
            {
                Console.Error.WriteLine($"  ✗ {exc.Message}");
                return 1;
            }
            var (freqIssues, _freqWarns, freqStats) = KnowledgeSources.VerifyUsage(root!);
            if (json)
            {
                Console.WriteLine(JsonFor(new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["counts"] = counts,
                    ["written"] = false,
                    ["issues"] = freqIssues.Cast<object?>().ToList(),
                    ["stats"] = freqStats,
                }));
            }
            else
            {
                var total = counts.Values.OfType<long>().Sum();
                Console.WriteLine($"== nf knowledge frequency（{counts.Count} 源有事件 · 共 {total} 次）==");
                foreach (var (k, v) in counts) Console.WriteLine($"  {PadCp(k, 22)} {PyS(v)}");
                if (counts.Count == 0) Console.WriteLine("  （trace 中无 knowledge_source 事件）");
                foreach (var i in freqIssues) Console.Error.WriteLine($"  [FAIL] {i}");
                Console.WriteLine("  （未写台账；加 --write 落盘）");
            }
            return freqIssues.Count > 0 ? 1 : 0;
        }
        if (sub == "order")
        {
            var rows = KnowledgeSources.ResolveOrder(root!, knowledgeClearance is "public" or "internal" or "restricted"
                ? knowledgeClearance : "");
            if (json)
            {
                Console.WriteLine(JsonFor(new Dictionary<string, object?>
                {
                    ["clearance"] = knowledgeClearance.Length == 0 ? "不裁剪" : knowledgeClearance,
                    ["query_order"] = rows.Cast<object?>().ToList(),
                }));
            }
            else
            {
                Console.WriteLine("== nf knowledge order（查询有序：合同级 → 参考级" +
                                  (knowledgeClearance.Length > 0 ? "· 裁剪至 " + knowledgeClearance : "") + "）==");
                for (var i = 0; i < rows.Count; i++)
                {
                    var r = rows[i];
                    Console.WriteLine($"  {i + 1}. {r["id"],-22} {r["authority"],-9} {r["kind"],-18} {r["locator"]}");
                }
            }
            return 0;
        }
        if (sub == "visible")
        {
            var clearance = knowledgeClearance.Length > 0 ? knowledgeClearance : "public";
            var allowed = KnowledgeSources.VisibleIds(root!, clearance);
            var rows = KnowledgeSources.SourcesOf(root!).Select(s => new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["id"] = s.GetValueOrDefault("id")?.ToString() ?? "",
                ["visibility"] = s.GetValueOrDefault("visibility")?.ToString() ?? "",
                ["visible"] = allowed.Contains(s.GetValueOrDefault("id")?.ToString() ?? ""),
            }).ToList();
            if (json)
            {
                Console.WriteLine(JsonFor(new Dictionary<string, object?>
                {
                    ["clearance"] = clearance, ["sources"] = rows.Cast<object?>().ToList(),
                }));
            }
            else
            {
                Console.WriteLine($"== nf knowledge visible --as {clearance} ==");
                foreach (var r in rows)
                    Console.WriteLine($"  {r["id"],-22} {r["visibility"],-11} {(r["visible"] is true ? "可见" : "裁剪")}");
            }
            return 0;
        }
        if (sub == "transform")
        {
            if (positional.Count >= 3 && positional[2] is "add" or "promote")
                return Fail("knowledge transform add/promote（写面）未移植：本引擎只做只读面");
            var (issues, _, stats) = KnowledgeSources.VerifyTransform(root!);
            var entries = KnowledgeSources.LogEntries(root!);
            if (json)
            {
                Console.WriteLine(JsonFor(new Dictionary<string, object?>
                {
                    ["issues"] = issues.Cast<object?>().ToList(),
                    ["stats"] = stats,
                    ["entries"] = entries.Cast<object?>().ToList(),
                }));
            }
            else
            {
                Console.WriteLine($"== nf knowledge transform（消化记录：{stats.GetValueOrDefault("entries")} 条）==");
                foreach (var e in entries)
                    Console.WriteLine($"  {e.GetValueOrDefault("from"),-18} → {e.GetValueOrDefault("to"),-28} " +
                                      $"转正={PyBool(e.GetValueOrDefault("promoted"))}");
                foreach (var issue in issues) Console.Error.WriteLine("  [FAIL] " + issue);
                if (issues.Count == 0)
                    Console.WriteLine("  ✓ 记录与产物摘要一致（无记录 = 无转正，符合 stay-reference）");
            }
            return issues.Count == 0 ? 0 : 1;
        }
        if (sub == "lint")
        {
            var (issues, warns, stats) = KnowledgeSources.Lint(root!);
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
                Console.WriteLine("== nf knowledge lint（知识层巡检）==");
                foreach (var issue in issues) Console.Error.WriteLine("  [FAIL] " + issue);
                foreach (var warn in warns) Console.WriteLine("  [WARN] " + warn);
                if (issues.Count == 0)
                    Console.WriteLine($"  ✓ 声明/顺序/溯源/悬空/孤儿 全绿（时效缺失 {stats.GetValueOrDefault("no_stale_after")} 件已记 WARN）");
            }
            return issues.Count == 0 ? 0 : 1;
        }
        var (declIssues, declWarns, declStats) = KnowledgeSources.Scan(root!);
        if (json)
        {
            using var declDoc = JsonIo.ReadFile(Path.Combine(root!, "protocol", "knowledge_sources.json"));
            Console.WriteLine(JsonFor(new Dictionary<string, object?>
            {
                ["declaration"] = PythonJson.ToGraph(declDoc.RootElement),
                ["issues"] = declIssues.Cast<object?>().ToList(),
                ["warns"] = declWarns.Cast<object?>().ToList(),
                ["stats"] = declStats,
            }));
        }
        else
        {
            Console.WriteLine($"== nf knowledge（双源知识层 · {declStats.GetValueOrDefault("sources")} 源：" +
                              $"合同 {declStats.GetValueOrDefault("contract")} / 参考 {declStats.GetValueOrDefault("reference")}）==");
            foreach (var s in KnowledgeSources.SourcesOf(root!))
            {
                Console.WriteLine($"  {DocContractIo.PyValue(s, "id"),-22} {DocContractIo.PyValue(s, "authority"),-9} " +
                                  $"{DocContractIo.PyValue(s, "kind"),-18} {DocContractIo.PyValue(s, "visibility"),-10} " +
                                  $"{DocContractIo.PyValue(s, "locator")}");
            }
            foreach (var warn in declWarns) Console.WriteLine("  [WARN] " + warn);
            foreach (var issue in declIssues) Console.Error.WriteLine("  [FAIL] " + issue);
            if (declIssues.Count == 0)
                Console.WriteLine("  ✓ 权威分层/查询有序/时效/晋升/审核/认知裁剪 全部与判据一致");
        }
        return declIssues.Count == 0 ? 0 : 1;
    }

    private static string PyBool(object? value) => value is true ? "True" : "False";

    private static int StateFrontCommand()
    {
        // `nf state-front <path> [--check|--ab] [--mode front|back|none] [--json]`：全只读面（--out 写面未移植）。
        if (positional.Count < 2) return Fail("state-front 需要一个产物 md 路径");
        var target = positional[1];
        var full = Path.IsPathRooted(target) ? target : Path.Combine(root!, target.Replace('/', Path.DirectorySeparatorChar));
        if (!File.Exists(full)) { Console.Error.WriteLine($"  ✗ 找不到文件：{full}"); return 1; }
        var text = new System.Text.UTF8Encoding(false, true).GetString(File.ReadAllBytes(full));

        if (stateFrontAb)
        {
            var manifest = StateFront.AbManifest(text);
            if (json)
            {
                Console.WriteLine(JsonFor(manifest));
            }
            else
            {
                Console.WriteLine("== nf state-front --ab（三刺激件清单 · 不调模型）==");
                foreach (var mode in new[] { "front", "back", "none" })
                {
                    var entry = (Dictionary<string, object?>)manifest[mode]!;
                    var sha = ((string)entry["sha256"]!)[..16];
                    var stateFront = entry["state_front"] is true ? "True" : "False";
                    Console.WriteLine($"  {mode,-6} chars {entry["chars"],6} · sha256 {sha} · 状态块前置={stateFront}");
                }
            }
            return 0;
        }
        if (stateFrontCheck)
        {
            var issues = StateFront.CheckOrder(text);
            if (json)
            {
                Console.WriteLine(JsonFor(new Dictionary<string, object?>
                {
                    ["issues"] = issues.Cast<object?>().ToList(),
                }));
            }
            else
            {
                Console.WriteLine($"== nf state-front --check（{target}）==");
                foreach (var issue in issues) Console.WriteLine("  [FAIL] " + issue);
                if (issues.Count == 0) Console.WriteLine("  ✓ 状态块已前置（条件先行）");
            }
            return issues.Count == 0 ? 0 : 1;
        }
        var output = StateFront.Reorder(text, stateFrontMode);
        if (outPath is not null)
            return Fail("state-front --out（写面）未移植：本引擎只做只读面（--check / --ab / 排布预览）");
        if (json)
        {
            // 同 Python：这里用的是 **非缩进** json.dumps（默认分隔符 ", " / ": "、不排序键）
            var chars = PyScalar.PyLen(output);
            var front = StateFront.CheckOrder(output).Count == 0;
            Console.WriteLine("{\"kind\": \"state-front\", \"mode\": " + PythonJson.Quote(stateFrontMode) +
                              ", \"chars\": " + chars +
                              ", \"state_front\": " + (front ? "true" : "false") + "}");
        }
        else
        {
            Console.WriteLine($"== nf state-front（{target} → {stateFrontMode}）==");
            Console.WriteLine($"  输出长度 {PyScalar.PyLen(output)} 字符 · 状态块前置=" +
                              $"{(StateFront.CheckOrder(output).Count == 0 ? "True" : "False")}");
        }
        return 0;
    }

    // 把三件治理契约的 scan 结果统一成 CLI 面所需的形状
    private static (List<string> Issues, List<string> Warns, Dictionary<string, object?> Stats, string Glob,
        string[] ListKeys, string Kind) Wrap(
        (List<string> Issues, List<string> Warns, Dictionary<string, object?> Stats) result,
        string glob, string[] listKeys, string kind) => (result.Issues, result.Warns, result.Stats, glob, listKeys, kind);

}
