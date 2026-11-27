using System.Globalization;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Xml.Linq;

namespace Nf.Engine;

/// <summary>
/// 复刻 <c>core/output_forms.py</c>（45 产出形态面 · check32 子扫描）的**读面**：
/// <c>output list</c>（形态清单）与 <c>output check</c>（判件：按扩展名 + 内容嗅探判形态与上限档位，再跑该形态的校验器）。
///
/// 档位 = **本仓可做的判定强度**（T0 散文 → T4 可复算），不是"格式有多高级"。
/// 写面（<c>render --write</c> / <c>meter --write</c>）不属只读门。
///
/// <b>一处已声明边界（不静默放行）</b>：<c>toml</c> 形态的校验器依赖 Python 3.11 的 <c>tomllib</c>；
/// 本引擎 BCL-only 无 TOML 解析器，故对该形态**明确报"不可判定"**而不是返回空 issues
/// （返回空 = 把"没判"当"判过"，正是本工程要防的假绿）。
/// </summary>
public static partial class OutputForms
{
    public const string RegistryRel = "protocol/output_forms.json";
    public const string BaselineRel = "protocol/output_forms_baseline.json";
    public const string IndexRel = "outputs/INDEX.json";

    public static readonly string[] Tiers = { "T0", "T1", "T2", "T3", "T4" };

    private static readonly HashSet<string> Statuses = new(StringComparer.Ordinal)
    {
        "supported", "absorbed", "planned", "deferred", "unfit", "reference", "unreachable",
    };

    private static readonly Dictionary<string, string> ExtForm = new(StringComparer.Ordinal)
    {
        [".json"] = "json", [".jsonl"] = "jsonl", [".ndjson"] = "jsonl", [".yaml"] = "yaml",
        [".yml"] = "yaml", [".toml"] = "toml", [".csv"] = "csv", [".tsv"] = "csv", [".xml"] = "xml",
        [".md"] = "markdown", [".mmd"] = "mermaid", [".dot"] = "graphviz-dot", [".gv"] = "graphviz-dot",
        [".graphml"] = "graphml", [".svg"] = "svg", [".txt"] = "text", [".proto"] = "protobuf-proto3",
        [".graphql"] = "graphql-sdl", [".ttl"] = "turtle", [".sql"] = "sql-ddl",
    };

    private static readonly Dictionary<string, string> FormMaxTier = new(StringComparer.Ordinal)
    {
        ["json"] = "T2", ["jsonl"] = "T2", ["yaml"] = "T2", ["toml"] = "T2", ["csv"] = "T2",
        ["xml"] = "T1", ["svg"] = "T1", ["markdown"] = "T1", ["text"] = "T0",
        ["json-schema"] = "T2", ["vega-lite"] = "T3", ["mermaid"] = "T3", ["graphviz-dot"] = "T3",
        ["graphml"] = "T3", ["json-graph-format"] = "T3", ["quant-metrics"] = "T3",
        ["performance-report"] = "T4", ["concept-closure"] = "T4", ["system-card"] = "T3",
        ["domain-spec"] = "T3", ["domain-report"] = "T4", ["combo-cert"] = "T4",
    };

    private static readonly UTF8Encoding StrictUtf8 = new(false, throwOnInvalidBytes: true);
    // 真源是 `<!` + 可选空白 + DOCTYPE/ENTITY —— 首版漏了那个 `!`，DTD 守卫**整条不触发**
    // （合成语料 `<!DOCTYPE …` 当场照出来：py 判红、net 放行）。守卫失灵 = 安全面假绿，属最不该有的那类。
    private static readonly Regex DtdRe = new(@"<!\s*(?:DOCTYPE|ENTITY)", RegexOptions.IgnoreCase);
    private static readonly Regex DotHeadRe = new(@"^\s*(strict\s+)?(di)?graph\b", RegexOptions.Multiline);
    private static readonly string[] MermaidKinds =
    {
        "graph", "flowchart", "sequencediagram", "classdiagram", "erdiagram",
        "statediagram", "gantt", "pie", "journey", "mindmap",
    };

