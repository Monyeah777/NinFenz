using System.Globalization;

namespace Nf.Engine;

/// <summary>
/// 复刻 <c>core/world_model.py</c>（第一部分）：确定性抽象状态契约的**校验与扫描**。
///
/// 定位：把「预测未来表征而非生成词元」收窄成协议层可无歧义机检的契约——
/// <c>abstract_state</c>（有限状态变量 + 初始值）· <c>transition</c>（相位图：next/guard/writes）·
/// <c>invariants</c>（长期硬约束）· <c>checks</c>（finite_phase / monotonic / finite_sequence）。
///
/// 片内推进：本件只做校验与扫描（CLI `worldmodel` 浏览面）；**重放/轨迹（`--run` / `--walk` / `--state`）
/// 属第二部分**，未移植前明确拒绝——不提供半个面。
/// </summary>
public static partial class WorldModel
{
    public static readonly HashSet<string> Kinds = new(StringComparer.Ordinal)
    {
        "string", "integer", "number", "boolean", "array",
    };

    public static readonly HashSet<string> ItemKinds = new(StringComparer.Ordinal)
    {
        "string", "integer", "number", "boolean",
    };

    /// <summary>读 M00 数据槽可绑定投影（<c>protocol/world_slots.json</c>）。</summary>
    public static Dictionary<string, Dictionary<string, object?>> LoadSlots(string root)
    {
        var path = Path.Combine(root, "protocol", "world_slots.json");
        if (!File.Exists(path)) return new Dictionary<string, Dictionary<string, object?>>(StringComparer.Ordinal);
        try
        {
            using var doc = JsonIo.ReadFile(path);
            var graph = PythonJson.ToGraph(doc.RootElement) as Dictionary<string, object?>;
            var slots = graph?.GetValueOrDefault("slots") as Dictionary<string, object?>;
            var output = new Dictionary<string, Dictionary<string, object?>>(StringComparer.Ordinal);
            if (slots is not null)
            {
                foreach (var (key, value) in slots)
                {
                    if (value is Dictionary<string, object?> map) output[key] = map;
                }
            }
            return output;
        }
        catch (Exception exc) when (exc is System.Text.Json.JsonException or IOException)
        {
            return new Dictionary<string, Dictionary<string, object?>>(StringComparer.Ordinal);
        }
    }

    /// <summary>值是否匹配声明的 kind（整数不许被 bool 冒充——Python <c>isinstance(True, int)</c> 为真，故须排除）。</summary>
    public static bool ValueMatches(object? value, string kind, string? itemKind = null)
    {
        switch (kind)
        {
            case "integer":
                return value is long && value is not bool;
            case "number":
                return (value is long or double) && value is not bool;
            case "string":
                return value is string;
            case "boolean":
                return value is bool;
            case "array":
                if (value is not List<object?> list) return false;
                return itemKind is null || list.All(v => ValueMatches(v, itemKind));
            default:
                return false;
        }
    }

