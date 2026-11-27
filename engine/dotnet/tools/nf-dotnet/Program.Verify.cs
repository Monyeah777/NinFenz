using System.Text.Json;
using Nf.Engine;

internal static partial class Program
{
    private static int ReceiptsCommand()
    {
        var result = scope == "library"
            ? Receipts.VerifyLibraryReceipts(root!)
            : Receipts.VerifyProtocolReceipts(root!);
        if (json)
        {
            Console.WriteLine(JsonFor(new Dictionary<string, object?>
            {
                ["issues"] = result.Issues.Cast<object?>().ToList(),
                ["stats"] = new Dictionary<string, object?>
                {
                    ["entries"] = result.Count,
                    ["root"] = result.Root,
                },
            }));
        }
        else
        {
            Console.WriteLine($"== nf-dotnet receipts --scope {scope} ==");
            foreach (var issue in result.Issues) Console.WriteLine("  ✗ " + issue);
            if (result.Ok) Console.WriteLine("  ✓ 每条回执折叠到根，且根与实时重算一致");
            Console.WriteLine($"  —— {result.Detail}");
        }
        return result.Ok ? 0 : 1;
    }

    private static int TransparencyCommand()
    {
        var result = Receipts.VerifyTransparencyChain(root!);
        if (json)
        {
            Console.WriteLine(JsonFor(new Dictionary<string, object?>
            {
                ["issues"] = result.Issues.Cast<object?>().ToList(),
                ["stats"] = new Dictionary<string, object?>
                {
                    ["head"] = result.Root[..16],
                    ["issues"] = result.Issues.Count,
                    ["links"] = result.Count,
                    ["on_disk"] = true,
                },
            }));
        }
        else
        {
            Console.WriteLine("== nf-dotnet transparency ==");
            foreach (var issue in result.Issues) Console.WriteLine("  ✗ " + issue);
            if (result.Ok) Console.WriteLine("  ✓ 链自洽（在盘生成物一致）");
            Console.WriteLine($"  —— {result.Detail}");
        }
        return result.Ok ? 0 : 1;
    }

    private static int CombineVerifyCommand()
    {
        var rows = CertificateVerifier.VerifyAll(root!);
        var failed = rows.Count(r => r.Issues.Count > 0);
        if (json)
        {
            Console.WriteLine(PythonJson.Indented(new Dictionary<string, object?>
            {
                ["certificates"] = rows.Count,
                ["failed"] = failed,
                ["rows"] = rows.Select(r => (object?)new Dictionary<string, object?>
                {
                    ["issues"] = r.Issues.Cast<object?>().ToList(),
                    ["label"] = r.Label,
                    ["legal"] = r.Legal,
                    ["modules"] = r.Modules,
                }).ToList(),
            }));
        }
        else
        {
            Console.WriteLine("== nf-dotnet combine verify（T4 复算）==");
            foreach (var row in rows)
            {
                Console.WriteLine($"  {(row.Issues.Count == 0 ? "✓" : "✗")} {row.Label,-28} 模块 {row.Modules}");
            }
            Console.WriteLine($"  —— 证书 {rows.Count} 条，失败 {failed}");
        }
        return failed == 0 ? 0 : 1;
    }

    private static int CombinePlanCommand()
    {
        var result = Combinator.Build(root!, packs, extraModules, strictCoherence: strictCoherence);
        if (json)
        {
            Console.WriteLine(PythonJson.Indented(result.Certificate));
        }
        else
        {
            Console.WriteLine("== nf-dotnet combine plan ==");
            Console.WriteLine($"  包 {packs.Count} 个 · 模块 {result.Certificate["module_count"]} · 合法 {result.Legal}");
            Console.WriteLine($"  摘要 {result.Digest}");
            if (strictCoherence)
            {
                var conflicts = result.Certificate.TryGetValue("coherence_conflicts", out var c) && c is List<object?> list
                    ? list
                    : new List<object?>();
                Console.WriteLine($"  相干模式 strict · 撞号冲突 {conflicts.Count}");
                foreach (var row in conflicts.Cast<Dictionary<string, object?>>())
                {
                    Console.WriteLine($"  ✗ 包 {row["pack"]} 声明的 {row["module"]} 实际解析到包 {row["resolved_pack"]}（按 ISA v1 C1′ 判 DENY）");
                }
            }
        }
        return result.Legal ? 0 : 1;
    }

