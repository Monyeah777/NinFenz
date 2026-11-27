using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace Nf.Engine;

/// <summary>参数值校验 + 仓库路径解析 + 知识读面工具（馆藏 / 实践包 / 模块 / 管线 / 注册表）。</summary>
public static partial class McpServer
{
    private static void ValidateArgumentValue(string toolName, string name, JsonElement value,
                                              string? expected)
    {
        switch (expected)
        {
            case "string":
                if (value.ValueKind != JsonValueKind.String)
                    throw new ArgumentException($"工具 {toolName} 参数 {name} 须为字符串");
                RequireArgText(toolName, name, value.GetString()!);
                return;
            case "boolean":
                if (value.ValueKind is not (JsonValueKind.True or JsonValueKind.False))
                    throw new ArgumentException($"工具 {toolName} 参数 {name} 须为布尔");
                return;
            case "array":
                if (value.ValueKind != JsonValueKind.Array)
                    throw new ArgumentException($"工具 {toolName} 参数 {name} 须为数组");
                if (value.GetArrayLength() > MaxArrayItems)
                    throw new ArgumentException($"工具 {toolName} 参数 {name} 数组过长");
                foreach (var item in value.EnumerateArray())
                {
                    if (item.ValueKind != JsonValueKind.String)
                        throw new ArgumentException($"工具 {toolName} 参数 {name} 只能包含字符串");
                    RequireArgText(toolName, name, item.GetString()!);
                }
                return;
            default:
                throw new ArgumentException($"工具 {toolName} 参数 {name} 的声明类型未知");
        }
    }

    private static void RequireArgText(string toolName, string name, string text)
    {
        if (text.Length > MaxArgChars)
            throw new ArgumentException($"工具 {toolName} 参数 {name} 超长（{text.Length} > {MaxArgChars}）");
        if (text.Any(ch => char.IsControl(ch)))
            throw new ArgumentException($"工具 {toolName} 参数 {name} 含控制字符");
    }

    private static void RequireSafePackage(string package)
    {
        if (package.Length == 0)
            return;
        if (package.Length > 128 || package.IndexOfAny(new[] { '/', '\\', ':', '*', '?' }) >= 0 ||
            package is "." or "..")
            throw new ArgumentException("package 必须是单个包目录名（不含路径分隔符与通配符）");
    }