    /// <summary>校验单个 world_model 契约；返回可读违例清单（逐字对齐 Python 的文案）。</summary>
    public static List<string> ValidateContract(object? wmNode, string label = "world_model",
        Dictionary<string, Dictionary<string, object?>>? slotRegistry = null)
    {
        var issues = new List<string>();
        if (wmNode is not Dictionary<string, object?> wm) return new List<string> { $"{label}: 非对象" };

        var variables = new List<Dictionary<string, object?>>();
        object? initial = null;
        if (wm.GetValueOrDefault("abstract_state") is not Dictionary<string, object?> abstractState)
        {
            issues.Add($"{label}.abstract_state: 缺失或非对象");
        }
        else
        {
            if (abstractState.GetValueOrDefault("variables") is not List<object?> varList || varList.Count == 0)
            {
                issues.Add($"{label}.abstract_state.variables: 非空数组");
            }
            else
            {
                variables = varList.OfType<Dictionary<string, object?>>().ToList();
            }
            initial = abstractState.GetValueOrDefault("initial");
            if (initial is not Dictionary<string, object?>)
            {
                issues.Add($"{label}.abstract_state.initial: 缺失或非对象");
                initial = null;
            }
        }

        var names = new List<string>();
        var slots = new List<string>();
        var validVars = new List<Dictionary<string, object?>>();
        // Python 逐 idx 遍历原始列表（非对象项也要报「非对象」）——故此处用原始列表而非 OfType 结果
        var rawVars = (wm.GetValueOrDefault("abstract_state") as Dictionary<string, object?>)
            ?.GetValueOrDefault("variables") as List<object?> ?? new List<object?>();
        for (var idx = 0; idx < rawVars.Count; idx++)
        {
            var at = $"{label}.abstract_state.variables[{idx}]";
            if (rawVars[idx] is not Dictionary<string, object?> var)
            {
                issues.Add($"{at}: 非对象");
                continue;
            }
            var name = var.GetValueOrDefault("name");
            var kind = var.GetValueOrDefault("kind");
            var source = var.GetValueOrDefault("source");
            var slot = var.GetValueOrDefault("slot");
            var itemKind = var.GetValueOrDefault("item_kind");
            if (name is not string nameStr || nameStr.Trim().Length == 0)
            {
                issues.Add($"{at}.name: 非空字符串");
            }
            else
            {
                if (names.Contains(nameStr)) issues.Add($"{at}.name: 变量重名 {PyRepr(name)}");
                names.Add(nameStr);
            }
            var kindStr = kind as string ?? "";
            if (!Kinds.Contains(kindStr)) issues.Add($"{at}.kind: 非法类型 {PyRepr(kind)}");
            if (kindStr == "array")
            {
                if (itemKind is not null && !ItemKinds.Contains(itemKind as string ?? ""))
                    issues.Add($"{at}.item_kind: 非法元素类型 {PyRepr(itemKind)}");
            }
            else if (itemKind is not null)
            {
                issues.Add($"{at}.item_kind: 仅 kind=array 可用");
            }
            if (source is not string sourceStr || sourceStr.Trim().Length == 0)
                issues.Add($"{at}.source: 非空字符串");
            if (slot is not null)
            {
                if (slot is not string slotStr || slotStr.Trim().Length == 0)
                {
                    issues.Add($"{at}.slot: 非空字符串");
                }
                else if (slots.Contains(slotStr))
                {
                    issues.Add($"{at}.slot: 槽位重复 {PyRepr(slot)}");
                }
                else
                {
                    slots.Add(slotStr);
                }
            }
            validVars.Add(var);
        }

        if (initial is Dictionary<string, object?> initialMap)
        {
            var declared = validVars.Select(v => v.GetValueOrDefault("name")).OfType<string>().ToList();
            foreach (var key in initialMap.Keys.OrderBy(k => k, StringComparer.Ordinal))
            {
                if (!declared.Contains(key)) issues.Add($"{label}.abstract_state.initial: 未声明变量 {PyRepr(key)}");
            }
            foreach (var var in validVars)
            {
                if (var.GetValueOrDefault("name") is not string name) continue;
                if (!initialMap.TryGetValue(name, out var value))
                {
                    issues.Add($"{label}.abstract_state.initial: 缺变量 {PyRepr(name)} 的初始值");
                    continue;
                }
                var kind = var.GetValueOrDefault("kind") as string ?? "";
                var itemKind = var.GetValueOrDefault("item_kind") as string;
                if (Kinds.Contains(kind) && !ValueMatches(value, kind, itemKind))
                {
                    issues.Add($"{label}.abstract_state.initial.{name}: 值 {PyRepr(value)} 不匹配 kind={PyRepr(kind)}");
                }
            }
        }

        object? initialPhase = null;
        var phases = new List<Dictionary<string, object?>>();
        var rawPhases = new List<object?>();
        if (wm.GetValueOrDefault("transition") is not Dictionary<string, object?> transition)
        {
            issues.Add($"{label}.transition: 缺失或非对象");
        }
        else
        {
            initialPhase = transition.GetValueOrDefault("initial_phase");
            if (transition.GetValueOrDefault("phases") is List<object?> list && list.Count > 0)
            {
                rawPhases = list;
                phases = list.OfType<Dictionary<string, object?>>().ToList();
            }
            else
            {
                issues.Add($"{label}.transition.phases: 非空数组");
            }
            if (initialPhase is not string ip || ip.Trim().Length == 0)
            {
                issues.Add($"{label}.transition.initial_phase: 非空字符串");
                initialPhase = null;
            }
        }

        var phaseNames = new List<string>();
        var edges = new Dictionary<string, string>(StringComparer.Ordinal);
        for (var idx = 0; idx < rawPhases.Count; idx++)
        {
            var at = $"{label}.transition.phases[{idx}]";
            if (rawPhases[idx] is not Dictionary<string, object?> phase)
            {
                issues.Add($"{at}: 非对象");
                continue;
            }
            var pname = phase.GetValueOrDefault("phase");
            var next = phase.GetValueOrDefault("next");
            var guard = phase.GetValueOrDefault("guard");
            var writes = phase.GetValueOrDefault("writes");
            if (pname is not string pnameStr || pnameStr.Trim().Length == 0)
            {
                issues.Add($"{at}.phase: 非空字符串");
                continue;
            }
            if (phaseNames.Contains(pnameStr)) issues.Add($"{at}.phase: 相位重名 {PyRepr(pname)}");
            phaseNames.Add(pnameStr);
            if (next is not string nextStr || nextStr.Trim().Length == 0)
                issues.Add($"{at}.next: 非空字符串");
            if (guard is not string guardStr || guardStr.Trim().Length == 0)
                issues.Add($"{at}.guard: 非空守卫说明");
            if (writes is not List<object?> || ((List<object?>)writes).Any(w => w is not string ws || ws.Trim().Length == 0))
                issues.Add($"{at}.writes: 字符串数组（可为空）");
            if (pname is string p && next is string n) edges[p] = n;
        }

        var phaseSet = phaseNames.ToHashSet(StringComparer.Ordinal);
        if (initialPhase is string initialPhaseStr && !phaseSet.Contains(initialPhaseStr))
            issues.Add($"{label}.transition.initial_phase: {PyRepr(initialPhase)} 不在 phases 内");
        foreach (var (pname, next) in edges)
        {
            if (!phaseSet.Contains(next))
                issues.Add($"{label}.transition.phases[{PyRepr(pname)}].next: {PyRepr(next)} 无对应相位");
        }

        if (initialPhase is string startPhase && phaseSet.Contains(startPhase)
            && edges.Values.All(phaseSet.Contains))
        {
            var seen = new HashSet<string>(StringComparer.Ordinal) { startPhase };
            var frontier = new Queue<string>();
            frontier.Enqueue(startPhase);
            while (frontier.Count > 0)
            {
                var current = frontier.Dequeue();
                if (edges.TryGetValue(current, out var next) && seen.Add(next)) frontier.Enqueue(next);
            }
            var unreachable = phaseSet.Except(seen).OrderBy(x => x, StringComparer.Ordinal).ToList();
            if (unreachable.Count > 0)
                issues.Add($"{label}.transition: 从 initial_phase 不可达的相位 {PyScalar.PyRepr(unreachable.Cast<object?>().ToList())}");
        }

        if (wm.GetValueOrDefault("invariants") is not List<object?> invariants || invariants.Count == 0)
        {
            issues.Add($"{label}.invariants: 非空数组");
        }
        else
        {
            for (var idx = 0; idx < invariants.Count; idx++)
            {
                if (invariants[idx] is not string inv || inv.Trim().Length == 0)
                    issues.Add($"{label}.invariants[{idx}]: 非空字符串");
            }
        }

        var declaredKinds = new Dictionary<string, object?>(StringComparer.Ordinal);
        foreach (var v in validVars)
        {
            if (v.GetValueOrDefault("name") is string n) declaredKinds[n] = v.GetValueOrDefault("kind");
        }
        if (wm.TryGetValue("checks", out var checksNode) && checksNode is not null)
        {
            if (checksNode is not List<object?> checkList || checkList.Count == 0)
            {
                issues.Add($"{label}.checks: 非空数组");
            }
            else
            {
                for (var idx = 0; idx < checkList.Count; idx++)
                {
                    var at = $"{label}.checks[{idx}]";
                    if (checkList[idx] is not Dictionary<string, object?> check)
                    {
                        issues.Add($"{at}: 非对象");
                        continue;
                    }
                    var kind = check.GetValueOrDefault("kind") as string ?? "";
                    var field = check.GetValueOrDefault("field");
                    var values = check.GetValueOrDefault("values");
                    if (kind is not ("finite_phase" or "monotonic" or "finite_sequence"))
                        issues.Add($"{at}.kind: 非法检查类型 {PyRepr(check.GetValueOrDefault("kind"))}");
                    if (field is not string fieldStr || fieldStr.Trim().Length == 0)
                    {
                        issues.Add($"{at}.field: 非空字符串");
                    }
                    else if (!declaredKinds.ContainsKey(fieldStr))
                    {
                        issues.Add($"{at}.field: 未声明变量 {PyRepr(field)}");
                    }
                    if (kind is "finite_phase" or "finite_sequence")
                    {
                        if (values is not List<object?> valueList || valueList.Count == 0
                            || valueList.Any(v => v is not string vs || vs.Trim().Length == 0))
                        {
                            issues.Add($"{at}.values: {kind} 需非空字符串数组");
                        }
                    }
                    else if (kind == "monotonic")
                    {
                        var fieldKind = field is string f && declaredKinds.TryGetValue(f, out var k) ? k as string : null;
                        if (fieldKind is not ("integer" or "number"))
                            issues.Add($"{at}.field: monotonic 只能用于 integer/number 变量");
                    }
                    if (kind == "finite_sequence")
                    {
                        var spec = field is string f2
                            ? validVars.FirstOrDefault(v => v.GetValueOrDefault("name") as string == f2)
                            : null;
                        if ((spec?.GetValueOrDefault("kind") as string) != "array")
                        {
                            issues.Add($"{at}.field: finite_sequence 只能用于 array 变量");
                        }
                        else if (spec.GetValueOrDefault("item_kind") is string ik && ik != "string")
                        {
                            issues.Add($"{at}.field: finite_sequence 的 array 元素应为 string");
                        }
                    }
                }
            }
        }

        if (slotRegistry is { Count: > 0 })
        {
            foreach (var var in validVars)
            {
                if (var.GetValueOrDefault("slot") is not string slot || slot.Trim().Length == 0) continue;
                var name = var.GetValueOrDefault("name");
                var source = var.GetValueOrDefault("source");
                if (!slotRegistry.TryGetValue(slot, out var spec))
                {
                    issues.Add($"{label}.abstract_state.variables[{PyRepr(name)}].slot: " +
                               $"未在 protocol/world_slots.json 注册 {PyRepr(slot)}");
                    continue;
                }
                if (!PyEqualsPy(spec.GetValueOrDefault("kind"), var.GetValueOrDefault("kind")))
                    issues.Add($"{label}.abstract_state.variables[{PyRepr(name)}].slot: " +
                               $"类型漂移 slot={PyRepr(spec.GetValueOrDefault("kind"))} var={PyRepr(var.GetValueOrDefault("kind"))}");
                if (var.GetValueOrDefault("kind") as string == "array"
                    && var.GetValueOrDefault("item_kind") is not null
                    && !PyEqualsPy(spec.GetValueOrDefault("item_kind"), var.GetValueOrDefault("item_kind")))
                {
                    issues.Add($"{label}.abstract_state.variables[{PyRepr(name)}].slot: " +
                               $"元素类型漂移 slot={PyRepr(spec.GetValueOrDefault("item_kind"))} " +
                               $"var={PyRepr(var.GetValueOrDefault("item_kind"))}");
                }
                if (spec.GetValueOrDefault("owner") is not null && !PyEqualsPy(source, spec.GetValueOrDefault("owner")))
                    issues.Add($"{label}.abstract_state.variables[{PyRepr(name)}].slot: " +
                               $"owner 漂移 slot={PyRepr(spec.GetValueOrDefault("owner"))} var.source={PyRepr(source)}");
            }
        }

        return issues;
    }

