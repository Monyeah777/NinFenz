using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace Nf.Engine;

/// <summary>工具载荷构造（verify / receipts / 断言 / 决策 / 馆藏 / 建模 / 签名 / 知识序 / 资产）+ 参数校验。</summary>
public static partial class McpServer
{
    private static Dictionary<string, object?> VerifyPayload(string root)
    {
        var protocol = Receipts.VerifyProtocolReceipts(root);
        var library = Receipts.VerifyLibraryReceipts(root);
        var chain = Receipts.VerifyTransparencyChain(root);
        var rows = CertificateVerifier.VerifyAll(root);
        var assertions = Assertions.Run(root);
        var decisions = Decisions.Verify(root);
        var cog = Cognition.Run(root);
        var lib = Library.Verify(root);
        var model = Modeling.Run(root);
        var components = new List<object?>
        {
            Component(protocol.Name, protocol.Ok, protocol.Issues, protocol.Detail),
            Component(library.Name, library.Ok, library.Issues, library.Detail),
            Component(chain.Name, chain.Ok, chain.Issues, chain.Detail),
            Component("protocol/combo_certificates.json", rows.All(r => r.Issues.Count == 0),
                rows.Where(r => r.Issues.Count > 0).SelectMany(r => r.Issues).ToList(),
                $"证书 {rows.Count} 条 · 失败 {rows.Count(r => r.Issues.Count > 0)}"),
            Component("protocol/assertions.json", assertions.Issues.Count == 0, assertions.Issues,
                $"断言 {assertions.Results.Count} 条 · 问题 {assertions.Issues.Count}"),
            Component("decisions/ADR-*.md", decisions.Issues.Count + decisions.Projection.Count == 0,
                decisions.Issues.Concat(decisions.Projection).ToList(),
                $"ADR {decisions.Stats["decisions"]} 条"),
            Component("library/NF-*.md", lib.Issues.Count + lib.Projection.Count == 0,
                lib.Issues.Concat(lib.Projection).ToList(), $"条目 {lib.Stats["entries"]}"),
            Component("model", model.Issues.Count == 0, model.Issues, $"问题 {model.Issues.Count}"),
        };
        var ok = components.Cast<Dictionary<string, object?>>().All(c => c["ok"] is true)
                 && cog.Issues.Count == 0;
        if (cog.Issues.Count > 0) components.Add(Component("cognition", false, cog.Issues, $"问题 {cog.Issues.Count}"));
        return new Dictionary<string, object?>(StringComparer.Ordinal) { ["ok"] = ok, ["components"] = components };
    }

