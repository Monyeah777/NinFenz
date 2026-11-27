using System.Globalization;

namespace Nf.Engine;

/// <summary>运行时重放面：初始状态 / 相位推进 / 状态槽读写 / 深拷贝（<see cref="Runtime"/>）。</summary>
public static partial class WorldModel
{
    /// <summary><c>abstract_state.initial</c> 的深拷贝。</summary>
    public static Dictionary<string, object?> InitialState(Dictionary<string, object?> wm)
    {
        var abstractState = wm.GetValueOrDefault("abstract_state") as Dictionary<string, object?> ?? new(StringComparer.Ordinal);
        return (DeepCopy(abstractState.GetValueOrDefault("initial")) as Dictionary<string, object?>)
               ?? new Dictionary<string, object?>(StringComparer.Ordinal);
    }

    /// <summary>按相位图前进一步（不解释 guard，只执行已声明的确定性 next）。</summary>
    public static Dictionary<string, object?> AdvancePhase(Dictionary<string, object?> wm, Dictionary<string, object?> state)
    {
        var graph = BuildGraph(wm);
        var phase = state.GetValueOrDefault("phase");
        var phases = (Dictionary<string, object?>)graph["phases"]!;
        if (phase is not string phaseStr || !phases.TryGetValue(phaseStr, out var node))
            throw new InvalidOperationException($"当前相位未在 world_model.transition.phases 声明: {PyRepr(phase)}");
        var next = ((Dictionary<string, object?>)node!)["next"];
        var output = DeepCopy(state) as Dictionary<string, object?> ?? new(StringComparer.Ordinal);
        output["phase"] = next;
        return output;
    }

    /// <summary>从 initial_phase 重放相位序列；返回 (序列, 终止原因, 重复相位)。</summary>
    public static (List<string> Sequence, string Reason, string? Repeat) PhaseSequence(Dictionary<string, object?> wm, int limit = 100)
    {
        var graph = BuildGraph(wm);
        var current = graph.GetValueOrDefault("initial_phase");
        if (current is null) return (new List<string>(), "dangling", null);
        var sequence = new List<string>();
        var seen = new HashSet<string>(StringComparer.Ordinal);
            var currentStr = current as string ?? PyRepr(current);
        for (var i = 0; i < Math.Max(1, limit); i++)
        {
            if (seen.Contains(currentStr)) return (sequence, "cycle", currentStr);
            sequence.Add(currentStr);
            seen.Add(currentStr);
            var phases = (Dictionary<string, object?>)graph["phases"]!;
            var nextNode = phases.TryGetValue(currentStr, out var node) ? node as Dictionary<string, object?> : null;
            var next = nextNode?.GetValueOrDefault("next");
            if (next is null) return (sequence, "dangling", currentStr);
            currentStr = next as string ?? PyRepr(next);
        }
        return (sequence, "limit", currentStr);
    }

    /// <summary>可执行 world_model：状态校验 + 相位前进 + 确定性重放（等价 <c>WorldModelRuntime</c>）。</summary>
    public sealed class Runtime
    {
        private readonly Dictionary<string, object?> _contract;
        private readonly Dictionary<string, object?> _graph;
        private readonly Dictionary<string, Dictionary<string, object?>> _variables = new(StringComparer.Ordinal);
        private readonly Dictionary<string, object?> _initial;

        public Runtime(Dictionary<string, object?> contract)
        {
            var issues = ValidateContract(contract);
            if (issues.Count > 0) throw new WorldModelViolation(issues);
            _contract = contract;
            _graph = BuildGraph(contract);
            var abstractState = contract.GetValueOrDefault("abstract_state") as Dictionary<string, object?> ?? new(StringComparer.Ordinal);
            foreach (var item in (abstractState.GetValueOrDefault("variables") as List<object?> ?? new List<object?>())
                         .OfType<Dictionary<string, object?>>())
            {
                if (item.GetValueOrDefault("name") is string name) _variables[name] = item;
            }
            _initial = InitialState(contract);
        }

        public Dictionary<string, object?> Contract => _contract;
        public Dictionary<string, object?> Initial => _initial;

