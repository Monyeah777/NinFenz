using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text;
using System.Text.RegularExpressions;

namespace Nf.Engine;

/// <summary>知识声明 / 资产台账 / 输出形态 / 小面负例。</summary>
public static partial class SelfTest
{
    /// <summary>合成知识源声明（合同级 nf-protocol + 参考级 ext-assets）。</summary>
    private static string KnowledgeDecl(string contractLocator, bool withKind, bool reverseOrder = false)
    {
        var order = reverseOrder
            ? "\"query_order\": [\"ext-assets\", \"nf-protocol\"],"
            : "\"query_order\": [\"nf-protocol\", \"ext-assets\"],";
        var kindLine = withKind ? "\"kind\": \"local-compiled\", " : "";
        return string.Join("\n", new[]
        {
            "{",
            "  \"schema\": \"nf-knowledge-sources/1\",",
            "  \"authority_vocabulary\": [\"contract\", \"reference\"],",
            "  \"kind_vocabulary\": [\"local-compiled\", \"external-retrieval\"],",
            "  \"visibility_vocabulary\": [\"public\", \"internal\", \"restricted\"],",
            $"  {order}",
            "  \"promotion\": {\"evidence_tiers\": [\"machine-checkable\", \"reproducible\", \"externally-attestable\"],",
            "    \"triggers\": [\"reuse-frequency\", \"author-mark\", \"machine-check-pass\"],",
            "    \"rule\": \"三档证据齐方可转正\", \"on_missing_evidence\": \"stay-reference\"},",
            "  \"review\": {\"machine_gates\": [\"check37\"], \"rule\": \"逐条核证据\"},",
            "  \"cognition\": {\"filter_module\": \"M23\"},",
            "  \"sources\": [",
            $"    {{\"id\": \"nf-protocol\", \"authority\": \"contract\", {kindLine}\"locator\": \"{contractLocator}\", \"requires_source_label\": false, \"visibility\": \"public\", \"freshness\": {{\"policy\": \"stale_after\"}}}},",
            "    {\"id\": \"ext-assets\", \"authority\": \"reference\", \"kind\": \"external-retrieval\", \"locator\": \"library\", \"requires_source_label\": true, \"visibility\": \"internal\", \"freshness\": {\"policy\": \"ttl\", \"ttl_days\": 180}}",
            "  ]",
            "}", "",
        });
    }

    // ---------------------------------------- ⑧a Python 字符串语义（码点 vs UTF-16 单元）

    /// <summary>
    /// 实测教训：`state-front --ab` 的 `sha256` 两侧全同、`chars` 差 1——因为 Python 的
    /// <c>len(str)</c> 数**码点**，而 C# 的 <c>string.Length</c> 数 **UTF-16 代码单元**，
    /// 非 BMP 字符（emoji 等）会差一。切片同理（<c>s[:n]</c> 按码点，不能劈开代理对）。
    /// </summary>
    private static void PythonStringCases(List<Check> checks)
    {
        checks.Add(Guarded("字符串语义·len 数码点（非 BMP 字符算 1 而不是 2）", () =>
        {
            var emoji = "😀";
            var ok = PyScalar.PyLen(emoji) == 1 && PyScalar.PyLen("中文") == 2
                     && PyScalar.PyLen("😀😀") == 2 && PyScalar.PyLen("") == 0;
            return (ok, $"PyLen(\"😀\")={PyScalar.PyLen(emoji)}（.NET Length={emoji.Length}）· " +
                        $"PyLen(\"中文\")={PyScalar.PyLen("中文")}");
        }));

        checks.Add(Guarded("字符串语义·切片按码点，不劈开代理对", () =>
        {
            var sliced = PyScalar.PySlice("😀abc", 2);
            var ok = sliced == "😀a" && PyScalar.PySlice("abc", 9) == "abc" && PyScalar.PySlice("", 3) == "";
            return (ok, $"PySlice(\"😀abc\", 2)={PyScalar.PyRepr(sliced)}");
        }));
    }

    // --------------------------------- ⑱ 知识层可见性秩与复用面（单一真相源）