    /// <summary>形态清单真源（<c>protocol/output_forms.json</c>）；缺件/非对象 → 空表。</summary>
    public static Dictionary<string, object?> LoadRegistry(string root)
    {
        var (data, _) = ReadJson(Rel(root, RegistryRel));
        return data as Dictionary<string, object?> ?? new Dictionary<string, object?>(StringComparer.Ordinal);
    }

    /// <summary>按扩展名 + 内容嗅探判形态，返回 (form, 上限档位)。认不出即 <c>text</c>/<c>T0</c>。</summary>
    public static (string Form, string Tier) Detect(string root, string rel)
    {
        var suffix = Path.GetExtension(rel).ToLowerInvariant();
        var form = ExtForm.GetValueOrDefault(suffix, "text");
        if (suffix == ".json")
        {
            var (data, _) = ReadJson(Rel(root, rel));
            if (data is Dictionary<string, object?> map)
            {
                var sch = PyStrOrEmpty(map.GetValueOrDefault("$schema"));
                if (sch.Contains("json-schema.org", StringComparison.Ordinal)) form = "json-schema";
                var kind = PyStrOrEmpty(map.GetValueOrDefault("kind"));
                if (kind.StartsWith("nf-domain-spec", StringComparison.Ordinal)) form = "domain-spec";
                else if (PyStrOrEmpty(map.GetValueOrDefault("schema")).StartsWith("nf-combo/1", StringComparison.Ordinal)) form = "combo-cert";
                else if (kind.StartsWith("nf-domain-report", StringComparison.Ordinal)) form = "domain-report";
                else if (kind.StartsWith("nf-system-card", StringComparison.Ordinal)) form = "system-card";
                else if (sch.Contains("vega-lite", StringComparison.Ordinal)) form = "vega-lite";
                else if (sch.Contains("vega", StringComparison.Ordinal)) form = "vega";
                else if (kind.StartsWith("nf-performance", StringComparison.Ordinal)) form = "performance-report";
                else if (kind.StartsWith("nf-quant-metrics", StringComparison.Ordinal)) form = "quant-metrics";
                else if (kind.StartsWith("nf-concept-closure", StringComparison.Ordinal)) form = "concept-closure";
            }
        }
        return (form, FormMaxTier.GetValueOrDefault(form, "T1"));
    }

    /// <summary>该形态的结构校验器（真源 <c>_FORM_CHECK</c> 表；未登记的形态返回空表 = 只判形态与档位）。</summary>
    public static List<string> Check(string root, string rel, string form) => form switch
    {
        "json" or "json-schema" or "vega" or "json-graph-format" or "performance-report"
            or "concept-closure" or "system-card" => CheckJson(root, rel),
        "jsonl" => CheckJsonl(root, rel),
        "csv" => CheckCsv(root, rel),
        "xml" or "svg" => CheckXml(root, rel),
        "markdown" => CheckMarkdown(root, rel),
        "toml" => CheckToml(),
        "yaml" => CheckYaml(root, rel),
        "vega-lite" => CheckVegaLite(root, rel),
        "mermaid" => CheckMermaid(root, rel),
        "graphviz-dot" => CheckDot(root, rel),
        "graphml" => CheckGraphml(root, rel),
        "quant-metrics" => CheckQuantMetrics(root, rel),
        "domain-spec" => CheckDomainSpec(root, rel),
        "domain-report" => CheckDomainReport(root, rel),
        "combo-cert" => CheckComboCert(root, rel),
        _ => new List<string>(),
    };

    // ---------------------------------------------------------------- JSON 读取

    public static string Rel(string root, string rel) => Path.Combine(root, rel.Replace('/', Path.DirectorySeparatorChar));
    private static string ReadText(string path) => KnowledgeSig.Norm(StrictUtf8.GetString(File.ReadAllBytes(path)));

