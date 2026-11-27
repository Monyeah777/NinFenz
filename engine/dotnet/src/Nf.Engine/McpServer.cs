using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace Nf.Engine;

/// <summary>
/// NF .NET 引擎的 MCP stdio 服务器：**协议机制与仓库侧 <c>core/mcp_runtime.py</c> 对齐**
/// （JSON-RPC 2.0 · 换行分隔帧 · dual-era 版本处理 · 可缓存结果三键 · 同一套错误码与消息），
/// **工具目录不同**——这里暴露的是本引擎自己的只读判据面（不回填 Python 侧的快照工具集）。
///
/// 与 Python 侧的差别（刻意）：不需要 mcp 快照，直接对仓库根求解。
/// </summary>
public static partial class McpServer
{
    public const string ModernVersion = "2026-07-28";
    public const string LegacyVersion = "2025-11-25";
    public static readonly string[] SupportedVersions = { ModernVersion, LegacyVersion };
    public const string JsonRpcVersion = "2.0";

    private const string MetaProtocolVersion = "io.modelcontextprotocol/protocolVersion";
    private const string MetaClientInfo = "io.modelcontextprotocol/clientInfo";
    private const string MetaClientCapabilities = "io.modelcontextprotocol/clientCapabilities";
    private const string MetaServerInfo = "io.modelcontextprotocol/serverInfo";

    private const int ParseError = -32700;
    private const int InvalidRequest = -32600;
    private const int MethodNotFound = -32601;
    private const int InvalidParams = -32602;
    private const int InternalError = -32603;
    private const int UnsupportedProtocolVersion = -32022;
    internal const int MaxRequestChars = 8 * 1024 * 1024;
    private const int MaxArgs = 8;
    private const int MaxArgChars = 4096;
    private const int MaxArrayItems = 128;
    private const int MaxToolTextBytes = 8 * 1024 * 1024;

    public const string ServerName = "nf-dotnet-engine";
    public const string ServerVersion = "0.1.0";