    /// <summary>
    /// 两条钉：① **可见性秩**——clearance 达到源的秩才可见（`public ⊆ internal ⊆ restricted`），
    /// 且越权源不进入查询顺序；② **复用面**——同一内容存在两份（馆藏条目 / 实践包源件全文摘要相同）
    /// 即 FAIL，因为"同一内容两份 = 两个真源"。
    /// </summary>
    private static void KnowledgeCliFacesCases(List<Check> checks, string work)
    {
        var root = Path.Combine(work, "knowledge-visible");
        WriteFile(root, "protocol/transform_log.json", "{\"schema\": \"nf-transform-log/1\", \"entries\": []}\n");
        WriteFile(root, "protocol/knowledge_usage.json",
            "{\"schema\": \"nf-knowledge-usage/1\", \"counts\": {}, \"total\": 0}\n");
        WriteFile(root, "protocol/knowledge_sources.json", string.Join("\n", new[]
        {
            "{", "  \"schema\": \"nf-knowledge-sources/1\",",
            "  \"authority_vocabulary\": [\"contract\", \"reference\"],",
            "  \"kind_vocabulary\": [\"local-compiled\", \"external-retrieval\"],",
            "  \"visibility_vocabulary\": [\"public\", \"internal\", \"restricted\"],",
            "  \"query_order\": [\"pub-src\", \"int-src\", \"res-src\"],",
            "  \"promotion\": {\"evidence_tiers\": [\"machine-checkable\", \"reproducible\", \"externally-attestable\"],",
            "    \"triggers\": [\"reuse-frequency\", \"author-mark\", \"machine-check-pass\"],",
            "    \"rule\": \"三档证据齐方可转正\", \"on_missing_evidence\": \"stay-reference\"},",
            "  \"review\": {\"machine_gates\": [\"check37\"], \"rule\": \"逐条核证据\"},",
            "  \"cognition\": {\"filter_module\": \"M23\"},", "  \"sources\": [",
            "    {\"id\": \"pub-src\", \"authority\": \"contract\", \"kind\": \"local-compiled\", \"locator\": \"library\", \"requires_source_label\": false, \"visibility\": \"public\", \"freshness\": {\"policy\": \"stale_after\"}},",
            "    {\"id\": \"int-src\", \"authority\": \"contract\", \"kind\": \"local-compiled\", \"locator\": \"library\", \"requires_source_label\": false, \"visibility\": \"internal\", \"freshness\": {\"policy\": \"stale_after\"}},",
            "    {\"id\": \"res-src\", \"authority\": \"reference\", \"kind\": \"external-retrieval\", \"locator\": \"library\", \"requires_source_label\": true, \"visibility\": \"restricted\", \"freshness\": {\"policy\": \"no-cache\"}}",
            "  ]", "}", "",
        }));
        checks.Add(Guarded("知识层·可见性秩：public ⊆ internal ⊆ restricted（越权源被裁掉）", () =>
        {
            var pub = KnowledgeSources.VisibleIds(root, "public");
            var mid = KnowledgeSources.VisibleIds(root, "internal");
            var all = KnowledgeSources.VisibleIds(root, "restricted");
            var unknown = KnowledgeSources.VisibleIds(root, "bogus");
            var order = KnowledgeSources.ResolveOrder(root, "internal").Select(r => (string)r["id"]!).ToList();
            var ok = pub.SetEquals(new[] { "pub-src" }) && mid.SetEquals(new[] { "pub-src", "int-src" })
                     && all.Count == 3 && unknown.Count == 0
                     && order.SequenceEqual(new[] { "pub-src", "int-src" });
            return (ok, $"public={pub.Count} · internal={mid.Count} · restricted={all.Count} · " +
                        $"未知级={unknown.Count} · 裁剪后顺序=[{string.Join(",", order)}]");
        }));

        var dup = Path.Combine(work, "knowledge-reuse");
        // 两件**逐字节相同**——这正是要抓的「同一内容两份 = 两个真源」
        const string sameBytes = "---\nid: NF-1\ntitle: 甲\n---\n正文同一份\n";
        WriteFile(dup, "library/NF-1.md", sameBytes);
        WriteFile(dup, "patterns/p/PATTERN.md", sameBytes);
        checks.Add(Guarded("知识层·复用面：同一内容存在两份即 FAIL（两个真源）", () =>
        {
            var (issues, _, stats) = KnowledgeSources.VerifyReuse(dup);
            var hit = issues.FirstOrDefault(i => i.Contains("同一内容存在两份", StringComparison.Ordinal));
            return (hit is not null && (int)(stats["unique_digests"] ?? 0) == 1,
                hit ?? $"未报同内容两份（unique_digests={stats.GetValueOrDefault("unique_digests")}）");
        }));
    }

    // ------------------------------------------- ⑧b YAML 边界与转义（构造矩阵实测）

    /// <summary>
    /// 构造矩阵探针实测出的三处真问题，逐条钉住：
    /// ① `.NaN` 曾落到 double.Parse 抛 FormatException（**进程级异常**）——修后按 PyYAML 语义
    ///    成为 NaN，而**裸 `NaN` 是字符串**（PyYAML 的特殊值必须带点）；
    /// ② `"\x41"` 曾把 `\x` 吞掉变成 `x41`——修后还原成 `A`；
    /// ③ 块标量 / 锚点 / 别名 / 合并键 / 未闭合引号**必须显式 fail-closed**——
    ///    此前它们被静默当字符串（`k: |` → 字面 `"|"`），使"越界即报错"的承诺对这几族是假的。
    /// </summary>
    private static void YamlBoundaryCases(List<Check> checks)
    {
        checks.Add(Guarded("YAML·特殊浮点：`.NaN` 不崩；裸 NaN 是字符串（同 PyYAML）", () =>
        {
            var map = MiniYaml.Parse("a: .NaN\nb: .inf\nc: NaN\nd: nan\ne: .INF\n");
            var ok = map["a"] is double nanA && double.IsNaN(nanA)
                     && map["b"] is double infB && double.IsPositiveInfinity(infB)
                     && map["c"] is "NaN" && map["d"] is "nan"
                     && map["e"] is double infE && double.IsPositiveInfinity(infE);
            return (ok, $"a={PyScalar.TypeName(map["a"])} b={PyScalar.TypeName(map["b"])} " +
                        $"c={PyScalar.PyRepr(map["c"])} d={PyScalar.PyRepr(map["d"])}");
        }));

        checks.Add(Guarded("YAML·双引号转义族：`\\x41` 还原成 A（此前被吞成 x41）", () =>
        {
            var map = MiniYaml.Parse("a: \"\\x41\"\nb: \"\\u4e2d\"\nc: \"a\\tb\"\nd: \"\\0\"\n");
            var ok = (string?)map["a"] == "A" && (string?)map["b"] == "中"
                     && (string?)map["c"] == "a\tb" && (string?)map["d"] == "\0";
            return (ok, $"a={PyScalar.PyRepr(map["a"])} b={PyScalar.PyRepr(map["b"])} c={PyScalar.PyRepr(map["c"])}");
        }));

        checks.Add(Guarded("YAML·子集外构造必须显式 fail-closed（不许静默当字符串）", () =>
        {
            var cases = new (string Doc, string Want)[]
            {
                ("k: |\n  内容\n", "块标量"),
                ("k: >-\n  内容\n", "块标量"),
                ("a: &x 1\nb: *x\n", "锚点"),
                ("- *x\n", "别名"),
                ("a:\n  <<: 1\n", "合并键"),
                ("k: \"未闭合\n", "未闭合的引号"),
                ("k:\n\tj: 1\n", "TAB"),
            };
            var results = new List<string>();
            var allOk = true;
            foreach (var (doc, want) in cases)
            {
                try
                {
                    MiniYaml.Parse(doc);
                    allOk = false;
                    results.Add(want + "→未报错");
                }
                catch (InvalidOperationException exc)
                {
                    var hit = exc.Message.Contains(want, StringComparison.Ordinal);
                    allOk = allOk && hit;
                    results.Add(want + (hit ? "✓" : "→文案不符"));
                }
            }
            return (allOk, string.Join(" · ", results));
        }));
    }

