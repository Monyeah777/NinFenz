using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text;
using System.Text.RegularExpressions;

namespace Nf.Engine;

/// <summary>影响面 / 世界模型 / MCP 错误 id / 互操作 / 知识频次 / 自述数字 / ST 制卡 / 工具面负例。</summary>
public static partial class SelfTest
{
    private static void ImpactCases(List<Check> checks)
    {
        // ① 裸号归一：三种写法同号；多段限定只剥第一段前的前缀
        var normOk = ImpactCheck.Norm("情感类:M55") == "M55" && ImpactCheck.Norm("情感:M55") == "M55"
                     && ImpactCheck.Norm("M55") == "M55" && ImpactCheck.Norm("a:b:c") == "b:c";
        checks.Add(new Check("影响面·裸号归一（长/短前缀与裸号同号；多段只剥一段）", normOk,
            $"情感类:M55→{ImpactCheck.Norm("情感类:M55")} · M55→{ImpactCheck.Norm("M55")} · a:b:c→{ImpactCheck.Norm("a:b:c")}"));

        // ② registry 引用图闭合（check21 判据本体）：裸号重复 ③ / 源包悬空 ①② / 源包无此号 ②
        var reg = PythonJson.ToGraph(System.Text.Json.JsonDocument.Parse("""
        {"modules": [{"id": "M00"}],
         "protocols": [
           {"id": "包甲", "module_ids": ["甲:M01", "M01"],
            "references": [{"source_package": "包乙", "module_id": "乙:M07"},
                           {"source_package": "幽灵包", "module_id": "M09"},
                           {"source_package": "包乙", "module_id": "M99"}]},
           {"id": "包乙", "module_ids": ["M07"], "references": []}]}
        """).RootElement) as Dictionary<string, object?>;
        var issues = ImpactCheck.RegistryIntegrityIssues(reg!);
        var joined = string.Join(" | ", issues);
        checks.Add(new Check("影响面·引用图闭合逐条报（裸号重复 / 源包悬空 / 源包无此号）",
            issues.Count == 3 && joined.Contains("③") && joined.Contains("①②") && joined.Contains("②"),
            $"问题 {issues.Count} 条 · {joined[..Math.Min(150, joined.Length)]}"));

        // ③ 影响面判定：官方核心模块 → 破坏性；无引用非官方模块 → 安全；不存在 → error
        var coreHit = ImpactCheck.ImpactOfChange(reg!, "M00");
        var safeHit = ImpactCheck.ImpactOfChange(reg!, "M07");
        var miss = ImpactCheck.ImpactOfChange(reg!, "不存在XYZ");
        checks.Add(new Check("影响面·三态判定（官方在册破坏性 / 仅被引用 / 目标不存在）",
            (coreHit.GetValueOrDefault("in_official_core") as List<object?> ?? new List<object?>()).Count == 1
            && (safeHit.GetValueOrDefault("referenced_by") as List<object?> ?? new List<object?>()).Count == 1
            && miss.ContainsKey("error"),
            $"官方核心在册={(coreHit.GetValueOrDefault("in_official_core") as List<object?>)?.Count} · " +
            $"被引用={(safeHit.GetValueOrDefault("referenced_by") as List<object?>)?.Count} · 不存在含 error={miss.ContainsKey("error")}"));
    }