    private static readonly (string Name, string Description, Dictionary<string, object?> Schema)[] Tools =
    {
        ("nf_verify", "只读总检：协议回执 / 馆藏回执 / 透明链 / 组合证书 / 断言表 / 决策门禁 / 馆藏条目与投影 / 建模三件", ObjectSchema()),
        ("nf_receipts", "回执复算（scope=protocol|library）", ObjectSchema(("scope", "string", "protocol 或 library，缺省 protocol"))),
        ("nf_transparency", "透明链复算（哈希链自洽 + 在盘生成物一致）", ObjectSchema()),
        ("nf_combine_verify", "组合证书 T4 复算（按 packs+extra_modules 重算并与在盘证书逐字段比对）", ObjectSchema()),
        ("nf_combine_plan", "组合求解（并集闭包补齐 → 层栈/闭包/借阅 → 证书）", ObjectSchema(("packs", "array", "包名数组"), ("extra_modules", "array", "额外模块 id 数组（可选）"), ("strict_coherence", "boolean", "ISA v1 C1′ 严格相干：撞号即 DENY（默认与 Python 同口径静默塌陷）"))),
        ("nf_assertions", "数据化断言表求值（封闭 kind 集）", ObjectSchema()),
        ("nf_decisions", "决策记录门禁（ADR 编号/状态/取代链/证据/回执锚定/INDEX 投影）", ObjectSchema()),
        ("nf_cognition", "认知族门禁（术语表真源逐字命中 + 执行分档结构块）", ObjectSchema()),
        ("nf_library", "馆藏门（frontmatter + 签名锚漂移 + INDEX/ALIAS 投影）", ObjectSchema()),
        ("nf_model", "内容建模三件（part=vocab|normative|contracts，缺省三件全跑）", ObjectSchema(("part", "string", "vocab / normative / contracts"))),
        ("nf_sig", "知识签名（verify=true 时跑两遍一致性证明）", ObjectSchema(("verify", "boolean", "true=只跑可复现性校验"))),
        ("nf_bench", "性能基线测量（八项关键操作）", ObjectSchema()),
        ("nf_patterns_list", "实践包清单（id / 名称 / 状态 / 适用面；真源 = 各包 frontmatter，投影 = patterns/INDEX.md）", ObjectSchema()),
        ("nf_patterns_for", "反向查询：某文件适用哪些实践包（含通配符走 fnmatch，Windows 下大小写不敏感）", ObjectSchema(("target", "string", "目标路径（仓库相对，如 protocol/RECEIPTS.json）"))),
        ("nf_patterns_verify", "实践包门禁（必填字段 / 可证性 / INDEX 投影一致 → issues/warns/projection/stats）", ObjectSchema()),
        ("nf_stats", "自述数字实算（README / README.en / llms.txt 生成区 == 实算；在盘 repo_stats.json == 实算）", ObjectSchema()),
        ("nf_interop", "互操作导出面：kind 缺省列 12 形状清单；给 kind 返回该形状派生文档；check=true 跑导出面门禁", ObjectSchema(("kind", "string", "导出形状（openapi/asyncapi/intoto/sbom/slsa/a2a/prov/cyclonedx/vc/c2pa/cid/decisions）"), ("check", "boolean", "true=跑门禁（覆盖完整 + 形状合法 + 确定性）"))),
        ("nf_st_validate", "ST 制卡校验器（卡 / 世界书 / MVU 变量 JSON → R1/R3/R4 可自动化项报告；只读，不落报告文件）", ObjectSchema(("path", "string", "被校验 JSON 的路径"))),
        // —— 以下三个与仓库侧 mcp_runtime 的**同名同形**：工具级逐字节对账已实测（见 README 第二十四片）
        ("pipeline_list", "列出 NF 管线清单（03_管线库 + community 包 pipelines）", ObjectSchema(("query", "string", "可选过滤串（匹配 id/标题）"))),
        ("spec_list", "列出 registry protocols 协议包清单（id/version/模块数/类别）", ObjectSchema()),
        ("registry_search", "查询 registry 模块/协议（按 id/name 子串匹配，只读）", ObjectSchema(("query", "string", "检索串（如 M90 或 域包 id）"))),
        ("library_read", "取云端图书馆馆藏条目正文（按 NF 编号，大小写不敏感；返回 frontmatter + 全文）", ObjectSchema(("entry_id", "string", "馆藏编号（如 NF-1）"))),
        ("pattern_list", "列出实践包清单（id / path / title / status；只读）", ObjectSchema()),
        ("pattern_read", "取实践包（patterns/）正文：按 id 返回 frontmatter + 可执行规则 + 正反例（只读）", ObjectSchema(("pattern_id", "string", "pattern id（如 fail-closed-verification）"))),
        ("module_read", "取模块文档正文（04_模块库 与 community 包 modules；支持全限定 id 与裸号）", ObjectSchema(("module_id", "string", "模块 id（如 M90 / 通用:M10）"))),
        ("pipeline_read", "取管线正文（按 Pxx 编号或仓库内相对路径；只读 03_管线库 与 community/*/pipelines）", ObjectSchema(("pipeline", "string", "Pxx 或相对路径（如 03_管线库/P90….md）"))),
        ("library_search", "仓库侧知识库检索：馆藏条目（正文级）+ docs + community README + 编号方案文档", ObjectSchema(("query", "string", "检索串"))),
        ("knowledge_order_read", "解析知识源查询顺序（先合同级后参考级；可按可见性 clearance 裁剪）", ObjectSchema(("clearance", "string", "可见性上限（public/internal/restricted）"))),
        ("asset_list", "列出资产文件与声明的键（可限定包；只读）", ObjectSchema(("package", "string", "包名（可选）"))),
        ("asset_read", "取资产正文（按资产键；可限定包）", ObjectSchema(("key", "string", "资产键"), ("package", "string", "包名（可选）"))),
    };