    private static object? Component(string name, bool ok, IEnumerable<string> issues, string detail)
        => new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["name"] = name, ["ok"] = ok, ["issues"] = issues.Cast<object?>().ToList(), ["detail"] = detail,
        };

    private static Dictionary<string, object?> ReceiptsPayload(string root, string scope)
    {
        var result = scope == "library" ? Receipts.VerifyLibraryReceipts(root) : Receipts.VerifyProtocolReceipts(root);
        return new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["issues"] = result.Issues.Cast<object?>().ToList(),
            ["stats"] = new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["entries"] = result.Count, ["root"] = result.Root,
            },
        };
    }

    private static Dictionary<string, object?> AssertionsPayload(string root)
    {
        var result = Assertions.Run(root);
        return new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["issues"] = result.Issues.Cast<object?>().ToList(), ["results"] = result.Results,
        };
    }

    private static Dictionary<string, object?> DecisionsPayload(string root)
    {
        var result = Decisions.Verify(root);
        return new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["issues"] = result.Issues.Cast<object?>().ToList(),
            ["projection"] = result.Projection.Cast<object?>().ToList(),
            ["stats"] = result.Stats,
            ["warns"] = result.Warns.Cast<object?>().ToList(),
        };
    }

    private static Dictionary<string, object?> CognitionPayload(string root)
    {
        var result = Cognition.Run(root);
        return new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["issues"] = result.Issues.Cast<object?>().ToList(),
            ["stats"] = result.Stats,
            ["warns"] = result.Warns.Cast<object?>().ToList(),
        };
    }

    private static Dictionary<string, object?> LibraryPayload(string root)
    {
        var result = Library.Verify(root);
        return new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["issues"] = result.Issues.Cast<object?>().ToList(),
            ["projection"] = result.Projection.Cast<object?>().ToList(),
            ["stats"] = result.Stats,
            ["warns"] = result.Warns.Cast<object?>().ToList(),
        };
    }

    private static Dictionary<string, object?> ModelPayload(string root, string part)
    {
        var result = Modeling.Run(root, part);
        return new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["issues"] = result.Issues.Cast<object?>().ToList(),
            ["stats"] = result.Stats,
            ["warns"] = result.Warns.Cast<object?>().ToList(),
        };
    }

    private static Dictionary<string, object?> SigPayload(string root, bool verify)
    {
        if (!verify) return new Dictionary<string, object?>(StringComparer.Ordinal) { ["records"] = KnowledgeSig.Scan(root).Records };
        var (issues, stats) = KnowledgeSig.VerifyReproducible(root);
        return new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["issues"] = issues.Cast<object?>().ToList(), ["stats"] = stats,
        };
    }

    /// <summary>等价 Python <c>library._tokens</c>：英文词 + 数字 + 中文整段与 2-gram。</summary>
    private static List<string> Tokens(string text)
    {
        var lowered = text.ToLowerInvariant();
        var tokens = System.Text.RegularExpressions.Regex.Matches(lowered, "[a-z0-9_]+")
            .Select(m => m.Value).ToList();
        foreach (System.Text.RegularExpressions.Match han in
                 System.Text.RegularExpressions.Regex.Matches(lowered, "[\u4e00-\u9fa5]+"))
        {
            var run = han.Value;
            tokens.Add(run);
            if (run.Length > 2)
            {
                for (var i = 0; i + 2 <= run.Length; i++) tokens.Add(run.Substring(i, 2));
            }
        }
        return tokens;
    }

    /// <summary>等价 Python <c>library.search</c>（倒排权重 + 裸子串兜底 + (-score, id) 排序）。</summary>
    private static List<Dictionary<string, object?>> LibrarySearchIndex(string root, string query, int limit = 10)
    {
        var entries = Library.Entries(root);
        var index = new Dictionary<string, Dictionary<string, int>>(StringComparer.Ordinal);
        foreach (var entry in entries)
        {
            var (text, _) = ReadRepoText(root, entry.Path);
            var body = System.Text.RegularExpressions.Regex.Replace(text, "(?m)^#{1,6}\\s*", "");
            if (body.Length > 8000) body = body[..8000];
            var fields = new (string Text, int Weight)[]
            {
                (DictStr(entry.Fm, "title"), 6),
                (DictStr(entry.Fm, "description"), 4),
                (string.Join(" ", DictList(entry.Fm, "tags")), 3),
                (string.Join(" ", DictList(entry.Fm, "sources")), 2),
                (entry.Id, 5),
                (body, 1),
            };
            foreach (var (fieldText, weight) in fields)
            {
                foreach (var token in Tokens(fieldText).Distinct(StringComparer.Ordinal))
                {
                    if (!index.TryGetValue(token, out var byId)) index[token] = byId = new Dictionary<string, int>(StringComparer.Ordinal);
                    byId[entry.Id] = (byId.TryGetValue(entry.Id, out var w) ? w : 0) + weight;
                }
            }
        }

        var scores = new Dictionary<string, int>(StringComparer.Ordinal);
        var queryLow = query.Trim().ToLowerInvariant();
        foreach (var token in Tokens(query).Distinct(StringComparer.Ordinal))
        {
            if (!index.TryGetValue(token, out var byId)) continue;
            foreach (var (id, weight) in byId) scores[id] = (scores.TryGetValue(id, out var s) ? s : 0) + weight;
        }
        foreach (var entry in entries)
        {
            var (text, _) = ReadRepoText(root, entry.Path);
            if (queryLow.Length > 0 && text.ToLowerInvariant().Contains(queryLow, StringComparison.Ordinal))
                scores[entry.Id] = (scores.TryGetValue(entry.Id, out var s) ? s : 0) + 2;
        }

        var output = new List<Dictionary<string, object?>>();
        foreach (var (id, score) in scores.OrderBy(kv => -kv.Value).ThenBy(kv => kv.Key, StringComparer.Ordinal))
        {
            var entry = entries.First(e => e.Id == id);
            output.Add(new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["id"] = id,
                ["score"] = score,
                ["title"] = DictStr(entry.Fm, "title") is { Length: > 0 } t ? t : id,
                ["type"] = DictStr(entry.Fm, "type"),
                ["status"] = DictStr(entry.Fm, "status") is { Length: > 0 } st ? st : "active",
                ["path"] = entry.Path,
                ["description"] = DictStr(entry.Fm, "description"),
            });
            if (output.Count >= limit) break;
        }
        return output;
    }

    private static List<object?> LibrarySearch(string root, string query)
    {
        var q = query.Trim();
        var hits = new List<object?>();
        foreach (var hit in LibrarySearchIndex(root, q))
        {
            hits.Add(new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["kind"] = "library", ["id"] = hit["id"], ["path"] = hit["path"],
                ["title"] = hit["title"], ["score"] = hit["score"], ["status"] = hit["status"],
                ["type"] = hit["type"], ["uri"] = "nf://repo/library/" + hit["id"],
            });
        }
        foreach (var file in Directory.Exists(root)
                     ? Directory.GetFiles(root, "*.md").Select(Path.GetFileName).Select(x => x!).OrderBy(x => x, StringComparer.Ordinal)
                     : Enumerable.Empty<string>())
        {
            var include = file.StartsWith("0", StringComparison.Ordinal) ||
                          file.StartsWith("4", StringComparison.Ordinal) ||
                          (file.Length >= 2 && char.IsAsciiDigit(file[0]) && char.IsAsciiDigit(file[1]));
            if (!include) continue;
            var (text, _) = ReadRepoText(root, file);
            var title = MdTitle(text);
            if (file.Contains(q, StringComparison.Ordinal) || title.Contains(q, StringComparison.Ordinal))
                hits.Add(new Dictionary<string, object?>(StringComparer.Ordinal) { ["kind"] = "doc", ["path"] = file, ["title"] = title });
        }
        foreach (var pattern in new[] { "docs/*.md", "community/*/README.md" })
        {
            foreach (var file in Assertions.Glob(root, pattern))
            {
                var rel = Path.GetRelativePath(root, file).Replace('\\', '/');
                var (text, _) = ReadRepoText(root, rel);
                var title = MdTitle(text);
                if (Path.GetFileName(rel).Contains(q, StringComparison.Ordinal) || title.Contains(q, StringComparison.Ordinal))
                    hits.Add(new Dictionary<string, object?>(StringComparer.Ordinal) { ["kind"] = "doc", ["path"] = rel, ["title"] = title });
            }
        }
        return hits.Take(10).ToList();
    }

    private static Dictionary<string, object?> KnowledgeOrder(string root, string clearance)
    {
        using var decl = JsonIo.ReadFile(
            RepoPath(root, "protocol/knowledge_sources.json", "知识源路径"));
        var order = decl.RootElement.TryGetProperty("query_order", out var qo) && qo.ValueKind == JsonValueKind.Array
            ? qo.EnumerateArray().Select(x => x.ValueKind == JsonValueKind.String ? x.GetString()! : x.GetRawText()).ToList()
            : new List<string>();
        var sources = new Dictionary<string, JsonElement>(StringComparer.Ordinal);
        if (decl.RootElement.TryGetProperty("sources", out var sourceArray))
        {
            foreach (var source in sourceArray.EnumerateArray())
            {
                if (source.TryGetProperty("id", out var id) && id.ValueKind == JsonValueKind.String)
                    sources[id.GetString()!] = source;
            }
        }
        var rank = new Dictionary<string, int>(StringComparer.Ordinal) { ["public"] = 0, ["internal"] = 1, ["restricted"] = 2 };
        HashSet<string>? allowed = null;
        if (clearance.Length > 0)
        {
            allowed = new HashSet<string>(StringComparer.Ordinal);
            if (rank.TryGetValue(clearance, out var cap))
            {
                foreach (var (id, source) in sources)
                {
                    var visibility = source.TryGetProperty("visibility", out var v) && v.ValueKind == JsonValueKind.String
                        ? v.GetString()! : "";
                    if (rank.TryGetValue(visibility, out var sourceRank) && sourceRank <= cap) allowed.Add(id);
                }
            }
        }
        var rows = new List<object?>();
        foreach (var id in order)
        {
            if (!sources.TryGetValue(id, out var source)) continue;
            if (allowed is not null && !allowed.Contains(id)) continue;
            var requiresLabel = source.TryGetProperty("requires_source_label", out var r) && r.ValueKind == JsonValueKind.True;
            rows.Add(new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["id"] = id,
                ["authority"] = source.TryGetProperty("authority", out var a) ? a.ToString() : "",
                ["kind"] = source.TryGetProperty("kind", out var k) ? k.ToString() : "",
                ["locator"] = source.TryGetProperty("locator", out var l) ? l.ToString() : "",
                ["requires_source_label"] = requiresLabel ? "true" : "false",
                ["visibility"] = source.TryGetProperty("visibility", out var vv) ? vv.ToString() : "",
            });
        }
        return new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["clearance"] = clearance.Length > 0 ? clearance : "不裁剪",
            ["contract_first"] = true,
            ["count"] = rows.Count,
            ["query_order"] = rows,
        };
    }

    private static (string Text, int Bytes) AssetText(string root, string rel) => ReadRepoText(root, rel);

    /// <summary>等价 Python <c>_asset_keys_of_file</c>：文件名令牌 ∪ 正文键声明（`KEY` / "KEY": / ## KEY）。</summary>
    private static List<string> AssetKeysOfFile(string file)
    {
        var stem = Path.GetFileNameWithoutExtension(file);
        var keys = new HashSet<string>(StringComparer.Ordinal);
        foreach (System.Text.RegularExpressions.Match m in
                 System.Text.RegularExpressions.Regex.Matches(stem, "[A-Z][A-Z0-9_]*"))
        {
            keys.Add(m.Value);
        }
        var text = new System.Text.UTF8Encoding(false).GetString(ReadToolBytes(file));
        var head = text.Length > 6000 ? text[..6000] : text;
        foreach (var pattern in new[] { "`([A-Z][A-Z0-9_]{2,})`", "\"([A-Z][A-Z0-9_]{2,})\"\\s*:", "##\\s*([A-Z][A-Z0-9_]{2,})" })
        {
            foreach (System.Text.RegularExpressions.Match m in System.Text.RegularExpressions.Regex.Matches(head, pattern))
            {
                keys.Add(m.Groups[1].Value);
            }
        }
        return keys.OrderBy(x => x, StringComparer.Ordinal).ToList();
    }

    private static List<Dictionary<string, object?>> AssetLs(string root, string package)
    {
        RequireSafePackage(package);
        var patterns = package.Length > 0
            ? new[] { $"community/{package}/assets/*.md" }
            : new[] { "community/*/assets/*.md", "05_资产库/用户自定义/*.md" };
        var rows = new List<Dictionary<string, object?>>();
        foreach (var pattern in patterns)
        {
            foreach (var file in Assertions.Glob(root, pattern))
            {
                if (Path.GetFileName(file) == "README.md") continue;
                var rel = Path.GetRelativePath(root, file).Replace('\\', '/');
                try
                {
                    _ = RepoPath(root, rel, "资产路径");
                }
                catch (ArgumentException)
                {
                    // 越根项不得进入列出面，更不能被随后的键扫描读取。
                    continue;
                }
                var keys = AssetKeysOfFile(file);
                if (keys.Count == 0) continue;
                rows.Add(new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["package"] = rel.StartsWith("community/", StringComparison.Ordinal) ? rel.Split('/')[1] : "官方",
                    ["file"] = rel,
                    ["keys"] = keys,
                });
            }
        }
        return rows;
    }

    private static Dictionary<string, object?> AssetGet(string root, string key, string package)
    {
        RequireSafePackage(package);
        var req = key.Trim();
        var patterns = package.Length > 0
            ? new[] { $"community/{package}/assets/*.md" }
            : new[] { "community/*/assets/*.md", "05_资产库/用户自定义/*.md" };
        var hits = new List<(string Package, string File)>();
        foreach (var pattern in patterns)
        {
            foreach (var file in Assertions.Glob(root, pattern))
            {
                if (Path.GetFileName(file) == "README.md") continue;
                var rel = Path.GetRelativePath(root, file).Replace('\\', '/');
                _ = RepoPath(root, rel, "资产路径");
                if (!AssetKeysOfFile(file).Contains(req, StringComparer.Ordinal)) continue;
                hits.Add((rel.StartsWith("community/", StringComparison.Ordinal) ? rel.Split('/')[1] : "官方", rel));
            }
        }
        if (hits.Count == 0)
            throw new ArgumentException($"资产键未找到：{key}（asset ls / 包 assets/README.md 可枚举）（修复指引：用包内资产键表登记的键名重试）");
        var matches = new List<object?>();
        foreach (var (pkg, rel) in hits)
        {
            var (text, bytes) = AssetText(root, rel);
            matches.Add(new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["package"] = pkg, ["file"] = rel, ["bytes"] = bytes, ["text"] = text,
            });
        }
        return new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["found"] = true, ["key"] = req, ["matches"] = matches,
        };
    }

    private static List<string> DictList(Dictionary<string, object?> map, string key)
        => map.TryGetValue(key, out var value) && value is List<string> list ? list : new List<string>();

    private static void ValidateArguments(string toolName, JsonElement args)
    {
        if (args.ValueKind == JsonValueKind.Undefined)
            return;
        if (args.ValueKind != JsonValueKind.Object)
            throw new ArgumentException("arguments 须为对象");
        var properties = args.EnumerateObject().ToList();
        if (properties.Count > MaxArgs)
            throw new ArgumentException($"工具 {toolName} 参数过多（{properties.Count} > {MaxArgs}）");
        var schema = Tools.First(t => t.Name == toolName).Schema;
        var allowed = (Dictionary<string, object?>)schema["properties"]!;
        foreach (var property in properties)
        {
            if (!allowed.TryGetValue(property.Name, out var rawRule))
                throw new ArgumentException($"工具 {toolName} 不接受参数 {property.Name}（修复指引：按 inputSchema 传参）");
            var rule = rawRule as Dictionary<string, object?>;
            var expected = rule is not null && rule.TryGetValue("type", out var type) ? type as string : null;
            ValidateArgumentValue(toolName, property.Name, property.Value, expected);
        }
    }
}