    /// <summary>
    /// <c>_read_json</c> 等价：读不到 / 解析失败 → <c>(null, 原因文案)</c>。
    /// **解析失败的具体文案随各自 JSON 运行时**（CPython 与 System.Text.Json 不同）——属已登记的不可约类。
    /// </summary>
    public static (object? Data, string Error) ReadJson(string path)
    {
        string text;
        try
        {
            text = ReadText(path);
        }
        catch (Exception exc) when (exc is IOException or UnauthorizedAccessException)
        {
            return (null, $"不可读：{exc.Message}");
        }
        try
        {
            using var doc = JsonIo.Parse(text);
            return (PythonJson.ToGraph(doc.RootElement), "");
        }
        catch (JsonException exc)
        {
            return (null, $"JSON 解析失败：{exc.Message}");
        }
    }

    /// <summary>对象层重复键（Python <c>object_pairs_hook</c> 语义：每个对象各自查重，最后去重排序）。</summary>
    private static (List<string> Dups, string Error) ScanDuplicateKeys(byte[] utf8)
    {
        var reader = new Utf8JsonReader(utf8, new JsonReaderOptions
        {
            MaxDepth = JsonIo.MaxDepth,
            AllowTrailingCommas = false,
            CommentHandling = JsonCommentHandling.Disallow,
        });
        var stack = new Stack<HashSet<string>>();
        var dups = new List<string>();
        try
        {
            while (reader.Read())
            {
                switch (reader.TokenType)
                {
                    case JsonTokenType.StartObject:
                        stack.Push(new HashSet<string>(StringComparer.Ordinal));
                        break;
                    case JsonTokenType.EndObject:
                        if (stack.Count > 0) stack.Pop();
                        break;
                    case JsonTokenType.PropertyName:
                        var name = reader.GetString() ?? "";
                        if (stack.Count > 0 && !stack.Peek().Add(name)) dups.Add(name);
                        break;
                }
            }
        }
        catch (JsonException exc)
        {
            return (new List<string>(), $"JSON 不可解析：{exc.Message}");
        }
        dups.Sort(StringComparer.Ordinal);
        return (dups.Distinct(StringComparer.Ordinal).ToList(), "");
    }

    private static List<string> CheckJson(string root, string rel)
    {
        var (dups, err) = ScanDuplicateKeys(File.ReadAllBytes(Rel(root, rel)));
        if (err.Length > 0) return new List<string> { err };
        return dups.Select(d => $"JSON 重复键：{d}").ToList();
    }

    private static List<string> CheckJsonl(string root, string rel)
    {
        var issues = new List<string>();
        var lines = KnowledgeSig.SplitLines(ReadText(Rel(root, rel)));
        for (var i = 0; i < lines.Count; i++)
        {
            if (lines[i].Trim().Length == 0) continue;
            try
            {
                using var _ = JsonIo.Parse(lines[i]);
            }
            catch (JsonException exc)
            {
                issues.Add($"第 {i + 1} 行非 JSON：{exc.Message}");
            }
        }
        return issues;
    }

    private static List<string> CheckCsv(string root, string rel)
    {
        var text = ReadText(Rel(root, rel));
        if (text.Contains('\x00')) return new List<string> { "含 NUL 字节（非文本 CSV）" };
        var rows = ParseCsv(text).Where(r => r.Count > 0).ToList();
        if (rows.Count == 0) return new List<string> { "空表" };
        var width = rows[0].Count;
        var issues = width > 0 ? new List<string>() : new List<string> { "表头为空" };
        for (var i = 1; i < rows.Count; i++)
            if (rows[i].Count != width)
                issues.Add($"第 {i + 1} 行字段数 {rows[i].Count} ≠ 表头 {width}");
        if (rows[0].Distinct(StringComparer.Ordinal).Count() != width) issues.Add("表头有重名列");
        return issues;
    }