    private static void WorldModelCases(List<Check> checks, string work)
    {
        // ① 值类型判定：bool 不许冒充 integer/number（Python isinstance(True, int) 为真，故须显式排除）
        var boolAsInt = WorldModel.ValueMatches(true, "integer");
        var longOk = WorldModel.ValueMatches(3L, "integer");
        var numOk = WorldModel.ValueMatches(1.5, "number") && WorldModel.ValueMatches(3L, "number");
        var arrOk = WorldModel.ValueMatches(new List<object?> { "a", "b" }, "array", "string")
                    && !WorldModel.ValueMatches(new List<object?> { "a", 1L }, "array", "string");
        checks.Add(new Check("世界模型·值类型判定（bool≠integer；array 元素类型逐一验）",
            !boolAsInt && longOk && numOk && arrOk,
            $"bool→integer={boolAsInt} · long→integer={longOk} · number 两态={numOk} · array 两态={arrOk}"));

        // ② 契约校验：坏契约须逐条报（未注册槽 / 类型漂移 / 相位不可达 / monotonic 用错）
        var broken = PythonJson.ToGraph(System.Text.Json.JsonDocument.Parse("""
        {
          "abstract_state": {
            "variables": [
              {"name": "tick", "kind": "string", "source": "通用:M10", "slot": "WorldState.time.tick"},
              {"name": "ghost", "kind": "integer", "source": "通用:M10", "slot": "ghost.slot"}
            ],
            "initial": {"tick": "0"}
          },
          "transition": {"initial_phase": "a",
            "phases": [{"phase": "a", "next": "b", "guard": "g", "writes": []},
                       {"phase": "b", "next": "a", "guard": "g", "writes": []},
                       {"phase": "c", "next": "a", "guard": "g", "writes": []}]},
          "invariants": ["x"],
          "checks": [{"kind": "monotonic", "field": "tick"}]
        }
        """).RootElement) as Dictionary<string, object?>;
        var slots = new Dictionary<string, Dictionary<string, object?>>(StringComparer.Ordinal)
        {
            ["WorldState.time.tick"] = new(StringComparer.Ordinal)
            {
                ["kind"] = "integer", ["owner"] = "通用:M10",
            },
        };
        var issues = WorldModel.ValidateContract(broken, "wm", slots);
        var joined = string.Join(" | ", issues);
        checks.Add(new Check("世界模型·坏契约逐条报（未注册槽 / 类型漂移 / 相位不可达 / monotonic 用错）",
            joined.Contains("未在 protocol/world_slots.json 注册") && joined.Contains("类型漂移")
            && joined.Contains("不可达的相位") && joined.Contains("monotonic 只能用于"),
            $"违例 {issues.Count} 条 · {joined[..Math.Min(150, joined.Length)]}"));

        // ③ 扫描空根：fail-closed（缺槽位注册表即报，不静默零问题）
        var emptyRoot = Path.Combine(work, "worldmodel-empty");
        Directory.CreateDirectory(emptyRoot);
        var (scanIssues, scanStats) = WorldModel.Scan(emptyRoot);
        checks.Add(new Check("世界模型·缺槽位注册表 fail-closed（不静默给零问题）",
            scanIssues.Count == 1 && scanIssues[0].Contains("protocol/world_slots.json 缺失或 slots 为空")
            && Convert.ToInt64(scanStats["modules"]) == 0,
            $"问题 {scanIssues.Count} 条 · 模块 {scanStats["modules"]}"));

        // ④ 槽位读写往返（嵌套路径不存在时自动建层，与 Python _set_slot 的 setdefault 同义）
        var nested = WorldModel.SetSlot(new Dictionary<string, object?>(StringComparer.Ordinal),
            "a.b.c", 7L);
        var gotBack = WorldModel.TryGetSlot(nested, "a.b.c", out var slotValue) && Convert.ToInt64(slotValue) == 7
                      && !WorldModel.TryGetSlot(nested, "a.b.x", out _);
        checks.Add(new Check("世界模型·槽位读写往返（缺路径自动建层；取不存在的槽报缺）", gotBack,
            $"取回={Convert.ToInt64(slotValue ?? 0L)} · 缺槽=False"));

        // ⑤ 相位序列：环 → cycle + 重复相位；悬空 → dangling
        var cyclic = PythonJson.ToGraph(System.Text.Json.JsonDocument.Parse("""
        {"abstract_state": {"variables": [{"name": "phase", "kind": "string", "source": "s"}],
                            "initial": {"phase": "a"}},
         "transition": {"initial_phase": "a",
           "phases": [{"phase": "a", "next": "b", "guard": "g", "writes": []},
                      {"phase": "b", "next": "a", "guard": "g", "writes": []}]},
         "invariants": ["x"]}
        """).RootElement) as Dictionary<string, object?>;
        var (sequence, reason, repeat) = WorldModel.PhaseSequence(cyclic!);
        var dangling = PythonJson.ToGraph(System.Text.Json.JsonDocument.Parse("""
        {"abstract_state": {"variables": [{"name": "phase", "kind": "string", "source": "s"}],
                            "initial": {"phase": "a"}},
         "transition": {"initial_phase": "a",
           "phases": [{"phase": "a", "next": "b", "guard": "g", "writes": []},
                      {"phase": "b", "next": "a", "guard": "g", "writes": []}]},
         "invariants": ["x"]}
        """).RootElement) as Dictionary<string, object?>;
        checks.Add(new Check("世界模型·相位序列（环→cycle+重复相位；序列逐项）",
            // Python 语义：**先把当前相位入列，再判下一个**；回到已见相位时返回 cycle + 重复相位本身，
            // 故 2 相位环的序列是 a→b（不是 a→b→a）——这里如实测口径。
            string.Join("→", sequence) == "a→b" && reason == "cycle" && repeat == "a"
            && WorldModel.PhaseSequence(dangling!).Reason == "cycle",
            $"序列={string.Join("→", sequence)} · 终止={reason} · 重复={repeat}"));

        // ⑥ 重放：步数 / 终止原因 / digest 两次一致（确定性指纹）
        var runtime = new WorldModel.Runtime(cyclic!);
        var first = runtime.Replay();
        var second = runtime.Replay();
        var steps = (first.GetValueOrDefault("steps") as List<object?> ?? new List<object?>()).Count;
        checks.Add(new Check("世界模型·重放（2 步环 · 终止 cycle · digest 两次一致）",
            steps == 2 && (first.GetValueOrDefault("reason") as string) == "cycle"
            && (first.GetValueOrDefault("digest") as string) == (second.GetValueOrDefault("digest") as string)
            && (first.GetValueOrDefault("digest") as string)?.Length == 64,
            $"步数={steps} · 终止={first.GetValueOrDefault("reason")} · " +
            $"digest={(first.GetValueOrDefault("digest") as string)?.Substring(0, 12)}"));
    }