    /// <summary>扫描全部模块文档中的 world_model 契约（返回 issues 与 stats）。</summary>
    public static (List<string> Issues, Dictionary<string, object?> Stats) Scan(string root)
    {
        var issues = new List<string>();
        var slotRegistry = LoadSlots(root);
        if (slotRegistry.Count == 0) issues.Add("protocol/world_slots.json 缺失或 slots 为空");

        long modules = 0, variables = 0, phases = 0, invariants = 0, checks = 0, slots = 0;
        var models = new List<object?>();

        foreach (var rel in ModuleDocs.Files(root))
        {
            var abs = Path.Combine(root, rel.Replace('/', Path.DirectorySeparatorChar));
            string text;
            try
            {
                text = File.ReadAllText(abs, new System.Text.UTF8Encoding(false, true));
            }
            catch (Exception exc) when (exc is IOException or System.Text.DecoderFallbackException)
            {
                issues.Add($"{rel}: 读取失败 {exc.Message}");
                continue;
            }
            var mc = ModuleContracts.MachineContractOf(abs);
            if (mc is null || !mc.TryGetValue("world_model", out var wmNode)) continue;

            issues.AddRange(ValidateContract(wmNode, $"{rel}.world_model", slotRegistry));
            modules++;
            var wm = wmNode as Dictionary<string, object?> ?? new Dictionary<string, object?>(StringComparer.Ordinal);
            var abstractState = wm.GetValueOrDefault("abstract_state") as Dictionary<string, object?>;
            var transition = wm.GetValueOrDefault("transition") as Dictionary<string, object?>;
            var invs = wm.GetValueOrDefault("invariants") as List<object?>;
            var checkList = wm.GetValueOrDefault("checks") as List<object?>;
            if (abstractState is not null)
            {
                var varList = abstractState.GetValueOrDefault("variables") as List<object?> ?? new List<object?>();
                variables += varList.Count;
                slots += varList.OfType<Dictionary<string, object?>>()
                    .Count(v => Truthy(v.GetValueOrDefault("slot")));
            }
            if (transition is not null) phases += (transition.GetValueOrDefault("phases") as List<object?>)?.Count ?? 0;
            if (invs is not null) invariants += invs.Count;
            if (checkList is not null) checks += checkList.Count;

            var modelSlots = abstractState is null
                ? 0
                : ((abstractState.GetValueOrDefault("variables") as List<object?> ?? new List<object?>())
                   .OfType<Dictionary<string, object?>>().Count(v => Truthy(v.GetValueOrDefault("slot"))));
            models.Add(new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["module"] = mc.GetValueOrDefault("id") is string id && id.Length > 0 ? id : rel,
                ["source"] = rel,
                ["initial_phase"] = transition?.GetValueOrDefault("initial_phase"),
                ["phases"] = (long)((transition?.GetValueOrDefault("phases") as List<object?>)?.Count ?? 0),
                ["invariants"] = (long)(invs?.Count ?? 0),
                ["checks"] = (long)(checkList?.Count ?? 0),
                ["slots"] = (long)modelSlots,
            });
        }