        /// <summary>校验运行态：变量封闭、类型匹配、结构化 checks 全部成立。</summary>
        public List<string> ValidateState(Dictionary<string, object?>? state, Dictionary<string, object?>? previous = null)
        {
            var issues = new List<string>();
            if (state is null) return new List<string> { "state 非对象" };
            var declared = _variables.Keys.ToHashSet(StringComparer.Ordinal);
            var unknown = state.Keys.Where(k => !declared.Contains(k)).OrderBy(k => k, StringComparer.Ordinal).ToList();
            var missing = declared.Where(k => !state.ContainsKey(k)).OrderBy(k => k, StringComparer.Ordinal).ToList();
            if (unknown.Count > 0)
                issues.Add($"state 含未声明变量 {PyScalar.PyRepr(unknown.Cast<object?>().ToList())}");
            if (missing.Count > 0)
                issues.Add($"state 缺声明变量 {PyScalar.PyRepr(missing.Cast<object?>().ToList())}");
            foreach (var (name, spec) in _variables)
            {
                if (!state.ContainsKey(name)) continue;
                if (!ValueMatches(state[name], spec.GetValueOrDefault("kind") as string ?? "",
                                  spec.GetValueOrDefault("item_kind") as string))
                {
                    issues.Add($"state.{name} 类型不匹配 kind={PyRepr(spec.GetValueOrDefault("kind"))} " +
                               $"item_kind={PyRepr(spec.GetValueOrDefault("item_kind"))}");
                }
            }
            foreach (var check in (_contract.GetValueOrDefault("checks") as List<object?> ?? new List<object?>())
                         .OfType<Dictionary<string, object?>>())
            {
                var kind = check.GetValueOrDefault("kind") as string ?? "";
                var field = check.GetValueOrDefault("field");
                var fieldName = field as string ?? "";
                if (kind == "finite_phase")
                {
                    var values = (check.GetValueOrDefault("values") as List<object?> ?? new List<object?>())
                        .Select(PyRepr).ToHashSet(StringComparer.Ordinal);
                    if (state.ContainsKey(fieldName) && !values.Contains(PyRepr(state.GetValueOrDefault(fieldName))))
                    {
                        var sorted = (check.GetValueOrDefault("values") as List<object?> ?? new List<object?>())
                            .OrderBy(PyRepr, StringComparer.Ordinal).Cast<object?>().ToList();
                        issues.Add($"check finite_phase：{fieldName}={PyRepr(state.GetValueOrDefault(fieldName))} " +
                                   $"不在 {PyScalar.PyRepr(sorted)}");
                    }
                }
                else if (kind == "monotonic")
                {
                    if (state.ContainsKey(fieldName) && previous is not null && previous.ContainsKey(fieldName))
                    {
                        if (!ValueMatches(state[fieldName], "number") || !ValueMatches(previous[fieldName], "number"))
                        {
                            issues.Add($"check monotonic：{fieldName} 非数值");
                        }
                        else if (ToDouble(state[fieldName]) < ToDouble(previous[fieldName]))
                        {
                            issues.Add($"check monotonic：{fieldName} {PyRepr(state[fieldName])} < " +
                                       $"上一状态 {PyRepr(previous[fieldName])}");
                        }
                    }
                }
                else if (kind == "finite_sequence")
                {
                    var values = (check.GetValueOrDefault("values") as List<object?> ?? new List<object?>())
                        .Select(PyRepr).ToHashSet(StringComparer.Ordinal);
                    var seq = state.GetValueOrDefault(fieldName);
                    if (seq is not List<object?> list)
                    {
                        issues.Add($"check finite_sequence：{fieldName} 应为 array");
                    }
                    else
                    {
                        var bad = list.Where(v => !values.Contains(PyRepr(v))).ToList();
                        if (bad.Count > 0)
                            issues.Add($"check finite_sequence：{fieldName} 含非法相位 " +
                                       $"{PyScalar.PyRepr(bad.Cast<object?>().ToList())}");
                    }
                }
            }
            return issues;
        }

        /// <summary>从具体状态按 slot 路径抽取抽象状态。</summary>
        public (Dictionary<string, object?> State, List<string> Issues) ExtractState(Dictionary<string, object?> concrete)
        {
            var issues = new List<string>();
            var state = new Dictionary<string, object?>(StringComparer.Ordinal);
            foreach (var (name, spec) in _variables)
            {
                if (spec.GetValueOrDefault("slot") is not string slot || slot.Trim().Length == 0)
                {
                    issues.Add($"变量 {name} 缺 slot，无法从具体状态抽取");
                    continue;
                }
                if (!TryGetSlot(concrete, slot, out var value))
                {
                    issues.Add($"slot 路径缺失：{slot}（{name}）");
                    continue;
                }
                state[name] = value;
            }
            return (state, issues);
        }

