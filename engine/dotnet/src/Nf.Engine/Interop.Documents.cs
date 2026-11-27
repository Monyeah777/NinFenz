using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;

namespace Nf.Engine;

/// <summary>主文档形状：OpenAPI / AsyncAPI / PROV / 决策面 / A2A（含 schema 辅助）。</summary>
public static partial class Interop
{
    /// <summary>服务端点契约 → OpenAPI 3.1 文档。</summary>
    public static Dictionary<string, object?> Openapi(string root)
    {
        var contract = ReadJson(root, ContractRel);
        var conv = contract.GetValueOrDefault("conventions") as Dictionary<string, object?> ?? new(StringComparer.Ordinal);
        var nonIdem = new Dictionary<string, string>(StringComparer.Ordinal);
        foreach (var e in (contract.GetValueOrDefault("idempotency_exceptions") as List<object?> ?? new List<object?>())
                     .OfType<Dictionary<string, object?>>())
        {
            nonIdem[PyText(e.GetValueOrDefault("id"))] = e.GetValueOrDefault("key") is string k ? k : "";
        }

        var paths = new Dictionary<string, object?>(StringComparer.Ordinal);
        foreach (var ep in (contract.GetValueOrDefault("endpoints") as List<object?> ?? new List<object?>())
                     .OfType<Dictionary<string, object?>>())
        {
            var path = PyText(ep.GetValueOrDefault("path"));
            var method = PyText(ep.GetValueOrDefault("method")).ToLowerInvariant();
            if (path.Length == 0 || method.Length == 0) continue;
            var req = ep.GetValueOrDefault("request") as Dictionary<string, object?> ?? new(StringComparer.Ordinal);
            var resp = ep.GetValueOrDefault("response") as Dictionary<string, object?> ?? new(StringComparer.Ordinal);
            var epId = PyText(ep.GetValueOrDefault("id"));

            var ok200 = new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["description"] = "成功",
                ["content"] = new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["application/json"] = new Dictionary<string, object?>(StringComparer.Ordinal)
                    {
                        ["schema"] = new Dictionary<string, object?>(StringComparer.Ordinal)
                        {
                            ["type"] = "object",
                            ["properties"] = resp.ToDictionary(kv => kv.Key, kv => (object?)SchemaFor(kv.Value), StringComparer.Ordinal),
                        },
                    },
                },
            };
            var op = new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["operationId"] = epId,
                ["summary"] = $"maps_to {PyText(ep.GetValueOrDefault("maps_to"))}",
                ["x-nf-idempotency"] = nonIdem.ContainsKey(epId)
                    ? $"non-idempotent（幂等键 {nonIdem[epId]}）"
                    : "idempotent",
                ["responses"] = new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["200"] = ok200,
                    ["default"] = new Dictionary<string, object?>(StringComparer.Ordinal)
                    {
                        ["description"] = "错误（RFC 9457 Problem Details 映射见 x-nf-error-mapping）",
                        ["content"] = new Dictionary<string, object?>(StringComparer.Ordinal)
                        {
                            ["application/json"] = new Dictionary<string, object?>(StringComparer.Ordinal)
                            {
                                ["schema"] = new Dictionary<string, object?>(StringComparer.Ordinal)
                                {
                                    ["$ref"] = "#/components/schemas/NfError",
                                },
                            },
                        },
                    },
                },
            };
            if (req.Count > 0 || method == "post")
            {
                op["requestBody"] = new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["required"] = true,
                    ["content"] = new Dictionary<string, object?>(StringComparer.Ordinal)
                    {
                        ["application/json"] = new Dictionary<string, object?>(StringComparer.Ordinal)
                        {
                            ["schema"] = new Dictionary<string, object?>(StringComparer.Ordinal)
                            {
                                ["type"] = "object",
                                ["properties"] = req.ToDictionary(kv => kv.Key, kv => (object?)SchemaFor(kv.Value), StringComparer.Ordinal),
                            },
                        },
                    },
                };
            }
            if (PyTruthy(ep.GetValueOrDefault("streaming")))
            {
                var content = (Dictionary<string, object?>)ok200["content"]!;
                content["text/event-stream"] = new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["schema"] = new Dictionary<string, object?>(StringComparer.Ordinal) { ["type"] = "string" },
                    ["x-nf-streaming"] = conv.GetValueOrDefault("streaming") ?? "",
                };
            }
            var tmplVars = Regex.Matches(path, @"\{([^}]+)\}").Select(m => m.Groups[1].Value).ToList();
            if (tmplVars.Count > 0)
            {
                op["parameters"] = tmplVars.Select(name => (object?)new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["name"] = name,
                    ["in"] = "path",
                    ["required"] = true,
                    ["schema"] = new Dictionary<string, object?>(StringComparer.Ordinal) { ["type"] = "string" },
                    ["x-nf-derived"] = "由 protocol/endpoint_contract.json 的路径模板派生",
                }).ToList();
            }
            if (PyTruthy(ep.GetValueOrDefault("deprecated")))
            {
                op["deprecated"] = true;
                op["x-nf-sunset"] = ep.GetValueOrDefault("sunset");            // 可能是 null（Python 同）
                op["x-nf-replacement"] = ep.GetValueOrDefault("replacement");  // 可能是 null
            }
            if (!paths.TryGetValue(path, out var bucket) || bucket is not Dictionary<string, object?> ops)
            {
                ops = new Dictionary<string, object?>(StringComparer.Ordinal);
                paths[path] = ops;
            }
            ops[method] = op;
        }

        return new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["openapi"] = "3.1.0",
            ["info"] = new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["title"] = "NinFenz 服务端点契约（派生）",
                ["version"] = "1.0.0",
                ["description"] = $"由 protocol/endpoint_contract.json 实时派生（status={PyText(contract.GetValueOrDefault("status"))}）；本文件非真源。",
            },
            ["servers"] = new List<object?>(),
            ["paths"] = paths,
            ["components"] = new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["schemas"] = new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["NfError"] = new Dictionary<string, object?>(StringComparer.Ordinal)
                    {
                        ["type"] = "object",
                        ["required"] = new List<object?> { "error" },
                        ["properties"] = new Dictionary<string, object?>(StringComparer.Ordinal)
                        {
                            ["error"] = new Dictionary<string, object?>(StringComparer.Ordinal)
                            {
                                ["type"] = "object",
                                ["required"] = new List<object?> { "code", "message" },
                                ["properties"] = new Dictionary<string, object?>(StringComparer.Ordinal)
                                {
                                    ["code"] = new Dictionary<string, object?>(StringComparer.Ordinal)
                                    {
                                        ["type"] = "integer", ["description"] = "机器可判定错误码",
                                    },
                                    ["message"] = new Dictionary<string, object?>(StringComparer.Ordinal)
                                    {
                                        ["type"] = "string", ["description"] = "人读说明，必须带修复指引",
                                    },
                                    ["data"] = new Dictionary<string, object?>(StringComparer.Ordinal)
                                    {
                                        ["type"] = new List<object?> { "object", "null" },
                                    },
                                },
                            },
                        },
                    },
                },
            },
            ["x-nf-error-mapping"] = new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["type"] = "about:blank",
                ["title"] = "error.message",
                ["detail"] = "error.message + 修复指引（patterns/error-message-guidance）",
                ["instance"] = "请求路径",
                ["status"] = "HTTP 状态码（与 message 同源）",
                ["source"] = conv.GetValueOrDefault("errors") ?? "",
            },
            ["x-nf-endpoints"] = (long)((contract.GetValueOrDefault("endpoints") as List<object?>)?.Count ?? 0),
        };
    }

    /// <summary>事件登记 → AsyncAPI 3.0 文档 + CloudEvents 属性。</summary>
    public static Dictionary<string, object?> Asyncapi(string root)
    {
        var reg = ReadJson(root, EventsRel);
        var ext = ReadJson(root, ExternalEventsRel);
        var events = new Dictionary<string, Dictionary<string, object?>>(StringComparer.Ordinal);
        foreach (var src in new[] { reg, ext })
        {
            if (src.GetValueOrDefault("events") is not Dictionary<string, object?> map) continue;
            foreach (var (name, meta) in map)
            {
                if (!events.ContainsKey(name))
                    events[name] = meta as Dictionary<string, object?> ?? new Dictionary<string, object?>(StringComparer.Ordinal);
            }
        }

        var channels = new Dictionary<string, object?>(StringComparer.Ordinal);
        var messages = new Dictionary<string, object?>(StringComparer.Ordinal);
        var ordered = events.Keys.OrderBy(k => k, StringComparer.Ordinal).ToList();
        foreach (var name in ordered)
        {
            var meta = events[name];
            var fields = meta.GetValueOrDefault("fields") as Dictionary<string, object?> ?? new(StringComparer.Ordinal);
            channels[$"nf/{name}"] = new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["address"] = $"nf/{name}",
                ["title"] = name,
                ["messages"] = new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    [$"nf.{name}"] = new Dictionary<string, object?>(StringComparer.Ordinal)
                    {
                        ["$ref"] = $"#/components/messages/{Ptr(name)}",
                    },
                },
                ["x-nf-cloudevents"] = new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["type"] = $"nf.{name}", ["source"] = "urn:nf:repo",
                    ["specversion"] = "1.0", ["datacontenttype"] = "application/json",
                },
            };
            messages[name] = new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["name"] = name,
                ["contentType"] = "application/json",
                ["payload"] = new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["type"] = "object",
                    ["properties"] = fields.ToDictionary(kv => kv.Key,
                        kv => (object?)SchemaFor((kv.Value as Dictionary<string, object?>)?.GetValueOrDefault("type") ?? ""),
                        StringComparer.Ordinal),
                },
                ["x-nf-note"] = PyScalar.PySlice(PyText(meta.GetValueOrDefault("note")), 200),
            };
        }

        var operations = new Dictionary<string, object?>(StringComparer.Ordinal);
        foreach (var name in ordered)
        {
            operations[$"publish/{name}"] = new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["action"] = "send",
                ["channel"] = new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["$ref"] = $"#/channels/{Ptr($"nf/{name}")}",
                },
            };
        }

        return new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["asyncapi"] = "3.0.0",
            ["info"] = new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["title"] = "NinFenz 事件登记（派生）",
                ["version"] = "1.0.0",
                ["description"] = "由 protocol/event_registry.json + external_events.json 实时派生；本文件非真源。",
            },
            ["channels"] = channels,
            ["operations"] = operations,
            ["components"] = new Dictionary<string, object?>(StringComparer.Ordinal) { ["messages"] = messages },
            ["x-nf-events"] = (long)events.Count,
        };
    }

    /// <summary>PROV-O 溯源图（资产 / 馆藏 / 消化 / 回执 → 实体·活动·代理三元组）。</summary>
    public static Dictionary<string, object?> Prov(string root)
    {
        var prov = ReadJson(root, "05_资产库/provenance.json");
        var transform = ReadJson(root, "protocol/transform_log.json");
        var rec = ReadJson(root, ReceiptsRel);
        var nodes = new Dictionary<string, Dictionary<string, object?>>(StringComparer.Ordinal);
        void Add(Dictionary<string, object?> node)
        {
            var id = PyText(node.GetValueOrDefault("@id"));
            if (!nodes.ContainsKey(id)) nodes[id] = node;
        }

        foreach (var a in (prov.GetValueOrDefault("assets") as List<object?> ?? new List<object?>())
                     .OfType<Dictionary<string, object?>>())
        {
            Add(new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["@id"] = $"nf:asset/{PyText(a.GetValueOrDefault("key"))}",
                ["@type"] = "prov:Entity",
                ["prov:label"] = PyText(a.GetValueOrDefault("key")),
                ["nf:file"] = PyText(a.GetValueOrDefault("file")),
                ["nf:module"] = PyText(a.GetValueOrDefault("module")),
                ["nf:status"] = PyText(a.GetValueOrDefault("status")),
                ["nf:version"] = PyText(a.GetValueOrDefault("version")),
            });
        }

        var idx = Path.Combine(root, "library", "INDEX.md");
        if (File.Exists(idx))
        {
            var text = StrictUtf8.GetString(File.ReadAllBytes(idx)).Replace("\r\n", "\n").Replace('\r', '\n');
            foreach (var line in text.Split('\n'))
            {
                if (!Regex.IsMatch(line, @"^\|\s*NF-[A-Za-z0-9\-]+\s*\|")) continue;
                var cells = line.Trim().Trim('|').Split('|').Select(c => c.Trim()).ToList();
                if (cells.Count < 6) continue;
                var eid = cells[0];
                var author = cells[3];
                var date = cells[4];
                var lic = cells[5];
                Add(new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["@id"] = $"nf:library/{eid}", ["@type"] = "prov:Entity",
                    ["prov:label"] = cells[1], ["nf:license"] = lic,
                });
                Add(new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["@id"] = $"nf:activity/library-ingest/{eid}",
                    ["@type"] = "prov:Activity",
                    ["prov:endedAtTime"] = date,
                    ["prov:wasAssociatedWith"] = $"nf:agent/{author}",
                    ["prov:generated"] = $"nf:library/{eid}",
                });
                Add(new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["@id"] = $"nf:agent/{author}", ["@type"] = "prov:Person", ["prov:label"] = author,
                });
            }
        }

        foreach (var e in (rec.GetValueOrDefault("entries") as List<object?> ?? new List<object?>())
                     .OfType<Dictionary<string, object?>>())
        {
            Add(new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["@id"] = $"nf:file/{PyText(e.GetValueOrDefault("path"))}",
                ["@type"] = "prov:Entity",
                ["nf:sha256"] = PyText(e.GetValueOrDefault("digest")),
            });
        }

        var i = 0;
        foreach (var t in (transform.GetValueOrDefault("entries") as List<object?> ?? new List<object?>())
                     .OfType<Dictionary<string, object?>>())
        {
            i++;
            var used = t.GetValueOrDefault("source") ?? t.GetValueOrDefault("from");
            var generated = t.GetValueOrDefault("product") ?? t.GetValueOrDefault("to");
            Add(new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["@id"] = $"nf:transform/{i}",
                ["@type"] = "prov:Activity",
                ["prov:used"] = $"nf:file/{PyText(used)}",
                ["prov:generated"] = $"nf:file/{PyText(generated)}",
                ["nf:digest"] = PyText(t.GetValueOrDefault("digest")),
            });
        }

        Add(new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["@id"] = "nf:agent/verify-sh",
            ["@type"] = "prov:SoftwareAgent",
            ["prov:label"] = "NinFenz verify.sh 门禁",
            ["nf:present"] = File.Exists(Path.Combine(root, "verify.sh")),
        });

        var graph = nodes.Keys.OrderBy(k => k, StringComparer.Ordinal).Select(k => (object?)nodes[k]).ToList();
        return new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["@context"] = new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["prov"] = "http://www.w3.org/ns/prov#",
                ["nf"] = "https://ninfenz.dev/ns#",
            },
            ["schema"] = "nf-prov/1",
            ["note"] = "由仓内声明件派生（资产 / 馆藏 / 消化记录 / 回执）；本文件非真源，空面即如实为空。",
            ["@graph"] = graph,
            ["x-nf-counts"] = new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["entities"] = (long)graph.Count(n => ((Dictionary<string, object?>)n!)["@type"] as string == "prov:Entity"),
                ["activities"] = (long)graph.Count(n => ((Dictionary<string, object?>)n!)["@type"] as string == "prov:Activity"),
                ["agents"] = (long)graph.Count(n => ((Dictionary<string, object?>)n!)["@type"] as string is "prov:Person" or "prov:SoftwareAgent"),
            },
        };
    }

    /// <summary>决策面（能力 + 公开裁决索引；**不导出逐次工单**，并显式声明这一点）。</summary>
    public static Dictionary<string, object?> Decisions(string root)
    {
        var decl = ReadJson(root, "protocol/decision_layer.json");
        var audits = new List<object?>();
        var auditDir = Path.Combine(root, "results", "audit");
        if (Directory.Exists(auditDir))
        {
            foreach (var path in Directory.GetFiles(auditDir, "*.md").OrderBy(p => p, StringComparer.Ordinal))
            {
                string head;
                try
                {
                    var text = StrictUtf8.GetString(File.ReadAllBytes(path));
                    head = PyScalar.PySlice(text, 1200);
                }
                catch (IOException)
                {
                    continue;   // 尽力而为：读不到就跳过（缺件由回执门报出）
                }
                if (!head.StartsWith("---", StringComparison.Ordinal)) continue;
                var parts = head.Split("---", 3);
                if (parts.Length < 2) continue;
                var rec = new Dictionary<string, string>(StringComparer.Ordinal);
                foreach (var line in parts[1].Split('\n'))
                {
                    var at = line.IndexOf(':');
                    if (at < 0) continue;
                    rec[line[..at].Trim()] = line[(at + 1)..].Trim();
                }
                if (rec.TryGetValue("id", out var id) && id.Length > 0)
                {
                    audits.Add(new Dictionary<string, object?>(StringComparer.Ordinal)
                    {
                        ["id"] = id,
                        ["title"] = rec.GetValueOrDefault("title", ""),
                        ["date"] = rec.GetValueOrDefault("date", ""),
                        ["verdict"] = rec.GetValueOrDefault("verdict", ""),
                    });
                }
            }
        }

        var adapters = new List<object?>();
        foreach (var a in (decl.GetValueOrDefault("adapters") as List<object?> ?? new List<object?>())
                     .OfType<Dictionary<string, object?>>())
        {
            adapters.Add(new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["id"] = a.GetValueOrDefault("id"),
                ["kind"] = a.GetValueOrDefault("kind"),
                ["inGatePath"] = a.GetValueOrDefault("in_gate_path"),
                ["calibrated"] = a.GetValueOrDefault("calibrated"),
            });
        }
        var candidates = new List<object?>();
        foreach (var c in (decl.GetValueOrDefault("candidates") as List<object?> ?? new List<object?>())
                     .OfType<Dictionary<string, object?>>())
        {
            var local = c.GetValueOrDefault("local") as Dictionary<string, object?>;
            candidates.Add(new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["id"] = c.GetValueOrDefault("id"),
                ["source"] = c.GetValueOrDefault("source"),
                ["license"] = c.GetValueOrDefault("license"),
                ["pulled"] = c.GetValueOrDefault("pulled"),
                ["evidence"] = PyScalar.PySlice(PyText(c.GetValueOrDefault("evidence")), 200),
                ["local"] = local is null
                    ? null
                    : new Dictionary<string, object?>(StringComparer.Ordinal)
                    {
                        ["runtime"] = local.GetValueOrDefault("runtime"),
                        ["servedBy"] = local.GetValueOrDefault("served_by"),
                    },
            });
        }

        return new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["schema"] = "nf-decision-surface/1",
            ["primitives"] = decl.GetValueOrDefault("primitives") as Dictionary<string, object?> ?? new(StringComparer.Ordinal),
            ["responseContract"] = decl.GetValueOrDefault("response_contract") as Dictionary<string, object?> ?? new(StringComparer.Ordinal),
            ["adapters"] = adapters,
            ["candidates"] = candidates,
            ["boundaries"] = decl.GetValueOrDefault("boundaries") as List<object?> ?? new List<object?>(),
            ["workloop"] = decl.GetValueOrDefault("workloop") as Dictionary<string, object?> ?? new(StringComparer.Ordinal),
            ["publicDecisionIndex"] = audits,
            ["x-nf-internal"] = "逐次工单（挑活/风险/收口）留在内部档案 .rivet/private_archive/work_orders/，" +
                                "不随本面发布（STRATEGY §四 计划内部消化）；本面只投影**能力与公开裁决索引**。",
        };
    }

    /// <summary>A2A Agent Card（能力面 = 端点契约投影 + MCP 包版本）。</summary>
    public static Dictionary<string, object?> A2a(string root)
    {
        var contract = ReadJson(root, ContractRel);
        var pkg = ReadJson(root, "protocol/mcp_package.json");
        var endpoints = (contract.GetValueOrDefault("endpoints") as List<object?> ?? new List<object?>())
            .OfType<Dictionary<string, object?>>().ToList();
        var skills = endpoints.Select(ep => (object?)new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["id"] = PyText(ep.GetValueOrDefault("id")),
            ["name"] = PyText(ep.GetValueOrDefault("id")),
            ["description"] = $"maps_to {PyText(ep.GetValueOrDefault("maps_to"))}（" +
                              $"{PyText(ep.GetValueOrDefault("method"))} {PyText(ep.GetValueOrDefault("path"))}）",
            ["tags"] = new List<object?> { "ninfenz", "content-contract" },
        }).ToList();
        var version = pkg.GetValueOrDefault("version") as string;
        return new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["protocolVersion"] = "0.2.5",
            ["name"] = "NinFenz",
            ["description"] = "内容契约层：装配 / 质检 / 图书馆 / 一致性报告（只读面）",
            ["url"] = "urn:nf:repo",
            ["preferredTransport"] = "stdio",
            ["version"] = version is { Length: > 0 } ? version : "1.0.0",
            ["capabilities"] = new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["streaming"] = endpoints.Any(e => PyTruthy(e.GetValueOrDefault("streaming"))),
                ["pushNotifications"] = false,
            },
            ["defaultInputModes"] = new List<object?> { "text/plain", "application/json" },
            ["defaultOutputModes"] = new List<object?> { "text/plain", "application/json" },
            ["skills"] = skills,
            ["x-nf-note"] = $"能力面 = protocol/endpoint_contract.json 的投影；服务本体 " +
                            $"status={PyText(contract.GetValueOrDefault("status"))}（未实装，本卡不据此宣称在线）",
        };
    }

    /// <summary>字段说明串 → JSON Schema 片段（只做可判定映射，未识别一律 object 兜底）。</summary>
    public static Dictionary<string, object?> SchemaFor(object? descNode)
    {
        var desc = PyText(descNode);
        var m = Regex.Match(desc, @"^\s*([a-z]+)");
        var token = m.Success ? m.Groups[1].Value : "";
        var jtype = TypeMap.Contains(token) ? token : "object";
        var nullable = desc.Contains("null");
        var output = new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["type"] = nullable ? new List<object?> { jtype, "null" } : jtype,
        };
        if (jtype == "array") output["items"] = new Dictionary<string, object?>(StringComparer.Ordinal);
        if (jtype == "object") output["additionalProperties"] = true;
        if (desc.Trim().Length > 0) output["description"] = desc;
        return output;
    }

    /// <summary>JSON Pointer 转义（RFC 6901：<c>~</c> → <c>~0</c>、<c>/</c> → <c>~1</c>）。</summary>
    public static string Ptr(string token) => token.Replace("~", "~0").Replace("/", "~1");
}
