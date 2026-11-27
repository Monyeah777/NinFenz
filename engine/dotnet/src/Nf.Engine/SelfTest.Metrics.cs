using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text;
using System.Text.RegularExpressions;

namespace Nf.Engine;

/// <summary>概念闭包 / 度量复算 / 输出门 / 辅助扫描器 / 组合域 / 模块生命周期负例。</summary>
public static partial class SelfTest
{
    // ---------------------------------------------------------------- ②⁹ᵉ 概念图闭包求值器（第 71 片）

    private static void ConceptClosureCases(List<Check> checks, string work, string repoRoot)
    {
        var root = Path.Combine(work, "concept-closure");
        if (Directory.Exists(root)) Directory.Delete(root, recursive: true);
        Directory.CreateDirectory(root);
        string Write(string name, string body)
        {
            var full = Path.Combine(root, name);
            File.WriteAllText(full, body);
            return full;
        }
        const string head = "# 合成概念图\n\n```yaml\nconcept_graph:\n  version: \"1.0\"\n  domain: 合成域\n"
                            + "  provenance_strength: domain-logic\n  provenance_legend:\n    domain-logic: 域内推理\n";
        const string nodes = "  nodes:\n"
                             + "    - id: C00\n      name: 根\n      layer: P00\n      provenance: [domain-logic]\n"
                             + "    - id: C01\n      name: 甲\n      layer: P10\n      provenance: [domain-logic]\n"
                             + "      aliases: [甲, Alpha]\n      prereqs: [C00]\n"
                             + "    - id: C02\n      name: 乙\n      layer: P20\n      provenance: [domain-logic]\n"
                             + "      prereqs: [C01]\n";
        const string tail = "  branches:\n    - id: main\n      nodes: [C00, C01, C02]\n"
                            + "  orderings:\n    - id: seq\n      seq: [C00, C01, C02]\n```\n";
        var healthy = Write("healthy.md", head + nodes + tail);

        // ① 图语义主线：健康图零问题；闭包 / 缺失 / 就绪 / 拓扑序 / 别名解析都对
        var graph = ConceptGraph.LoadGraph(healthy);
        var closure = ConceptGraph.Closure(graph, "C02");
        var order = ConceptGraph.Toposort(graph);
        checks.Add(new Check("概念图·语义主线（健康图零问题 · 闭包/拓扑序/别名解析）",
            ConceptGraph.Problems(graph).Count == 0
            && string.Join(",", closure) == "C00,C01,C02"
            && string.Join(",", order) == "C00,C01,C02"
            && ConceptGraph.Resolve(graph, "Alpha") == "C01"
            && ConceptGraph.Resolve(graph, "  甲  ") == "C01"
            && ConceptGraph.Missing(graph, "C02", new[] { "C01" }).Count == 2
            && string.Join(",", ConceptGraph.Frontier(graph, new[] { "C00" })) == "C01"
            && ConceptGraph.Violations(graph, new[] { "C02", "C01", "C00" }).Count == 2,
            $"闭包 {string.Join(",", closure)} · 序 {string.Join(",", order)}"));

        // ② problems() 逐条判据各触发一次（环 / 悬空 / 自环 / 重复 id / 缺 name / 缺 provenance / 图例漂移 / 层位）
        var expectations = new (string Name, string Body, string Need)[]
        {
            ("环", head + nodes.Replace("      prereqs: [C00]\n", "      prereqs: [C00, C02]\n") + tail, "环"),
            ("悬空", head + nodes.Replace("      prereqs: [C01]\n", "      prereqs: [C01, C99]\n") + tail, "悬空前置"),
            ("自环", head + nodes.Replace("      prereqs: [C00]\n", "      prereqs: [C01]\n") + tail, "自环"),
            ("重复id", head + nodes.Replace("    - id: C02\n", "    - id: C01\n") + tail, "节点 id 重复"),
            ("缺name", head + nodes.Replace("      name: 甲\n", "") + tail, "缺 name"),
            ("图例漂移", head + nodes.Replace("      provenance: [domain-logic]\n      aliases: [甲, Alpha]\n",
                "      provenance: [external-x]\n      aliases: [甲, Alpha]\n") + tail, "不在 provenance_legend 中"),
            ("层位越界", head + nodes.Replace("      layer: P10\n", "      layer: P99\n") + tail, "层位越界"),
            ("缺强度声明", head.Replace("  provenance_strength: domain-logic\n", "") + nodes + tail,
                "缺 provenance_strength 声明"),
            ("别名重复", head + nodes.Replace("      aliases: [甲, Alpha]\n", "      aliases: [甲, Alpha, 乙]\n")
                .Replace("      name: 乙\n", "      name: 乙\n      aliases: [乙]\n") + tail, "别名重复"),
            ("未归分支", head + nodes + tail.Replace("nodes: [C00, C01, C02]", "nodes: [C00, C01]"), "未归入任何分支"),
        };
        var misses = new List<string>();
        foreach (var (name, body, need) in expectations)
        {
            var issues = ConceptGraph.Problems(ConceptGraph.LoadGraph(Write($"bad-{name}.md", body)));
            if (!issues.Any(i => i.Contains(need, StringComparison.Ordinal))) misses.Add(name);
        }
        checks.Add(new Check("概念图·problems 逐条判据真的在判（十类注入各命中一次）",
            misses.Count == 0, misses.Count == 0 ? "十类全部命中" : "未命中：" + string.Join("、", misses)));

        // ③ 取块与结构错误的文案（缺件 / 缺机读块 / 顶层键错）
        var messages = new List<string>();
        try { ConceptGraph.LoadGraph(Path.Combine(root, "不存在.md")); }
        catch (ConceptGraph.ClosureError exc) { messages.Add(exc.Message); }
        try { ConceptGraph.LoadGraph(Write("noblock.md", "# 只有散文\n")); }
        catch (ConceptGraph.ClosureError exc) { messages.Add(exc.Message); }
        // 注意：块里**没有** `concept_graph:` 标记行 → 走的是「缺机读块」；要让「结构非法」出现，
        // 标记行须在场而顶层键不是映射（与真源两条报错的分界一致）。
        try { ConceptGraph.LoadGraph(Write("wrongkey.md", "```yaml\nconcept_graph: 1\n```\n")); }
        catch (ConceptGraph.ClosureError exc) { messages.Add(exc.Message); }
        checks.Add(new Check("概念图·三条拒绝文案（缺件 / 缺机读块 / 顶层键错）",
            messages.Count == 3 && messages[0].Contains("概念图资产不存在")
            && messages[1].Contains("机器可读块") && messages[2].Contains("机读块结构非法"),
            string.Join(" | ", messages.Select(m => m[..Math.Min(24, m.Length)]))));

        // ④ 求值器人读面：条目键全表 + 缺口清单（含 CJK 按码点补齐）
        var list = DomainClosure.RenderList(graph);
        var gaps = DomainClosure.RenderGaps(graph, Array.Empty<string>(), "", 3);
        checks.Add(new Check("求值器·人读面（条目键全表 / 缺口清单 / CJK 补齐按码点）",
            list.StartsWith("== 条目键全表（3 概念 + 0 包外前置）==", StringComparison.Ordinal)
            && list.Contains("C01  [main   ] P10    甲（别名：甲、Alpha）")
            && gaps.StartsWith("== 前置缺失清单（L=0 概念 · 非空项 3）==", StringComparison.Ordinal),
            list.Split('\n')[1]));

        // ⑤ 端到端：真仓资产上跑自检（登记样例路径）与全仓图扫描
        var asset = Path.Combine(repoRoot, ConceptGraph.DefaultAsset.Replace('/', Path.DirectorySeparatorChar));
        var (fails, passes) = DomainClosure.SelfCheck(asset);
        var (scanIssues, scanStats) = ConceptGraph.Scan(repoRoot);
        checks.Add(new Check("概念图·真仓自检与全仓扫描（登记样例全过 · 图资产零问题）",
            fails.Count == 0 && passes.Count >= 14 && scanIssues.Count == 0
            && Convert.ToInt64(scanStats["graphs"]) >= 1 && Convert.ToInt64(scanStats["nodes"]) > 0,
            $"自检 {passes.Count}/{passes.Count + fails.Count} · 图 {scanStats["graphs"]} 个 / "
            + $"节点 {scanStats["nodes"]} / 边 {scanStats["edges"]} · 扫描问题 {scanIssues.Count}"));
    }