        /// <summary>先按 slot 抽取抽象状态，再校验状态类型与 checks。</summary>
        public List<string> ValidateConcrete(Dictionary<string, object?> concrete,
            Dictionary<string, object?>? previousConcrete = null)
        {
            var (state, issues) = ExtractState(concrete);
            if (issues.Count > 0) return issues;
            Dictionary<string, object?>? previous = null;
            if (previousConcrete is not null)
            {
                var (prev, prevIssues) = ExtractState(previousConcrete);
                if (prevIssues.Count > 0) return prevIssues;
                previous = prev;
            }
            return ValidateState(state, previous);
        }

        /// <summary>前进一步；先验状态，再按相位图更新 phase 与 phase_trace（若声明）。</summary>
        public (Dictionary<string, object?> After, Dictionary<string, object?> Trace) Advance(
            Dictionary<string, object?> state, Dictionary<string, object?>? previous = null)
        {
            var issues = ValidateState(state, previous);
            if (issues.Count > 0) throw new WorldModelViolation(issues);
            var phaseFrom = state.GetValueOrDefault("phase");
            var phases = (Dictionary<string, object?>)_graph["phases"]!;
            if (phaseFrom is not string phaseFromStr || !phases.TryGetValue(phaseFromStr, out var node))
                throw new WorldModelViolation(new List<string> { $"当前相位未声明：{PyRepr(phaseFrom)}" });

            var before = (Dictionary<string, object?>)DeepCopy(state)!;
            var after = (Dictionary<string, object?>)DeepCopy(state)!;
            var transition = (Dictionary<string, object?>)node!;
            after["phase"] = transition.GetValueOrDefault("next");
            if (_variables.TryGetValue("phase_trace", out var traceSpec) && traceSpec.GetValueOrDefault("kind") as string == "array")
            {
                var chain = (state.GetValueOrDefault("phase_trace") as List<object?> ?? new List<object?>()).ToList();
                chain.Add(phaseFromStr);
                after["phase_trace"] = chain;
            }
            var trace = new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["phase_from"] = phaseFrom,
                ["phase_to"] = transition.GetValueOrDefault("next"),
                ["guard"] = transition.GetValueOrDefault("guard") ?? "",
                ["writes"] = (transition.GetValueOrDefault("writes") as List<object?>)?.ToList() ?? new List<object?>(),
                ["state_before"] = before,
                ["state_after"] = after,
            };
            return (after, trace);
        }

