using System.Globalization;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Xml.Linq;

namespace Nf.Engine;

/// <summary>形态库 / 计量 / 基线 / INDEX 复算门 + Python 渲染口径辅助。</summary>
public static partial class OutputForms
{
    // ---------------------------------------------------------------- 小工具

    private static List<object?> PyList(object? v) => v as List<object?> ?? new List<object?>();

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

    private static long PyIntOf(object? v) => v switch
    {
        long l => l,
        int i => i,
        double d => (long)d,
        bool b => b ? 1 : 0,
        string s => long.TryParse(s, NumberStyles.Integer, CultureInfo.InvariantCulture, out var parsed) ? parsed : 0,
        _ => 0,
    };

    private static string PyStr(object? v) => v switch
    {
        null => "None",
        string s => s,
        bool b => b ? "True" : "False",
        long l => l.ToString(CultureInfo.InvariantCulture),
        int i => i.ToString(CultureInfo.InvariantCulture),
        double d => PythonJson.PyFloatRepr(d),
        _ => PyScalar.PyRepr(v),
    };

    /// <summary>Python <c>x or fallback</c> 的 **str** 口径（假值走 fallback，不经过 <c>str(None)</c>）。</summary>
    private static string PyStrOrEmpty(object? v, string fallback = "") =>
        PyTruthy(v) ? PyStr(v) : fallback;

    private static string PySlice(string s, int maxCodePoints) => PyScalar.PySlice(s, maxCodePoints);

    private static string PyReprList(IEnumerable<string> items) =>
        "[" + string.Join(", ", items.Select(PyScalar.PyRepr)) + "]";

    private static string PyReprTuple(object? item) => "(" + PyScalar.PyRepr(item) + ",)";

    // ---------------------------------------------------------------- 包级产出清单 / 门禁合成

    /// <summary><c>_pack_dirs</c>：community 下**声明了 outputs/INDEX.json** 的包目录名（排序）。</summary>
    public static List<string> PackDirs(string root)
    {
        var baseDir = Path.Combine(root, "community");
        if (!Directory.Exists(baseDir)) return new List<string>();
        return Directory.GetDirectories(baseDir)
            .Where(d => File.Exists(Path.Combine(d, "outputs", "INDEX.json")))
            .Select(Path.GetFileName).Where(n => n is not null).Select(n => n!)
            .OrderBy(n => n, StringComparer.Ordinal).ToList();
    }