    // ---------------------------------------------------------------- ②⁹ᶠ 度量引擎复算（第 72 片 · quant_metrics / domain_metrics）

    /// <summary>
    /// **真材料的复算证据**（不是自造期望值）：拿真仓在盘的 T4 产物当期望——对每个声明
    /// `domain-report` 的包用 `DomainMetrics.Evaluate` 按 INDEX 里的 params 重算，与 `outputs/REPORT.json` 比；
    /// 量化金融域包另比 `PERFORMANCE_REPORT.json` / 两张 Vega 规格 / 一张 Mermaid 图。
    /// 这正是 `output verify` 的 `_recompute_entry` 将来要做的事——**先在这里证它算得对**。
    /// </summary>
    private static void MetricsRecomputeCases(List<Check> checks, string repoRoot, string work)
    {
        var community = Path.Combine(repoRoot, "community");
        var domainChecked = 0;
        var families = new HashSet<string>(StringComparer.Ordinal);
        var mismatches = new List<string>();
        if (Directory.Exists(community))
            foreach (var pkgDir in Directory.GetDirectories(community).OrderBy(d => d, StringComparer.Ordinal))
            {
                var indexPath = Path.Combine(pkgDir, "outputs", "INDEX.json");
                if (!File.Exists(indexPath)) continue;
                var (index, err) = OutputForms.ReadJson(indexPath);
                if (err.Length > 0 || index is not Dictionary<string, object?> idx) continue;
                foreach (var entry in ConceptGraph.PyList(idx.GetValueOrDefault("outputs"))
                             .OfType<Dictionary<string, object?>>())
                {
                    var spec = entry.GetValueOrDefault("recompute") as Dictionary<string, object?> ?? new(StringComparer.Ordinal);
                    if (PyText(spec.GetValueOrDefault("id")) != "domain-report") continue;
                    var rawParams = spec.GetValueOrDefault("params") as Dictionary<string, object?> ?? new(StringComparer.Ordinal);
                    var family = PyText(rawParams.GetValueOrDefault("family"));
                    var inputs = ConceptGraph.PyList(spec.GetValueOrDefault("inputs"));
                    if (family.Length == 0 || inputs.Count == 0) continue;
                    var rel = PyText(inputs[0]);
                    var csv = Path.Combine(pkgDir, rel.Replace('/', Path.DirectorySeparatorChar));
                    var outPath = Path.Combine(pkgDir, PyText(entry.GetValueOrDefault("path")).Replace('/', Path.DirectorySeparatorChar));
                    if (!File.Exists(csv) || !File.Exists(outPath)) continue;
                    var (rows, loadErr) = DomainMetrics.LoadRows(csv);
                    if (loadErr.Length > 0) { mismatches.Add($"{Path.GetFileName(pkgDir)}: {loadErr}"); continue; }
                    var (onDisk, diskErr) = OutputForms.ReadJson(outPath);
                    if (diskErr.Length > 0 || onDisk is not Dictionary<string, object?> expected) continue;
                    // 在盘 REPORT.json 是**生成器包装件**（kind/code/domain/family/sample/sample_rows/metrics），
                    // `metrics` 才是 evaluate() 的产物——比较必须按同一形状，否则比的是两个东西。
                    Dictionary<string, object?> metrics;
                    try
                    {
                        metrics = DomainMetrics.Evaluate(family, rows, rawParams);
                    }
                    catch (ArgumentException exc)
                    {
                        mismatches.Add($"{Path.GetFileName(pkgDir)}/{family}: 复算异常 {exc.Message}");
                        continue;
                    }
                    var fresh = new Dictionary<string, object?>(StringComparer.Ordinal)
                    {
                        ["kind"] = "nf-domain-report/1",
                        ["code"] = PyText(rawParams.GetValueOrDefault("code")) is "None" ? "" : PyText(rawParams.GetValueOrDefault("code")),
                        ["domain"] = PyText(rawParams.GetValueOrDefault("domain")) is "None" ? "" : PyText(rawParams.GetValueOrDefault("domain")),
                        ["family"] = family,
                        ["sample"] = rel,
                        ["sample_rows"] = (long)rows.Count,
                        ["metrics"] = metrics,
                    };
                    domainChecked++;
                    families.Add(family);
                    if (PythonJson.CanonicalizeGraph(fresh) != PythonJson.CanonicalizeGraph(expected))
                    {
                        var diffs = DeepDiff(fresh, expected);
                        mismatches.Add($"{Path.GetFileName(pkgDir)}/{family}"
                                       + (mismatches.Count == 0
                                           ? " ⇒ " + string.Join(" | ", diffs.Take(3))
                                           : ""));
                    }
                }
            }
        checks.Add(new Check("度量引擎·真仓 T4 复算（domain-report ↔ 在盘 REPORT.json 逐字段一致）",
            mismatches.Count == 0 && domainChecked >= 50,
            $"复算 {domainChecked} 包 · 族 {families.Count} 种（{string.Join("、", families.OrderBy(x => x, StringComparer.Ordinal))}）"
            + $" · 不一致 {mismatches.Count}{(mismatches.Count > 0 ? "：" + string.Join("、", mismatches.Take(4)) : "")}"));

        // 量化金融域包：绩效报告 + 两张 Vega 规格 + Mermaid 口径声明链（全部与在盘产物逐字段/逐字节比）
        var quant = Path.Combine(repoRoot, "community", "量化金融域包", "outputs");
        var notes = new List<string>();
        var quantOk = true;
        if (Directory.Exists(quant))
        {
            var seriesPath = Path.Combine(quant, "samples", "EQUITY_CURVE.csv");
            var (series, seriesErr) = QuantMetrics.LoadEquityCurve(seriesPath);
            quantOk = seriesErr.Length == 0;
            if (!quantOk) notes.Add("净值曲线装载失败：" + seriesErr);
            if (quantOk)
            {
                var (report, _) = OutputForms.ReadJson(Path.Combine(quant, "PERFORMANCE_REPORT.json"));
                var fresh = QuantMetrics.PerformanceReport(series,
                    "2026-06-01", "2026-08-21", currency: "CNY", returnBasis: "simple",
                    frequency: "daily", riskFreeRateAnnual: 0.015, benchmarkId: "NF-SAMPLE-INDEX",
                    costBpsFee: 3.0, costBpsSlippage: 5.0, fillRule: "next_open",
                    singleSideTurnover: true, asOf: "2026-08-21");
                var same = report is Dictionary<string, object?> onDisk
                           && PythonJson.CanonicalizeGraph(fresh) == PythonJson.CanonicalizeGraph(onDisk);
                if (!same) { quantOk = false; notes.Add("PERFORMANCE_REPORT 不一致"); }

                var (vegaEq, _) = OutputForms.ReadJson(Path.Combine(quant, "charts", "EQUITY_CURVE.vega.json"));
                var freshEq = QuantMetrics.VegaEquityCurve(series, "净值曲线（策略 vs 基准，合成样例）");
                if (vegaEq is not Dictionary<string, object?> eqDisk
                    || PythonJson.CanonicalizeGraph(freshEq) != PythonJson.CanonicalizeGraph(eqDisk))
                { quantOk = false; notes.Add("EQUITY_CURVE.vega 不一致"); }

                var (vegaDd, _) = OutputForms.ReadJson(Path.Combine(quant, "charts", "DRAWDOWN.vega.json"));
                var freshDd = QuantMetrics.VegaDrawdown(series, "回撤曲线（净值口径）");
                if (vegaDd is not Dictionary<string, object?> ddDisk
                    || PythonJson.CanonicalizeGraph(freshDd) != PythonJson.CanonicalizeGraph(ddDisk))
                { quantOk = false; notes.Add("DRAWDOWN.vega 不一致"); }

                var mmdPath = Path.Combine(quant, "charts", "DECLARATION_CHAIN.mmd");
                if (File.Exists(mmdPath))
                {
                    var expected = KnowledgeSig.Norm(File.ReadAllText(mmdPath, new System.Text.UTF8Encoding(false)));
                    if (QuantMetrics.MermaidDeclarationFlow() != expected)
                    { quantOk = false; notes.Add("DECLARATION_CHAIN.mmd 不一致"); }
                }
            }
        }
        else
        {
            quantOk = false;
            notes.Add("量化金融域包不在场");
        }
        checks.Add(new Check("度量引擎·量化四件复算（绩效报告 / 两条 Vega 规格 / Mermaid 声明链）",
            quantOk, notes.Count == 0 ? "四件逐字段/逐字节一致" : string.Join("、", notes)));

        // 金标向量：真仓夹具没走到的族与边界（calibration / 各 k / 平局 / 空串 / 带单价），
        // 期望值由真源导出（MetricsGolden 是机械导出件）——与上面的「真材料复算」互补。
        using var goldenDoc = JsonIo.Parse(MetricsGolden.GoldenJson);
        var cases = PythonJson.ToGraph(goldenDoc.RootElement) as List<object?> ?? new List<object?>();
        var goldenBad = new List<string>();
        var goldenOk = 0;
        foreach (var item in cases.OfType<Dictionary<string, object?>>())
        {
            var name = PyText(item.GetValueOrDefault("name"));
            var family = PyText(item.GetValueOrDefault("family"));
            var csv = PyText(item.GetValueOrDefault("csv"));
            var parameters = item.GetValueOrDefault("params") as Dictionary<string, object?> ?? new(StringComparer.Ordinal);
            var expected = item.GetValueOrDefault("expected");
            var csvPath = Path.Combine(work, "golden-" + name + ".csv");
            File.WriteAllText(csvPath, csv);
            var (rows, loadErr) = DomainMetrics.LoadRows(csvPath);
            if (loadErr.Length > 0) { goldenBad.Add($"{name}: {loadErr}"); continue; }
            Dictionary<string, object?> fresh;
            try
            {
                fresh = DomainMetrics.Evaluate(family, rows, parameters);
            }
            catch (ArgumentException exc)
            {
                goldenBad.Add($"{name}: {exc.Message}");
                continue;
            }
            if (PythonJson.CanonicalizeGraph(fresh) == PythonJson.CanonicalizeGraph(expected)) goldenOk++;
            else goldenBad.Add($"{name} ⇒ " + string.Join(" | ", DeepDiff(fresh, expected).Take(2)));
        }
        checks.Add(new Check("度量引擎·金标向量（未走到族与边界 · 期望值由真源导出）",
            goldenBad.Count == 0 && goldenOk >= 13,
            $"{goldenOk}/{cases.Count} 一致{(goldenBad.Count > 0 ? "：" + string.Join("、", goldenBad.Take(3)) : "")}"));
    }