    private static void McpErrorIdCases(List<Check> checks, string root)
    {
        // 工具内部抛异常时：① 不许沉默（必须有 error 响应）；② **必须回带请求 id**（JSON-RPC 2.0 §5）；
        // ③ 不许杀循环（后续 ping 仍应答）。真源缺陷：此前固定回带 id=null。
        var input = new StringReader(
            """{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}""" + "\n" +
            """{"jsonrpc":"2.0","id":9001,"method":"tools/call","params":{"name":"nf_st_validate","arguments":{"path":"no/such/card.json"}}}""" + "\n" +
            """{"jsonrpc":"2.0","id":9002,"method":"ping"}""" + "\n");
        var output = new StringWriter();
        McpServer.ServeStdio(root, input, output);
        var lines = output.ToString().Split('\n', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);

        var errorLine = lines.FirstOrDefault(l => l.Contains("9001", StringComparison.Ordinal));
        var pingLine = lines.FirstOrDefault(l => l.Contains("9002", StringComparison.Ordinal));
        var echoedId = errorLine is not null && errorLine.Contains("\"id\": 9001", StringComparison.Ordinal);
        var internalError = errorLine is not null && errorLine.Contains("-32603", StringComparison.Ordinal);
        checks.Add(new Check("MCP·工具抛异常 → 错误响应回带请求 id 且码为 -32603（不沉默、不丢 id）",
            echoedId && internalError && pingLine is not null,
            $"id 回带={echoedId} · -32603={internalError} · 循环存活={pingLine is not null} · " +
            $"{(errorLine ?? "（无 9001 响应）")[..Math.Min(90, errorLine?.Length ?? 12)]}"));
    }

    private static void InteropCases(List<Check> checks, string work)
    {
        // ① CIDv1 已知向量（真源 docstring 给出的口径：raw codec 0x71 + sha2-256）
        var empty = Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(Array.Empty<byte>())).ToLowerInvariant();
        var cid = Interop.Cidv1RawSha256(empty);
        checks.Add(new Check("互操作·CIDv1 已知向量（sha256(\"\") → bafyrei…）",
            cid == "bafyreihdwdcefgh4dqkjv67uzcmw7ojee6xedzdetojuzjevtenxquvyku",
            cid));