        return (issues, new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["modules"] = modules,
            ["variables"] = variables,
            ["phases"] = phases,
            ["invariants"] = invariants,
            ["checks"] = checks,
            ["slots"] = slots,
            ["slot_registry"] = (long)slotRegistry.Count,
            ["models"] = models,
        });
    }

    /// <summary>Python <c>repr()</c>（文案里用）；非 ASCII 直接输出（与 Python 一致）。</summary>
    private static string PyRepr(object? v) => PyScalar.PyRepr(v);

    private static bool PyEqualsPy(object? a, object? b) => PyScalar.PyEquals(a, b);

    // ------------------------------------------------------------------ 第二部分：相位图与运行时

    /// <summary>把 <c>world_model.transition</c> 投影成可执行的确定性相位图。</summary>
    public static Dictionary<string, object?> BuildGraph(Dictionary<string, object?> wm)
    {
        var transition = wm.GetValueOrDefault("transition") as Dictionary<string, object?> ?? new(StringComparer.Ordinal);
        var phases = new Dictionary<string, object?>(StringComparer.Ordinal);
        if (transition.GetValueOrDefault("phases") is List<object?> list)
        {
            foreach (var item in list.OfType<Dictionary<string, object?>>())
            {
                if (item.GetValueOrDefault("phase") is not string phase) continue;
                phases[phase] = new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["next"] = item.GetValueOrDefault("next"),
                    ["guard"] = item.GetValueOrDefault("guard") ?? "",
                    ["writes"] = (item.GetValueOrDefault("writes") as List<object?>)?.ToList() ?? new List<object?>(),
                };
            }
        }
        return new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["initial_phase"] = transition.GetValueOrDefault("initial_phase"),
            ["phases"] = phases,
        };
    }

    /// <summary>对 replay 的 steps 做规范 JSON 摘要，作为确定性重放指纹（等价 Python <c>trace_digest</c>）。</summary>
    public static string TraceDigest(Dictionary<string, object?> result)
    {
        var payload = PythonJson.Compact(result.GetValueOrDefault("steps") ?? new List<object?>());
        var bytes = System.Security.Cryptography.SHA256.HashData(System.Text.Encoding.UTF8.GetBytes(payload));
        return Convert.ToHexString(bytes).ToLowerInvariant();
    }
}