        /// <summary>从 initial（或给定状态）重放相位迁移，直到回到已见相位或超限。</summary>
        public Dictionary<string, object?> Replay(Dictionary<string, object?>? state = null, int maxSteps = 100)
        {
            var current = state is null
                ? (Dictionary<string, object?>)DeepCopy(_initial)!
                : (Dictionary<string, object?>)DeepCopy(state)!;
            var steps = new List<object?>();
            var seen = new HashSet<string>(StringComparer.Ordinal);
            Dictionary<string, object?>? last = null;
            var reason = "limit";
            string? repeat = null;
            for (var i = 0; i < Math.Max(1, maxSteps); i++)
            {
                var phase = current.GetValueOrDefault("phase");
                var phaseKey = PyRepr(phase);
                if (seen.Contains(phaseKey)) { reason = "cycle"; repeat = phase as string ?? phaseKey; break; }
                seen.Add(phaseKey);
                var (nextState, trace) = Advance(current, last);
                trace["step"] = (long)(steps.Count + 1);
                steps.Add(trace);
                last = current;
                current = nextState;
            }
            var result = new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["reason"] = reason,
                ["repeat"] = repeat,
                ["steps"] = steps,
                ["final_state"] = current,
            };
            result["digest"] = TraceDigest(result);
            return result;
        }

        /// <summary>从具体状态前进一步；校验、抽取、推进并写回 slot。</summary>
        public (Dictionary<string, object?> Next, Dictionary<string, object?> Trace) AdvanceConcrete(
            Dictionary<string, object?> concrete, Dictionary<string, object?>? previousConcrete = null)
        {
            var (state, extractIssues) = ExtractState(concrete);
            if (extractIssues.Count > 0) throw new WorldModelViolation(extractIssues);
            Dictionary<string, object?>? previous = null;
            if (previousConcrete is not null)
            {
                var (prev, prevIssues) = ExtractState(previousConcrete);
                if (prevIssues.Count > 0) throw new WorldModelViolation(prevIssues);
                previous = prev;
            }
            var (abstractNext, trace) = Advance(state, previous);
            var concreteNext = concrete.ToDictionary(kv => kv.Key, kv => kv.Value, StringComparer.Ordinal);
            foreach (var (name, spec) in _variables)
            {
                if (spec.GetValueOrDefault("slot") is string slot && abstractNext.ContainsKey(name))
                    concreteNext = SetSlot(concreteNext, slot, abstractNext[name]);
            }
            trace["concrete_before"] = concrete;
            trace["concrete_after"] = concreteNext;
            return (concreteNext, trace);
        }

        /// <summary>从具体状态重放，直到回到已见相位或超限。</summary>
        public Dictionary<string, object?> ReplayConcrete(Dictionary<string, object?>? concrete = null, int maxSteps = 100)
        {
            Dictionary<string, object?> current;
            if (concrete is null)
            {
                current = new Dictionary<string, object?>(StringComparer.Ordinal);
                foreach (var (name, spec) in _variables)
                {
                    if (spec.GetValueOrDefault("slot") is string slot)
                        current = SetSlot(current, slot, _initial.GetValueOrDefault(name));
                }
            }
            else
            {
                current = (Dictionary<string, object?>)DeepCopy(concrete)!;
            }

            var steps = new List<object?>();
            var seen = new HashSet<string>(StringComparer.Ordinal);
            Dictionary<string, object?>? last = null;
            var reason = "limit";
            string? repeat = null;
            for (var i = 0; i < Math.Max(1, maxSteps); i++)
            {
                var (abstractState, extractIssues) = ExtractState(current);
                if (extractIssues.Count > 0) throw new WorldModelViolation(extractIssues);
                var phase = abstractState.GetValueOrDefault("phase");
                var phaseKey = PyRepr(phase);
                if (seen.Contains(phaseKey)) { reason = "cycle"; repeat = phase as string ?? phaseKey; break; }
                seen.Add(phaseKey);
                var previousCurrent = current;
                var (next, trace) = AdvanceConcrete(current, last);
                trace["step"] = (long)(steps.Count + 1);
                steps.Add(trace);
                last = previousCurrent;
                current = next;
            }
            var result = new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["reason"] = reason,
                ["repeat"] = repeat,
                ["steps"] = steps,
                ["final_state"] = current,
            };
            result["digest"] = TraceDigest(result);
            return result;
        }

        private static double ToDouble(object? v) => v switch
        {
            long l => l,
            double d => d,
            _ => double.NaN,
        };
    }

    /// <summary>world_model 运行态违例（对应 Python <c>WorldModelViolation</c>）。</summary>
    public sealed class WorldModelViolation : Exception
    {
        public WorldModelViolation(List<string> issues) : base(string.Join("; ", issues)) => Issues = issues;

        public List<string> Issues { get; }
    }

    /// <summary>按点分路径取槽位值（等价 Python <c>_get_slot</c>）。</summary>
    public static bool TryGetSlot(Dictionary<string, object?> state, string slot, out object? value)
    {
        object? current = state;
        foreach (var part in SlotParts(slot))
        {
            if (current is not Dictionary<string, object?> map || !map.TryGetValue(part, out current))
            {
                value = null;
                return false;
            }
        }
        value = current;
        return true;
    }

    /// <summary>按点分路径写槽位值（等价 Python <c>_set_slot</c>：深拷贝 + 逐段 setdefault）。</summary>
    public static Dictionary<string, object?> SetSlot(Dictionary<string, object?> state, string slot, object? value)
    {
        var output = (Dictionary<string, object?>)DeepCopy(state)!;
        var parts = SlotParts(slot);
        if (parts.Count == 0) return output;
        var current = output;
        foreach (var part in parts.Take(parts.Count - 1))
        {
            if (!current.TryGetValue(part, out var child))
            {
                child = new Dictionary<string, object?>(StringComparer.Ordinal);
                current[part] = child;
            }
            if (child is not Dictionary<string, object?> childMap)
                throw new InvalidOperationException($"slot 中段非对象：{slot}");
            current = childMap;
        }
        current[parts[^1]] = value;
        return output;
    }

    private static List<string> SlotParts(string slot)
        => slot.Split('.').Where(p => p.Length > 0).ToList();

    /// <summary>Python <c>copy.deepcopy</c> 的等价（对象图限 JSON 值域）。</summary>
    public static object? DeepCopy(object? node) => node switch
    {
        null => null,
        Dictionary<string, object?> map => map.ToDictionary(kv => kv.Key, kv => DeepCopy(kv.Value), StringComparer.Ordinal),
        List<object?> list => list.Select(DeepCopy).ToList(),
        _ => node,
    };

    /// <summary>Python 真值判定（用于 <c>if v.get("slot")</c>）。</summary>
    private static bool Truthy(object? v) => v switch
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
}