    /// <summary>Python <c>csv.reader</c> 默认方言（逗号 / 双引号 / 双写转义 / 可跨行）。</summary>
    private static List<List<string>> ParseCsv(string text)
    {
        var rows = new List<List<string>>();
        var row = new List<string>();
        var field = new StringBuilder();
        var inQuotes = false;
        var started = false;
        for (var i = 0; i < text.Length; i++)
        {
            var c = text[i];
            if (inQuotes)
            {
                if (c == '"')
                {
                    if (i + 1 < text.Length && text[i + 1] == '"') { field.Append('"'); i++; }
                    else inQuotes = false;
                    continue;
                }
                field.Append(c);
                continue;
            }
            if (c == '"' && field.Length == 0 && !started) { inQuotes = true; started = true; continue; }
            if (c == ',') { row.Add(field.ToString()); field.Clear(); started = false; continue; }
            if (c == '\n')
            {
                // **空行产出的是空记录 `[]`**（Python csv.reader 口径），不是"一个空字段"——
                // 两者在真源里分别走「空表」与「表头为空」两条判定，混了就判错。
                if (row.Count == 0 && field.Length == 0 && !started) rows.Add(new List<string>());
                else { row.Add(field.ToString()); rows.Add(row); }
                field.Clear();
                row = new List<string>();
                started = false;
                continue;
            }
            field.Append(c);
            started = true;
        }
        if (field.Length > 0 || row.Count > 0) { row.Add(field.ToString()); rows.Add(row); }
        return rows;
    }

    private static string XmlGuard(string text) =>
        DtdRe.IsMatch(text) ? "含 DTD/ENTITY 声明（本仓 XML 产出面禁 DTD：堵实体展开类攻击）" : "";

    private static List<string> CheckXml(string root, string rel)
    {
        var text = ReadText(Rel(root, rel));
        var guard = XmlGuard(text);
        if (guard.Length > 0) return new List<string> { guard };
        try
        {
            XDocument.Parse(text);
        }
        catch (System.Xml.XmlException exc)
        {
            return new List<string> { $"XML 良构性失败：{exc.Message}" };
        }
        return new List<string>();
    }

    private static List<string> CheckMarkdown(string root, string rel)
    {
        var text = ReadText(Rel(root, rel));
        var issues = new List<string>();
        if (AssetShelf.PyStrip(text).Length == 0) issues.Add("空档");
        if (AssetShelf.CountNonOverlapping(text, "```") % 2 != 0) issues.Add("代码围栏未闭合（``` 奇数个）");
        return issues;
    }

    /// <summary>
    /// <b>已声明边界</b>：真源用 Python 3.11 <c>tomllib</c> 判 TOML 良构；本引擎 BCL-only 无 TOML 解析器。
    /// 返回"不可判定"而不是空表——**"不支持"绝不等价"通过"**（真源自己的子集纪律，此处照同一标准执行）。
    /// </summary>
    private static List<string> CheckToml() => new()
    {
        "TOML 形态不可判定：本引擎未内建 TOML 解析器（BCL-only）——明确拒绝，不静默放行",
    };

    private static List<string> CheckYaml(string root, string rel)
    {
        var issues = new List<string>();
        var lines = KnowledgeSig.SplitLines(ReadText(Rel(root, rel)));
        for (var i = 0; i < lines.Count; i++)
        {
            var line = lines[i];
            // 真源是 `"\t" in line[: len(line) - len(line.lstrip())]` —— 查的是**行首空白段**里有没有 Tab。
            // 首版写成"lstrip 后第一个字符是不是 Tab"（那永远不是空白）→ Tab 缩进**整条漏判**。
            var lead = 0;
            while (lead < line.Length && AssetShelf.IsPySpace(line[lead])) lead++;
            if (line[..lead].Contains('\t'))
                issues.Add($"第 {i + 1} 行用 Tab 缩进（YAML 禁 Tab）");
            var body = line.Trim();
            if (body.StartsWith("- ", StringComparison.Ordinal) || body.Length == 0
                || body.StartsWith("#", StringComparison.Ordinal)) continue;
            if (!line.Contains(':'))
                issues.Add($"第 {i + 1} 行非映射项（收窄子集要求 key: value）：{PySlice(body, 40)}");
        }
        return issues;
    }