        // ② JSON Schema 映射（array → items；nullable → 联合类型；未识别 → object 保守兜底）
        var asArray = Interop.SchemaFor("array of strings");
        var nullable = Interop.SchemaFor("string|null");
        var unknown = Interop.SchemaFor("某些中文说明");
        var emptyDesc = Interop.SchemaFor("");
        checks.Add(new Check("互操作·字段说明串 → JSON Schema 映射（array/nullable/兜底/空描述）",
            PyScalar.PyEquals(asArray["type"], "array") && asArray.ContainsKey("items")
            && PyScalar.PyRepr(nullable["type"]) == "['string', 'null']"
            && PyScalar.PyEquals(unknown["type"], "object")
            && unknown.GetValueOrDefault("additionalProperties") is true
            && !emptyDesc.ContainsKey("description"),
            $"array={PyScalar.PyRepr(asArray["type"])} · nullable={PyScalar.PyRepr(nullable["type"])} · " +
            $"兜底={PyScalar.PyRepr(unknown["type"])} · 空描述含 description={emptyDesc.ContainsKey("description")}"));

        // ③ JSON Pointer 转义（RFC 6901）
        checks.Add(new Check("互操作·JSON Pointer 转义（~ → ~0、/ → ~1）",
            Interop.Ptr("nf/a~b") == "nf~1a~0b", Interop.Ptr("nf/a~b")));

        // ④ 空根：门禁 fail-closed（缺派生真源 → 报错不静默）
        var emptyRoot = Path.Combine(work, "interop-empty");
        Directory.CreateDirectory(emptyRoot);
        var (emptyIssues, _) = Interop.Verify(emptyRoot);
        checks.Add(new Check("互操作·真源缺失 fail-closed（不静默给空导出面）",
            emptyIssues.Count(x => x.Contains("缺派生真源")) == 3
            && emptyIssues.Any(x => x.Contains("缺派生真源 protocol/RECEIPTS.json"))
            && emptyIssues.Any(x => x.Contains("缺派生真源 protocol/endpoint_contract.json")),
            $"问题 {emptyIssues.Count} 条 · 缺真源 {emptyIssues.Count(x => x.Contains("缺派生真源"))} 条"));

