using System.Text.Json;
using Nf.Engine;

internal static partial class Program
{
    private static int WorldModelCommand()
    {
        var (issues, stats) = WorldModel.Scan(root!);

        // 具体状态（--state）：JSON 文件，缺 / 解析失败即受控失败（与 Python 的 OSError/JSONDecodeError 同向）
        Dictionary<string, object?>? concrete = null;
        if (!string.IsNullOrEmpty(worldModelState))
        {
            var path = Path.IsPathRooted(worldModelState) ? worldModelState : Path.Combine(root!, worldModelState);
            try
            {
                using var doc = JsonIo.ReadFile(path);
                concrete = PythonJson.ToGraph(doc.RootElement) as Dictionary<string, object?>;
            }
            catch (Exception exc) when (exc is IOException or System.Text.Json.JsonException)
            {
                Console.Error.WriteLine($"  ✗ {exc.Message}");
                return 1;
            }
        }

        // --run / --walk：对每个模型重放（契约从模块文档里现读，与 Python 的 _load 同源）
        var models = (stats.GetValueOrDefault("models") as List<object?> ?? new List<object?>())
            .OfType<Dictionary<string, object?>>().ToList();
        if (worldModelRun && json)
        {
            var runs = new List<object?>();
            foreach (var model in models)
            {
                var result = RunWorldModel(root!, model, concrete);
                if (result is null) continue;
                runs.Add(new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["module"] = model.GetValueOrDefault("module"),
                    ["source"] = model.GetValueOrDefault("source"),
                    ["result"] = result,
                });
            }
            Console.WriteLine(PythonJson.Indented(new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["kind"] = "worldmodel-run",
                ["issues"] = issues.Cast<object?>().ToList(),
                ["runs"] = runs,
            }));
            return issues.Count > 0 ? 1 : 0;
        }
        if (json)
        {
            Console.WriteLine(PythonJson.Indented(new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["kind"] = "worldmodel",
                ["issues"] = issues.Cast<object?>().ToList(),
                ["stats"] = stats,
            }));
        }
        else
        {
            string N(string key) => stats.TryGetValue(key, out var v) && v is not null
                ? Convert.ToInt64(v, System.Globalization.CultureInfo.InvariantCulture).ToString()
                : "0";
            Console.WriteLine("== nf worldmodel（JEPA-inspired 确定性抽象状态契约 · check32 硬门）==");
            Console.WriteLine($"  模块 {N("modules")} · 变量 {N("variables")} · 相位 {N("phases")} · " +
                              $"不变式 {N("invariants")} · checks {N("checks")} · slots {N("slots")}/{N("slot_registry")}");
            foreach (var node in (stats.GetValueOrDefault("models") as List<object?> ?? new List<object?>()))
            {
                var m = node as Dictionary<string, object?>;
                if (m is null) continue;
                Console.WriteLine($"  · {PyS(m["module"])}（{PyS(m["source"])} · initial={PyS(m["initial_phase"])} · " +
                                  $"{PyS(m["phases"])} phases · {PyS(m["invariants"])} invariants · {PyS(m["checks"])} checks）");
            }
            if (worldModelWalk)
            {
                foreach (var model in models)
                {
                    var contract = LoadWorldModel(root!, model);
                    if (contract is null) continue;
                    var (sequence, reason, repeat) = WorldModel.PhaseSequence(contract);
                    Console.WriteLine($"  → {PyS(model["module"])} 重放：{string.Join(" → ", sequence)}" +
                                      $"（终止={reason}" + (repeat is null ? "" : $" · 重复={repeat}") + "）");
                }
            }
            if (worldModelRun)
            {
                foreach (var model in models)
                {
                    var result = RunWorldModel(root!, model, concrete);
                    if (result is null) continue;
                    var steps = (result.GetValueOrDefault("steps") as List<object?> ?? new List<object?>())
                        .OfType<Dictionary<string, object?>>().ToList();
                    var repeat = result.GetValueOrDefault("repeat");
                    Console.WriteLine($"  → {PyS(model["module"])} 运行：{steps.Count} steps（" +
                                      $"{PyS(result.GetValueOrDefault("reason"))}" +
                                      (repeat is null ? "" : $" · 重复={PyS(repeat)}") +
                                      $" · digest={PyS(result.GetValueOrDefault("digest"))[..12]}）");
                    foreach (var step in steps)
                    {
                        Console.WriteLine($"    {PyS(step["step"])}. {PyS(step["phase_from"])} → " +
                                          $"{PyS(step["phase_to"])}（guard={PyS(step["guard"])}）");
                    }
                }
            }
            foreach (var i in issues) Console.Error.WriteLine($"  [FAIL] {i}");
        }
        return issues.Count > 0 ? 1 : 0;
    }

    /// <summary>从模块文档里现读 <c>machine_contract.world_model</c>（等价 Python <c>_load</c>）。</summary>
    private static Dictionary<string, object?>? LoadWorldModel(string root, Dictionary<string, object?> model)
    {
        var source = model.GetValueOrDefault("source") as string ?? "";
        var abs = Path.Combine(root, source.Replace('/', Path.DirectorySeparatorChar));
        var mc = ModuleContracts.MachineContractOf(abs);
        return mc?.GetValueOrDefault("world_model") as Dictionary<string, object?>;
    }

    /// <summary>跑一个模型的重放（有具体状态则 replay_concrete，否则 replay）；违例 → 受控失败。</summary>
    private static Dictionary<string, object?>? RunWorldModel(string root, Dictionary<string, object?> model,
    Dictionary<string, object?>? concrete)
    {
        var contract = LoadWorldModel(root, model);
        if (contract is null) return null;
        var runtime = new WorldModel.Runtime(contract);
        return concrete is not null ? runtime.ReplayConcrete(concrete) : runtime.Replay();
    }

    // 构建回路（check33 第 16 条 · core/workloop.py）：`--list` 列候选、默认出工单（stub 适配器离线确定性）。
    // **写面不移植**：`--write` 落 `.rivet/` 内部档案、`--close` 收口记档，都明确拒绝（只读门不落盘）。
    private static int WorkloopCommand()
    {
        if (writeRequested)
        {
            Console.Error.WriteLine("错误：--write 是写面（工单落 .rivet/private_archive/work_orders，属内部档案）"
                                    + "——只读门不落盘，不提供");
            return 2;
        }
        if (closeFlag.Length > 0)
        {
            Console.Error.WriteLine("错误：--close 是写面（回收结果写 .rivet/ 记档）——只读门不落盘，不提供");
            return 2;
        }
        var source = sourceFlag ?? "";
        if (workloopList)
        {
            var rows = Workloop.Items(root!, Math.Max(1, topCount), source);
            if (json)
            {
                Console.WriteLine(JsonFor(rows.Cast<object?>().ToList()));
                return 0;
            }
            foreach (var it in rows)
            {
                Console.WriteLine("  " + PadCp(PyS(it["id"]), 28) + " " + PadCp(PyS(it["kind"]), 16)
                                  + " " + PyS(it["title"]));
            }
            Console.WriteLine($"  （共 {Workloop.Items(root!, source: source).Count} 项在册"
                              + (source.Length > 0 ? $"（来源限定 {source}）" : "")
                              + "；这是决策层的候选面）");
            return 0;
        }
        if (adapterFlag != "stub")
        {
            Console.Error.WriteLine($"错误：适配器 {adapterFlag} 走外呼（端点类），属声明边界——"
                                    + "引擎只保留 fail-closed 分支，不发起网络写面");
            return 2;
        }
        var doc = Workloop.Plan(root!, adapterFlag, Math.Max(1, topCount), source);
        if (json)
        {
            Console.WriteLine(JsonFor(doc));
        }
        else
        {
            Console.WriteLine(Workloop.RenderBrief(doc));
        }
        return PyS(doc.GetValueOrDefault("status")) == "ok" ? 0 : 1;
    }

    // 图书馆许可证门（core/license_gate.py）：登记行「许可」列 + 条目内联声明双源校验。
    private static int LicenseCommand()
    {
        var scan = LicenseGate.Scan(root!);
        if (json)
        {
            Console.WriteLine(JsonFor(new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["issues"] = scan.Issues.Cast<object?>().ToList(),
                ["stats"] = scan.Stats,
            }));
            return scan.Issues.Count > 0 ? 1 : 0;
        }
        var stats = scan.Stats;
        var undeclared = AsObjList(stats.GetValueOrDefault("undeclared"));
        var noInline = AsObjList(stats.GetValueOrDefault("no_inline"));
        var mismatched = AsObjList(stats.GetValueOrDefault("mismatched"));
        var warnings = AsObjList(stats.GetValueOrDefault("warnings"));
        Console.WriteLine("== nf license（图书馆许可证门）==");
        Console.WriteLine($"  登记 {PyS(stats.GetValueOrDefault("entries"))} 件"
                          + $" · 已声明 {PyS(stats.GetValueOrDefault("declared"))}"
                          + $" · 未声明 {undeclared.Count} · 无内联 {noInline.Count}"
                          + $" · 双源不一致 {mismatched.Count}");
        foreach (var issue in scan.Issues) Console.Error.WriteLine($"  [FAIL] {issue}");
        foreach (var warn in warnings) Console.WriteLine($"  [WARN] {PyS(warn)}");
        if (scan.Issues.Count == 0)
            Console.WriteLine("  ✓ 许可面无 FAIL（WARN 为待投稿人回填项，不阻断入库）");
        return scan.Issues.Count > 0 ? 1 : 0;
    }

    // 基线相对回归评分（check33 第 3 条 · core/regression_score.py）。**声明边界**：信号源 `purity_scan`
    // 是源码 AST linter 面，本引擎不复算——文本面显式打一行 UNKNOWN，机读面在 `boundary` 清单里列名，
    // 既不静默丢弃也不伪造 1.0（故本面不进「逐字节一致」清单，按边界面单独断言）。
    // `--write-baseline` 是写面（改基线件），明确拒绝。
    private static int ScoreCommand()
    {
        if (scoreWriteBaseline)
        {
            Console.Error.WriteLine("错误：--write-baseline 是写面（改写基线件 protocol/score_baseline.json）"
                                    + "——只读门不落盘，不提供");
            return 2;
        }
        var current = RegressionScore.Evaluate(root!);
        var baseRel = scoreBaselinePath.Length > 0 ? scoreBaselinePath : RegressionScore.DefaultBaselineRel;
        var basePath = Path.IsPathRooted(baseRel) ? baseRel : Path.Combine(root!, baseRel);
        var baseline = File.Exists(basePath)
            ? RegressionScore.LoadBaseline(basePath)
            : new Dictionary<string, object?>(StringComparer.Ordinal) { ["schema"] = RegressionScore.Schema };
        var effectiveTolerance = scoreTolerance ?? 0.0;
        var comparison = RegressionScore.Compare(current, baseline, effectiveTolerance);
        if (json)
        {
            Console.WriteLine(PythonJson.Indented(new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["current"] = current, ["compare"] = comparison,
            }));
            return comparison["ok"] is true ? 0 : 1;
        }
        Console.WriteLine("== nf score（基线相对回归评分）==");
        Console.WriteLine($"  当前 {F2(current.GetValueOrDefault("score"))}"
                          + $" · 基线 {F2(comparison["baseline_score"])}"
                          + $" · delta {SignedF2(comparison["delta"])}"
                          + $" · 容差 {F2(effectiveTolerance)}");
        Console.WriteLine("  " + PyS(comparison["verdict"]));
        foreach (var signal in current["signals"] as List<object?> ?? new List<object?>())
        {
            var row = (Dictionary<string, object?>)signal!;
            Console.WriteLine($"  · {PadCp(PyS(row["name"]), 18)} w={F2(row["weight"])} v={F2(row["value"])}");
        }
        Console.WriteLine($"  · {PadCp(RegressionScore.BoundarySignals[0], 18)} w=0.15 "
                          + "v=UNKNOWN（声明边界：源码 AST linter 面，本引擎不复算，不伪造）");
        foreach (var item in comparison["regressed"] as List<object?> ?? new List<object?>())
        {
            var row = (Dictionary<string, object?>)item!;
            Console.Error.WriteLine($"    [REGRESS] {PyS(row["signal"])} {F4(row["from"])} → {F4(row["to"])}"
                                     + $"（{F4(row["drop"])}）");
        }
        return comparison["ok"] is true ? 0 : 1;
    }

    private static string F2(object? v) => ((double)Convert.ToDouble(v, System.Globalization.CultureInfo.InvariantCulture))
    .ToString("F2", System.Globalization.CultureInfo.InvariantCulture);

    private static string F4(object? v) => ((double)Convert.ToDouble(v, System.Globalization.CultureInfo.InvariantCulture))
    .ToString("F4", System.Globalization.CultureInfo.InvariantCulture);

    private static string SignedF2(object? v)
    {
        var d = Convert.ToDouble(v, System.Globalization.CultureInfo.InvariantCulture);
        var text = d.ToString("F2", System.Globalization.CultureInfo.InvariantCulture);
        return d >= 0 ? "+" + text : text;
    }

    // 决策层统一入口（core/decision_layer.py · check33 第 15 条）：
    // `--dry-run` 走声明面体检；默认把 typed-decision 请求交给适配器（stub 离线确定性）。
    // **端口边界**：端点类适配器（systemone-http / openai-json）只保留 fail-closed 分支——引擎不发起外呼，
    // 参数齐备时输出 abstained 并注明「引擎不发起外呼」（与 DecisionLayer 同一条边界）。
    private static int DecideCommand()
    {
        var inv = System.Globalization.CultureInfo.InvariantCulture;
        string Fmt(object? value, string format) =>
            Convert.ToDouble(value ?? 0.0, inv).ToString(format, inv);

        if (questionsPath is null)
        {
            Console.Error.WriteLine("错误：decide 需要 --questions <问题 JSON 文件>");
            return 2;
        }
        if (decideDryRun)
        {
            var scan = DecisionLayer.Scan(root!);
            if (json)
            {
                Console.WriteLine(JsonFor(new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["issues"] = scan.Issues.Cast<object?>().ToList(),
                    ["stats"] = scan.Stats,
                }));
            }
            else
            {
                foreach (var issue in scan.Issues) Console.Error.WriteLine($"  [FAIL] {issue}");
                if (scan.Issues.Count == 0)
                    Console.WriteLine($"  ✓ 决策层面体检通过（{scan.SummaryLine}）");
            }
            return scan.Issues.Count > 0 ? 1 : 0;
        }
        var state = decideStateText;
        if (decideStatePath is not null)
            state = File.ReadAllText(decideStatePath, new System.Text.UTF8Encoding(false, true));
        Dictionary<string, object?> questions;
        using (var doc = JsonIo.ReadFile(questionsPath))
        {
            questions = PythonJson.ToGraph(doc.RootElement) as Dictionary<string, object?>
                        ?? new Dictionary<string, object?>(StringComparer.Ordinal);
        }
        var request = new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["state"] = state, ["questions"] = questions,
        };
        var output = DecisionLayer.Decide(request, adapterFlag, endpointFlag, modelFlag, root!);
        if (json)
        {
            Console.WriteLine(JsonFor(output));
        }
        else if (PyS(output.GetValueOrDefault("status")) == "abstained")
        {
            Console.WriteLine($"  ⚠ abstained：{PyS(output.GetValueOrDefault("reason"))}");
        }
        else
        {
            foreach (var pair in output.GetValueOrDefault("answers") as Dictionary<string, object?>
                     ?? new Dictionary<string, object?>(StringComparer.Ordinal))
            {
                var ans = pair.Value as Dictionary<string, object?>
                          ?? new Dictionary<string, object?>(StringComparer.Ordinal);
                var type = PyS(ans.GetValueOrDefault("type"));
                if (type == "choice")
                {
                    var options = AsObjList(ans.GetValueOrDefault("options"));
                    var probs = AsObjList(ans.GetValueOrDefault("probs"));
                    var argmax = ans.GetValueOrDefault("argmax");
                    var index = options.FindIndex(o => PyScalar.PyEquals(o, argmax));
                    var p = options.Count > 0 && index >= 0 && index < probs.Count ? probs[index] : 0.0;
                    Console.WriteLine($"  {PadCp(pair.Key, 14)} choice → {PyS(argmax)}（p={Fmt(p, "F3")}）");
                }
                else if (type == "score")
                {
                    var probs = AsObjList(ans.GetValueOrDefault("probs"));
                    Console.WriteLine($"  {PadCp(pair.Key, 14)} score → 期望值 {Fmt(ans.GetValueOrDefault("value"), "F2")}"
                                      + $"（{string.Join(" ", probs.Select(x => Fmt(x, "F2")))}）");
                }
                else
                {
                    Console.WriteLine($"  {PadCp(pair.Key, 14)} noul → p(true)={Fmt(ans.GetValueOrDefault("p"), "F3")}");
                }
            }
            var meta = output.GetValueOrDefault("meta") as Dictionary<string, object?>
                       ?? new Dictionary<string, object?>(StringComparer.Ordinal);
            Console.WriteLine($"  （适配器 {PyS(meta.GetValueOrDefault("adapter"))}"
                              + $" · calibrated={PyS(meta.GetValueOrDefault("calibrated"))}"
                              + " · 决策层不出现在门禁路径）");
        }
        return PyS(output.GetValueOrDefault("status")) == "ok" ? 0 : 1;
    }

    private static int DecisionsCommand()
    {
        var result = Decisions.Verify(root!);
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
            Console.WriteLine($"== nf-dotnet decisions verify（{result.Stats["decisions"]} 条 · accepted {result.Stats["accepted"]}）==");
            foreach (var issue in result.Issues.Concat(result.Projection)) Console.WriteLine("  ✗ " + issue);
            if (failed == 0) Console.WriteLine("  ✓ 编号/状态/取代链/证据可解析/三段齐/回执锚定/INDEX 投影 全部一致");
        }
        return failed == 0 ? 0 : 1;
    }

    private static int AssertionsCommand()
    {
        var result = Assertions.Run(root!);
        var capabilities = Assertions.CapabilityReport(root!);
        if (json)
        {
            Console.WriteLine(JsonFor(new Dictionary<string, object?>
            {
                ["capabilities"] = capabilities,
                ["issues"] = result.Issues.Cast<object?>().ToList(),
                ["results"] = result.Results,
            }));
        }
        else
        {
            Console.WriteLine("== nf-dotnet assertions（数据化断言表）==");
            foreach (var row in result.Results.Cast<Dictionary<string, object?>>())
            {
                var mark = row["ok"] is true ? "✓" : "✗";
                Console.WriteLine($"  {mark} {row["id"],-40} [{row["kind"]}] {row["detail"]}");
            }
            foreach (var issue in result.Issues) Console.WriteLine("  ! " + issue);
            Console.WriteLine($"  —— 断言 {result.Results.Count} 条 · 问题 {result.Issues.Count}");
        }
        return result.Issues.Count == 0 ? 0 : 1;
    }

}