    private static List<string> CheckVegaLite(string root, string rel)
    {
        var (data, err) = ReadJson(Rel(root, rel));
        if (err.Length > 0) return new List<string> { err };
        if (data is not Dictionary<string, object?> map) return new List<string>();
        var issues = new List<string>();
        if (!PyStr(map.GetValueOrDefault("$schema")).Contains("vega-lite", StringComparison.Ordinal))
            issues.Add("缺 $schema（应为 vega-lite v5）");
        if (!new[] { "mark", "layer", "hconcat", "vconcat", "concat", "facet", "spec", "repeat" }
                .Any(k => map.ContainsKey(k)))
            issues.Add("缺 mark/layer 等绘图主体");
        if (!map.ContainsKey("data")) issues.Add("缺 data（图不能没有数据源）");
        var enc = map.GetValueOrDefault("encoding");
        if (enc is Dictionary<string, object?> encMap)
        {
            foreach (var (ch, spec) in encMap)
            {
                if (spec is not Dictionary<string, object?> specMap) { issues.Add($"encoding.{ch} 非对象"); continue; }
                if (!new[] { "field", "aggregate", "value", "datum", "timeUnit", "bin" }.Any(k => specMap.ContainsKey(k)))
                    issues.Add($"encoding.{ch} 无 field/aggregate/value（通道未绑定）");
            }
        }
        else if (enc is not null) issues.Add("encoding 非对象");
        return issues;
    }

    private static List<string> CheckMermaid(string root, string rel)
    {
        var body = KnowledgeSig.SplitLines(ReadText(Rel(root, rel)))
            .Select(x => x.TrimEnd())
            .Where(x => x.Trim().Length > 0 && !x.Trim().StartsWith("%%", StringComparison.Ordinal))
            .ToList();
        if (body.Count == 0) return new List<string> { "空图" };
        var head = body[0].Trim().ToLowerInvariant();
        if (!MermaidKinds.Any(head.StartsWith)) 
            return new List<string> { $"首行非已知图种：{PyScalar.PyRepr(PySlice(body[0].Trim(), 40))}" };
        return new List<string>();
    }

    private static List<string> CheckDot(string root, string rel)
    {
        var text = ReadText(Rel(root, rel));
        var issues = new List<string>();
        if (!DotHeadRe.IsMatch(text)) issues.Add("缺 digraph/graph 头");
        var open = text.Count(c => c == '{');
        var close = text.Count(c => c == '}');
        if (open != close) issues.Add($"花括号不配对（{{ {open} / }} {close}）");
        return issues;
    }

    private static List<string> CheckGraphml(string root, string rel)
    {
        var path = Rel(root, rel);
        var guard = XmlGuard(ReadText(path));
        if (guard.Length > 0) return new List<string> { $"GraphML {guard}" };
        XDocument tree;
        try
        {
            tree = XDocument.Parse(ReadText(path));
        }
        catch (System.Xml.XmlException exc)
        {
            return new List<string> { $"GraphML XML 解析失败：{exc.Message}" };
        }
        var rootEl = tree.Root!;
        var issues = new List<string>();
        if (rootEl.Name.LocalName != "graphml") issues.Add($"根元素应为 graphml，实为 {rootEl.Name.LocalName}");
        var graphs = rootEl.Descendants().Where(e => e.Name.LocalName == "graph").ToList();
        if (graphs.Count == 0) issues.Add("缺 <graph> 元素");
        var nodes = graphs.SelectMany(g => g.Elements().Where(e => e.Name.LocalName == "node"))
            .Select(n => n.Attribute("id")?.Value).Where(v => v is not null).ToHashSet(StringComparer.Ordinal);
        foreach (var g in graphs)
            foreach (var e in g.Elements().Where(x => x.Name.LocalName == "edge"))
                foreach (var end in new[] { "source", "target" })
                {
                    var v = e.Attribute(end)?.Value;
                    if (v is null || !nodes.Contains(v)) issues.Add($"边端点悬空：{end}={v ?? "None"}");
                }
        return issues;
    }