    private static string PyText(object? v) => v switch
    {
        null => "None",
        string s => s,
        bool b => b ? "True" : "False",
        long l => l.ToString(System.Globalization.CultureInfo.InvariantCulture),
        int i => i.ToString(System.Globalization.CultureInfo.InvariantCulture),
        double d => PythonJson.PyFloatRepr(d),
        _ => PyScalar.PyRepr(v),
    };

    private static bool PyTruthy(object? v) => v switch
    {
        null => false,
        bool b => b,
        string s => s.Length > 0,
        long l => l != 0,
        int i => i != 0,
        double d => d != 0,
        List<object?> list => list.Count > 0,
        Dictionary<string, object?> map => map.Count > 0,
        _ => true,
    };

    /// <summary>复刻 <c>output_forms._deep_diff</c>（只取前若干条，供复算不一致时定位）。</summary>
    private static List<string> DeepDiff(object? a, object? b, string path = "$", List<string>? output = null)
    {
        output ??= new List<string>();
        if (a is Dictionary<string, object?> ma && b is Dictionary<string, object?> mb)
        {
            foreach (var k in ma.Keys.Union(mb.Keys).OrderBy(x => x, StringComparer.Ordinal))
            {
                if (!ma.ContainsKey(k)) output.Add($"{path}.{k} 仅存于在盘");
                else if (!mb.ContainsKey(k)) output.Add($"{path}.{k} 仅存于复算");
                else DeepDiff(ma[k], mb[k], $"{path}.{k}", output);
            }
        }
        else if (a is List<object?> la && b is List<object?> lb)
        {
            if (la.Count != lb.Count) output.Add($"{path} 长度 {la.Count}≠{lb.Count}");
            for (var i = 0; i < Math.Min(la.Count, lb.Count); i++) DeepDiff(la[i], lb[i], $"{path}[{i}]", output);
        }
        else if (a is long or int or double && b is long or int or double && a is not bool && b is not bool)
        {
            var da = Convert.ToDouble(a, System.Globalization.CultureInfo.InvariantCulture);
            var db = Convert.ToDouble(b, System.Globalization.CultureInfo.InvariantCulture);
            if (Math.Abs(da - db) > 1e-9)
                output.Add($"{path} 数值 {PyScalar.PyRepr(a)}≠{PyScalar.PyRepr(b)}");
        }
        else if (!PyScalar.PyEquals(a, b))
        {
            output.Add($"{path} {PyScalar.PyRepr(a)}≠{PyScalar.PyRepr(b)}");
        }
        return output;
    }