    private static void WriteFile(string root, string rel, string text)
    {
        var full = Path.Combine(root, rel.Replace('/', Path.DirectorySeparatorChar));
        Directory.CreateDirectory(Path.GetDirectoryName(full)!);
        File.WriteAllText(full, text, new UTF8Encoding(false));
    }

    private static string PatternDoc(string id) => string.Join("\n", new[]
    {
        "---", $"id: {id}", "name: 示例实践包", "status: active", "scope:", "  - 代码层",
        "applies_to:", "  - src", "rules:", "  - 规则一", "evidence:", "  - check34",
        "---", "", "## 正文", "",
    });

    private static string RfcDoc(string rfc, string supersededBy) => string.Join("\n", new[]
    {
        "# 示例协议件",
        "> 最后更新：2026-01-02",
        $"> **RFC**: {rfc} · **Category**: Standards Track · **Date**: 2026-01-02 · **Status**: " +
        (supersededBy == "—" ? "Active" : "Superseded") +
        $" · **Supersedes**: — · **Superseded by**: {supersededBy}",
        "", "正文。", "",
    });

    private static Check Guarded(string name, Func<(bool Passed, string Detail)> body)
    {
        try
        {
            var (passed, detail) = body();
            return new Check(name, passed, detail);
        }
        catch (Exception ex)
        {
            return new Check(name, false, $"未处理异常：{ex.GetType().Name}: {ex.Message}");
        }
    }

    // ---------------------------------------------------------------- ② 模块工具面（tool_face）

    // ---------------------------------------------------------------- ②′ ST 制卡校验器

    // ---------------------------------------------------------------- ②″ 自述数字实算

    // ---------------------------------------------------------------- ②‴ 知识源频次复算

    // ---------------------------------------------------------------- ②⁗ 互操作导出面

    // ---------------------------------------------------------------- ②⁵ MCP 错误响应契约

    // ---------------------------------------------------------------- ②⁶ 世界模型校验

    // ---------------------------------------------------------------- ②⁷ registry 引用图 / 影响面

    // ---------------------------------------------------------------- ②⁸ 市场分级与 See-Also

    // ---------------------------------------------------------------- ②⁹ 资产台账（check23 同语义）