    private static List<string> CheckQuantMetrics(string root, string rel)
    {
        var issues = CheckJson(root, rel);
        var (data, err) = ReadJson(Rel(root, rel));
        if (err.Length > 0 || data is not Dictionary<string, object?> map)
        {
            if (err.Length > 0) issues.Add(err);
            return issues;
        }
        var entries = PyList(map.GetValueOrDefault("metrics")).Concat(PyList(map.GetValueOrDefault("declared_only")));
        foreach (var entry in entries)
        {
            if (entry is not Dictionary<string, object?> m) { issues.Add($"条目非对象：{PyReprTuple(entry)}"); continue; }
            // 真源是 `m.get("id") or "?"` / `str(m.get("engine") or "")` —— **None 走假值分支**，
            // 不是 Python 的 str(None)="None"（首版照直用 PyStr 就栽在这里：真仓 QUANT_METRICS 的 engine 为 null，
            // 引擎误报"宣称 engine=None"）。凡 `x or 默认` 一律经 PyTruthy 判后再取串。
            var mid = PyStrOrEmpty(m.GetValueOrDefault("id"), "?");
            var eng = PyStrOrEmpty(m.GetValueOrDefault("engine"));
            if (eng.Length > 0)
            {
                var at = eng.IndexOf(':');
                var mod = at < 0 ? eng : eng[..at];
                var fn = at < 0 ? "" : eng[(at + 1)..];
                if (mod != "quant_metrics" || !OutputTables.QuantMetricNames.Contains(fn))
                    issues.Add($"{mid}: 宣称 engine={eng}，但 core/quant_metrics 无该实现（宣称≠实现）");
            }
            if (PyStr(m.GetValueOrDefault("verifiable")) == "T4" && eng.Length == 0)
                issues.Add($"{mid}: 标 T4（可复算）却无 engine");
            var required = PyList(m.GetValueOrDefault("required_params")).Select(PyStr).ToList();
            if (PyTruthy(m.GetValueOrDefault("annual_factor_required")) && !required.Contains("annual_factor"))
                issues.Add($"{mid}: 需年化因子却未列入 required_params（口径四要素不全）");
        }
        var names = PyList(map.GetValueOrDefault("metrics")).Select(m => PyStr((m as Dictionary<string, object?>)?.GetValueOrDefault("id"))).ToHashSet(StringComparer.Ordinal);
        var expected = (map.GetValueOrDefault("annual_factors") as Dictionary<string, object?>)?.Keys.ToHashSet(StringComparer.Ordinal)
                       ?? new HashSet<string>(StringComparer.Ordinal);
        var want = new HashSet<string>(new[] { "daily", "weekly", "monthly" }, StringComparer.Ordinal);
        if (!expected.SetEquals(want))
            issues.Add($"annual_factors 键集应为 daily/weekly/monthly，实为 {PyReprList(expected.OrderBy(x => x, StringComparer.Ordinal))}");
        if (names.Count != PyList(map.GetValueOrDefault("metrics")).Count) issues.Add("metrics 存在重复 id");
        return issues;
    }