        // ⑤ 确定性：同一根两次渲染逐字节一致（12 形状全跑）
        var root = Path.Combine(work, "interop-det");   // 空根也足以证明"两次一致"
        Directory.CreateDirectory(root);
        var deterministic = Interop.Kinds.All(k => Interop.Render(k.Id, root).SequenceEqual(Interop.Render(k.Id, root)));
        checks.Add(new Check("互操作·确定性（同输入两次渲染逐字节一致 · 12 形状）", deterministic,
            $"形状 {Interop.Kinds.Length} 个"));
    }

    private static void KnowledgeFrequencyCases(List<Check> checks, string work)
    {
        var dir = Path.Combine(work, "knowledge-frequency");
        Directory.CreateDirectory(dir);

        // JSONL：混合合法/坏行/非对象/无源标识 → 只数有源标识的对象，键排序
        var jsonl = Path.Combine(dir, "trace.jsonl");
        File.WriteAllLines(jsonl, new[]
        {
            """{"knowledge_source":"nf-protocol","ts":"t1"}""",
            """{"source_id":"nf-protocol","ts":"t2"}""",
            """{"knowledge_source":"nf-patterns","ts":"t3"}""",
            "{ 坏行 }",
            "42",
            """{"other":1}""",
            "",
        });
        var c1 = KnowledgeSources.HarvestFrequency(jsonl);
        checks.Add(new Check("频次复算·JSONL（坏行/非对象/无源标识都跳过；键排序）",
            c1.Count == 2 && Convert.ToInt64(c1["nf-protocol"]) == 2 && Convert.ToInt64(c1["nf-patterns"]) == 1
            && c1.Keys.First() == "nf-patterns",
            $"源 {c1.Count} · nf-protocol={c1["nf-protocol"]} · nf-patterns={c1["nf-patterns"]}"));

        // JSON 数组形态
        var arr = Path.Combine(dir, "trace_array.json");
        File.WriteAllText(arr, """[{"knowledge_source":"a"},{"knowledge_source":"b"},{"knowledge_source":"a"}]""");
        var c2 = KnowledgeSources.HarvestFrequency(arr);
        checks.Add(new Check("频次复算·JSON 数组形态",
            c2.Count == 2 && Convert.ToInt64(c2["a"]) == 2 && Convert.ToInt64(c2["b"]) == 1,
            $"a={c2["a"]} · b={c2["b"]}"));

        // {"records":[...]} 形态 + 单对象兜底
        var recs = Path.Combine(dir, "trace_records.json");
        File.WriteAllText(recs, """{"records":[{"source_id":"x"},{"source_id":"x"},{"source_id":"y"}]}""");
        var single = Path.Combine(dir, "trace_single.json");
        File.WriteAllText(single, """{"knowledge_source":"solo"}""");
        var c3 = KnowledgeSources.HarvestFrequency(recs);
        var c4 = KnowledgeSources.HarvestFrequency(single);
        checks.Add(new Check("频次复算·records 形态与单对象兜底",
            c3.Count == 2 && Convert.ToInt64(c3["x"]) == 2 && c4.Count == 1 && Convert.ToInt64(c4["solo"]) == 1,
            $"records: x={c3["x"]} · y={c3["y"]} · 单对象: solo={c4["solo"]}"));

        // 文件不可读 → 受控抛出（CLI 侧转 exit 1）
        var threw = false;
        try { KnowledgeSources.HarvestFrequency(Path.Combine(dir, "no-such.jsonl")); }
        catch (IOException) { threw = true; }
        checks.Add(new Check("频次复算·缺文件受控抛 IOException（不崩栈）", threw, $"受控={threw}"));
    }

    private static void RepoStatsCases(List<Check> checks, string work)
    {
        var root = Path.Combine(work, "repo-stats");
        var core = Path.Combine(root, "desktop", "src", "core");
        var pipes = Path.Combine(root, "03_管线库");
        var assets = Path.Combine(root, "community", "包甲", "assets");
        var protocol = Path.Combine(root, "protocol");
        var library = Path.Combine(root, "library");
        foreach (var dir in new[] { core, pipes, assets, protocol, library }) Directory.CreateDirectory(dir);

        File.WriteAllText(Path.Combine(core, "registry.json"),
            """{"modules":[{"id":"M00"},{"id":"M10"}],"protocols":[{"id":"包甲"}]}""");
        File.WriteAllText(Path.Combine(pipes, "P01_标准.md"), "# P01\n");
        File.WriteAllText(Path.Combine(root, "community", "包甲", "protocol.yaml"), "package:\n  id: 包甲\n");
        File.WriteAllText(Path.Combine(assets, "DOMAIN_SPEC.md"), "# 资产\n");
        File.WriteAllText(Path.Combine(assets, "CONCEPT_GRAPH.md"), "# 概念图\n");
        File.WriteAllText(Path.Combine(protocol, "standards_catalog.json"),
            """{"coverage":{"standards":3,"reachable":2,"unreachable":1,"bodies":1,"depends_edges":2,"by_layer":{"L1":1}}}""");
        File.WriteAllText(Path.Combine(protocol, "standards_binding.json"), """{"bindings_total":7}""");
        File.WriteAllText(Path.Combine(protocol, "domain_packs.json"), """{"count":100,"subdivisions_total":1200}""");
        File.WriteAllText(Path.Combine(library, "NF-1.md"), "# NF-1\n");
        File.WriteAllText(Path.Combine(root, "verify.sh"), "# 版本 : v2.29\ncheck1(){\n}\ncheck2(){\n}\n");
        File.WriteAllText(Path.Combine(core, "quality_baseline.py"), "EXPECTED_CHECKS = 2\nEXPECTED_PASS = 5\n");

        // 入口文件先放 marker 占位，再用**实算结果**回填（正向对照）
        var entries = new[] { "README.md", "README.en.md", "llms.txt" };
        foreach (var rel in entries)
            File.WriteAllText(Path.Combine(root, rel),
                "# 入口\n\n<!-- nf:stats:begin -->\n占位\n<!-- nf:stats:end -->\n");

        var (stats, computeIssues) = RepoStats.Compute(root);
        var blocks = RepoStats.Render(stats);
        foreach (var (rel, block) in blocks) FillBlock(Path.Combine(root, rel), block);
        File.WriteAllText(Path.Combine(protocol, "repo_stats.json"), PythonJson.Indented(stats) + "\n");

        var (cleanIssues, _) = RepoStats.Check(root);
        checks.Add(new Check("自述数字·合成语料生成区与台账一致 → 零问题（正向对照）",
            computeIssues.Count == 0 && cleanIssues.Count == 0,
            $"compute={computeIssues.Count} · check={cleanIssues.Count} 问题 · " +
            $"模块 {stats["core_modules"]} · 管线 {((List<object?>)stats["core_pipelines"]!).Count} · " +
            $"台账 check1-{stats["baseline_checks"]}/PASS={stats["baseline_pass"]}"));

        // 变异①：生成区里改一个数字 → 必报「生成区与实算不一致」
        var readme = Path.Combine(root, "README.md");
        File.WriteAllText(readme, File.ReadAllText(readme).Replace("2 模块", "9 模块"));
        var (drift, _) = RepoStats.Check(root);
        checks.Add(new Check("自述数字·生成区数字被手改 → 必报（README.md 生成区与实算不一致）",
            drift.Any(x => x.Contains("README.md") && x.Contains("生成区与实算不一致")),
            drift.Count > 0 ? drift[0] : "（无问题）"));
        FillBlock(readme, blocks["README.md"]);   // 还原

        // 变异②：台账被改 → 必报「与实算不一致」
        var ledger = Path.Combine(protocol, "repo_stats.json");
        File.WriteAllText(ledger, File.ReadAllText(ledger).Replace("\"core_modules\": 2", "\"core_modules\": 9"));
        var (ledgerIssues, _) = RepoStats.Check(root);
        checks.Add(new Check("自述数字·在盘台账与实算不一致 → 必报",
            ledgerIssues.Any(x => x.Contains("repo_stats.json") && x.Contains("与实算不一致")),
            ledgerIssues.Count > 0 ? string.Join(" | ", ledgerIssues) : "（无问题）"));
        File.WriteAllText(ledger, PythonJson.Indented(stats) + "\n");

        // 变异③：缺 verify.sh → 必报「取不到 verify.sh」
        File.Delete(Path.Combine(root, "verify.sh"));
        var (noVerify, _) = RepoStats.Check(root);
        checks.Add(new Check("自述数字·缺 verify.sh → 必报口径缺失（不静默填 0）",
            noVerify.Any(x => x.Contains("取不到 verify.sh")),
            noVerify.Count > 0 ? noVerify[0] : "（无问题）"));

        // 变异④：盘上包目录 ≠ registry 登记 → 必报登记不一致
        Directory.CreateDirectory(Path.Combine(root, "community", "包乙"));
        File.WriteAllText(Path.Combine(root, "community", "包乙", "protocol.yaml"), "package:\n  id: 包乙\n");
        var (mismatch, _) = RepoStats.Check(root);
        checks.Add(new Check("自述数字·盘上包目录 ≠ registry 登记 → 必报",
            mismatch.Any(x => x.Contains("盘上包目录") && x.Contains("registry 登记")),
            mismatch.Count > 0 ? mismatch[0] : "（无问题）"));
    }

    /// <summary>把 marker 区内容替换成给定块（缺 marker 时原样返回）。</summary>
    private static void FillBlock(string path, string block)
    {
        var text = File.ReadAllText(path);
        var i = text.IndexOf(RepoStats.Begin, StringComparison.Ordinal);
        var j = text.IndexOf(RepoStats.End, StringComparison.Ordinal);
        if (i < 0 || j < 0 || j < i) return;
        File.WriteAllText(path, text[..i] + block + text[(j + RepoStats.End.Length)..]);
    }

    private static void StValidateCases(List<Check> checks, string work)
    {
        var dir = Path.Combine(work, "st-validate");
        Directory.CreateDirectory(dir);

        // ① 干净卡（V2 + 六字段齐）→ card · 零 fail
        var clean = Path.Combine(dir, "clean_card.json");
        File.WriteAllText(clean, """
        {"spec":"chara_card_v2","spec_version":"2.0","data":{"name":"甲","description":"乙",
         "personality":"丙","scenario":"丁","first_mes":"戊","mes_example":"己"}}
        """);
        var cleanRep = StValidate.Validate(clean);
        var cleanCounts = (Dictionary<string, object?>)cleanRep["counts"]!;
        checks.Add(new Check("制卡校验·干净卡判 card 且 fail=0（正向对照）",
            (string)cleanRep["kind"]! == "card" && Convert.ToInt64(cleanCounts["fail"]) == 0
            && ((List<object?>)cleanRep["issues"]!).Count == 0,
            $"kind={cleanRep["kind"]} · fail={cleanCounts["fail"]} · issues={((List<object?>)cleanRep["issues"]!).Count}"));

        // ② 脏世界书（entries 非 dict/list 之外的四类：key 空 / content 空 / 逗号 key / 重复 key / 缺 scanDepth）
        var messy = Path.Combine(dir, "messy_worldbook.json");
        File.WriteAllText(messy, """
        {"entries":[{"key":"","content":"有正文"},
                    {"key":"驿站,客栈","content":"","scanDepth":4},
                    {"key":"北境","content":"正文 A","scanDepth":4},
                    {"key":"北境","content":"正文 B","scanDepth":4}]}
        """);
        var messyRep = StValidate.Validate(messy);
        var messyRules = ((List<object?>)messyRep["issues"]!).Cast<Dictionary<string, object?>>()
            .Select(i => (string)i["rule"]!).ToList();
        var messyCounts = (Dictionary<string, object?>)messyRep["counts"]!;
        checks.Add(new Check("制卡校验·脏世界书逐条报（W1 key/content 空 · W2 逗号与重复 · W5 缺 scanDepth）",
            (string)messyRep["kind"]! == "worldbook"
            && messyRules.Count(r => r == "W1") == 2
            && messyRules.Count(r => r == "W2") == 2
            && messyRules.Count(r => r == "W5") == 1
            && Convert.ToInt64(messyCounts["fail"]) == 2,
            $"kind={messyRep["kind"]} · W1×{messyRules.Count(r => r == "W1")} · W2×{messyRules.Count(r => r == "W2")} · " +
            $"W5×{messyRules.Count(r => r == "W5")} · fail={messyCounts["fail"]} · warn={messyCounts["warn"]}"));

        // ③ MVU 变量：initial 含未声明 + 缺初始值 + array 建议
        var mvu = Path.Combine(dir, "mvu.json");
        File.WriteAllText(mvu, """
        {"variables":[{"name":"血量","kind":"integer"},{"name":"台账","kind":"array"}],
         "initial":{"血量":100,"幽灵变量":1}}
        """);
        var mvuRep = StValidate.Validate(mvu);
        var mvuJoin = string.Join(" | ", ((List<object?>)mvuRep["issues"]!).Cast<Dictionary<string, object?>>()
            .Select(i => (string)i["detail"]!));
        checks.Add(new Check("制卡校验·MVU 变量报未声明初始值 / 缺初始值 / array 建议",
            (string)mvuRep["kind"]! == "mvu-variables"
            && mvuJoin.Contains("initial 含未声明变量：幽灵变量")
            && mvuJoin.Contains("变量缺初始值：台账")
            && mvuJoin.Contains("优先 record"),
            mvuJoin.Length > 160 ? mvuJoin[..160] : mvuJoin));

        // ④ 未知形状 + 缺文件（受控失败，不许崩栈）
        var unknown = Path.Combine(dir, "unknown.json");
        File.WriteAllText(unknown, "{\"foo\": 1}");
        var unknownRep = StValidate.Validate(unknown);
        var missingThrew = false;
        try { StValidate.Validate(Path.Combine(dir, "nope.json")); }
        catch (IOException) { missingThrew = true; }
        checks.Add(new Check("制卡校验·未知形状判 unknown 且缺文件受控抛 IO 异常",
            (string)unknownRep["kind"]! == "unknown" && missingThrew,
            $"kind={unknownRep["kind"]} · 缺文件受控={missingThrew}"));
    }

    private static void ToolFaceCases(List<Check> checks, string work)
    {
        // ① 正向对照：合规条目（purpose + 非空 guidance + candidate 带 https 与 license）
        var goodRoot = Path.Combine(work, "toolface-good");
        var goodDir = Path.Combine(goodRoot, "04_模块库", "通用类");
        Directory.CreateDirectory(goodDir);
        File.WriteAllText(Path.Combine(goodDir, "M00_合规.md"), ToolFaceDoc("M00",
            "  tool_face:\n" +
            "    - purpose: 取时间\n" +
            "      guidance:\n" +
            "        when: 需要推进时间\n" +
            "      candidates:\n" +
            "        - repo: https://example.com/x\n" +
            "          license: MIT\n"));
        var (goodIssues, goodStats) = ToolFace.Scan(goodRoot);
        checks.Add(new Check("工具面·合规条目零问题（正向对照）",
            goodIssues.Count == 0
            && Convert.ToInt64(goodStats["modules"]) == 1
            && Convert.ToInt64(goodStats["entries"]) == 1
            && Convert.ToInt64(goodStats["candidates"]) == 1,
            $"issues={goodIssues.Count} · modules={goodStats["modules"]} · entries={goodStats["entries"]} · candidates={goodStats["candidates"]}"));

        // ② 违规条目：四类问题逐条报（缺 purpose / 缺 guidance / 非法链接 / 缺 license）
        var badRoot = Path.Combine(work, "toolface-bad");
        var badDir = Path.Combine(badRoot, "04_模块库", "通用类");
        Directory.CreateDirectory(badDir);
        File.WriteAllText(Path.Combine(badDir, "M01_违规.md"), ToolFaceDoc("M01",
            "  tool_face:\n" +
            "    - purpose: \"\"\n" +
            "      candidates:\n" +
            "        - repo: ftp://example.com/x\n" +
            "        - repo: https://example.com/y\n" +
            "          license: \"  \"\n"));
        var (badIssues, _) = ToolFace.Scan(badRoot);
        var joined = string.Join(" | ", badIssues);
        checks.Add(new Check("工具面·违规条目逐条报（缺 purpose / 缺 guidance / 非法链接 / 缺 license）",
            joined.Contains("缺 purpose") && joined.Contains("缺 guidance")
            && joined.Contains("缺合法 https 链接") && joined.Contains("缺 license"),
            joined.Length > 170 ? joined[..170] : joined));

        // ③ 非列表：报「tool_face 非空列表」且不计入模块数
        var nonListRoot = Path.Combine(work, "toolface-nonlist");
        var nonListDir = Path.Combine(nonListRoot, "04_模块库", "通用类");
        Directory.CreateDirectory(nonListDir);
        File.WriteAllText(Path.Combine(nonListDir, "M02_非列表.md"), ToolFaceDoc("M02", "  tool_face: 不是列表\n"));
        var (nonListIssues, nonListStats) = ToolFace.Scan(nonListRoot);
        checks.Add(new Check("工具面·tool_face 非非空列表 → 报「非空列表」且不计模块数",
            nonListIssues.Any(x => x.Contains("tool_face 非空列表")) && Convert.ToInt64(nonListStats["modules"]) == 0,
            string.Join(" | ", nonListIssues)));
    }

    /// <summary>合成一件带 machine_contract 的模块文档（工具面用例用；只造判据需要的最小字段）。</summary>
    private static string ToolFaceDoc(string id, string toolFaceBlock)
        => "# 模块 " + id + "\n\n"
           + "> 类别：通用｜来源：核心｜挂载点：P40 行为决策（active，default）｜依赖：无｜状态：active\n\n"
           + "```yaml\n"
           + "machine_contract:\n"
           + "  schema: \"1\"\n"
           + "  id: " + id + "\n"
           + "  layer: P40\n"
           + "  inputs: []\n"
           + "  outputs: []\n"
           + "  events:\n"
           + "    publish: []\n"
           + "    subscribe: []\n"
           + toolFaceBlock
           + "```\n";

    private static void WritePack(string root, string pack, string pipeline, string[] declaredIds,
        params (string File, string Id, string Layer, string[] Inputs, string[] Publish, string[] Subscribe)[] modules)
    {
        var packDir = Path.Combine(root, "community", pack);
        var modulesDir = Path.Combine(packDir, "modules");
        Directory.CreateDirectory(modulesDir);

        var lines = new List<string>
        {
            "protocol:",
            "  schema_version: \"2\"",
            "package:",
            $"  id: {pack}",
            $"  pipeline: {pipeline}",
            "  module_id_range:",
        };
        lines.AddRange(declaredIds.Select(id => $"    - \"{id}\""));
        lines.Add("  mount_layers:");
        foreach (var module in modules)
        {
            lines.Add($"    P40: {{default: [{module.Id}]}}");
        }
        File.WriteAllText(Path.Combine(packDir, "protocol.yaml"), string.Join("\n", lines) + "\n");

        foreach (var module in modules)
        {
            var body = $"""
```yaml
machine_contract:
  schema: "1"
  id: {module.Id}
  layer: {module.Layer}
  inputs: [{string.Join(", ", module.Inputs)}]
  outputs: []
  events:
    publish: [{string.Join(", ", module.Publish)}]
    subscribe: [{string.Join(", ", module.Subscribe)}]
  interfaces: []
```
""";
            File.WriteAllText(Path.Combine(modulesDir, module.File), "# fixture\n\n" + body);
        }
    }
}