    private static void AssetCases(List<Check> checks, string work)
    {
        var root = Path.Combine(work, "asset-ledger");
        if (Directory.Exists(root)) Directory.Delete(root, recursive: true);
        Directory.CreateDirectory(root);
        string Header(string key, string ver, string st)
            => $"<!-- nf-asset: key=\"{key}\" version=\"{ver}\" status=\"{st}\" -->\n";

        var ledger = new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["schema_version"] = "1",
            ["tier"] = "community",
            ["package"] = "合成资产集",
            ["assets"] = new List<object?>
            {
                new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["file"] = "good.md", ["key"] = "GOOD", ["source"] = "合成来源",
                    ["version"] = "1.0", ["status"] = "active",
                },
                new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["file"] = "dup1.md", ["key"] = "DUP", ["source"] = "合成来源",
                    ["version"] = "1.0", ["status"] = "active",
                },
                new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["file"] = "dup2.md", ["key"] = "DUP", ["source"] = "合成来源",
                    ["version"] = "1.0", ["status"] = "active",
                },
                new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["file"] = "missing.md", ["key"] = "MISSING", ["source"] = "合成来源",
                    ["version"] = "1.0", ["status"] = "active",
                },
            },
        };
        File.WriteAllText(Path.Combine(root, "provenance.json"), PythonJson.Indented(ledger) + "\n");
        File.WriteAllText(Path.Combine(root, "good.md"), Header("GOOD", "1.0", "active") + "# 好资产\n");
        File.WriteAllText(Path.Combine(root, "dup1.md"), Header("DUP", "1.0", "active") + "# 一\n");
        File.WriteAllText(Path.Combine(root, "dup2.md"), Header("DUP", "1.0", "active") + "# 二\n");
        File.WriteAllText(Path.Combine(root, "orphan.md"), Header("ORPHAN", "1.0", "active") + "# 孤儿\n");
        File.WriteAllText(Path.Combine(root, "untracked.md"), "# 无头\n");
        // 货架单层不变量：community/<包>/assets 下出现子目录即 FAIL
        var shelf = Path.Combine(root, "community", "合成包", "assets");
        Directory.CreateDirectory(Path.Combine(shelf, "子目录"));
        File.WriteAllText(Path.Combine(shelf, "a.md"), Header("SHELF", "1.0", "active") + "# 架内\n");

        var (issues, stats) = AssetLedger.VerifyRoot(root);
        var joined = string.Join(" | ", issues);
        checks.Add(new Check("资产台账·闭合判定（重键 / 文件缺失 / 孤儿头 / 未托管 / 货架子目录）",
            Convert.ToInt64(stats["ledgers"]) == 1 && Convert.ToInt64(stats["assets"]) == 4
            && joined.Contains("键重复") && joined.Contains("在册文件缺失")
            && joined.Contains("孤儿文件头（键不在台账）: orphan.md")
            && joined.Contains("孤儿文件头（键不在台账）: community/合成包/assets/a.md")
            && joined.Contains("资产货架含子目录 子目录")
            && Convert.ToInt64(stats["untracked"]) == 1,
            $"台账 {stats["ledgers"]} · 在册 {stats["assets"]} · 未托管 {stats["untracked"]} · " +
            $"孤儿 {stats["orphans"]} · 问题 {issues.Count} 条"));

        // 货架检查**不许静默失灵**：显式钉一次货架计数（历史上这里曾把 `*` 当字面目录名 → 整条检查 no-op）
        var (shelfIssues, shelfStats) = AssetLedger.VerifyShelfShape(root);
        checks.Add(new Check("资产台账·货架单层不变量真的在跑（不许静默 no-op）",
            Convert.ToInt64(shelfStats["shelves"]) == 1 && shelfIssues.Count == 1,
            $"货架 {shelfStats["shelves"]} 个 · 问题 {shelfIssues.Count} 条"));

        // 过滤器与非法取值：tier/status 非法即抛（CLI 层按真源口径 exit 2）
        var rows = AssetLedger.IterAssets(root);
        var activeOnly = AssetLedger.FilterRows(rows, status: "active");
        var badTier = false;
        try { AssetLedger.FilterRows(rows, tier: "bogus"); }
        catch (AssetLedger.LedgerError) { badTier = true; }
        var inventory = AssetLedger.InventoryRoot(root);
        checks.Add(new Check("资产台账·浏览/过滤/盘点（行数 · 非法 tier 抛错 · 盘点摘要）",
            rows.Count == 4 && activeOnly.Count == 4 && badTier && inventory.Count == 1
            && Convert.ToInt64(inventory[0]["assets"]) == 4
            && (inventory[0]["package"] as string) == "合成资产集",
            $"行 {rows.Count} · 过滤后 {activeOnly.Count} · 非法 tier 抛错={badTier} · 盘点 {inventory.Count} 行"));
    }

    // ---------------------------------------------------------------- ②⁹ᵇ 资产质量五面（45 W2 · 第 68 片）

    private static void AssetQualityCases(List<Check> checks, string work)
    {
        var root = Path.Combine(work, "asset-quality");
        if (Directory.Exists(root)) Directory.Delete(root, recursive: true);
        foreach (var rel in new[] { "community/合成甲包/assets", "community/合成乙包/assets",
                                    "05_资产库/用户自定义", "04_模块库", "docs", "protocol" })
            Directory.CreateDirectory(Path.Combine(root, rel.Replace('/', Path.DirectorySeparatorChar)));

        // 合格档一律 ≥200 字符：把「短档 / 低信息候选」隔离到专门造的那一份上，不靠运气。
        var pad = string.Concat(Enumerable.Repeat("补长正文，用来顶过 200 字符阈值，避免整棵树被标成低信息候选；", 6));
        string Asset(string key) => $"# 合成档\n\n`{key}` 定义。\n\n## {key}\n\n{pad}\n";
        var dirA = Path.Combine(root, "community", "合成甲包", "assets");
        var dirB = Path.Combine(root, "community", "合成乙包", "assets");
        File.WriteAllText(Path.Combine(dirA, "ALPHA.md"), Asset("KEY_ALPHA"));
        File.WriteAllText(Path.Combine(dirA, "README.md"), "# 键表（人读）\n");
        File.WriteAllText(Path.Combine(dirB, "BETA.md"), Asset("KEY_BETA"));
        File.WriteAllText(Path.Combine(root, "05_资产库", "用户自定义", "USER.md"), Asset("KEY_USER"));
        File.WriteAllText(Path.Combine(root, "04_模块库", "M01合成.md"),
            "# 合成模块\n\n引用 `KEY_ALPHA` `KEY_BETA` `KEY_USER`。\n");
        File.WriteAllText(Path.Combine(root, "docs", "note.md"), "# 说明\n");

        // ① 键发现两套口径**不许互相替换**：密度面认带连字符条目键，投影面不认（各自照抄真源）
        const string probeText = "文首 `C01-01` 与 \"A_B\": 与\n\n## HEADKEY\n";
        var densityKeys = AssetDensity.KeysOf("PROBE.md", probeText);
        var projectionKeys = AssetLedgerProjection.FileKeys("PROBE.md", probeText);
        checks.Add(new Check("资产质量·键发现两套口径（密度认连字符 / 投影不认，不许混用）",
            densityKeys.Contains("C01-01") && projectionKeys.Contains("A_B")
            && !projectionKeys.Contains("C01-01")
            && densityKeys.Contains("HEADKEY") && projectionKeys.Contains("HEADKEY"),
            "密度=" + string.Join(",", densityKeys) + " · 投影=" + string.Join(",", projectionKeys)));

        // ② 行数基线：自洽即 PASS（先钉"不误报"），改一字节即 FAIL（再钉"真的会红"）
        var baselineDoc = new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["schema"] = AssetLineBaseline.Schema,
            ["note"] = "合成基线",
            ["recorded_at"] = "2026-09-27",
            ["packages"] = AssetLineBaseline.ScanPackages(root).Cast<object?>().ToList(),
        };
        File.WriteAllText(Path.Combine(root, "protocol", "asset_line_baseline.json"),
            PythonJson.Indented(baselineDoc) + "\n");
        var (bOkIssues, bOkWarns, bOkStats) = AssetLineBaseline.Verify(root);
        checks.Add(new Check("资产质量·行数基线自洽不误报（在册 N 包 · 零 FAIL 零 WARN）",
            bOkIssues.Count == 0 && bOkWarns.Count == 0
            && Convert.ToInt64(bOkStats["packages"]) == 2 && Convert.ToInt64(bOkStats["baseline"]) == 2,
            $"在册 {bOkStats["packages"]} · 基线 {bOkStats["baseline"]} · 问题 {bOkIssues.Count}"));

        // ③ 键表投影：自洽即 PASS；新增键即"过期"
        var entries = AssetLedgerProjection.Build(root);
        File.WriteAllText(Path.Combine(root, "protocol", "community_asset_ledger.json"),
            PythonJson.Indented(new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["schema"] = AssetLedgerProjection.LedgerSchemaName,
                ["entries"] = entries.Cast<object?>().ToList(),
            }) + "\n");
        var (lOkIssues, lOkStats) = AssetLedgerProjection.Verify(root);
        checks.Add(new Check("资产质量·键表投影自洽（条目数与重算一致 · 零 FAIL）",
            lOkIssues.Count == 0 && Convert.ToInt64(lOkStats["entries"]) == entries.Count,
            $"条目 {lOkStats["entries"]} · 问题 {lOkIssues.Count}"));

        // ④ 引用度：**只有文件名令牌、正文不出现**的键才会零引用（资产档自身也在语料里）
        File.WriteAllText(Path.Combine(dirA, "ORPHANKEY.md"),
            "# 孤键档\n\n正文刻意不提那个只写在文件名上的键。\n" + pad + "\n");
        var (uIssues, uStats) = AssetDensity.UsageScan(root);
        var zeroKeys = ((List<object?>)uStats["zero_keys"]!).Select(PyScalar.PyRepr).ToList();
        checks.Add(new Check("资产质量·引用度（零引用键被点名 · 正文声明过的键不算零引用）",
            uIssues.Count == 0 && Convert.ToInt64(uStats["zero_usage"]) == 1
            && zeroKeys.Contains("'ORPHANKEY'")
            && Convert.ToInt64(uStats["used"]) == Convert.ToInt64(uStats["assets"]) - 1,
            $"资产键 {uStats["assets"]} · 零引用 {uStats["zero_usage"]} = [{string.Join(",", zeroKeys)}]"));

        // ⑤ 密度：空档 = FAIL（空档不进档数，只进问题；短档另计数）
        File.WriteAllText(Path.Combine(dirA, "EMPTY.md"), "");
        var (dIssues, dStats) = AssetDensity.Scan(root);
        checks.Add(new Check("资产质量·密度（空档即 FAIL · 无键/短档只计数不翻红）",
            dIssues.Count == 1 && dIssues[0].Contains("为空档（0 字符）")
            && Convert.ToInt64(dStats["files"]) == 4 && Convert.ToInt64(dStats["tiny"]) == 0
            && Convert.ToString(dStats["avg_keys_per_file"])!.Length > 0,
            $"问题 {dIssues.Count} · 档 {dStats["files"]} · 短档 {dStats["tiny"]}"));

        // ⑥ 厚度：短档成为低信息候选，平均值为整数（不是浮点）
        File.WriteAllText(Path.Combine(dirA, "THIN.md"), "太短。\n");
        var (tIssues, tStats) = AssetDensity.ThicknessScan(root);
        var lowFiles = ((List<object?>)tStats["low_files"]!).Select(PyScalar.PyRepr).ToList();
        checks.Add(new Check("资产质量·厚度（低信息候选点名到档 · 平均值取整）",
            tIssues.Count == 0 && Convert.ToInt64(tStats["low_info"]) == 1
            && lowFiles.Count == 1 && lowFiles[0]!.Contains("THIN.md")
            && tStats["avg_chars"] is long && tStats["avg_sections"] is long,
            $"低信息 {tStats["low_info"]} = [{string.Join(",", lowFiles)}] · 平均字符 {tStats["avg_chars"]}"));

        // ⑦ 漂移三态：内容改动 / 新包未登记 / 缺包跳过——三条判定各走各的分支
        File.AppendAllText(Path.Combine(dirA, "ALPHA.md"), "\n追加一行。\n");
        var (bDrift, _w1, _s1) = AssetLineBaseline.Verify(root);
        var driftText = string.Join(" | ", bDrift);
        Directory.CreateDirectory(Path.Combine(root, "community", "合成丙包", "assets"));
        File.WriteAllText(Path.Combine(root, "community", "合成丙包", "assets", "DELTA.md"), Asset("KEY_DELTA"));
        var (bNew, _w2, _s2) = AssetLineBaseline.Verify(root);
        var newText = string.Join(" | ", bNew);
        Directory.Delete(Path.Combine(root, "community", "合成乙包"), recursive: true);
        var (bGone, bGoneWarns, _s3) = AssetLineBaseline.Verify(root);
        var staleLedger = AssetLedgerProjection.Verify(root).Issues;
        checks.Add(new Check("资产质量·漂移三分支（外形不一致 / 新包未登记 / 缺包只 WARN · 投影随动过期）",
            driftText.Contains("资产行数与基线不一致") && newText.Contains("社区包资产未登记基线")
            && bGoneWarns.Any(w => w.Contains("不在场"))
            && staleLedger.Any(i => i.Contains("与资产扫描不一致")),
            $"漂移 {bDrift.Count} 条 · 新包 {bNew.Count} 条 · WARN {bGoneWarns.Count} 条 · 投影过期 {staleLedger.Count} 条"));

        // ⑧ glob 口径：`*.md` 后缀按平台（Windows 不分大小写）且**不过滤点文件**——不许静默丢面
        var before = AssetShelf.MarkdownFiles(root).Count;
        File.WriteAllText(Path.Combine(dirA, "UPPER.MD"), Asset("KEY_UPPER"));
        File.WriteAllText(Path.Combine(dirA, ".hidden.md"), Asset("KEY_HIDDEN"));
        var after = AssetShelf.MarkdownFiles(root).Count;
        var expectDelta = OperatingSystem.IsWindows() ? 2 : 1;
        checks.Add(new Check("资产质量·glob 口径（后缀按平台判大小写 + 点文件在面内）",
            after - before == expectDelta,
            $"档数 {before} → {after}（期望 +{expectDelta} · Windows 上 .MD 与 .hidden.md 都算）"));
    }

    // ---------------------------------------------------------------- ②⁹ᶜ 判据面小口三件（第 69 片 · explain / who-refers / diff）

    private static void SmallFacesCases(List<Check> checks, string work)
    {
        var root = Path.Combine(work, "small-faces");
        if (Directory.Exists(root)) Directory.Delete(root, recursive: true);
        Directory.CreateDirectory(root);

        // ① 修复指引表：机械导出件的长度与**码点序**键序（"10" 排在 "2" 前），缺键必须是 null
        var keys = CheckGuide.SortedKeys();
        checks.Add(new Check("小口·修复指引表（42 条 · 码点序键序 · 缺键 null）",
            CheckGuide.Count == 42 && keys.Count == 42
            && string.Join(",", keys.Take(4)) == "1,10,11,12"
            && keys[^1] == "9"
            && CheckGuide.Get("42") is not null && CheckGuide.Get("32")!.Contains("质量纵深汇总"),
            $"条目 {CheckGuide.Count} · 前三键 {string.Join(",", keys.Take(3))} · 末键 {keys[^1]}"));

        // ② 引用反查：**类别感知**匹配（合成 registry —— 真仓被引声明恰好都是裸号，正向对账看不出这条差别）
        var regPath = Path.Combine(root, "synth_registry.json");
        var registry = new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["registry_schema_version"] = "2",
            ["protocols"] = new List<object?>
            {
                new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["id"] = "包甲",
                    ["references"] = new List<object?>
                    {
                        Ref("情感:M55", "源甲", true), Ref("法律:M55", "源乙", false), Ref("M55", "源丙", null),
                    },
                },
                new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["id"] = "包乙",
                    ["references"] = new List<object?> { Ref("情感:M55", "源丁", null) },
                },
            },
        };
        File.WriteAllText(regPath, PythonJson.Indented(registry) + "\n");
        var catHits = Retriever.ReferencedBy("情感:M55", regPath);
        var bareHits = Retriever.ReferencedBy("M55", regPath);
        var catText = string.Join(" | ", catHits.Select(r => PyScalar.PyRepr(r["module_id"])));
        checks.Add(new Check("小口·引用反查类别感知（限定查询不越界到别的类别 · 裸号查询全命中）",
            catHits.Count == 3 && catText.Contains("情感:M55") && !catText.Contains("法律:M55")
            && bareHits.Count == 4,
            $"情感:M55 → {catHits.Count} 条 [{catText}] · M55 → {bareHits.Count} 条"));

        // ③ registry 缺件：真源吞成空表（不是报错）——只读门也不许在这里翻红
        var missingHits = Retriever.ReferencedBy("M55", Path.Combine(root, "不存在.json"));
        checks.Add(new Check("小口·引用反查 registry 缺件 → 空表不抛（与真源 try/except 同语义）",
            missingHits.Count == 0, $"命中 {missingHits.Count} 条"));

        // ④ 签名差异四分支：verdict 与 impact 各走一次
        var baseSig = Sig("01", "v1.0", new[] { "M01", "M02" });
        var sameSig = Sig("01", "v1.0", new[] { "M02", "M01" });          // 同集合、不同顺序 → 必须零差异
        var addSig = Sig("01", "v1.0", new[] { "M01", "M02", "M03" });    // 新增
        var dropSig = Sig("01", "v1.0", new[] { "M02" });                 // 移除 M01
        var docIdSig = Sig("02", "v1.0", new[] { "M01", "M02" });         // 编号变更
        var sameDiff = SignatureDiff.Diff(baseSig, sameSig);
        var addDiff = SignatureDiff.Diff(baseSig, addSig);
        var dropDiff = SignatureDiff.Diff(baseSig, dropSig);
        var idDiff = SignatureDiff.Diff(baseSig, docIdSig);
        checks.Add(new Check("小口·签名差异四分支（顺序无关 · 只增 additive · 移除需评审/bump · 编号变破坏/bump）",
            ((List<object?>)sameDiff["changes"]!).Count == 0
            && (string)addDiff["impact"]! == "additive"
            && (string)addDiff["verdict"]! == "兼容"
            && (string)dropDiff["impact"]! == "bump"
            && ((string)dropDiff["verdict"]!).Contains("需评审")
            && (string)idDiff["impact"]! == "bump"
            && ((string)idDiff["verdict"]!).Contains("破坏"),
            $"同集合 changes={((List<object?>)sameDiff["changes"]!).Count} · 只增={addDiff["impact"]} · " +
            $"移除={dropDiff["verdict"]} · 编号变={idDiff["verdict"]}"));

        // ⑤ 端到端：合成文档对经 BuildSignature → Diff（证明两条链真的接上了，不是只测比较器）
        var docA = Path.Combine(root, "01_甲.md");
        var docB = Path.Combine(root, "01_甲增.md");
        File.WriteAllText(docA, "# 甲\n\n```yaml\nid: M01\n```\n\n引用 M01 与 M02。\n");
        File.WriteAllText(docB, "# 甲\n\n```yaml\nid: M01\n```\n\n引用 M01 与 M02。\n\n## 乙\n\n新增引用 M03。\n");
        var endToEnd = SignatureDiff.Diff(KnowledgeSig.BuildSignature("01_甲.md", root),
                                          KnowledgeSig.BuildSignature("01_甲增.md", root));
        var added = ((List<object?>)endToEnd["changes"]!)
            .Cast<Dictionary<string, object?>>().Any(c => (string)c["kind"]! == "新增");
        checks.Add(new Check("小口·签名差异端到端（合成文档 → 签名 → 差异；新增项被抓到）",
            added && (string)endToEnd["impact"]! == "additive" && endToEnd["from"] as string == "01_甲.md",
            $"from={endToEnd["from"]} · impact={endToEnd["impact"]} · changes={((List<object?>)endToEnd["changes"]!).Count}"));

        static Dictionary<string, object?> Ref(string mid, string pkg, bool? ro) =>
            new(StringComparer.Ordinal)
            {
                ["module_id"] = mid, ["source_package"] = pkg,
                ["source_schema_version"] = "2", ["asset_readonly"] = ro,
            };

        static Dictionary<string, object?> Sig(string docId, string version, string[] refs) =>
            new(StringComparer.Ordinal)
            {
                ["kind"] = "doc", ["path"] = "01_甲.md", ["doc_id"] = docId, ["title"] = "甲",
                ["version"] = version, ["self_id"] = "M01", ["layer"] = "P01", ["category"] = "事件",
                ["heading_count"] = 2L, ["headings"] = new List<object?> { "甲" },
                ["schema_names"] = new List<object?>(), ["refs"] = refs.Cast<object?>().ToList(),
                ["meta_line_count"] = 0L, ["line_count"] = 3L, ["body_hash"] = "h",
            };
    }

    // ---------------------------------------------------------------- ②⁹ᵈ 产出形态面（第 70 片 · output list / check）

    private static void OutputFormsCases(List<Check> checks, string work)
    {
        var root = Path.Combine(work, "output-forms");
        if (Directory.Exists(root)) Directory.Delete(root, recursive: true);
        Directory.CreateDirectory(root);
        string W(string rel, string text)
        {
            var full = Path.Combine(root, rel);
            Directory.CreateDirectory(Path.GetDirectoryName(full)!);
            File.WriteAllText(full, text);
            return rel;
        }

        // ① 形态识别：扩展名 + 内容嗅探（六类特型 + 未知兜底 text/T0）
        W("a.json", "{\"kind\": \"nf-domain-spec/1\"}\n");
        W("b.json", "{\"schema\": \"nf-combo/1\"}\n");
        W("c.json", "{\"$schema\": \"https://json-schema.org/draft/2020-12/schema\"}\n");
        W("d.json", "{\"kind\": \"nf-performance/1\"}\n");
        W("e.json", "{\"kind\": \"nf-quant-metrics/1\"}\n");
        W("f.json", "{\"kind\": \"nf-system-card/1\"}\n");
        W("g.unknown", "x\n");
        var detected = new[]
        {
            OutputForms.Detect(root, "a.json"), OutputForms.Detect(root, "b.json"),
            OutputForms.Detect(root, "c.json"), OutputForms.Detect(root, "d.json"),
            OutputForms.Detect(root, "e.json"), OutputForms.Detect(root, "f.json"),
        };
        checks.Add(new Check("产出形态·识别（domain-spec / combo-cert / json-schema / performance / quant / system-card）",
            string.Join(",", detected.Select(d => d.Form))
            == "domain-spec,combo-cert,json-schema,performance-report,quant-metrics,system-card"
            && OutputForms.Detect(root, "g.unknown") == ("text", "T0"),
            "识别=" + string.Join(",", detected.Select(d => d.Form))));

        // ② JSON 重复键（嵌套对象各自查重）+ 正常 JSON 零问题
        var dup = W("dup.json", "{\"a\": 1, \"b\": {\"k\": 1, \"k\": 2}, \"a\": 3}\n");
        var dupIssues = OutputForms.Check(root, dup, "json");
        W("ok.json", "{\"a\": 1}\n");
        checks.Add(new Check("产出形态·JSON 重复键（含嵌套各自查重 · 正常件零问题）",
            dupIssues.Count == 2 && dupIssues[0] == "JSON 重复键：a" && dupIssues[1] == "JSON 重复键：k"
            && OutputForms.Check(root, "ok.json", "json").Count == 0,
            string.Join(" | ", dupIssues)));

        // ③ CSV：行长不符 / 表头重名 / 空表
        W("bad.csv", "a,b,c\n1,2\n");
        W("duphead.csv", "a,a\n1,2\n");
        W("empty.csv", "\n");
        var csvIssues = OutputForms.Check(root, "bad.csv", "csv");
        checks.Add(new Check("产出形态·CSV（行长≠表头 · 表头重名 · 空表）",
            csvIssues.Count == 1 && csvIssues[0].Contains("字段数 2 ≠ 表头 3")
            && OutputForms.Check(root, "duphead.csv", "csv").Any(i => i.Contains("表头有重名列"))
            && OutputForms.Check(root, "empty.csv", "csv").Any(i => i == "空表"),
            string.Join(" | ", csvIssues)));

        // ④ XML/GraphML：**DTD 守卫必须触发**（钉住一处真缺陷：首版正则漏了 `!` → 守卫整条不生效）
        W("dtd.xml", "<?xml version=\"1.0\"?>\n<!DOCTYPE r [<!ENTITY x \"y\">]>\n<r>&x;</r>\n");
        W("dangling.graphml", "<?xml version=\"1.0\"?>\n<graphml xmlns=\"http://graphml.graphdrawing.org/xmlns\">\n"
                              + "  <graph><node id=\"a\"/><edge source=\"a\" target=\"幽灵\"/></graph>\n</graphml>\n");
        checks.Add(new Check("产出形态·XML/GraphML（DTD 守卫真的在跑 · 悬空边被抓）",
            OutputForms.Check(root, "dtd.xml", "xml").Any(i => i.Contains("含 DTD/ENTITY 声明"))
            && OutputForms.Check(root, "dtd.xml", "svg").Any(i => i.Contains("含 DTD/ENTITY 声明"))
            && OutputForms.Check(root, "dangling.graphml", "graphml").Any(i => i.Contains("边端点悬空：target=幽灵")),
            string.Join(" | ", OutputForms.Check(root, "dtd.xml", "xml"))));

        // ⑤ YAML：**Tab 缩进必须被抓**（第二处真缺陷：首版查的是"lstrip 后首字符"，那永远不是空白）
        W("tab.yaml", "a:\n\tb: 1\n");
        W("nomap.yaml", "a: 1\n散行\n");
        checks.Add(new Check("产出形态·YAML（Tab 缩进真的被查 · 非映射行被抓）",
            OutputForms.Check(root, "tab.yaml", "yaml").Any(i => i.Contains("Tab 缩进"))
            && OutputForms.Check(root, "nomap.yaml", "yaml").Any(i => i.Contains("非映射项")),
            string.Join(" | ", OutputForms.Check(root, "tab.yaml", "yaml"))));

        // ⑥ TOML：**明确拒绝，不许返回空表**（空表 = 把"没判"当"判过"）
        W("x.toml", "a = 1\n");
        var toml = OutputForms.Check(root, "x.toml", "toml");
        checks.Add(new Check("产出形态·TOML（BCL 无解析器 → 明确拒绝，不静默放行）",
            toml.Count == 1 && toml[0].Contains("不可判定") && toml[0].Contains("不静默放行"),
            string.Join(" | ", toml)));

        // ⑦ JSON-Schema 子集：类型 / 必填 / 附加属性 / oneOf / 不支持关键字进 unsupported
        var schema = new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["type"] = "object",
            ["required"] = new List<object?> { "id" },
            ["additionalProperties"] = false,
            ["properties"] = new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["id"] = new Dictionary<string, object?>(StringComparer.Ordinal) { ["type"] = "string" },
            },
        };
        var instance = new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["id"] = 7L, ["extra"] = true,
        };
        var unsupported = new List<string>();
        var schemaErrors = JsonSchemaSubset.Check(instance, schema, unsupported: unsupported);
        var withConditional = new Dictionary<string, object?>(schema, StringComparer.Ordinal) { ["if"] = new Dictionary<string, object?>() };
        var condUnsup = new List<string>();
        JsonSchemaSubset.Check(instance, withConditional, unsupported: condUnsup);
        checks.Add(new Check("产出形态·JSON-Schema 子集（类型/多余字段 · 不支持关键字进 unsupported 不静默通过）",
            schemaErrors.Count == 2
            && schemaErrors[0] == "$.id: 类型应为 string，实为 int"
            && schemaErrors[1] == "$: 多余字段 extra（additionalProperties=false）"
            && condUnsup.Any(u => u.StartsWith("if@$", StringComparison.Ordinal)),
            string.Join(" | ", schemaErrors) + " · unsupported=" + string.Join(",", condUnsup)));
    }
}