    // ---------------------------------------------------------------- ②⁹ᵍ 产出形态门禁合成（第 73 片 · verify/render/meter）

    private static void OutputGateCases(List<Check> checks, string work, string repoRoot)
    {
        // ① 真仓三件：check32 三合一零问题 / 渲染全「同」（在盘与复算一致）/ 机验率有值
        var (scanIssues, scanStats) = OutputForms.Scan(repoRoot);
        var (_, renderRows) = OutputForms.RenderOutputs(repoRoot);
        var (_, meterStats) = OutputForms.Meter(repoRoot);
        checks.Add(new Check("产出门禁·真仓三合一（check32 零问题 · 渲染全同步 · 机验率在册）",
            scanIssues.Count == 0 && renderRows.Count >= 400 && renderRows.All(r => !PyTruthy(r["changed"]))
            && (meterStats.GetValueOrDefault("packages") as Dictionary<string, object?>)?.Count >= 50
            && (scanStats.GetValueOrDefault("index") as Dictionary<string, object?>)?.GetValueOrDefault("outputs") is long,
            $"扫描问题 {scanIssues.Count} · 渲染 {renderRows.Count} 件 · 包 {((meterStats.GetValueOrDefault("packages") as Dictionary<string, object?>)?.Count ?? 0)}"));

        // ② 合成违规：形态清单（重复 id / 档位非法 / 缺可达性实证 / 缺规范入口）与包级产出（声明件不存在 / T4 无 recompute）
        var root = Path.Combine(work, "output-gate");
        if (Directory.Exists(root)) Directory.Delete(root, recursive: true);
        Directory.CreateDirectory(Path.Combine(root, "protocol"));
        Directory.CreateDirectory(Path.Combine(root, "community", "合成包", "outputs"));
        File.WriteAllText(Path.Combine(root, "protocol", "output_forms.json"), PythonJson.Indented(
            new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["schema"] = "nf-output-forms/1",
                ["categories"] = new List<object?>
                {
                    new Dictionary<string, object?>(StringComparer.Ordinal) { ["id"] = "cat", ["name"] = "类目" },
                },
                ["forms"] = new List<object?>
                {
                    new Dictionary<string, object?>(StringComparer.Ordinal)
                    {
                        ["id"] = "f1", ["category"] = "cat", ["tier"] = "T2", ["status"] = "supported",
                        ["spec"] = new Dictionary<string, object?>(StringComparer.Ordinal) { ["uri"] = "https://x" },
                        ["evidence"] = new Dictionary<string, object?>(StringComparer.Ordinal) { ["reachable"] = true },
                    },
                    new Dictionary<string, object?>(StringComparer.Ordinal)   // 重复 id + 档位非法 + 缺 uri + 缺实证
                    {
                        ["id"] = "f1", ["category"] = "cat", ["tier"] = "T9", ["status"] = "supported",
                    },
                },
            }) + "\n");
        File.WriteAllText(Path.Combine(root, "community", "合成包", "outputs", "INDEX.json"),
            PythonJson.Indented(new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["schema"] = "nf-output-index/1",
                ["package"] = "合成包",
                ["outputs"] = new List<object?>
                {
                    new Dictionary<string, object?>(StringComparer.Ordinal)
                    {
                        ["path"] = "outputs/缺失.json", ["form"] = "json", ["tier"] = "T2", ["role"] = "r",
                    },
                    new Dictionary<string, object?>(StringComparer.Ordinal)
                    {
                        ["path"] = "outputs/T4.md", ["form"] = "markdown", ["tier"] = "T4", ["role"] = "r",
                    },
                },
            }) + "\n");
        File.WriteAllText(Path.Combine(root, "community", "合成包", "outputs", "T4.md"), "# 占位\n");
        var (regIssues, _) = OutputForms.RegistryVerify(root);
        var (idxIssues, _) = OutputForms.IndexVerify(root);
        var regText = string.Join(" | ", regIssues);
        var idxText = string.Join(" | ", idxIssues);
        checks.Add(new Check("产出门禁·合成违规（清单四类 + 包级两类各自报出）",
            regText.Contains("形态 id 重复：f1") && regText.Contains("f1 档位非法")
            && regText.Contains("缺规范入口 spec.uri") && regText.Contains("缺可达性实证")
            && idxText.Contains("声明产出面不存在") && idxText.Contains("声明 T4（可复算）却无 recompute 声明"),
            "清单问题 " + regIssues.Count + " 条 · 包级问题 " + idxIssues.Count + " 条"));

        // ③ 机验率基线回退必须报（可重签工件的语义：低了就是 FAIL）
        File.WriteAllText(Path.Combine(root, "protocol", "output_forms_baseline.json"),
            PythonJson.Indented(new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["schema"] = "nf-output-forms-baseline/1",
                ["packages"] = new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["合成包"] = new Dictionary<string, object?>(StringComparer.Ordinal)
                    {
                        ["machine_verifiable"] = 9L, ["functional"] = 9L, ["prose_assets"] = 0L,
                        ["machine_verifiable_ratio"] = 1.0,
                    },
                },
                ["totals"] = new Dictionary<string, object?>(StringComparer.Ordinal),
            }) + "\n");
        var (baseIssues, _) = OutputForms.BaselineVerify(root);
        var baseText = string.Join(" | ", baseIssues);
        checks.Add(new Check("产出门禁·机验率基线回退即 FAIL（机验面与功能面各报一条）",
            baseText.Contains("机验产出面回退") && baseText.Contains("功能面（T4 可复算）回退"),
            string.Join(" | ", baseIssues)));

        // ④ `_deep_diff` 四类差异（字典并集键 / 列表长度 / 数值容差 / 值不等）
        var left = new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["a"] = 1L, ["b"] = new List<object?> { 1L, 2L }, ["c"] = "x", ["d"] = 1e-12,
        };
        var right = new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["a"] = 2L, ["b"] = new List<object?> { 1L }, ["c"] = "y", ["e"] = 1L,
        };
        var diffs = OutputForms.DeepDiff(left, right);
        var diffText = string.Join(" | ", diffs);
        checks.Add(new Check("产出门禁·复算比对器 `_deep_diff`（数值容差 · 列表长度 · 并集键 · 值不等）",
            diffText.Contains("$.a 数值 1≠2") && diffText.Contains("$.b 长度 2≠1")
            && diffText.Contains("$.c 'x'≠'y'") && diffText.Contains("$.e 仅存于在盘"),
            diffText));
    }

    // ---------------------------------------------------------------- ②⁹ʰ check32 四件子扫描器（第 74 片）

    private static void AuxScannerCases(List<Check> checks, string work, string repoRoot)
    {
        var root = Path.Combine(work, "aux-scanners");
        if (Directory.Exists(root)) Directory.Delete(root, recursive: true);
        Directory.CreateDirectory(root);
        using var doc = JsonIo.Parse(AuxGolden.GoldenJson);
        var cases = PythonJson.ToGraph(doc.RootElement) as List<object?> ?? new List<object?>();
        var bad = new List<string>();
        var byScanner = new Dictionary<string, int>(StringComparer.Ordinal);
        foreach (var item in cases.OfType<Dictionary<string, object?>>())
        {
            var name = PyText(item.GetValueOrDefault("name"));
            var scanner = PyText(item.GetValueOrDefault("scanner"));
            var expected = (Dictionary<string, object?>)item.GetValueOrDefault("expected")!;
            // `files` 为空 = **真仓基线**（在快照上实测的期望）；非空 = 合成负例（写到临时根再跑）。
            var files = item.GetValueOrDefault("files") as Dictionary<string, object?> ?? new(StringComparer.Ordinal);
            string dir;
            if (files.Count == 0)
            {
                dir = repoRoot;
            }
            else
            {
                dir = Path.Combine(root, name.Replace("/", "-"));
                Directory.CreateDirectory(dir);
                foreach (var (rel, content) in files)
                {
                    var full = Path.Combine(dir, rel.Replace('/', Path.DirectorySeparatorChar));
                    Directory.CreateDirectory(Path.GetDirectoryName(full)!);
                    File.WriteAllText(full, PyText(content));
                }
            }
            var (issues, stats) = scanner switch
            {
                "world_slots" => AuxScanners.WorldSlotsScan(dir),
                "instruction_step_audit" => AuxScanners.InstructionStepAudit(dir),
                "payload_registry" => AuxScanners.PayloadRegistryScan(dir),
                "payload_consumer" => AuxScanners.PayloadConsumerScan(dir),
                _ => (new List<string>(), new Dictionary<string, object?>(StringComparer.Ordinal)),
            };
            byScanner[scanner] = byScanner.GetValueOrDefault(scanner) + 1;
            var issuesOk = issues.SequenceEqual(
                ConceptGraph.PyList(expected.GetValueOrDefault("issues")).Select(PyText), StringComparer.Ordinal);
            var statsOk = PythonJson.CanonicalizeGraph(stats)
                          == PythonJson.CanonicalizeGraph(expected.GetValueOrDefault("stats"));
            if (!issuesOk || !statsOk)
            {
                var detail = issuesOk ? "" : "issues：" + string.Join(" | ", issues);
                if (!statsOk)
                    detail += (detail.Length > 0 ? " · " : "")
                              + "stats：" + string.Join(" | ",
                                  DeepDiff(stats, expected.GetValueOrDefault("stats")).Take(3));
                bad.Add($"{name} ⇒ {detail}");
            }
        }
        checks.Add(new Check("check32 子扫描器·金标向量（四件 · 14 条：真仓 4 + 合成负例 10）",
            bad.Count == 0 && cases.Count == 14 && byScanner.Count == 4,
            $"{cases.Count - bad.Count}/{cases.Count} 一致（各扫描器 {byScanner.Count} 件）"
            + (bad.Count > 0 ? "：" + string.Join("、", bad.Take(3)) : "")));
    }

    // ---------------------------------------------------------------- ②⁹ⁱ check32 最后两件（第 75 片 · pack_combo.scan / domain_pack.manifest_verify）

    private static void ComboDomainCases(List<Check> checks, string work, string repoRoot)
    {
        var root = Path.Combine(work, "combo-domain");
        if (Directory.Exists(root)) Directory.Delete(root, recursive: true);
        Directory.CreateDirectory(root);
        using var doc = JsonIo.Parse(ComboDomainGolden.GoldenJson);
        var cases = PythonJson.ToGraph(doc.RootElement) as List<object?> ?? new List<object?>();
        var bad = new List<string>();
        foreach (var item in cases.OfType<Dictionary<string, object?>>())
        {
            var name = PyText(item.GetValueOrDefault("name"));
            var scanner = PyText(item.GetValueOrDefault("scanner"));
            var expected = (Dictionary<string, object?>)item.GetValueOrDefault("expected")!;
            var files = item.GetValueOrDefault("files") as Dictionary<string, object?> ?? new(StringComparer.Ordinal);
            string dir;
            if (files.Count == 0)
            {
                dir = repoRoot;
            }
            else
            {
                dir = Path.Combine(root, name);
                Directory.CreateDirectory(dir);
                foreach (var (rel, content) in files)
                {
                    var full = Path.Combine(dir, rel.Replace('/', Path.DirectorySeparatorChar));
                    Directory.CreateDirectory(Path.GetDirectoryName(full)!);
                    File.WriteAllText(full, PyText(content));
                }
            }
            var (issues, stats) = scanner switch
            {
                "combo_scan" => ComboScan.Scan(dir),
                "domain_manifest" => DomainPackScan.ManifestVerify(dir),
                _ => (new List<string>(), new Dictionary<string, object?>(StringComparer.Ordinal)),
            };
            var issuesOk = issues.SequenceEqual(
                ConceptGraph.PyList(expected.GetValueOrDefault("issues")).Select(PyText), StringComparer.Ordinal);
            var statsOk = PythonJson.CanonicalizeGraph(stats)
                          == PythonJson.CanonicalizeGraph(expected.GetValueOrDefault("stats"));
            if (!issuesOk || !statsOk)
            {
                var detail = issuesOk ? "" : "issues：" + string.Join(" | ", issues);
                if (!statsOk)
                    detail += (detail.Length > 0 ? " · " : "") + "stats："
                              + string.Join(" | ", DeepDiff(stats, expected.GetValueOrDefault("stats")).Take(3));
                bad.Add($"{name} ⇒ {detail}");
            }
        }
        checks.Add(new Check("check32 子扫描器·最后两件金标向量（组合证书+广度 / 域包名录 · 6 条）",
            bad.Count == 0 && cases.Count == 6,
            $"{cases.Count - bad.Count}/{cases.Count} 一致"
            + (bad.Count > 0 ? "：" + string.Join("、", bad.Take(2)) : "")));
    }

    // ---------------------------------------------------------------- ②⁹ʲ 模块生命周期（第 76 片 · check24 同语义）

    private static void ModuleLifecycleCases(List<Check> checks, string work, string repoRoot)
    {
        var root = Path.Combine(work, "module-lifecycle");
        if (Directory.Exists(root)) Directory.Delete(root, recursive: true);
        Directory.CreateDirectory(Path.Combine(root, "04_模块库", "通用类"));
        Directory.CreateDirectory(Path.Combine(root, "community", "合成包", "modules"));
        string Module(string id, string name, string meta, string? extra = null) =>
            $"# 模块 {id} · {name}\n\n> {meta}\n\n## 职能\n\n正文。\n{extra ?? ""}";
        File.WriteAllText(Path.Combine(root, "04_模块库", "通用类", "M01_甲.md"),
            Module("M01", "甲", "类别：通用｜挂载点：P00｜状态：deprecated（口径重写）"));
        File.WriteAllText(Path.Combine(root, "04_模块库", "通用类", "M02_乙.md"),
            Module("M02", "乙", "类别：通用｜挂载点：P00｜依赖：M01、M03"));
        File.WriteAllText(Path.Combine(root, "community", "合成包", "modules", "M03_丙.md"),
            Module("M03", "丙", "类别：事件｜挂载点：P10｜状态：retired"));
        File.WriteAllText(Path.Combine(root, "community", "合成包", "protocol.yaml"),
            "id: 合成包\nmodule_ids:\n  - M03\n");

        var (issues, stats) = ModuleLifecycle.VerifyModules(root);
        var text = string.Join(" | ", issues);
        checks.Add(new Check("模块生命周期·check24 同语义（deprecated/retired 被引用即 FAIL · 三态计数）",
            issues.Count == 2
            && text.Contains("04_模块库/通用类/M01_甲.md 状态=deprecated 但仍被引用：04_模块库/通用类/M02_乙.md(依赖引用)")
            && text.Contains("community/合成包/modules/M03_丙.md 状态=retired 但仍被引用：04_模块库/通用类/M02_乙.md(依赖引用)")
            && Convert.ToInt64(stats["modules"]) == 3 && Convert.ToInt64(stats["deprecated"]) == 1
            && Convert.ToInt64(stats["retired"]) == 1 && Convert.ToInt64(stats["active"]) == 1,
            $"问题 {issues.Count} · 模块 {stats["modules"]} · deprecated {stats["deprecated"]} · retired {stats["retired"]}"));

        // 真仓：248 模块全 active、引用门禁全绿、清单行数与模块数一致
        var (realIssues, realStats) = ModuleLifecycle.VerifyModules(repoRoot);
        var rows = ModuleLifecycle.Rows(repoRoot);
        checks.Add(new Check("模块生命周期·真仓（248 模块全 active · 引用门禁全绿 · ls 行数一致）",
            realIssues.Count == 0 && Convert.ToInt64(realStats["modules"]) == rows.Count
            && Convert.ToInt64(realStats["deprecated"]) == 0 && Convert.ToInt64(realStats["retired"]) == 0,
            $"模块 {realStats["modules"]} · ls 行 {rows.Count} · 问题 {realIssues.Count}"));

        // 状态位解析口径：缺省 active、词表外视作 active、原因与状态分离
        var noMeta = ModuleLifecycle.GetStatus("# 模块 M09 · 无元信息\n\n正文\n");
        var badWord = ModuleLifecycle.GetStatus("# 模块 M09\n\n> 状态：deprecateded\n");
        var withReason = ModuleLifecycle.GetStatus("# 模块 M09\n\n> 状态：deprecated（口径重写）\n");
        checks.Add(new Check("模块生命周期·状态位三态口径（缺省/词表外 → active · 原因与状态分离）",
            noMeta.Status == "active" && badWord.Status == "active"
            && withReason.Status == "deprecated" && withReason.Reason == "口径重写",
            $"{noMeta.Status}/{badWord.Status}/{withReason.Status}({withReason.Reason})"));
    }
}
