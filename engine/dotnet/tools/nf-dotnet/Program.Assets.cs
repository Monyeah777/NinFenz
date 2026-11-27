using System.Text.Json;
using Nf.Engine;

internal static partial class Program
{
    private static int AssetCommand()
    {
        // 只读八面：verify（与 check23 同语义的闭合门禁）/ inventory（盘点）/ ls（货架浏览）/
        //           baseline（行数基线）/ density（键语义密度）/ usage（引用度）/ thickness（语义厚度）/
        //           ledger（键表机读投影）。
        // 写面（add / rm / deprecate / restore / baseline --write / ledger --refresh）不移植——只读门不提供写命令。
        var sub = positional.Count >= 2 ? positional[1] : "";
        if (sub.Length == 0)
            return Usage("asset 需要子命令（verify / inventory / ls / baseline / density / usage / thickness / ledger）");
        if (sub is "add" or "rm" or "deprecate" or "restore")
            return Fail($"asset {sub} 是写面（改台账/文件头）——本引擎是只读门，不提供写命令");
        if (sub == "baseline" && writeRequested)
            return Fail("asset baseline --write 是写面（重签行数基线）——本引擎是只读门");
        if (sub == "ledger" && refreshRequested)
            return Fail("asset ledger --refresh 是写面（重生成键表投影）——本引擎是只读门");
        if (sub is not ("verify" or "inventory" or "ls" or "baseline" or "density" or "usage" or "thickness" or "ledger"))
            return Usage($"asset 的子命令须为 verify / inventory / ls / baseline / density / usage / thickness / ledger（写面不提供）：{sub}");

        // 扫描根：Python 侧 `asset * --root` 缺省 = 仓库根；本引擎避免与全局 --root 撞名，用 --assets-root
        var assetsRoot = assetsRootFlag is null
            ? root!
            : (Path.IsPathRooted(assetsRootFlag) ? assetsRootFlag : Path.Combine(root!, assetsRootFlag));
        try
        {
            if (sub == "verify")
            {
                var (issues, stats) = AssetLedger.VerifyRoot(assetsRoot);
                Console.WriteLine($"== nf asset verify（扫描根：{assetsRoot}）==");
                Console.WriteLine($"  台账 {PyS(stats["ledgers"])} · 托管资产 {PyS(stats["assets"])} · " +
                                  $"存量未托管 {PyS(stats["untracked"])} · 孤儿头 {PyS(stats["orphans"])}");
                foreach (var i in issues) Console.WriteLine($"  [FAIL] {i}");
                if (issues.Count > 0)
                {
                    Console.Error.WriteLine("  ✗ 供应链台账存在缺口——修复后重跑（verify.sh check23 同语义）");
                    return 1;
                }
                Console.WriteLine("  ✓ 台账闭合：每资产可溯源 / 可发现 / 键无孤儿");
                return 0;
            }

            if (sub == "inventory")
            {
                var rows = AssetLedger.InventoryRoot(assetsRoot);
                if (json)
                {
                    Console.WriteLine(PythonJson.Indented(new Dictionary<string, object?>(StringComparer.Ordinal)
                    {
                        ["kind"] = "asset-inventory",
                        ["rows"] = rows.Cast<object?>().ToList(),
                    }));
                    return 0;
                }
                Console.WriteLine($"== nf asset inventory（扫描根：{assetsRoot}）==");
                if (rows.Count == 0)
                {
                    Console.WriteLine("  （无 provenance.json 台账——nf asset add 建档首个资产集）");
                    return 0;
                }
                foreach (var r in rows)
                {
                    var err = r.TryGetValue("error", out var e) && e is not null ? $"（读取失败：{PyS(e)}）" : "";
                    Console.WriteLine($"  · {PadCp(PyS(r["dir"]), 28)} pkg={PadCp(PyS(r["package"]), 10)} " +
                                      $"tier={PadCp(PyS(r["tier"]), 12)} 在册={PyS(r["assets"])} " +
                                      $"未托管={PyS(r["untracked"])} 孤儿={PyS(r["orphans"])}{err}");
                }
                return 0;
            }

            if (sub == "baseline")
            {
                var (issues, warns, stats) = AssetLineBaseline.Verify(assetsRoot);
                Console.WriteLine($"== nf asset baseline（在册 {PyS(stats.GetValueOrDefault("packages", 0L))} 包 · " +
                                  $"基线 {PyS(stats.GetValueOrDefault("baseline", 0L))} 包）==");
                foreach (var w in warns) Console.WriteLine($"  [WARN] {w}");
                foreach (var i in issues) Console.WriteLine($"  [FAIL] {i}");
                if (issues.Count == 0) Console.WriteLine("  [OK] 社区包资产外形与基线一致（改外形须显式重签）");
                return issues.Count > 0 ? 1 : 0;
            }

            if (sub == "density")
            {
                var (issues, stats) = AssetDensity.Scan(assetsRoot);
                if (json)
                {
                    Console.WriteLine(PythonJson.Indented(new Dictionary<string, object?>(StringComparer.Ordinal)
                    {
                        ["kind"] = "asset-density",
                        ["ok"] = issues.Count == 0,
                        ["issues"] = issues.Cast<object?>().ToList(),
                        ["stats"] = stats,
                    }));
                    return issues.Count > 0 ? 1 : 0;
                }
                Console.WriteLine("== nf asset density（45 资产键语义密度）==");
                Console.WriteLine($"  资产文件 {PyS(stats["files"])} · 键 {PyS(stats["keys"])} · 平均 " +
                                  $"{((double)stats["avg_keys_per_file"]!).ToString("F2", System.Globalization.CultureInfo.InvariantCulture)} 键/档");
                Console.WriteLine($"  无键档（中文名/附机制，合法计数）{PyS(stats["unkeyed"])} · 短档(<200字) {PyS(stats["tiny"])}");
                foreach (var i in issues) Console.WriteLine($"  [FAIL] {i}");
                if (issues.Count == 0) Console.WriteLine("  ✓ 密度体检通过：无空档/不可读资产档");
                return issues.Count > 0 ? 1 : 0;
            }

            if (sub == "usage")
            {
                var (issues, stats) = AssetDensity.UsageScan(assetsRoot);
                if (json)
                {
                    Console.WriteLine(PythonJson.Indented(new Dictionary<string, object?>(StringComparer.Ordinal)
                    {
                        ["kind"] = "asset-usage",
                        ["issues"] = issues.Cast<object?>().ToList(),
                        ["stats"] = stats,
                    }));
                }
                else
                {
                    Console.WriteLine("== nf asset usage（45 资产引用度）==");
                    Console.WriteLine($"  资产键 {PyS(stats["assets"])} · 有引用 {PyS(stats["used"])} · " +
                                      $"零引用 {PyS(stats["zero_usage"])} · 引用总次数 {PyS(stats["total_refs"])}");
                    var zeroKeys = (List<object?>)stats["zero_keys"]!;
                    if (zeroKeys.Count > 0)
                        Console.WriteLine("  零引用键（低信息候选，不自动删）：" +
                                          string.Join("、", zeroKeys.Take(20).Select(PyS)));
                }
                return issues.Count > 0 || (strictRequested && Convert.ToInt64(stats["zero_usage"]) > 0) ? 1 : 0;
            }

            if (sub == "thickness")
            {
                var (issues, stats) = AssetDensity.ThicknessScan(assetsRoot);
                if (json)
                {
                    Console.WriteLine(PythonJson.Indented(new Dictionary<string, object?>(StringComparer.Ordinal)
                    {
                        ["kind"] = "asset-thickness",
                        ["issues"] = issues.Cast<object?>().ToList(),
                        ["stats"] = stats,
                    }));
                }
                else
                {
                    Console.WriteLine("== nf asset thickness（45 资产语义厚度）==");
                    Console.WriteLine($"  资产档 {PyS(stats["files"])} · 平均 {PyS(stats["avg_chars"])} 字符/档 · " +
                                      $"平均 {PyS(stats["avg_sections"])} 小节/档");
                    Console.WriteLine($"  低信息候选 {PyS(stats["low_info"])}（只报告不删）");
                    foreach (var f in ((List<object?>)stats["low_files"]!).Take(20))
                        Console.WriteLine($"  · {PyS(f)}");
                }
                return issues.Count > 0 ? 1 : 0;
            }

            if (sub == "ledger")
            {
                var (issues, stats) = AssetLedgerProjection.Verify(assetsRoot);
                if (json)
                {
                    Console.WriteLine(PythonJson.Indented(new Dictionary<string, object?>(StringComparer.Ordinal)
                    {
                        ["kind"] = "asset-ledger",
                        ["refresh"] = false,
                        ["issues"] = issues.Cast<object?>().ToList(),
                        ["stats"] = stats,
                    }));
                }
                else
                {
                    Console.WriteLine("== nf asset ledger（资产键表机读投影）==");
                    Console.WriteLine($"  校验：条目 {PyS(stats.GetValueOrDefault("entries", 0L))} · " +
                                      $"一致 {(issues.Count == 0 ? "是" : "否（refresh）")}");
                    foreach (var i in issues) Console.WriteLine($"  [FAIL] {i}");
                }
                return issues.Count > 0 ? 1 : 0;
            }

            // ls
            // 参数面与真源同严：`--tier/--status` 在 Python 侧是 argparse 的 choices（非法即 exit 2 用法错误），
            // 不能等到 filter_rows 才报（那是 exit 1）——退出码口径必须一致。
            if (assetTier.Length > 0 && assetTier is not ("official" or "community" or "experimental"))
                return Usage($"--tier 非法取值：{assetTier}（应为 official/community/experimental）");
            if (assetStatus.Length > 0 && assetStatus is not ("active" or "deprecated" or "retired"))
                return Usage($"--status 非法取值：{assetStatus}（应为 active/deprecated/retired）");
            var all = AssetLedger.IterAssets(assetsRoot);
            var filtered = AssetLedger.FilterRows(all, assetPkg, assetTier, assetStatus);
            if (json)
            {
                Console.WriteLine(JsonFor(new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["kind"] = "asset-ls",
                    ["rows"] = filtered.Cast<object?>().ToList(),
                }));
                return 0;
            }
            Console.WriteLine("== nf asset ls" +
                              (assetPkg.Length > 0 ? "（pkg=" + assetPkg + "）" : "") +
                              (assetTier.Length > 0 ? "（tier=" + assetTier + "）" : "") +
                              (assetStatus.Length > 0 ? "（status=" + assetStatus + "）" : "") + " ==");
            if (filtered.Count == 0)
            {
                Console.WriteLine("  （货架为空——nf asset add 入库首批资产）");
                return 0;
            }
            foreach (var r in filtered)
            {
                Console.WriteLine($"  · {PadCp(PyS(r["tier"]), 8)} {PadCp(PyS(r["key"]), 14)} " +
                                  $"v{PadCp(PyS(r["version"]), 6)} {PadCp(PyS(r["status"]), 10)} " +
                                  $"{PyS(r["file"])} -> {PyS(r["source"])}");
            }
            return 0;
        }
        catch (AssetLedger.LedgerError exc)
        {
            Console.Error.WriteLine($"  ✗ {exc.Message}");
            return 1;
        }
    }

    private static int DomainClosureCommand()
    {
        // 概念前置闭包只读求值器（scripts/ai_domain_closure.py）：图像语义走 ConceptGraph（与 check32 子扫描同实现）。
        var asset = closureAsset
            ?? Path.Combine(root!, ConceptGraph.DefaultAsset.Replace('/', Path.DirectorySeparatorChar));
        try
        {
            if (closureCheck)
            {
                var (fails, passes) = DomainClosure.SelfCheck(asset);
                foreach (var p in passes) Console.WriteLine($"  [PASS] {p}");
                foreach (var f in fails) Console.WriteLine($"  [FAIL] {f}");
                var suffix = DomainClosure.SamplesFor(asset) is null ? "（通用判据；该资产未登记键级样例）" : "";
                Console.WriteLine($"自检：{passes.Count}/{passes.Count + fails.Count} 通过{suffix}");
                return fails.Count == 0 ? 0 : 1;
            }
            var graph = ConceptGraph.LoadGraph(asset);
            var health = ConceptGraph.Problems(graph);
            if (health.Count > 0)
            {
                foreach (var item in health) Console.WriteLine($"  [FAIL] {item}");
                return 1;
            }
            var bids = ConceptGraph.BranchMap(graph);
            if (closureBranch.Length > 0 && !bids.ContainsKey(closureBranch))
            {
                Console.Error.WriteLine($"  ✗ 未知分支：{closureBranch}（可用：{SortedOrNone(bids.Keys)}）");
                return 2;
            }
            if (closureList)
            {
                Console.WriteLine(DomainClosure.RenderList(graph));
                return 0;
            }
            if (closureOrder.Length > 0)
            {
                var seqs = DomainClosure.Orderings(graph);
                if (!seqs.ContainsKey(closureOrder))
                {
                    Console.Error.WriteLine($"  ✗ 资产内无该序：{closureOrder}（可用：{SortedOrNone(seqs.Keys)}）");
                    return 2;
                }
                var bad = ConceptGraph.Violations(graph, seqs[closureOrder]);
                Console.WriteLine($"== 序校验：{closureOrder}（{seqs[closureOrder].Count} 个概念）==");
                Console.WriteLine($"  违反边：{bad.Count}");
                foreach (var (p, u) in bad) Console.WriteLine($"    {p} → {u} 被违反（前置排在后继之后）");
                return 0;
            }
            var loaded = DomainClosure.LoadedArg(closureLoaded);
            if (closureGaps)
            {
                Console.WriteLine(DomainClosure.RenderGaps(graph, loaded, closureBranch, Math.Max(1, closureLimit)));
                return 0;
            }
            if (closureReadyList)
            {
                var front = ConceptGraph.Frontier(graph, loaded, closureBranch);
                var sortedLoaded = loaded.Distinct(StringComparer.Ordinal)
                    .OrderBy(x => x, StringComparer.Ordinal).Cast<object?>().ToList();
                if (json)
                {
                    Console.WriteLine(PythonJson.Indented(new Dictionary<string, object?>(StringComparer.Ordinal)
                    {
                        ["loaded"] = sortedLoaded,
                        ["branch"] = closureBranch,
                        ["frontier"] = front.Cast<object?>().ToList(),
                        ["frontier_size"] = (long)front.Count,
                    }));
                }
                else
                {
                    Console.WriteLine($"== 下一步可装载集 frontier(L)（{(closureBranch.Length > 0 ? "分支 " + closureBranch : "全图")}）==");
                    Console.WriteLine($"  L = {(sortedLoaded.Count > 0 ? string.Join("、", sortedLoaded.Select(PyS)) : "（空）")}");
                    Console.WriteLine($"  frontier = {(front.Count > 0 ? string.Join("、", front) : "（空）")}（{front.Count} 个）");
                }
                return 0;
            }
            var label = asset.StartsWith(root!, StringComparison.Ordinal)
                ? Path.GetRelativePath(root!, asset)
                : asset;
            var result = DomainClosure.Report(graph, closureTarget, loaded, label);
            if (json) Console.WriteLine(PythonJson.Indented(result));
            else Console.WriteLine(DomainClosure.Render(result));
            return 0;
        }
        catch (ConceptGraph.ClosureError exc)
        {
            Console.Error.WriteLine($"  ✗ {exc.Message}");
            return 1;
        }
    }

    private static int OutputCommand()
    {
        // 产出形态面（45 · check32 output_forms 子扫描）**读面**：形态清单 + 判件。
        // 写面与合成面（render / meter / verify 三合一）留下一批——未移植即明确拒绝，不给半个面。
        var sub = positional.Count >= 2 ? positional[1] : "verify";
        if (sub == "render" && writeRequested)
            return Fail("output render --write 是写面（落盘产出面）——本引擎是只读门，不提供写命令");
        if (sub == "meter" && writeRequested)
            return Fail("output meter --write 是写面（重签机验率基线）——本引擎是只读门，不提供写命令");
        if (sub is not ("list" or "check" or "verify" or "render" or "meter"))
            return Usage($"output 的子命令须为 list / check / verify / render / meter：{sub}");

        if (sub == "verify")
        {
            var (issues, stats) = OutputForms.Scan(root!);
            if (json)
            {
                Console.WriteLine(JsonFor(new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["issues"] = issues.Cast<object?>().ToList(),
                    ["stats"] = stats,
                }));
                return issues.Count > 0 ? 1 : 0;
            }
            foreach (var i in issues) Console.Error.WriteLine($"  [FAIL] {i}");
            if (issues.Count == 0)
            {
                var reg = stats.GetValueOrDefault("registry") as Dictionary<string, object?> ?? new(StringComparer.Ordinal);
                var meter = stats.GetValueOrDefault("meter") as Dictionary<string, object?> ?? new(StringComparer.Ordinal);
                Console.WriteLine("  ✓ 产出形态面一致：形态 " + PyS(reg.GetValueOrDefault("forms"))
                                  + " 条（可达 " + (Convert.ToInt64(reg.GetValueOrDefault("forms")) - Convert.ToInt64(reg.GetValueOrDefault("unreachable")))
                                  + "）；包级产出 " + PyS((stats.GetValueOrDefault("index") as Dictionary<string, object?>)?.GetValueOrDefault("outputs"))
                                  + " 件；机验率 " + PyScalar.PyRepr(meter.ToDictionary(
                                      kv => kv.Key,
                                      kv => (object?)((Dictionary<string, object?>)kv.Value!).GetValueOrDefault("machine_verifiable_ratio"),
                                      StringComparer.Ordinal)));
            }
            return issues.Count > 0 ? 1 : 0;
        }

        if (sub == "render")
        {
            var (issues, rows) = OutputForms.RenderOutputs(root!, outputPackage);
            if (json)
            {
                Console.WriteLine(JsonFor(new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["issues"] = issues.Cast<object?>().ToList(),
                    ["rows"] = rows.Cast<object?>().ToList(),
                }));
                return issues.Count > 0 ? 1 : 0;
            }
            foreach (var r in rows)
                Console.WriteLine($"  {(PyTruthy(r["changed"]) ? "改" : "同")} {PadCp(PyS(r["path"]), 52)} "
                                  + $"生成器={PadCp(PyS(r["generator"]), 24)} "
                                  + (PyTruthy(r["written"]) ? "已落盘" : "未落盘（--write 才写）"));
            foreach (var i in issues) Console.Error.WriteLine($"  [FAIL] {i}");
            return issues.Count > 0 ? 1 : 0;
        }

        if (sub == "meter")
        {
            var (_, stats) = OutputForms.Meter(root!);
            if (json)
            {
                Console.WriteLine(JsonFor(stats));
                return 0;
            }
            Console.WriteLine("  " + PadCp("包", 18) + " " + PadCp("机验面", 8) + " " + PadCp("功能面", 8)
                              + " " + PadCp("散文资产", 10) + " 机验率");
            var packages = stats.GetValueOrDefault("packages") as Dictionary<string, object?> ?? new(StringComparer.Ordinal);
            foreach (var (pkg, raw) in packages)
            {
                var s = (Dictionary<string, object?>)raw!;
                Console.WriteLine("  " + PadCp(pkg, 18) + " " + PadCp(PyS(s["machine_verifiable"]), 8) + " "
                                  + PadCp(PyS(s["functional"]), 8) + " " + PadCp(PyS(s["prose_assets"]), 10)
                                  + " " + PyS(s["machine_verifiable_ratio"]));
            }
            Console.WriteLine("  合计：" + PyS(stats.GetValueOrDefault("totals")));
            return 0;
        }

        if (sub == "list")
        {
            var registry = OutputForms.LoadRegistry(root!);
            var rows = (registry.GetValueOrDefault("forms") as List<object?> ?? new List<object?>())
                .OfType<Dictionary<string, object?>>()
                .Where(f => assetStatus.Length == 0 || PyS(f.GetValueOrDefault("status")) == assetStatus)
                .Where(f => outputCategory.Length == 0 || PyS(f.GetValueOrDefault("category")) == outputCategory)
                .Where(f => assetTier.Length == 0 || PyS(f.GetValueOrDefault("tier")) == assetTier)
                .ToList();
            if (json)
            {
                Console.WriteLine(JsonFor(rows.Cast<object?>().ToList()));
                return 0;
            }
            Console.WriteLine("  " + PadCp("形态", 28) + " " + PadCp("类别", 14) + " " + PadCp("档位", 4)
                              + " " + PadCp("状态", 12) + " 规范入口/备注");
            foreach (var f in rows)
            {
                var spec = f.GetValueOrDefault("spec") as Dictionary<string, object?> ?? new(StringComparer.Ordinal);
                var uri = spec.TryGetValue("uri", out var u) ? u : "";
                Console.WriteLine("  " + PadCp(PyS(f.GetValueOrDefault("id")), 28) + " "
                                  + PadCp(PyS(f.GetValueOrDefault("category")), 14) + " "
                                  + PadCp(PyS(f.GetValueOrDefault("tier")), 4) + " "
                                  + PadCp(PyS(f.GetValueOrDefault("status")), 12) + " " + PyS(uri));
            }
            var cov = registry.GetValueOrDefault("coverage") as Dictionary<string, object?> ?? new(StringComparer.Ordinal);
            Console.WriteLine("  —— 共 " + PyS(cov.TryGetValue("forms", out var cf) ? cf : 0L)
                              + " 条（可达 " + PyS(cov.GetValueOrDefault("reachable"))
                              + " / 不可达 " + PyS(cov.GetValueOrDefault("unreachable"))
                              + "）；状态 " + PyS(cov.GetValueOrDefault("by_status"))
                              + "；档位 " + PyS(cov.GetValueOrDefault("by_tier")));
            return 0;
        }

        // check <paths...>
        var blob = new List<Dictionary<string, object?>>();
        var bad = 0;
        for (var i = 2; i < positional.Count; i++)
        {
            var p = positional[i];
            var rel = Path.IsPathRooted(p)
                ? Path.GetRelativePath(root!, Path.GetFullPath(p)).Replace('\\', '/')
                : p;
            var full = Path.Combine(root!, rel.Replace('/', Path.DirectorySeparatorChar));
            if (!File.Exists(full))
            {
                blob.Add(new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["path"] = rel, ["error"] = "文件不存在",
                });
                bad++;
                continue;
            }
            var (form, tier) = OutputForms.Detect(root!, rel);
            var issues = OutputForms.Check(root!, rel, form);
            blob.Add(new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["path"] = rel, ["form"] = form, ["max_tier"] = tier,
                ["issues"] = issues.Cast<object?>().ToList(),
            });
            if (issues.Count > 0) bad++;
        }
        if (json)
        {
            Console.WriteLine(JsonFor(blob.Cast<object?>().ToList()));
            return bad > 0 ? 1 : 0;
        }
        foreach (var r in blob)
        {
            if (r.TryGetValue("error", out var error) && error is not null)
            {
                Console.WriteLine($"  [FAIL] {PyS(r["path"])} {PyS(error)}");
                continue;
            }
            var issues = (List<object?>)r["issues"]!;
            Console.WriteLine($"  {(issues.Count > 0 ? "✗" : "✓")} {PadCp(PyS(r["path"]), 46)} " +
                              $"形态={PadCp(PyS(r["form"]), 14)} 上限档位={PyS(r["max_tier"])}");
            foreach (var issue in issues) Console.WriteLine($"      - {PyS(issue)}");
        }
        return bad > 0 ? 1 : 0;
    }

    private static int MarketCommand()
    {
        var regPath = registryPath is null
            ? Path.Combine(root!, "desktop", "src", "core", "registry.json")
            : (Path.IsPathRooted(registryPath) ? registryPath : Path.Combine(root!, registryPath));
        var registry = ImpactCheck.LoadRegistry(regPath);

        if (marketList)
        {
            if (marketTier is not null && marketTier is not ("official" or "community" or "experimental"))
                return Usage($"--tier 非法取值：{marketTier}（应为 official/community/experimental）");
            var items = MarketAnalyzer.ListMarket(registry, marketTier);
            if (json)
            {
                Console.WriteLine(PythonJson.Indented(new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["kind"] = "market-list",
                    ["tier"] = marketTier,
                    ["items"] = items.Cast<object?>().ToList(),
                }));
                return 0;
            }
            Console.WriteLine($"== nf market list{(marketTier is null ? "" : "（tier=" + marketTier + "）")} ==");
            var badge = new Dictionary<string, string>(StringComparer.Ordinal)
            {
                ["official"] = "🏛官方", ["community"] = "🌐社区", ["experimental"] = "🧪实验",
            };
            foreach (var it in items)
            {
                var grade = PyS(it.GetValueOrDefault("grade"));
                var badgeText = badge.TryGetValue(grade, out var b) ? b : grade;
                if (PyS(it.GetValueOrDefault("kind")) == "module")
                    Console.WriteLine($"  [{badgeText}] 模块 {PyS(it.GetValueOrDefault("id"))} · {PyS(it.GetValueOrDefault("name"))}");
                else
                    Console.WriteLine($"  [{badgeText}] 包 {PyS(it.GetValueOrDefault("id"))} v{PyS(it.GetValueOrDefault("version"))}" +
                                      $"（{PyS(it.GetValueOrDefault("modules"))} 模块）");
            }
            return 0;
        }

        // ---- 包视图（依赖闭包 + 挂载冲突预检；check15 ②③ 同构）----
        if (positional.Count < 2)
        {
            Console.Error.WriteLine("✗ 缺 pkg_dir（或加 --list 列目录）");
            return 2;
        }
        var pkgDirArg = positional[1];
        var pkgId = Path.GetFileName(pkgDirArg.TrimEnd('/', '\\'));
        var prots = MarketAnalyzer.Protocols(registry);
        var docPath = Path.Combine(root!, "02_联动注册表.md");
        var docText = File.Exists(docPath) ? File.ReadAllText(docPath, new System.Text.UTF8Encoding(false, true)) : "";
        // 与 Python 同口径：pkg_dir 按**进程 CWD** 解析（真源如此），doc 与各包 protocol.yaml 按 ROOT 解析
        var regIssues = MarketAnalyzer.CheckRegisterable(pkgDirArg, docText);
        if (!prots.ContainsKey(pkgId))
        {
            if (json)
            {
                Console.WriteLine(PythonJson.Indented(new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["kind"] = "market-package",
                    ["pkg_id"] = pkgId,
                    ["registered"] = false,
                    ["issues"] = regIssues.Cast<object?>().ToList(),
                }));
                return regIssues.Count > 0 ? 1 : 0;
            }
            Console.WriteLine($"  ✗ 包 {pkgId} 不在 registry protocols[]——无 references 可查"
                              + "（修复指引：核对包名（`nf market --list` 可枚举已登记包）；若是新包，"
                              + "先按 02 §8.3 登记三要件完成登记）");
            return regIssues.Count > 0 ? 1 : 0;
        }
        var data = MarketAnalyzer.PackData(root!);
        var (seen, depIssues) = MarketAnalyzer.Dependencies(pkgId, prots, data);
        var conflicts = MarketAnalyzer.Conflicts(pkgId, prots, data);
        var grades = MarketAnalyzer.GradesOfPackage(prots, pkgId);
        if (json)
        {
            Console.WriteLine(JsonFor(new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["kind"] = "market-package",
                ["pkg_id"] = pkgId,
                ["registered"] = true,
                ["issues"] = regIssues.Cast<object?>().ToList(),
                ["dependencies"] = seen.OrderBy(x => x, StringComparer.Ordinal).Cast<object?>().ToList(),
                ["dependency_issues"] = depIssues.Cast<object?>().ToList(),
                ["conflicts"] = conflicts.Cast<object?>().ToList(),
                ["grades"] = grades.ToDictionary(kv => kv.Key, kv => (object?)kv.Value, StringComparer.Ordinal),
            }));
            return 0;
        }
        Console.WriteLine($"== nf market {pkgId} ==");
        Console.WriteLine("  登记状态: " + (regIssues.Count == 0
            ? "在册（02 §8 + registry protocols[]）"
            : string.Join("; ", regIssues)));
        if (grades.Count > 0)
        {
            var badge = new Dictionary<string, string>(StringComparer.Ordinal)
            {
                ["official"] = "🏛官方", ["community"] = "🌐社区", ["experimental"] = "🧪实验",
            };
            Console.WriteLine("  分级徽章: " + string.Join(", ",
                grades.Select(kv => $"{kv.Key}({(badge.TryGetValue(kv.Value, out var b) ? b : kv.Value)})")));
        }
        Console.WriteLine("  依赖闭包: " + (seen.Count > 0
            ? string.Join(", ", seen.OrderBy(x => x, StringComparer.Ordinal))
            : "无跨包引用"));
        foreach (var i in depIssues) Console.WriteLine($"  [依赖] {i}");
        if (conflicts.Count > 0)
        {
            foreach (var i in conflicts) Console.WriteLine($"  [冲突] {i}");
        }
        else
        {
            Console.WriteLine("  挂载冲突: 无");
        }
        return 0;
    }

}