    private static Dictionary<string, object?> ObjectSchema(params (string Name, string Type, string Description)[] properties)
    {
        var props = new Dictionary<string, object?>(StringComparer.Ordinal);
        foreach (var (name, type, description) in properties)
        {
            props[name] = new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["type"] = type, ["description"] = description,
            };
        }
        return new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["type"] = "object", ["properties"] = props, ["additionalProperties"] = false,
        };
    }

    /// <summary>等价 Python <c>encode_message</c>：单行 JSON，U+2028/2029/0085 转义（帧边界陷阱）。</summary>
    /// <summary>
    /// 本引擎暴露的工具名。供自检做「真源 <c>core.mcp_runtime.TOOL_DEFS</c> ⊆ 引擎工具面」的**镜像交叉核验**：
    /// <c>ProseLint.CommandFace</c> 用的是真源那 12 个基名（引擎自有 18 个 <c>nf_*</c> 不在其内），
    /// 若引擎的 MCP 面把基名工具删了，这条钉会红。
    /// </summary>
    public static IReadOnlyList<string> ToolNames => Tools.Select(t => t.Name).ToList();

    public static string EncodeMessage(object? message)
        => PythonJson.CanonicalizeGraph(message)
            .Replace("\u2028", "\\u2028").Replace("\u2029", "\\u2029").Replace("\u0085", "\\u0085");

    /// <summary>等价 Python <c>McpRuntime.handle</c>。返回 null 表示"不应答"（通知或非法输入）。</summary>
    public static Dictionary<string, object?>? Handle(string root, JsonElement msg)
    {
        if (msg.ValueKind != JsonValueKind.Object)
            return Err(root, InvalidRequest, "消息必须是 JSON 对象", null, null);
        if (Str(msg, "jsonrpc") != JsonRpcVersion)
            return Err(root, InvalidRequest, $"jsonrpc 版本必须为 {JsonRpcVersion}", null, null);
        if (!msg.TryGetProperty("method", out var methodElement) || methodElement.ValueKind != JsonValueKind.String)
            return Err(root, InvalidRequest, "缺 method", null, null);
        var method = methodElement.GetString()!;

        var isRequest = msg.TryGetProperty("id", out var idElement);
        JsonElement? id = isRequest ? idElement : null;
        if (isRequest && !IsValidId(idElement))
            return Err(root, InvalidRequest, "id 必须是字符串、数字或 null（修复指引：按 JSON-RPC 2.0 §4 用请求序号，勿用结构体/布尔）", null, null);

        JsonElement paramsElement = default;
        var hasParams = msg.TryGetProperty("params", out var p) && p.ValueKind != JsonValueKind.Null;
        if (hasParams)
        {
            paramsElement = p;
            if (p.ValueKind is not (JsonValueKind.Object or JsonValueKind.Array))
                return Err(root, InvalidRequest, "params 必须是结构化值（对象或数组）（修复指引：JSON-RPC 2.0 §4.2——原始类型参数非法）", id, null);
            if (p.ValueKind == JsonValueKind.Array)
                return Err(root, InvalidParams, "params 只接受按名对象（修复指引：改用 {name: value} 形式，本运行时无位置参数面）", id, null);
        }

        // modern 版本协商：请求自带 _meta 版本时逐请求校验
        if (hasParams && paramsElement.TryGetProperty("_meta", out var meta) && meta.ValueKind == JsonValueKind.Object)
        {
            var requested = meta.TryGetProperty(MetaProtocolVersion, out var rv) && rv.ValueKind == JsonValueKind.String
                ? rv.GetString()
                : null;
            if (requested is not null && !SupportedVersions.Contains(requested, StringComparer.Ordinal))
            {
                if (!isRequest) return null;
                return Err(root, UnsupportedProtocolVersion, "Unsupported protocol version", null,
                    new Dictionary<string, object?>(StringComparer.Ordinal)
                    {
                        ["supported"] = SupportedVersions.Cast<object?>().ToList(),
                        ["requested"] = requested,
                    });
            }
        }

        Dictionary<string, object?>? result;
        try
        {
            result = Dispatch(root, method, hasParams ? paramsElement : default);
        }
        catch (ArgumentException exc)
        {
            return isRequest ? ErrorAt(InvalidParams, exc.Message, idElement) : null;
        }

        if (result is null)
        {
            return isRequest
                ? ErrorAt(MethodNotFound, $"Method not found: {method}", idElement)
                : null;
        }
        if (!isRequest) return null;
        return new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["jsonrpc"] = JsonRpcVersion, ["id"] = ToNode(idElement), ["result"] = result,
        };
    }

    private static Dictionary<string, object?>? Dispatch(string root, string method, JsonElement parameters)
    {
        switch (method)
        {
            case "server/discover":
                return new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["resultType"] = "complete",
                    ["supportedVersions"] = SupportedVersions.Cast<object?>().ToList(),
                    ["capabilities"] = Capabilities(),
                    ["_meta"] = new Dictionary<string, object?>(StringComparer.Ordinal)
                    {
                        [MetaServerInfo] = new Dictionary<string, object?>(StringComparer.Ordinal)
                        {
                            ["name"] = ServerName, ["version"] = ServerVersion,
                        },
                    },
                    ["instructions"] = "NF .NET 工业引擎只读判据面：回执/透明链/组合证书/断言表/决策门禁/馆藏门/建模三件/知识签名/性能基线。全部只读，不写仓库。",
                    ["ttlMs"] = 3600000,
                    ["cacheScope"] = "public",
                };
            case "initialize":
                var requested = parameters.ValueKind == JsonValueKind.Object &&
                                parameters.TryGetProperty("protocolVersion", out var pv) && pv.ValueKind == JsonValueKind.String
                    ? pv.GetString()
                    : null;
                var version = requested is not null && SupportedVersions.Contains(requested, StringComparer.Ordinal)
                    ? requested
                    : LegacyVersion;
                return new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["protocolVersion"] = version,
                    ["capabilities"] = Capabilities(),
                    ["serverInfo"] = new Dictionary<string, object?>(StringComparer.Ordinal)
                    {
                        ["name"] = ServerName, ["version"] = ServerVersion,
                    },
                };
            case "tools/list":
                return Cacheable(new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["tools"] = Tools.Select(t => (object?)new Dictionary<string, object?>(StringComparer.Ordinal)
                    {
                        ["name"] = t.Name, ["description"] = t.Description, ["inputSchema"] = t.Schema,
                    }).ToList(),
                });
            case "tools/call":
                return CallTool(root, parameters);
            case "ping":
                return new Dictionary<string, object?>(StringComparer.Ordinal);
            default:
                return null;
        }
    }

    private static Dictionary<string, object?> CallTool(string root, JsonElement parameters)
    {
        if (parameters.ValueKind != JsonValueKind.Object ||
            !parameters.TryGetProperty("name", out var nameElement) || nameElement.ValueKind != JsonValueKind.String)
            throw new ArgumentException("tools/call 需 params{name, arguments}");
        var name = nameElement.GetString()!;
        if (Tools.All(t => t.Name != name))
        {
            throw new ArgumentException($"未知工具：{name}（只读工具面 = {string.Join("、", Tools.Select(t => t.Name).OrderBy(x => x, StringComparer.Ordinal))}）");
        }
        var args = default(JsonElement);
        if (parameters.TryGetProperty("arguments", out var a) && a.ValueKind != JsonValueKind.Null)
        {
            if (a.ValueKind != JsonValueKind.Object)
                throw new ArgumentException("arguments 须为对象（修复指引：按 inputSchema 传 {name: value}）");
            args = a;
        }
        ValidateArguments(name, args);

        object? payload = name switch
        {
            "nf_verify" => VerifyPayload(root),
            "nf_receipts" => ReceiptsPayload(root, Str(args, "scope") is { Length: > 0 } scope ? scope : "protocol"),
            "nf_transparency" => Receipts.VerifyTransparencyChain(root) is var chain
                ? new Dictionary<string, object?>
                {
                    ["issues"] = chain.Issues.Cast<object?>().ToList(),
                    ["stats"] = new Dictionary<string, object?>
                    {
                        ["head"] = chain.Root[..16], ["links"] = chain.Count, ["issues"] = chain.Issues.Count,
                    },
                } : null,
            "nf_combine_verify" => new Dictionary<string, object?>
            {
                ["rows"] = CertificateVerifier.VerifyAll(root).Select(r => (object?)new Dictionary<string, object?>
                {
                    ["label"] = r.Label, ["legal"] = r.Legal, ["modules"] = r.Modules,
                    ["issues"] = r.Issues.Cast<object?>().ToList(),
                }).ToList(),
            },
            "nf_combine_plan" => Combinator.Build(root, StringList(args, "packs"), StringList(args, "extra_modules"),
                strictCoherence: Bool(args, "strict_coherence")).Certificate,
            "nf_assertions" => AssertionsPayload(root),
            "nf_decisions" => DecisionsPayload(root),
            "nf_cognition" => CognitionPayload(root),
            "nf_library" => LibraryPayload(root),
            "nf_model" => ModelPayload(root, Str(args, "part")),
            "nf_sig" => SigPayload(root, Bool(args, "verify")),
            "nf_bench" => new Dictionary<string, object?>
            {
                ["ops"] = Bench.Run(root).Select(m => (object?)new Dictionary<string, object?>
                {
                    ["name"] = m.Name, ["ms"] = m.Milliseconds, ["detail"] = m.Detail,
                }).ToList(),
            },
            "nf_patterns_list" => Patterns.Entries(root).Select(e => (object?)new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["id"] = e.Fm.TryGetValue("id", out var pid) ? pid : null,
                ["name"] = e.Fm.TryGetValue("name", out var pname) ? pname : null,
                ["status"] = e.Fm.TryGetValue("status", out var pst) ? pst : null,
                ["applies_to"] = e.Fm.TryGetValue("applies_to", out var pat) ? pat : null,
            }).ToList(),
            "nf_patterns_for" => Patterns.ForPath(root, Str(args, "target")).Cast<object?>().ToList(),
            "nf_patterns_verify" => PatternsPayload(root),
            "nf_stats" => RepoStatsPayload(root),
            "nf_interop" => InteropPayload(root, args),
            "nf_st_validate" => StValidate.Validate(ResolvePath(root, Str(args, "path"))),
            "pipeline_list" => PipelineList(root, Str(args, "query")),
            "spec_list" => SpecList(root),
            "registry_search" => RegistryQuery(root, Str(args, "query")),
            "library_read" => LibraryRead(root, Str(args, "entry_id")),
            "pattern_list" => PatternLs(root),
            "pattern_read" => PatternRead(root, Str(args, "pattern_id")),
            "module_read" => ModuleRead(root, Str(args, "module_id")),
            "pipeline_read" => PipelineRead(root, Str(args, "pipeline")),
            "library_search" => LibrarySearch(root, Str(args, "query")),
            "knowledge_order_read" => KnowledgeOrder(root, Str(args, "clearance")),
            "asset_list" => AssetLs(root, Str(args, "package")),
            "asset_read" => AssetGet(root, Str(args, "key"), Str(args, "package")),
            _ => null,
        };

        return new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["content"] = new List<object?>
            {
                new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["type"] = "text",
                    ["text"] = PythonJson.Indented(payload),
                },
            },
        };
    }

    private static Dictionary<string, object?> Capabilities()
        => new(StringComparer.Ordinal) { ["resources"] = new Dictionary<string, object?>(), ["tools"] = new Dictionary<string, object?>(), ["prompts"] = new Dictionary<string, object?>() };

    private static Dictionary<string, object?> Cacheable(Dictionary<string, object?> payload, long ttlMs = 3600000, string cacheScope = "public")
    {
        var output = new Dictionary<string, object?>(StringComparer.Ordinal) { ["resultType"] = "complete" };
        foreach (var kv in payload) output[kv.Key] = kv.Value;
        if (!output.ContainsKey("ttlMs")) output["ttlMs"] = ttlMs;
        if (!output.ContainsKey("cacheScope")) output["cacheScope"] = cacheScope;
        return output;
    }

    private static bool IsValidId(JsonElement id) => id.ValueKind switch
    {
        JsonValueKind.Null or JsonValueKind.String or JsonValueKind.Number => true,
        _ => false,
    };

    private static object? ToNode(JsonElement element) => element.ValueKind switch
    {
        JsonValueKind.String => element.GetString(),
        // 同 PythonJson.ToGraph：三元会把 long/double 统一成 double，整数会被静默转成 1.0
        JsonValueKind.Number => element.TryGetInt64(out var l) ? (object)l : element.GetDouble(),
        JsonValueKind.Null => null,
        _ => null,
    };

    private static Dictionary<string, object?> Err(string root, int code, string message, JsonElement? id, Dictionary<string, object?>? data)
    {
        var error = new Dictionary<string, object?>(StringComparer.Ordinal) { ["code"] = code, ["message"] = message };
        if (data is not null) error["data"] = data;
        return new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["jsonrpc"] = JsonRpcVersion,
            ["id"] = id is null ? null : ToNode(id.Value),
            ["error"] = error,
        };
    }

    private static Dictionary<string, object?> ErrorAt(int code, string message, JsonElement id)
        => new(StringComparer.Ordinal)
        {
            ["jsonrpc"] = JsonRpcVersion,
            ["id"] = ToNode(id),
            ["error"] = new Dictionary<string, object?>(StringComparer.Ordinal) { ["code"] = code, ["message"] = message },
        };

    private static string Str(JsonElement element, string name)
        => element.ValueKind == JsonValueKind.Object && element.TryGetProperty(name, out var v) &&
           v.ValueKind == JsonValueKind.String ? v.GetString()! : "";

    private static string DictStr(Dictionary<string, object?> map, string key)
        => map.TryGetValue(key, out var value) && value is string text ? text : "";

    private static bool Bool(JsonElement element, string name)
        => element.ValueKind == JsonValueKind.Object && element.TryGetProperty(name, out var v) &&
           v.ValueKind == JsonValueKind.True;

    private static List<string> StringList(JsonElement element, string name)
    {
        if (element.ValueKind != JsonValueKind.Object || !element.TryGetProperty(name, out var v) ||
            v.ValueKind != JsonValueKind.Array) return new List<string>();
        return v.EnumerateArray().Where(x => x.ValueKind == JsonValueKind.String)
            .Select(x => x.GetString()!).ToList();
    }

    /// <summary>按行读取且有硬上限；超限只排空到行尾，不把整条恶意消息读进内存。</summary>
    private sealed class BoundedLineReader
    {
        private readonly TextReader _reader;
        private readonly int _maxChars;
        private readonly char[] _buffer = new char[8192];
        private int _position;
        private int _length;

        public BoundedLineReader(TextReader reader, int maxChars)
        {
            _reader = reader;
            _maxChars = maxChars;
        }

        public string? ReadLine(out bool tooLong)
        {
            tooLong = false;
            var line = new StringBuilder();
            while (true)
            {
                if (_position >= _length)
                {
                    _length = _reader.Read(_buffer, 0, _buffer.Length);
                    _position = 0;
                    if (_length == 0)
                        return line.Length == 0 ? null : line.ToString();
                }
                var ch = _buffer[_position++];
                if (ch == '\n')
                {
                    if (line.Length > 0 && line[^1] == '\r')
                        line.Length--;
                    return line.ToString();
                }
                if (line.Length < _maxChars)
                    line.Append(ch);
                else
                    tooLong = true;
            }
        }
    }

    /// <summary>stdio 会话：逐行读 JSON-RPC、逐行写响应；stdout 只写 MCP 消息。</summary>
    public static int ServeStdio(string root, TextReader input, TextWriter output)
    {
        var reader = new BoundedLineReader(input, MaxRequestChars);
        while (reader.ReadLine(out var tooLong) is { } line)
        {
            if (tooLong)
            {
                output.WriteLine(EncodeMessage(Err(root, ParseError, "Parse error", null, null)));
                output.Flush();
                continue;
            }
            if (line.Trim().Length == 0) continue;
            JsonDocument doc;
            try
            {
                doc = JsonIo.Parse(line);
            }
            catch (JsonException)
            {
                // 文案与 core/mcp_runtime.py 同字：就是 "Parse error"（不带运行时细节）
                output.WriteLine(EncodeMessage(Err(root, ParseError, "Parse error", null, null)));
                output.Flush();
                continue;
            }
            Dictionary<string, object?>? response;
            using (doc)
            {
                // JSON-RPC 2.0 §5：**错误响应必须回带请求 id**（除解析错误外）。
                // 此前这里固定传 null，导致调用方按 id 匹配时"看不到"这次失败——
                // 单条消息不杀循环是对的，但"静默丢响应"不是。
                var idElement = (JsonElement?)null;
                if (doc.RootElement.ValueKind == JsonValueKind.Object
                    && doc.RootElement.TryGetProperty("id", out var rawId)
                    && rawId.ValueKind is JsonValueKind.String or JsonValueKind.Number or JsonValueKind.Null)
                {
                    idElement = rawId;
                }
                try
                {
                    response = Handle(root, doc.RootElement);
                }
                catch (Exception exc)
                {
                    // 防御：**单条消息异常不许杀循环**（同 core/mcp_runtime.py 的 INTERNAL_ERROR 分支）
                    _ = exc;
                    response = Err(root, InternalError, "Internal error", idElement, null);
                }
            }
            if (response is null) continue;
            output.WriteLine(EncodeMessage(response));
            output.Flush();
        }
        return 0;
    }
}