    private static string RepoPath(string root, string rel, string label)
    {
        if (string.IsNullOrWhiteSpace(rel) || rel.Any(ch => char.IsControl(ch)))
            throw new ArgumentException($"{label} 为空或含控制字符");
        if (Path.IsPathRooted(rel) || rel.StartsWith("~", StringComparison.Ordinal) ||
            Regex.IsMatch(rel, @"^[A-Za-z]:(?![\\/])") || rel.StartsWith("\\\\", StringComparison.Ordinal))
            throw new ArgumentException($"{label} 不接受绝对路径/盘符相对写法：{rel}");
        if (rel.Contains(':') || Regex.IsMatch(rel, @"\.[A-Za-z0-9]{1,8}:[^\\/\s]"))
            throw new ArgumentException($"{label} 不接受 NTFS 备用数据流写法：{rel}");
        var parts = rel.Replace('\\', '/').Split('/', StringSplitOptions.RemoveEmptyEntries);
        if (parts.Any(part => part == ".."))
            throw new ArgumentException($"{label} 含 .. 越界段：{rel}");
        if (parts.Any(part => Regex.IsMatch(
                part, @"^(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.[^.]*)?$")))
            throw new ArgumentException($"{label} 指向 Windows 设备名：{rel}");
        var rootFull = Path.GetFullPath(root);
        var full = Path.GetFullPath(Path.Combine(rootFull,
            rel.Replace('/', Path.DirectorySeparatorChar)));
        var prefix = rootFull.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar)
                     + Path.DirectorySeparatorChar;
        var comparison = OperatingSystem.IsWindows()
            ? StringComparison.OrdinalIgnoreCase
            : StringComparison.Ordinal;
        if (!full.Equals(rootFull, comparison) && !full.StartsWith(prefix, comparison))
            throw new ArgumentException($"{label} 越出仓库根：{rel}");
        if (File.Exists(full))
        {
            var target = ResolveExistingTarget(rootFull, full);
            if (!target.Equals(rootFull, comparison) && !target.StartsWith(prefix, comparison))
                throw new ArgumentException($"{label} 经符号链接越出仓库根：{rel}");
        }
        return full;
    }

    private static string ResolveExistingTarget(string rootFull, string full)
    {
        var current = rootFull;
        var relative = Path.GetRelativePath(rootFull, full);
        foreach (var part in relative.Split(
                     new[] { Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar },
                     StringSplitOptions.RemoveEmptyEntries))
        {
            if (part == ".") continue;
            current = Path.Combine(current, part);
            FileSystemInfo info = Directory.Exists(current)
                ? new DirectoryInfo(current)
                : new FileInfo(current);
            if (!info.Exists || info.LinkTarget is null) continue;
            var resolved = info.ResolveLinkTarget(returnFinalTarget: true)?.FullName;
            if (resolved is null) continue;
            current = resolved;
        }
        return Path.GetFullPath(current);
    }

    private static byte[] ReadToolBytes(string path)
    {
        using var stream = new FileStream(path, FileMode.Open, FileAccess.Read,
                                          FileShare.ReadWrite | FileShare.Delete);
        if (stream.Length > MaxToolTextBytes)
            throw new ArgumentException(
                $"仓库文本超过上限 {MaxToolTextBytes} 字节（修复指引：拆分文件）");
        if (stream.Length > Array.MaxLength)
            throw new ArgumentException("仓库文本长度超出运行时数组上限");
        var raw = new byte[(int)stream.Length];
        stream.ReadExactly(raw);
        return raw;
    }

    /// <summary>等价 Python <c>Path.read_text(encoding="utf-8")</c>：UTF-8 解码 + 通用换行归一；返回文本与归一后的字节数。</summary>
    private static (string Text, int Bytes) ReadRepoText(string root, string rel)
    {
        var full = RepoPath(root, rel, "资源路径");
        var raw = new System.Text.UTF8Encoding(false).GetString(ReadToolBytes(full));
        var text = KnowledgeSig.Norm(raw);
        return (text, System.Text.Encoding.UTF8.GetByteCount(text));
    }

    private static Dictionary<string, object?> LibraryRead(string root, string entryId)
    {
        var want = entryId.Trim();
        foreach (var entry in Library.Entries(root))
        {
            if (!string.Equals(entry.Id, want, StringComparison.OrdinalIgnoreCase)) continue;
            var (text, bytes) = ReadRepoText(root, entry.Path);
            return new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["found"] = true, ["id"] = entry.Id, ["path"] = entry.Path,
                ["status"] = DictStr(entry.Fm, "status") is { Length: > 0 } s ? s : "active",
                ["frontmatter"] = entry.Fm, ["bytes"] = bytes, ["text"] = text,
            };
        }
        throw new ArgumentException($"馆藏条目未找到：{entryId}（library_search 可枚举；编号大小写不敏感）（修复指引：用 nf library ls 列全量编号）");
    }

    /// <summary>实践包门禁的机读面（与 CLI <c>patterns verify --json</c> 同源，只扫一遍）。</summary>
    private static Dictionary<string, object?> PatternsPayload(string root)
    {
        var (issues, warns, stats) = Patterns.Scan(root);
        return new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["issues"] = issues.Cast<object?>().ToList(),
            ["warns"] = warns.Cast<object?>().ToList(),
            ["projection"] = Patterns.CheckProjection(root).Cast<object?>().ToList(),
            ["stats"] = stats,
        };
    }

    /// <summary>
    /// MCP 面按**仓库相对路径**收参（与其它工具一致，如 <c>protocol/RECEIPTS.json</c>）；绝对路径原样使用。
    /// 注意：CLI 的 <c>st-validate</c> 与 Python 同口径按进程 CWD 解析——两者刻意不同，
    /// 因为 MCP 消费方（外部 agent）的世界观是"这一个仓库"。
    /// </summary>
    private static string ResolvePath(string root, string rel)
        => RepoPath(root, rel, "工具路径");

    /// <summary>自述数字实算的机读面（与 CLI <c>stats --json</c> 同源；只实算一遍）。</summary>
    private static Dictionary<string, object?> RepoStatsPayload(string root)
    {
        var (issues, stats) = RepoStats.Check(root);
        return new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["issues"] = issues.Cast<object?>().ToList(),
            ["stats"] = stats,
        };
    }

    /// <summary>
    /// 互操作导出面的机读面：<c>check=true</c> → 门禁；给了 <c>kind</c> → 该形状派生文档；
    /// 都不给 → 12 形状清单（与 CLI <c>interop --list</c> 同源）。
    /// </summary>
    private static object? InteropPayload(string root, JsonElement args)
    {
        if (Bool(args, "check"))
        {
            var (issues, stats) = Interop.Verify(root);
            return new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["issues"] = issues.Cast<object?>().ToList(),
                ["stats"] = stats,
            };
        }
        var kind = Str(args, "kind");
        if (kind.Length > 0)
        {
            if (!Interop.Kinds.Any(k => k.Id == kind))
            {
                throw new ArgumentException(
                    $"interop 未知形状：{kind}（可选：{string.Join(" / ", Interop.Kinds.Select(k => k.Id))}）");
            }
            return Interop.Document(kind, root);
        }
        return Interop.Kinds.Select(k => (object?)new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["id"] = k.Id,
            ["label"] = k.Label,
        }).ToList();
    }

    private static List<Dictionary<string, object?>> PatternLs(string root)
    {
        return Patterns.Entries(root).Select(e => new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["id"] = e.Dir,
            ["path"] = e.Path,
            ["title"] = DictStr(e.Fm, "name") is { Length: > 0 } name ? name : e.Dir,
            ["status"] = DictStr(e.Fm, "status"),
        }).ToList();
    }

    private static Dictionary<string, object?> PatternRead(string root, string patternId)
    {
        var want = patternId.Trim();
        foreach (var file in Assertions.Glob(root, "patterns/*/PATTERN.md"))
        {
            if (Path.GetFileName(Path.GetDirectoryName(file)!) != want) continue;
            var rel = Path.GetRelativePath(root, file).Replace('\\', '/');
            var (text, bytes) = ReadRepoText(root, rel);
            return new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["found"] = true, ["id"] = want, ["path"] = rel, ["bytes"] = bytes, ["text"] = text,
            };
        }
        throw new ArgumentException($"pattern 未找到：{patternId}（修复指引：patterns/ 下按目录名取，如 fail-closed-verification）");
    }

    private sealed record ModuleIndexRow(string? McId, string? TitleId, string Rel, bool HasContract);

    private static List<ModuleIndexRow> ModuleIndex(string root)
    {
        var docs = new List<string>();
        var core = Path.Combine(root, "04_模块库");
        if (Directory.Exists(core))
        {
            docs.AddRange(Directory.GetFiles(core, "*.md", SearchOption.AllDirectories));
        }
        var community = Path.Combine(root, "community");
        if (Directory.Exists(community))
        {
            foreach (var package in Directory.GetDirectories(community).OrderBy(d => Path.GetFileName(d), StringComparer.Ordinal))
            {
                var modules = Path.Combine(package, "modules");
                if (!Directory.Exists(modules)) continue;
                docs.AddRange(Directory.GetFiles(modules, "*.md").OrderBy(f => Path.GetFileName(f), StringComparer.Ordinal));
            }
        }
        var rows = new List<ModuleIndexRow>();
        foreach (var doc in docs.OrderBy(d => Path.GetRelativePath(root, d).Replace('\\', '/'), StringComparer.Ordinal))
        {
            var rel = Path.GetRelativePath(root, doc).Replace('\\', '/');
            _ = RepoPath(root, rel, "模块路径");
            var text = new System.Text.UTF8Encoding(false).GetString(ReadToolBytes(doc));
            var body = MiniYaml.ExtractFence(text, "machine_contract");
            string? mcId = null;
            if (body is not null)
            {
                var parsed = MiniYaml.Parse(body);
                if (parsed.TryGetValue("machine_contract", out var mc) && mc is Dictionary<string, object?> map &&
                    map.TryGetValue("id", out var id) && id is string idText && idText.Length > 0)
                {
                    mcId = idText;
                }
            }
            var titleMatch = System.Text.RegularExpressions.Regex.Match(text, @"#\s*模块\s+([^\s·]+)");
            rows.Add(new ModuleIndexRow(mcId, titleMatch.Success ? titleMatch.Groups[1].Value.Trim() : null, rel, mcId is not null));
        }
        return rows;
    }

    private static Dictionary<string, object?> ModuleRead(string root, string moduleId)
    {
        var req = moduleId.Trim();
        var exact = new List<ModuleIndexRow>();
        var suffix = new List<ModuleIndexRow>();
        foreach (var row in ModuleIndex(root))
        {
            var ids = new[] { row.McId, row.TitleId }.Where(x => !string.IsNullOrEmpty(x)).Select(x => x!).ToList();
            if (ids.Contains(req, StringComparer.Ordinal)) exact.Add(row);
            else if (req.All(char.IsAsciiDigit) && ids.Any(x => x.Split(':')[^1] == req)) suffix.Add(row);
        }
        ModuleIndexRow hit;
        if (exact.Count > 0) hit = exact[0];
        else if (suffix.Count == 1) hit = suffix[0];
        else if (suffix.Count > 1)
            throw new ArgumentException("module_id 存在多个同号限定（如 通用:M10 / 生存:M10）——请用限定 id（修复指引：先 registry_search 查全限定 id 再重试）");
        else
            throw new ArgumentException($"模块未找到：{moduleId}（module ls / registry_search 可枚举）（修复指引：用仓库内真实模块 id，如 M90、M40 或 通用:M10）");

        var (text, bytes) = ReadRepoText(root, hit.Rel);
        return new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["found"] = true,
            ["id"] = hit.McId ?? hit.TitleId ?? req,
            ["path"] = hit.Rel,
            ["has_machine_contract"] = hit.HasContract,
            ["bytes"] = bytes,
            ["text"] = text,
        };
    }

    private static Dictionary<string, object?> PipelineRead(string root, string pipeline)
    {
        var req = pipeline.Trim();
        var candidate = RepoPath(root, req, "管线路径");
        if (req.EndsWith(".md", StringComparison.Ordinal) && File.Exists(candidate))
        {
            var allowed = req.StartsWith("03_管线库/", StringComparison.Ordinal) ||
                          req.Contains("/pipelines/", StringComparison.Ordinal);
            if (!allowed)
                throw new ArgumentException("管线路径越界：只读 03_管线库 与 community/*/pipelines（修复指引：路径须指向仓库内管线件，如 03_管线库/P90….md）");
            var safeRel = Path.GetRelativePath(root, candidate).Replace('\\', '/');
            var (text, bytes) = ReadRepoText(root, safeRel);
            return new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["found"] = true, ["path"] = safeRel, ["bytes"] = bytes, ["text"] = text,
            };
        }

        var hits = new List<string>();
        foreach (var pattern in new[] { "03_管线库/*.md", "community/*/pipelines/*.md" })
        {
            foreach (var file in Assertions.Glob(root, pattern))
            {
                if (Path.GetFileName(file).Split('_')[0] == req) hits.Add(file);
            }
        }
        if (hits.Count == 0)
            throw new ArgumentException($"管线未找到：{pipeline}（pipeline_list 可枚举）（修复指引：用 Pxx 编号或仓库内相对路径）");
        var rel = Path.GetRelativePath(root, hits[0]).Replace('\\', '/');
        var (hitText, hitBytes) = ReadRepoText(root, rel);
        return new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["found"] = true, ["path"] = rel, ["bytes"] = hitBytes, ["text"] = hitText,
        };
    }

    /// <summary>等价 Python <c>_md_title</c>：首个以 # 开头的行 → <c>lstrip("# ").strip()</c>。</summary>
    private static string MdTitle(string text)
    {
        foreach (var line in KnowledgeSig.SplitLines(text))
        {
            if (line.StartsWith("#", StringComparison.Ordinal)) return line.TrimStart('#', ' ').Trim();
        }
        return "";
    }

    private static List<object?> PipelineList(string root, string query)
    {
        var output = new List<object?>();
        foreach (var pattern in new[] { "03_管线库/*.md", "community/*/pipelines/*.md" })
        {
            foreach (var file in Assertions.Glob(root, pattern))
            {
                var rel = Path.GetRelativePath(root, file).Replace('\\', '/');
                _ = RepoPath(root, rel, "管线路径");
                var text = new System.Text.UTF8Encoding(false).GetString(ReadToolBytes(file));
                var title = MdTitle(text);
                if (query.Length > 0 && !rel.Contains(query, StringComparison.Ordinal) &&
                    !title.Contains(query, StringComparison.Ordinal)) continue;
                output.Add(new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["path"] = rel, ["title"] = title,
                });
            }
        }
        return output;
    }

    private static List<object?> SpecList(string root)
    {
        using var registry = JsonIo.ReadFile(
            RepoPath(root, "desktop/src/core/registry.json", "注册表路径"));
        var output = new List<object?>();
        foreach (var protocol in registry.RootElement.GetProperty("protocols").EnumerateArray())
        {
            var moduleIds = protocol.TryGetProperty("module_ids", out var ids) && ids.ValueKind == JsonValueKind.Array
                ? ids.GetArrayLength()
                : 0;
            output.Add(new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["id"] = Str(protocol, "id"),
                ["version"] = Str(protocol, "version"),
                ["modules"] = moduleIds,
                ["categories"] = StringList(protocol, "categories").Cast<object?>().ToList(),
            });
        }
        return output;
    }

    private static Dictionary<string, object?> RegistryQuery(string root, string query)
    {
        using var registry = JsonIo.ReadFile(
            RepoPath(root, "desktop/src/core/registry.json", "注册表路径"));
        var q = query.Trim();
        var modules = new List<object?>();
        foreach (var module in registry.RootElement.GetProperty("modules").EnumerateArray())
        {
            var id = module.TryGetProperty("id", out var idElement) ? idElement.ToString() : "";
            var name = module.TryGetProperty("name", out var nameElement) ? nameElement.ToString() : "";
            if (!id.Contains(q, StringComparison.Ordinal) && !name.Contains(q, StringComparison.Ordinal)) continue;
            modules.Add(new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["id"] = module.TryGetProperty("id", out var mi) && mi.ValueKind == JsonValueKind.String ? mi.GetString() : null,
                ["name"] = module.TryGetProperty("name", out var mn) && mn.ValueKind == JsonValueKind.String ? mn.GetString() : null,
            });
        }
        var protocols = new List<object?>();
        foreach (var protocol in registry.RootElement.GetProperty("protocols").EnumerateArray())
        {
            var id = protocol.TryGetProperty("id", out var pid) ? pid.ToString() : "";
            var name = protocol.TryGetProperty("name", out var pname) ? pname.ToString() : "";
            if (!id.Contains(q, StringComparison.Ordinal) && !name.Contains(q, StringComparison.Ordinal)) continue;
            protocols.Add(new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["id"] = protocol.TryGetProperty("id", out var x) && x.ValueKind == JsonValueKind.String ? x.GetString() : null,
                ["version"] = protocol.TryGetProperty("version", out var v) && v.ValueKind == JsonValueKind.String ? v.GetString() : null,
                ["modules"] = protocol.TryGetProperty("module_ids", out var mids) && mids.ValueKind == JsonValueKind.Array
                    ? mids.GetArrayLength() : 0,
            });
        }
        return new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["modules"] = modules, ["protocols"] = protocols,
        };
    }
}