    private static int PatternsCommand()
    {
        var sub = positional.Count >= 2 ? positional[1] : "ls";
        if (sub == "reindex")
            return Usage("patterns reindex 是写面（重建 INDEX 投影）——本引擎是只读门，不提供写命令");
        if (sub is not ("ls" or "show" or "for" or "verify"))
            return Usage("patterns 的子命令须为 ls / show / for / verify（reindex 属写面，不提供）");

        if (sub == "ls")
        {
            var rows = Patterns.Entries(root!);
            if (json)
            {
                Console.WriteLine(JsonFor(rows.Select(e => (object?)new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["id"] = Fm(e, "id"),
                    ["name"] = Fm(e, "name"),
                    ["status"] = Fm(e, "status"),
                    ["applies_to"] = Fm(e, "applies_to"),
                }).ToList()));
            }
            else
            {
                Console.WriteLine($"== nf patterns ls（{rows.Count} 条）==");
                foreach (var e in rows)
                {
                    var id = Fm(e, "id") ?? e.Dir;
                    Console.WriteLine($"  {PadCp(PyS(id), 28)} {PadCp(PyS(Fm(e, "status")), 10)} {PyS(Fm(e, "name"))}");
                }
            }
            return 0;
        }

        if (sub == "show")
        {
            if (positional.Count < 3) return Usage("patterns show 需要一个 pattern id");
            var want = positional[2].Trim();
            var hit = Patterns.Entries(root!).FirstOrDefault(e =>
                (e.Fm.TryGetValue("id", out var id) && id is string s && s == want) || (e.Dir == want && !e.Fm.ContainsKey("id")));
            if (hit is null)
            {
                Console.Error.WriteLine($"  ✗ pattern 未找到：{positional[2]}（nf patterns ls 可枚举）");
                return 1;
            }
            if (json)
            {
                Console.WriteLine(JsonFor(new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["id"] = want,
                    ["path"] = hit.Path,
                    ["_meta"] = new Dictionary<string, object?>(StringComparer.Ordinal),
                    ["frontmatter"] = hit.Fm,
                }));
                return 0;
            }
            var text = File.ReadAllText(Path.Combine(root!, hit.Path), new System.Text.UTF8Encoding(false, true));
            Console.WriteLine($"== nf patterns show {want} ==");
            foreach (var key in hit.Fm.Keys.OrderBy(k => k, StringComparer.Ordinal))
                Console.WriteLine($"  {PadCp(key + ":", 12)} {PyS(hit.Fm[key])}");
            Console.WriteLine();
            var parts = text.Split("---", 3, StringSplitOptions.None);
            Console.WriteLine(PyScalar.PySlice(parts[^1].Trim(), 1200));
            return 0;
        }

        if (sub == "for")
        {
            if (positional.Count < 3) return Usage("patterns for 需要一个目标路径");
            var target = positional[2];
            var hits = Patterns.ForPath(root!, target);
            if (json)
            {
                Console.WriteLine(JsonFor(hits.Cast<object?>().ToList()));
            }
            else
            {
                Console.WriteLine($"== nf patterns for {target}（{hits.Count} 条适用）==");
                foreach (var h in hits)
                    Console.WriteLine($"  {PadCp(PyS(h["id"]), 28)} {PyS(h["name"])}（命中 {PyS(h["matched"])}）");
            }
            return 0;
        }

        var (issues, warns, stats) = Patterns.Scan(root!);
        var projection = Patterns.CheckProjection(root!);
        if (json)
        {
            Console.WriteLine(JsonFor(new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["issues"] = issues.Cast<object?>().ToList(),
                ["warns"] = warns.Cast<object?>().ToList(),
                ["projection"] = projection.Cast<object?>().ToList(),
                ["stats"] = stats,
            }));
        }
        else
        {
            Console.WriteLine($"== nf patterns verify（{stats["patterns"]} 条）==");
            foreach (var i in issues.Concat(projection)) Console.Error.WriteLine($"  [FAIL] {i}");
            foreach (var w in warns) Console.WriteLine($"  [WARN] {w}");
            if (issues.Count == 0 && projection.Count == 0)
                Console.WriteLine("  ✓ 格式合规 + 适用面/证据可证 + INDEX 投影一致");
        }
        return (issues.Count > 0 || projection.Count > 0) ? 1 : 0;
    }

    /// <summary>frontmatter 取值：键不存在 → null（Python <c>dict.get</c> 语义，缺键与 None 都渲染成 None）。</summary>
    private static object? Fm(Patterns.Entry e, string key) => e.Fm.TryGetValue(key, out var v) ? v : null;

    /// <summary>近似 Python <c>"%s"</c>：字符串原样、列表走 repr、None 字面量。</summary>
    private static string PyS(object? v) => v switch
{
    null => "None",
    bool b => b ? "True" : "False",
    string s => s,
    // 浮点必须走 Python 的 repr 口径：`"%s" % 1.0` 是 "1.0" 而不是 "1"
    // （首版缺这一支 → `output meter` 的机验率 1.0 被打成 "1"，与真源对不上）
    double d => PyScalar.PyRepr(d),
    List<string> list => PyScalar.PyRepr(list.Cast<object?>().ToList()),
    List<object?> list => PyScalar.PyRepr(list),
    Dictionary<string, object?> map => PyScalar.PyRepr(map),
    _ => v.ToString() ?? "None",
};

    /// <summary>Python <c>%-Ns</c>：按**码点**补空格（与 PyLen 同口径）。</summary>
    private static string PadCp(string s, int width)
    {
        var len = PyScalar.PyLen(s);
        return len >= width ? s : s + new string(' ', width - len);
    }

    /// <summary>
    /// Python CLI 的公共 JSON 信封：映射补 <c>kind</c>；列表补
    /// <c>{kind,count,rows}</c>（patterns for 另带 target）。这里只作用于本进程的
    /// 现代只读命令，已有 <c>kind</c> 的映射保持原样。
    /// </summary>
    private static string JsonFor(object? value, string? explicitKind = null)
    {
        var kind = explicitKind ?? JsonKind();
        if (value is Dictionary<string, object?> map)
        {
            if (kind is not null && !map.ContainsKey("kind"))
            {
                map = new Dictionary<string, object?>(map, StringComparer.Ordinal) { ["kind"] = kind };
            }
            return PythonJson.Indented(map);
        }
        if (kind is not null && value is System.Collections.IEnumerable sequence and not string)
        {
            var rows = sequence.Cast<object?>().ToList();
            var envelope = new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["kind"] = kind,
                ["count"] = (long)rows.Count,
                ["rows"] = rows,
            };
            if (kind == "patterns-for" && positional.Count >= 3) envelope["target"] = positional[2];
            return PythonJson.Indented(envelope);
        }
        return PythonJson.Indented(value);
    }

    private static string? JsonKind()
    {
        if (positional.Count == 0) return null;
        var cmd = positional[0];
        var sub = positional.Count >= 2 ? positional[1] : "";
        return cmd switch
        {
            "receipts" => scope == "library" ? "library-receipts" : "receipts",
            "transparency" => "transparency",
            "assertions" => "assertions",
            "decisions" => "decisions-verify",
            "cognition" => "cognition",
            "library" => "library-verify",
            "model" => "model",
            "patterns" => sub switch
            {
                "ls" => "patterns-ls", "show" => "patterns-show",
                "for" => "patterns-for", _ => "patterns-verify",
            },
            "pipeline" => "pipeline-dryrun",
            "module" when sub == "types" => "module-types",
            "module" when sub == "signature" => "module-signature",
            "handover" => sub == "verify" ? "handover-verify"
                : sub == "check" ? "handover-check" : "handover-ls",
            "postmortem" => sub == "verify" ? "postmortem-verify"
                : sub == "check" ? "postmortem-check" : "postmortem-ls",
            "audit" => sub == "verify" ? "audit-verify"
                : sub == "check" ? "audit-check" : "audit-ls",
            "sig" => "sig",
            "rfc" => "rfc",
            "endpoint" => "endpoint",
            "events" => "events",
            "toolface" => "toolface",
            "knowledge" => sub switch
            {
                "frequency" => "knowledge-frequency",
                "order" => "knowledge-order",
                "visible" => "knowledge-visible",
                "transform" => "knowledge-transform",
                "lint" => "knowledge-lint",
                _ => "knowledge",
            },
            "state-front" => stateFrontAb ? "state-front-ab"
                : stateFrontCheck ? "state-front-check" : "state-front",
            "interop" when interopCheck => "interop-verify",
            "workloop" => workloopList ? "workloop-ls" : "workloop",
            "license" => "license",
            "score" => "score",
            "review" => "review",
            "decide" => decideDryRun ? "decide-dryrun" : "decide",
            "doctor" => "doctor",
            "diff" => "diff",
            "driver" => sub.Length > 0 ? "driver-resolve" : "driver",
            "telemetry" when flags.Contains("--otlp") => "telemetry-otlp",
            "output" => sub switch
            {
                "list" => "output-list", "check" => "output-check",
                "render" => "output-render", "meter" => "output-meter",
                _ => "output-verify",
            },
            _ => null,
        };
    }

    private static string SortedOrNone(IEnumerable<string> keys)
    {
        var list = keys.OrderBy(x => x, StringComparer.Ordinal).ToList();
        return list.Count > 0 ? string.Join("、", list) : "（无）";
    }

    private static int CombineBreadthCommand()
    {
        var stats = samplesPath is null
            ? (pairsOnly ? Breadth.RunPairsOnly(root!) : Breadth.RunSelfContained(root!))
            : Breadth.Run(root!, JsonIo.ReadFile(samplesPath).RootElement);
        if (json)
        {
            Console.WriteLine(PythonJson.Indented(stats));
        }
        else
        {
            Console.WriteLine("== nf-dotnet combine breadth ==");
            Console.WriteLine($"  参与包 {stats["packs"]} · 两两 {stats["pairs_legal"]}/{stats["pairs"]}" +
                              $" · 三元 {stats["triples_legal"]}/{stats["triples"]}" +
                              $" · 四元 {stats["quads_legal"]}/{stats["quads"]}" +
                              $" · 五元 {stats["quints_legal"]}/{stats["quints"]}" +
                              $" · 六元 {stats["sexts_legal"]}/{stats["sexts"]} · 全合法={stats["all_legal"]}");
            if (samplesPath is null && pairsOnly) Console.WriteLine("  （仅两两全集；去掉 --pairs-only 即含四档抽样）");
        }
        return stats["all_legal"] is true ? 0 : 1;
    }

    private static int SelfTestCommand()
    {
        var checks = SelfTest.Run(root!);
        var failed = checks.Count(c => !c.Passed);
        if (json)
        {
            Console.WriteLine(PythonJson.Indented(new Dictionary<string, object?>
            {
                ["checks"] = checks.Count,
                ["failed"] = failed,
                ["rows"] = checks.Select(c => (object?)new Dictionary<string, object?>
                {
                    ["name"] = c.Name,
                    ["passed"] = c.Passed,
                    ["detail"] = c.Detail,
                }).ToList(),
            }));
        }
        else
        {
            Console.WriteLine("== nf-dotnet selftest（负例 / 健壮性自检）==");
            foreach (var check in checks)
            {
                Console.WriteLine($"  {(check.Passed ? "✓" : "✗")} {check.Name} —— {check.Detail}");
            }
            Console.WriteLine($"  —— 用例 {checks.Count} 条 · 通过 {checks.Count - failed} · 失败 {failed}");
        }
        return failed == 0 ? 0 : 1;
    }

    private static int AggregateCommand()
    {
        var components = new List<Receipts.ArtifactResult>
        {
            Receipts.VerifyProtocolReceipts(root!),
            Receipts.VerifyLibraryReceipts(root!),
            Receipts.VerifyTransparencyChain(root!),
        };
        var rows = CertificateVerifier.VerifyAll(root!);
        var combineIssues = rows.Where(r => r.Issues.Count > 0)
            .SelectMany(r => r.Issues.Select(i => r.Label + "：" + i)).ToList();
        var combineOk = combineIssues.Count == 0;
        var assertions = Assertions.Run(root!);
        var decisions = Decisions.Verify(root!);
        var library = Library.Verify(root!);
        var model = Modeling.Run(root!);
        var cognition = Cognition.Run(root!);
        var sig = KnowledgeSig.VerifyReproducible(root!);
        var conformance = Conformance.Run(root!);
        var conformanceFailed = conformance.Contracts.Where(c => !c.Ok).ToList();
        var decisionIssues = decisions.Issues.Concat(decisions.Projection).ToList();
        var libraryIssues = library.Issues.Concat(library.Projection).ToList();
        var ok = components.All(c => c.Ok) && combineOk &&
                 assertions.Issues.Count == 0 && decisionIssues.Count == 0 && libraryIssues.Count == 0 &&
                 model.Issues.Count == 0 && cognition.Issues.Count == 0 && sig.Issues.Count == 0 &&
                 conformanceFailed.Count == 0;

        if (json)
        {
            var list = components.Select(c => (object?)new Dictionary<string, object?>
            {
                ["name"] = c.Name,
                ["ok"] = c.Ok,
                ["issues"] = c.Issues.Cast<object?>().ToList(),
                ["detail"] = c.Detail,
            }).ToList();
            list.Add(new Dictionary<string, object?>
            {
                ["name"] = "protocol/combo_certificates.json",
                ["ok"] = combineOk,
                ["issues"] = combineIssues.Cast<object?>().ToList(),
                ["detail"] = $"证书 {rows.Count} 条 · 失败 {rows.Count(r => r.Issues.Count > 0)}",
            });
            list.Add(new Dictionary<string, object?>
            {
                ["name"] = "protocol/assertions.json",
                ["ok"] = assertions.Issues.Count == 0,
                ["issues"] = assertions.Issues.Cast<object?>().ToList(),
                ["detail"] = $"断言 {assertions.Results.Count} 条 · 问题 {assertions.Issues.Count}",
            });
            list.Add(new Dictionary<string, object?>
            {
                ["name"] = "decisions/ADR-*.md",
                ["ok"] = decisionIssues.Count == 0,
                ["issues"] = decisionIssues.Cast<object?>().ToList(),
                ["detail"] = $"ADR {decisions.Stats["decisions"]} 条 · accepted {decisions.Stats["accepted"]} · 问题 {decisionIssues.Count}",
            });
            list.Add(new Dictionary<string, object?>
            {
                ["name"] = "library/NF-*.md",
                ["ok"] = libraryIssues.Count == 0,
                ["issues"] = libraryIssues.Cast<object?>().ToList(),
                ["detail"] = $"条目 {library.Stats["entries"]} · 在役 {library.Stats["active"]} · WARN {library.Warns.Count} · 问题 {libraryIssues.Count}",
            });
            list.Add(new Dictionary<string, object?>
            {
                ["name"] = "protocol/{vocabularies,normative,data_contracts}.json",
                ["ok"] = model.Issues.Count == 0,
                ["issues"] = model.Issues.Cast<object?>().ToList(),
                ["detail"] = $"词表 {((Dictionary<string, object?>)model.Stats["vocab"]!)["schemes"]} · " +
                             $"规范件 {((Dictionary<string, object?>)model.Stats["normative"]!)["normative"]} · " +
                             $"契约 {((Dictionary<string, object?>)model.Stats["contracts"]!)["contracts"]}",
            });
            list.Add(new Dictionary<string, object?>
            {
                ["name"] = "protocol/{glossary,execution_modes}.json",
                ["ok"] = cognition.Issues.Count == 0,
                ["issues"] = cognition.Issues.Cast<object?>().ToList(),
                ["detail"] = $"术语 {((Dictionary<string, object?>)cognition.Stats["glossary"]!)["terms"]} · " +
                             $"分档 {((Dictionary<string, object?>)cognition.Stats["modes"]!)["modes"]} · 问题 {cognition.Issues.Count}",
            });
            list.Add(new Dictionary<string, object?>
            {
                ["name"] = "01-36 知识签名（两遍一致）",
                ["ok"] = sig.Issues.Count == 0,
                ["issues"] = sig.Issues.Cast<object?>().ToList(),
                ["detail"] = $"文档 {sig.Stats["docs"]} · 可复现 {sig.Stats["reproducible"]}",
            });
            list.Add(new Dictionary<string, object?>
            {
                ["name"] = $"conformance（已移植 {conformance.Contracts.Count}/{Conformance.AllContractIds.Length} 契约）",
                ["ok"] = conformanceFailed.Count == 0,
                ["issues"] = conformanceFailed.Select(c => (object?)(c.Id + "：" + c.Detail)).ToList(),
                ["detail"] = $"通过 {conformance.Passed} · 未移植 {conformance.Unported.Count}（不参与判定）",
            });
            Console.WriteLine(PythonJson.Indented(new Dictionary<string, object?>
            {
                ["ok"] = ok,
                ["components"] = list,
            }));
        }
        else
        {
            Console.WriteLine("== nf-dotnet verify（NF 工业引擎 · 只读聚合校验）==");
            foreach (var c in components)
            {
                Console.WriteLine($"  {(c.Ok ? "✓" : "✗")} {c.Name,-42} {c.Detail}");
                foreach (var issue in c.Issues.Take(5)) Console.WriteLine("      · " + issue);
            }
            Console.WriteLine($"  {(combineOk ? "✓" : "✗")} {"protocol/combo_certificates.json",-42} 证书 {rows.Count} 条 · 失败 {rows.Count(r => r.Issues.Count > 0)}");
            Console.WriteLine($"  {(assertions.Issues.Count == 0 ? "✓" : "✗")} {"protocol/assertions.json",-42} 断言 {assertions.Results.Count} 条 · 问题 {assertions.Issues.Count}");
            Console.WriteLine($"  {(decisionIssues.Count == 0 ? "✓" : "✗")} {"decisions/ADR-*.md",-42} ADR {decisions.Stats["decisions"]} 条 · 问题 {decisionIssues.Count}");
            Console.WriteLine($"  {(libraryIssues.Count == 0 ? "✓" : "✗")} {"library/NF-*.md",-42} 条目 {library.Stats["entries"]} · 在役 {library.Stats["active"]} · 问题 {libraryIssues.Count}");
            Console.WriteLine($"  {(model.Issues.Count == 0 ? "✓" : "✗")} {"model（词表/规范件/契约）",-42} 问题 {model.Issues.Count}");
            Console.WriteLine($"  {(cognition.Issues.Count == 0 ? "✓" : "✗")} {"cognition（术语表/执行分档）",-42} 问题 {cognition.Issues.Count}");
            Console.WriteLine($"  {(sig.Issues.Count == 0 ? "✓" : "✗")} {"sig（01-36 两遍一致）",-42} 文档 {sig.Stats["docs"]}");
            Console.WriteLine($"  {(conformanceFailed.Count == 0 ? "✓" : "✗")} {$"conformance（已移植 {conformance.Contracts.Count}/{Conformance.AllContractIds.Length}）",-42} 通过 {conformance.Passed} · 未移植 {conformance.Unported.Count}（不参与判定）");
            Console.WriteLine(ok ? "  —— 全部通过" : "  —— 存在失败项");
        }
        return ok ? 0 : 1;
    }

}