    /// <summary>形态清单自检：结构合法 + 类别/档位在册 + id 唯一 + 可达性实证齐备。</summary>
    public static (List<string> Issues, Dictionary<string, object?> Stats) RegistryVerify(string root)
    {
        var issues = new List<string>();
        var registry = LoadRegistry(root);
        if (registry.Count == 0)
            return (new List<string> { $"{RegistryRel} 缺失或不可解析（形态清单是真源）" },
                new Dictionary<string, object?>(StringComparer.Ordinal));
        if (PyStrOrEmpty(registry.GetValueOrDefault("schema")) != "nf-output-forms/1")
            issues.Add($"schema 应为 nf-output-forms/1，实为 {PyScalar.PyRepr(registry.GetValueOrDefault("schema"))}");
        var cats = PyList(registry.GetValueOrDefault("categories"));
        var catIds = cats.OfType<Dictionary<string, object?>>()
            .Select(c => PyStrOrEmpty(c.GetValueOrDefault("id"))).Where(x => x.Length > 0)
            .ToHashSet(StringComparer.Ordinal);
        if (catIds.Count == 0) issues.Add("categories 为空（形态必须有类别归属）");
        foreach (var c in cats)
        {
            if (c is not Dictionary<string, object?> cm) continue;
            if (PyStrOrEmpty(cm.GetValueOrDefault("id")).Length == 0
                || PyStrOrEmpty(cm.GetValueOrDefault("name")).Length == 0)
                issues.Add($"categories 条目缺 id/name：{PyScalar.PyRepr(c)}");
        }
        var forms = PyList(registry.GetValueOrDefault("forms"));
        var seen = new HashSet<string>(StringComparer.Ordinal);
        var perCat = new Dictionary<string, long>(StringComparer.Ordinal);
        var perTier = new Dictionary<string, long>(StringComparer.Ordinal);
        var perStatus = new Dictionary<string, long>(StringComparer.Ordinal);
        var unreachable = 0L;
        foreach (var f in forms)
        {
            if (f is not Dictionary<string, object?> fm)
            {
                issues.Add($"forms 条目非对象：{PyScalar.PyRepr(f)}");
                continue;
            }
            var fid = PyStrOrEmpty(fm.GetValueOrDefault("id"));
            if (fid.Length == 0)
            {
                issues.Add($"forms 条目缺 id：{PyScalar.PyRepr(f)}");
                continue;
            }
            if (!seen.Add(fid)) issues.Add($"形态 id 重复：{fid}");
            var category = PyStrOrEmpty(fm.GetValueOrDefault("category"));
            if (!catIds.Contains(category)) issues.Add($"{fid} 类别未在册：{PyScalar.PyRepr(fm.GetValueOrDefault("category"))}");
            var tier = PyStrOrEmpty(fm.GetValueOrDefault("tier"));
            if (!Tiers.Contains(tier)) issues.Add($"{fid} 档位非法：{PyScalar.PyRepr(fm.GetValueOrDefault("tier"))}（预期 {string.Join("/", Tiers)}）");
            var status = PyStrOrEmpty(fm.GetValueOrDefault("status"));
            if (!Statuses.Contains(status)) issues.Add($"{fid} 状态非法：{PyScalar.PyRepr(fm.GetValueOrDefault("status"))}");
            var spec = fm.GetValueOrDefault("spec") as Dictionary<string, object?> ?? new(StringComparer.Ordinal);
            if (status != "unfit" && PyStrOrEmpty(spec.GetValueOrDefault("uri")).Length == 0)
                issues.Add($"{fid} 缺规范入口 spec.uri（不适面才可空）");
            var evidence = fm.GetValueOrDefault("evidence") as Dictionary<string, object?> ?? new(StringComparer.Ordinal);
            if (!evidence.ContainsKey("reachable"))
                issues.Add($"{fid} 缺可达性实证 evidence.reachable（不伪造：查不到也要记 false）");
            else if (evidence.GetValueOrDefault("reachable") is bool rb && !rb)
                unreachable++;
            perCat[category] = perCat.GetValueOrDefault(category) + 1;
            perTier[tier] = perTier.GetValueOrDefault(tier) + 1;
            perStatus[status] = perStatus.GetValueOrDefault(status) + 1;
        }
        return (issues, new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["forms"] = (long)forms.Count, ["categories"] = (long)catIds.Count,
            ["by_category"] = perCat.ToDictionary(kv => kv.Key, kv => (object?)kv.Value, StringComparer.Ordinal),
            ["by_tier"] = perTier.ToDictionary(kv => kv.Key, kv => (object?)kv.Value, StringComparer.Ordinal),
            ["by_status"] = perStatus.ToDictionary(kv => kv.Key, kv => (object?)kv.Value, StringComparer.Ordinal),
            ["unreachable"] = unreachable,
        });
    }

    /// <summary>机验率与功能面计量（不改盘；基线比对见 <see cref="BaselineVerify"/>）。</summary>
    public static (List<string> Issues, Dictionary<string, object?> Stats) Meter(string root)
    {
        var packages = new Dictionary<string, object?>(StringComparer.Ordinal);
        foreach (var pkg in PackDirs(root))
        {
            var (idx, _) = ReadJson(Rel(root, $"community/{pkg}/{IndexRel}"));
            var entries = PyList((idx as Dictionary<string, object?>)?.GetValueOrDefault("outputs"));
            var mv = entries.OfType<Dictionary<string, object?>>()
                .Where(e => Tiers.Skip(2).Contains(PyStrOrEmpty(e.GetValueOrDefault("tier")))).ToList();
            var fnFaces = entries.OfType<Dictionary<string, object?>>()
                .Where(e => PyStrOrEmpty(e.GetValueOrDefault("tier")) == "T4").ToList();
            var assetsDir = Path.Combine(root, "community", pkg, "assets");
            var prose = Directory.Exists(assetsDir)
                ? Directory.GetFiles(assetsDir, "*.md").Select(Path.GetFileName)
                    .Where(n => n is not null && n != "README.md").ToList()
                : new List<string?>();
            var denom = mv.Count + prose.Count;
            packages[pkg] = new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["machine_verifiable"] = (long)mv.Count,
                ["functional"] = (long)fnFaces.Count,
                ["prose_assets"] = (long)prose.Count,
                ["machine_verifiable_ratio"] = denom > 0 ? PyScalar.PyRound((double)mv.Count / denom, 4) : 0.0,
                ["roles"] = Count(entries.OfType<Dictionary<string, object?>>()
                    .Select(e => new Dictionary<string, object?>(StringComparer.Ordinal)
                    { ["r"] = e.GetValueOrDefault("role") }), "r"),
                ["tiers"] = Count(entries.OfType<Dictionary<string, object?>>()
                    .Select(e => new Dictionary<string, object?>(StringComparer.Ordinal)
                    { ["t"] = e.GetValueOrDefault("tier") }), "t"),
            };
        }
        var totals = new Dictionary<string, object?>(StringComparer.Ordinal);
        if (packages.Count > 0)
        {
            long Mv(Dictionary<string, object?> p) => Convert.ToInt64(p["machine_verifiable"]);
            long Prose(Dictionary<string, object?> p) => Convert.ToInt64(p["prose_assets"]);
            var values = packages.Values.Cast<Dictionary<string, object?>>().ToList();
            totals = new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["machine_verifiable"] = values.Sum(Mv),
                ["functional"] = values.Sum(p => Convert.ToInt64(p["functional"])),
                ["prose_assets"] = values.Sum(Prose),
                ["machine_verifiable_ratio"] = PyScalar.PyRound(
                    (double)values.Sum(Mv) / Math.Max(1, values.Sum(p => Mv(p) + Prose(p))), 4),
            };
        }
        return (new List<string>(), new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["packages"] = packages, ["totals"] = totals,
        });
    }

    /// <summary>机验率基线（可重签）：低于基线即 FAIL——防「新增产出又退回散文」。</summary>
    public static (List<string> Issues, Dictionary<string, object?> Stats) BaselineVerify(string root)
    {
        var issues = new List<string>();
        var (baseDoc, err) = ReadJson(Rel(root, BaselineRel));
        var (_, stats) = Meter(root);
        if (err.Length > 0)
            return (new List<string> { $"{BaselineRel} 缺失或不可解析（{err}；重签：nf output meter --write）" }, stats);
        var prev = (baseDoc as Dictionary<string, object?>)?.GetValueOrDefault("packages") as Dictionary<string, object?>
                   ?? new Dictionary<string, object?>(StringComparer.Ordinal);
        foreach (var (pkg, cur) in (stats.GetValueOrDefault("packages") as Dictionary<string, object?>
                                    ?? new Dictionary<string, object?>(StringComparer.Ordinal)))
        {
            if (cur is not Dictionary<string, object?> c) continue;
            if (prev.GetValueOrDefault(pkg) is not Dictionary<string, object?> old) continue;
            var oldMv = PyLong(old.GetValueOrDefault("machine_verifiable"));
            var curMv = Convert.ToInt64(c["machine_verifiable"]);
            if (curMv < oldMv)
                issues.Add($"{pkg} 机验产出面回退：{oldMv} → {curMv}（基线 {BaselineRel}）");
            var oldFn = PyLong(old.GetValueOrDefault("functional"));
            var curFn = Convert.ToInt64(c["functional"]);
            if (curFn < oldFn) issues.Add($"{pkg} 功能面（T4 可复算）回退：{oldFn} → {curFn}");
        }
        stats["baseline"] = baseDoc is not null;
        return (issues, stats);
    }

    /// <summary>check32 子扫描入口：形态清单 + 包级产出清单 + 机验率基线三合一。</summary>
    public static (List<string> Issues, Dictionary<string, object?> Stats) Scan(string root)
    {
        var issues = new List<string>();
        var (regIssues, regStats) = RegistryVerify(root);
        issues.AddRange(regIssues.Select(i => $"形态清单: {i}"));
        var (idxIssues, idxStats) = IndexVerify(root);
        issues.AddRange(idxIssues.Select(i => $"包级产出面: {i}"));
        var (baseIssues, baseStats) = BaselineVerify(root);
        issues.AddRange(baseIssues.Select(i => $"机验率基线: {i}"));
        return (issues, new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["registry"] = regStats, ["index"] = idxStats,
            ["meter"] = (baseStats.GetValueOrDefault("packages") as Dictionary<string, object?>)
                       ?? new Dictionary<string, object?>(StringComparer.Ordinal),
        });
    }

    /// <summary>包级产出清单机检：声明存在 / 形态与档位属实 / schema 校验 / 双源一致 / T4 复算。</summary>
    public static (List<string> Issues, Dictionary<string, object?> Stats) IndexVerify(string root)
    {
        var issues = new List<string>();
        var rows = new List<Dictionary<string, object?>>();
        foreach (var pkg in PackDirs(root))
        {
            var rel = $"community/{pkg}/{IndexRel}";
            var (idx, err) = ReadJson(Rel(root, rel));
            if (err.Length > 0) { issues.Add($"{rel}: {err}"); continue; }
            if (idx is not Dictionary<string, object?> index) continue;
            if (PyStrOrEmpty(index.GetValueOrDefault("schema")) != "nf-output-index/1")
                issues.Add($"{rel}: schema 应为 nf-output-index/1");
            if (PyStrOrEmpty(index.GetValueOrDefault("package")) != pkg)
                issues.Add($"{rel}: package 字段 {PyScalar.PyRepr(index.GetValueOrDefault("package"))} ≠ 包目录名 {PyScalar.PyRepr(pkg)}");
            foreach (var entry in PyList(index.GetValueOrDefault("outputs")).OfType<Dictionary<string, object?>>())
            {
                var path = PyStrOrEmpty(entry.GetValueOrDefault("path"));
                var form = PyStrOrEmpty(entry.GetValueOrDefault("form"));
                var tier = PyStrOrEmpty(entry.GetValueOrDefault("tier"));
                if (path.Length == 0) { issues.Add($"{rel}: outputs 条目缺 path"); continue; }
                if (!Tiers.Contains(tier)) { issues.Add($"{rel}: {path} 档位非法 {PyScalar.PyRepr(entry.GetValueOrDefault("tier"))}"); continue; }
                var fullRel = $"community/{pkg}/{path}";
                if (!File.Exists(Rel(root, fullRel))) { issues.Add($"{rel}: 声明产出面不存在 {path}"); continue; }
                var (gotForm, gotTier) = Detect(root, fullRel);
                if (form.Length > 0 && form != gotForm) issues.Add($"{rel}: {path} 声明形态 {form}，实测 {gotForm}");
                if (Array.IndexOf(Tiers, tier) > Array.IndexOf(Tiers, gotTier))
                    issues.Add($"{rel}: {path} 声明档位 {tier} 超出本仓可判上限 {gotTier}");
                var useForm = form.Length > 0 ? form : gotForm;
                // `_FORM_CHECK.get(form or got_form)`：无校验器的形态返回空表（不是"没判"）
                issues.AddRange(Check(root, fullRel, useForm).Select(s => $"{rel}: {path} {s}"));
                var schRel = PyStrOrEmpty(entry.GetValueOrDefault("schema"));
                if (schRel.Length > 0)
                {
                    var (schemaDoc, serr) = ReadJson(Rel(root, $"community/{pkg}/{schRel}"));
                    if (serr.Length > 0) issues.Add($"{rel}: {path} schema {serr}");
                    else if (schemaDoc is Dictionary<string, object?> schemaMap)
                    {
                        var (inst, ierr) = ReadJson(Rel(root, fullRel));
                        if (ierr.Length > 0) issues.Add($"{rel}: {path} {ierr}");
                        else
                        {
                            var unsupported = new List<string>();
                            var errs = JsonSchemaSubset.Check(inst, schemaMap, unsupported: unsupported);
                            issues.AddRange(errs.Take(8).Select(e => $"{rel}: {path} schema 不符 {e}"));
                        }
                    }
                }
                if (entry.GetValueOrDefault("dual_source") is Dictionary<string, object?> ds)
                    issues.AddRange(DualSourceCheck(root, pkg, path, ds).Select(m => $"{rel}: {path} {m}"));
                if (entry.GetValueOrDefault("recompute") is Dictionary<string, object?>)
                {
                    var withPkg = new Dictionary<string, object?>(entry, StringComparer.Ordinal) { ["_pkg"] = pkg };
                    issues.AddRange(RecomputeEntry(root, withPkg).Issues.Select(s => $"{rel}: {s}"));
                }
                else if (tier == "T4")
                {
                    issues.Add($"{rel}: {path} 声明 T4（可复算）却无 recompute 声明");
                }
                rows.Add(new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["package"] = pkg, ["path"] = path, ["form"] = useForm,
                    ["tier"] = tier, ["role"] = PyStrOrEmpty(entry.GetValueOrDefault("role")),
                });
            }
        }
        return (issues, new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["packages"] = (long)PackDirs(root).Count, ["outputs"] = (long)rows.Count,
            ["by_role"] = Count(rows, "role"), ["by_tier"] = Count(rows, "tier"),
            ["by_form"] = Count(rows, "form"),
        });
    }

    /// <summary>T4 复算：生成器重算 → 与在盘产物比对（JSON 逐字段 / 文本逐字节）。</summary>
    public static (List<string> Issues, Dictionary<string, object?> Stats) RecomputeEntry(
        string root, Dictionary<string, object?> entry)
    {
        var outRel = PyStrOrEmpty(entry.GetValueOrDefault("path"));
        var gid = OutputGenerators.GenId(entry);
        if (!OutputGenerators.Registered(gid))
            return (new List<string> { $"{outRel} 声明复算 {PyScalar.PyRepr(gid)} 无对应引擎（不得假装可复算）" },
                new Dictionary<string, object?>(StringComparer.Ordinal));
        var (fresh, errs) = OutputGenerators.Generate(root, entry);
        if (fresh is null)
            return (errs.Select(e => $"{outRel}: {e}").ToList(), new Dictionary<string, object?>(StringComparer.Ordinal));
        var diskPath = Rel(root, OutputGenerators.PkgRel(entry, outRel));
        var onDisk = File.ReadAllBytes(diskPath);
        var diffs = new List<string>();
        if (fresh is string text)
        {
            if (!onDisk.SequenceEqual(Encoding.UTF8.GetBytes(OutputGenerators.Dump(text))))
                diffs.Add("文本面与复算不一致（逐字节）");
        }
        else
        {
            string decoded;
            try
            {
                decoded = StrictUtf8.GetString(onDisk);
                using var doc = JsonIo.Parse(decoded);
                var declared = PythonJson.ToGraph(doc.RootElement) as Dictionary<string, object?>
                               ?? new Dictionary<string, object?>(StringComparer.Ordinal);
                var subset = new Dictionary<string, object?>(StringComparer.Ordinal);
                if (fresh is Dictionary<string, object?> freshMap)
                    foreach (var key in freshMap.Keys) subset[key] = declared.GetValueOrDefault(key);
                diffs = DeepDiff(fresh, subset);
            }
            catch (Exception exc) when (exc is JsonException or System.Text.DecoderFallbackException)
            {
                return (new List<string> { $"{outRel}: 在盘产物不可解析 {exc.Message}" },
                    new Dictionary<string, object?>(StringComparer.Ordinal));
            }
            if (onDisk.AsSpan().IndexOf("\r\n"u8) >= 0)
                diffs.Add("在盘产物含 CRLF（仓库 EOL 契约 = LF）");
        }
        return (diffs.Select(d => $"{outRel}: 复算与在盘不一致 {d}").ToList(),
            new Dictionary<string, object?> { ["diff"] = (long)diffs.Count });
    }

    /// <summary>渲染包内声明的产出面（数据 / 图表）：<c>--write</c> 才落盘；缺生成器即报错不静默。</summary>
    public static (List<string> Issues, List<Dictionary<string, object?>> Rows) RenderOutputs(
        string root, string package = "", bool write = false)
    {
        var issues = new List<string>();
        var rows = new List<Dictionary<string, object?>>();
        foreach (var pkg in PackDirs(root))
        {
            if (package.Length > 0 && pkg != package) continue;
            var (idx, err) = ReadJson(Rel(root, $"community/{pkg}/{IndexRel}"));
            if (err.Length > 0) { issues.Add($"{pkg}: {err}"); continue; }
            foreach (var entry in PyList((idx as Dictionary<string, object?>)?.GetValueOrDefault("outputs"))
                         .OfType<Dictionary<string, object?>>())
            {
                var gid = OutputGenerators.GenId(entry);
                if (gid.Length == 0) continue;
                if (!OutputGenerators.Registered(gid))
                {
                    issues.Add($"{pkg}/{PyStrOrEmpty(entry.GetValueOrDefault("path"))}: 未登记生成器 {PyScalar.PyRepr(gid)}");
                    continue;
                }
                var withPkg = new Dictionary<string, object?>(entry, StringComparer.Ordinal) { ["_pkg"] = pkg };
                var (value, errs) = OutputGenerators.Generate(root, withPkg);
                if (value is null)
                {
                    issues.AddRange(errs.Select(e => $"{pkg}/{PyStrOrEmpty(entry.GetValueOrDefault("path"))}: {e}"));
                    continue;
                }
                var dest = Rel(root, $"community/{pkg}/{PyStrOrEmpty(entry.GetValueOrDefault("path"))}");
                var text = OutputGenerators.Dump(value);
                var bytes = Encoding.UTF8.GetBytes(text);
                var changed = !File.Exists(dest) || !File.ReadAllBytes(dest).SequenceEqual(bytes);
                if (write && changed)
                {
                    Directory.CreateDirectory(Path.GetDirectoryName(dest)!);
                    File.WriteAllBytes(dest, bytes);
                }
                rows.Add(new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["package"] = pkg, ["path"] = PyStrOrEmpty(entry.GetValueOrDefault("path")),
                    ["generator"] = gid, ["changed"] = changed,
                    ["written"] = write && changed,
                });
            }
        }
        return (issues, rows);
    }

    /// <summary>双源一致：数据面 vs 散文面（键集必须互为子集）。</summary>
    private static List<string> DualSourceCheck(string root, string pkg, string path,
        Dictionary<string, object?> ds)
    {
        var mdRel = PyStrOrEmpty(ds.GetValueOrDefault("markdown"));
        var pattern = PyStrOrEmpty(ds.GetValueOrDefault("key_pattern"));
        if (pattern.Length == 0) pattern = "`([A-Z][A-Z0-9_]{2,})`";
        var mdPath = Rel(root, $"community/{pkg}/{mdRel}");
        if (!File.Exists(mdPath)) return new List<string> { $"双源对照件不存在：{mdRel}" };
        var regex = new System.Text.RegularExpressions.Regex(pattern, RegexOptions.CultureInvariant);
        var mdKeys = regex.Matches(ReadText(mdPath)).Select(m => m.Groups[1].Value)
            .ToHashSet(StringComparer.Ordinal);
        foreach (var drop in PyList(ds.GetValueOrDefault("exclude"))) mdKeys.Remove(PyStr(drop));
        var (data, err) = ReadJson(Rel(root, $"community/{pkg}/{path}"));
        if (err.Length > 0) return new List<string> { err };
        var field = PyStrOrEmpty(ds.GetValueOrDefault("field"));
        if (field.Length == 0) field = "id";
        var dataKeys = new HashSet<string>(StringComparer.Ordinal);
        if (data is Dictionary<string, object?> map)
            foreach (var value in map.Values)
                foreach (var item in PyList(value).OfType<Dictionary<string, object?>>())
                    if (PyTruthy(item.GetValueOrDefault(field)))
                        dataKeys.Add(PyStr(item.GetValueOrDefault(field)));
        var onlyMd = mdKeys.Except(dataKeys).OrderBy(x => x, StringComparer.Ordinal).ToList();
        var onlyData = dataKeys.Except(mdKeys).OrderBy(x => x, StringComparer.Ordinal).ToList();
        var output = new List<string>();
        if (onlyMd.Count > 0) output.Add($"双源不一致：散文面独有键 {ReprList(onlyMd.Take(6))}");
        if (onlyData.Count > 0) output.Add($"双源不一致：数据面独有键 {ReprList(onlyData.Take(6))}");
        return output;
    }

    private static Dictionary<string, object?> Count(IEnumerable<Dictionary<string, object?>> rows, string key)
    {
        var output = new Dictionary<string, long>(StringComparer.Ordinal);
        foreach (var row in rows)
        {
            var k = PyStr(row.GetValueOrDefault(key));
            output[k] = output.GetValueOrDefault(k) + 1;
        }
        return output.OrderBy(kv => kv.Key, StringComparer.Ordinal)
            .ToDictionary(kv => kv.Key, kv => (object?)kv.Value, StringComparer.Ordinal);
    }

    /// <summary>复刻 <c>_deep_diff</c>：字典按并集键序、列表按下标、数值按 1e-9 容差。</summary>
    public static List<string> DeepDiff(object? a, object? b, string path = "$", List<string>? output = null)
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

    private static long PyLong(object? v) => v switch
    {
        long l => l,
        int i => i,
        double d => (long)Math.Truncate(d),
        _ => 0L,
    };

    private static string ReprList(IEnumerable<string> items) =>
        "[" + string.Join(", ", items.Select(PyScalar.PyRepr)) + "]";
}