    private static List<string> CheckDomainSpec(string root, string rel)
    {
        var issues = CheckJson(root, rel);
        var (data, err) = ReadJson(Rel(root, rel));
        if (err.Length > 0 || data is not Dictionary<string, object?> map)
        {
            if (err.Length > 0) issues.Add(err);
            return issues;
        }
        var code = PyStrOrEmpty(map.GetValueOrDefault("code"));
        var subs = PyList(map.GetValueOrDefault("subdivisions"));
        if (subs.Count != 12) issues.Add($"细分条目应为 12 条，实为 {subs.Count}");
        for (var i = 0; i < subs.Count; i++)
        {
            if (subs[i] is not Dictionary<string, object?> s) continue;
            var want = $"{code}-{i + 1:D2}";
            if (PyStr(s.GetValueOrDefault("id")) != want)
                issues.Add($"第 {i + 1} 条 id 应为 {want}，实为 {PyScalar.PyRepr(s.GetValueOrDefault("id"))}");
            var anchor = PyStrOrEmpty(s.GetValueOrDefault("anchor"));
            if (!anchor.StartsWith("http://", StringComparison.Ordinal) && !anchor.StartsWith("https://", StringComparison.Ordinal))
                issues.Add($"{PyStr(s.GetValueOrDefault("id"))} 锚非绝对 URL");
            if (PyIntOf(s.GetValueOrDefault("anchor_status")) == 0)
                issues.Add($"{PyStr(s.GetValueOrDefault("id"))} 锚缺可达性实测值（不得假装可达：探不到记 0 并在锚表注明）");
        }
        return issues;
    }

    private static List<string> CheckDomainReport(string root, string rel)
    {
        var issues = CheckJson(root, rel);
        var (data, err) = ReadJson(Rel(root, rel));
        if (err.Length > 0 || data is not Dictionary<string, object?> map)
        {
            if (err.Length > 0) issues.Add(err);
            return issues;
        }
        var family = PyStrOrEmpty(map.GetValueOrDefault("family"));
        if (!OutputTables.DomainMetricFamilies.Contains(family))
            issues.Add($"度量族未在本仓引擎登记：{PyScalar.PyRepr(family)}（不得宣称可复算）");
        var metrics = map.GetValueOrDefault("metrics") as Dictionary<string, object?> ?? new(StringComparer.Ordinal);
        if (PyStrOrEmpty(metrics.GetValueOrDefault("family")) != family) issues.Add("metrics.family 与报告 family 不一致");
        if (PyIntOf(map.GetValueOrDefault("sample_rows")) < 1) issues.Add("样例规模为 0（无样例即无口径值）");
        return issues;
    }

    private static List<string> CheckComboCert(string root, string rel)
    {
        var issues = CheckJson(root, rel);
        var (data, err) = ReadJson(Rel(root, rel));
        if (err.Length > 0 || data is not Dictionary<string, object?> map)
        {
            if (err.Length > 0) issues.Add(err);
            return issues;
        }
        using var schemaDoc = JsonIo.Parse(OutputTables.ComboCertSchemaJson);
        var schema = (Dictionary<string, object?>)PythonJson.ToGraph(schemaDoc.RootElement)!;
        var unsupported = new List<string>();
        var schemaErrors = JsonSchemaSubset.Check(map, schema, unsupported: unsupported);
        issues.AddRange(schemaErrors.Take(4).Select(e => $"证书不合 schema：{e}"));
        if (unsupported.Count > 0)
            issues.Add($"证书校验器遇不支持关键字：{PyReprList(unsupported.Distinct(StringComparer.Ordinal).OrderBy(x => x, StringComparer.Ordinal).Take(2))}");

        var packs = PyList(map.GetValueOrDefault("packs")).Select(PyStr).ToList();
        var extra = PyList(map.GetValueOrDefault("extra_modules")).Select(PyStr).ToList();
        if (packs.Count == 0 && extra.Count == 0)
        {
            issues.Add("复算失败：组合证书缺 packs/extra_modules（无输入即无复算）");
            return issues;
        }
        var result = Combinator.Build(root, packs, extra);
        if (!result.Legal) issues.Add("组合非法（五不变量未全成立）");
        if (!PyScalar.PyEquals(result.Certificate.GetValueOrDefault("digest"), map.GetValueOrDefault("digest")))
            issues.Add("证书摘要与实时复算不一致（组合输入已变）");
        return issues;
    }
}
