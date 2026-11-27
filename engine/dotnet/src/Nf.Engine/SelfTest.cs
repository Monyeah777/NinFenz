using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text;
using System.Text.RegularExpressions;

namespace Nf.Engine;

/// <summary>
/// 负例 / 健壮性自检：证明引擎**会红在该红的地方**（不只是顺路径为绿）。
///
/// 覆盖三组：
/// ① 合成组合负例（临时 fixture 根）：撞号（默认塌陷 vs 严格相干）、深链 fail-closed、未知包、悬空依赖、未桥接事件；
/// ② 仓库产物篡改负例（内存注入）：协议回执记录、透明链链节、组合证书字段；
/// ③ 文件字节篡改负例（临时副本）：馆藏条目改一字节。
/// ④ 一致性契约负例（临时 fixture 根）：公开面泄漏、投影手改、取代链成环 + 干净语料正向对照。
/// ⑤ 签名锚方案分支（临时 fixture 根）：未知方案 / sigstore 必须 FAIL，hmac 缺密钥只许 WARN。
/// ⑥ 敌意输入：JSON 深度容忍度对齐 Python（不自设 64）、MCP 单条坏消息不许杀循环。
/// ⑦ 文档四型：镜像表自洽（清单内每件都有合法归属）+ 缺件不误报。
/// ⑧ 数字保真（整数不许变浮点）+ YAML 子集语义（PyYAML 口径）。
/// ⑧a Python 字符串语义：len() 数码点（不是 UTF-16 单元）、切片不劈开代理对。
/// ⑧b YAML 边界与转义：`.NaN` 不许崩、`\x41` 要还原成 A、子集外构造必须显式 fail-closed。
/// ⑨ IDL 子集校验器：越界关键字 / 未知字段 / 枚举 / 键名模式 / 缺 schema 目录。
/// ⑩ 治理族契约：条件先行排布 / 一致性声明三段与重叠 / 包装声明工具面 / ST 落产物判。
/// ⑪ 治理文档族：接力（未决带判据 + refs）/ 复盘（禁指责 + 根因机制 + 行动项可指派）/ 审计（对象 digest 绑定）。
/// ⑫ 端点契约：`maps_to` 必须指向现存 CLI 子命令或 MCP 工具；幂等语义不许沉默。
/// ⑬ 机读契约族：模块边界签名（漂移即 FAIL、非边界文本不算漂移）与事件背书（无发布方即 FAIL、挂账/跨包只 WARN）。
/// ⑭ 类型积压台账：untyped 缺 note 即 FAIL；在盘台账与实时重算不一致即 FAIL（防"台账当装饰"）。
/// ⑮ I/O 类型面：越词表 / 可证不匹配即 FAIL；键集不一致与未标只 WARN（不该被误判成红）。
/// ⑯ 管线抽象执行：模块缺失 / 依赖落在更后层 = hard FAIL；解析失败与 Python 同向抛异常（不是给判定）。
/// ⑰ 双源知识层：locator 缺件（防纸面源）/ 查询有序 / 幽灵频次 = FAIL；缺键文案按 Python 渲染成 None。
/// ⑱ 知识层可见性与复用面：clearance 秩裁剪（public ⊆ internal ⊆ restricted）；同内容两份即 FAIL。
/// 全部 fixture 只写临时目录，**绝不改动被检仓库**。
/// </summary>
public static partial class SelfTest
{
    public sealed record Check(string Name, bool Passed, string Detail);

    public static IReadOnlyList<Check> Run(string root)
    {
        var checks = new List<Check>();
        var work = Path.Combine(Path.GetTempPath(), "nf-selftest-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(work);
        try
        {
            SyntheticCases(checks, work);
            TamperCases(checks, root, work);
            StrictModeIsSafe(checks, root);
            FuzzCases(checks, root, work);
            ParallelInvariance(checks, root);
            ConformanceCases(checks, work);
            AnchorSchemeCases(checks, work);
            HostileCases(checks, work);
            DocKindCases(checks, work);
            NumberAndYamlCases(checks);
            PythonStringCases(checks);
            YamlBoundaryCases(checks);
            ToolFaceCases(checks, work);
            StValidateCases(checks, work);
            RepoStatsCases(checks, work);
            KnowledgeFrequencyCases(checks, work);
            InteropCases(checks, work);
            McpErrorIdCases(checks, root);
            WorldModelCases(checks, work);
            ImpactCases(checks);
            MarketCases(checks);
            AssetCases(checks, work);
            AssetQualityCases(checks, work);
            SmallFacesCases(checks, work);
            OutputFormsCases(checks, work);
            ConceptClosureCases(checks, work, root);
            MetricsRecomputeCases(checks, root, work);
            OutputGateCases(checks, work, root);
            AuxScannerCases(checks, work, root);
            ComboDomainCases(checks, work, root);
            ModuleLifecycleCases(checks, work, root);
            ProtocolGoldenCases(checks, work, root);
            CoreRegistryCases(checks, work, root);
            DocCompletenessCases(checks, work, root);
            TextHygieneCases(checks, work, root);
            LicenseGateCases(checks, work, root);
            ProseLintCases(checks, work, root);
            AutofixCases(checks, work, root);
            TelemetrySemconvCases(checks, work);
            DriverCases(checks, work, root);
            ExtensionPolicyCases(checks, work, root);
            StructureGateCases(checks, work, root);
            AnchorChecksCases(checks, work, root);
            Safe(checks, "深化面", () => DeepeningGateCases(checks, work, root));
            Safe(checks, "决策层", () => DecisionLayerCases(checks, work, root));
            Safe(checks, "出口面", () => ExitFacesCases(checks, work, root));
            Safe(checks, "回归面", () => RegressionCases(checks, work, root));
            Safe(checks, "构建回路", () => WorkloopCases(checks, work, root));
            Safe(checks, "GEO 出口", () => GeoExportCases(checks, work, root));
            Safe(checks, "FDE 样例", () => FdeSampleCases(checks, work, root));
            Safe(checks, "馆藏回执", () => LibraryReceiptsCases(checks, work, root));
            Safe(checks, "语料身份", () => CorpusStampCases(checks, work, root));
            Safe(checks, "装配面", () => AssembleCases(checks, work, root));
            SchemaLintCases(checks, work);
            GovernanceCases(checks, work);
            GovernanceDocCases(checks, work);
            EndpointCases(checks, work);
            MachineContractCases(checks, work);
            TypeBacklogCases(checks, work);
            IoTypeCases(checks, work);
            PipelineDryrunCases(checks, work);
            KnowledgeCases(checks, work);
            KnowledgeCliFacesCases(checks, work);
        }
        finally
        {
            try { Directory.Delete(work, recursive: true); } catch (IOException) { /* 临时目录清理失败不影响判定（best-effort 显式忽略） */ }
        }
        return NormalizeTempPaths(checks);
    }

    /// <summary>
    /// 输出归一（第一百一十四片）：全部 fixture 都建在系统临时目录下，而临时目录名**每次运行都不同**
    /// （<c>…\Temp\nf-selftest-&lt;guid&gt;\…</c>，另有 <c>nf-market-fix-&lt;guid&gt;</c>）。于是
    /// <c>selftest --json</c> 这个机器面里凡是引用合成树路径的 <c>detail</c> 都会变 ⇒ **逐字节不可复现**，
    /// 与构建期的源码路径问题同源（那边用 <c>PathMap</c> 归一，见 Directory.Build.props）。
    /// 这里把临时根换成固定占位 <c>&lt;tmp&gt;</c>：既保留「是合成树里的哪一支」这条诊断信息，
    /// 又让输出可逐字节比对（实测：改后 `selftest --json` 三次运行 sha256 全同）。
    /// </summary>
    private static List<Check> NormalizeTempPaths(List<Check> checks)
    {
        var temp = Path.GetTempPath().TrimEnd(Path.DirectorySeparatorChar, '/');
        // 三种形态都要替：普通反斜杠、正斜杠、以及**Python 异常串里被转义的双反斜杠**
        // （`str(OSError)` 打出来的文件名是 repr ⇒ `C:\\Users\\…`；只替单反斜杠会漏）。
        var forms = new[]
        {
            temp,
            temp.Replace('\\', '/'),
            temp.Replace("\\", "\\\\"),
        };
        return checks
            .Select(c => new Check(c.Name, c.Passed, forms.Aggregate(c.Detail,
                (acc, f) => acc.Replace(f, "<tmp>", StringComparison.Ordinal))))
            .Select(c => c with { Detail = CollapseTempLeaf(c.Detail) })
            .ToList();
    }

    /// <summary>
    /// 把 <c>&lt;tmp&gt;</c> 之后**那一段每次运行都变的目录**（`nf-selftest-&lt;guid&gt;` /
    /// `nf-market-fix-&lt;guid&gt;`）一并折叠掉——诊断信息保留「合成树里的哪一支」，运行期噪声去掉。
    /// 三种分隔符形态都要覆盖：单反斜杠、双反斜杠（Python 异常串的 repr 形态）、正斜杠。
    /// </summary>
    private static string CollapseTempLeaf(string detail) =>
        Regex.Replace(detail, @"(<tmp>)\\{1,2}[^\\/]+|<tmp>/[^\\/]+", "<tmp>", RegexOptions.None);

    // ---------------------------------------------------------------- ① 合成组合负例

    private static void SyntheticCases(List<Check> checks, string work)
    {
        // 撞号：两包各自声明同一 module id
        var dup = Path.Combine(work, "dup");
        WritePack(dup, "PackA", "P99", new[] { "DUP:M01" },
            ("a.md", "DUP:M01", "P40", Array.Empty<string>(), Array.Empty<string>(), Array.Empty<string>()));
        WritePack(dup, "PackB", "P98", new[] { "DUP:M01" },
            ("b.md", "DUP:M01", "P60", Array.Empty<string>(), Array.Empty<string>(), Array.Empty<string>()));

        var dupDefault = Combinator.Build(dup, new[] { "PackA", "PackB" });
        checks.Add(new Check("撞号·默认模式与 Python 一致（不报错）", dupDefault.Legal,
            "legal=" + dupDefault.Legal));

        var records = ModuleContracts.Community(dup).RecordsByKey;
        var resolvedPack = records.TryGetValue("DUP:M01", out var rec) ? rec.Pack : "(缺失)";
        checks.Add(new Check("撞号·归属塌陷被观察到（跨包静默改写）", resolvedPack != "PackA",
            $"PackA 声明的 DUP:M01 解析到 pack={resolvedPack}"));

        var dupStrict = Combinator.Build(dup, new[] { "PackA", "PackB" }, strictCoherence: true);
        var hasConflicts = dupStrict.Certificate.TryGetValue("coherence_conflicts", out var conflicts)
                           && conflicts is List<object?> list && list.Count > 0;
        checks.Add(new Check("撞号·严格相干模式判非法并列出冲突", !dupStrict.Legal && hasConflicts,
            $"legal={dupStrict.Legal} · conflicts={(hasConflicts ? "有" : "无")}"));

        // 干净语料：严格相干模式**不得**改变证书（只在撞号时才扩展形状），否则这个开关就没法当 CI 开关用
        var clean = Path.Combine(work, "clean-coherence");
        WritePack(clean, "PackC", "P94", new[] { "OK:M01" },
            ("c.md", "OK:M01", "P40", Array.Empty<string>(), Array.Empty<string>(), Array.Empty<string>()));
        var cleanDefault = Combinator.Build(clean, new[] { "PackC" });
        var cleanStrict = Combinator.Build(clean, new[] { "PackC" }, strictCoherence: true);
        var sameBytes = PythonJson.CanonicalizeGraph(cleanDefault.Certificate)
                        == PythonJson.CanonicalizeGraph(cleanStrict.Certificate);
        checks.Add(new Check("干净语料·严格相干模式证书逐字节不变（且合法）",
            sameBytes && cleanDefault.Legal && cleanStrict.Legal,
            $"legal={cleanDefault.Legal}/{cleanStrict.Legal} · 逐字节相同={sameBytes}"));

        // 深链：链深 20，只声明头件 → 闭包补齐 12 轮上限 → fail-closed
        var deep = Path.Combine(work, "deep");
        var chainDocs = new List<(string, string, string, string[], string[], string[])>();
        for (var i = 60; i <= 79; i++)
        {
            var id = $"CH:M{i}";
            var inputs = i < 79 ? new[] { $"CH:M{i + 1}" } : Array.Empty<string>();
            chainDocs.Add(($"c{i}.md", id, "P40", inputs, Array.Empty<string>(), Array.Empty<string>()));
        }
        WritePack(deep, "Chain", "P97", new[] { "CH:M60" }, chainDocs.ToArray());
        var deepResult = Combinator.Build(deep, new[] { "Chain" });
        var deepClosure = (Dictionary<string, object?>)deepResult.Certificate["dependency_closure"]!;
        var dangling = (List<object?>)deepClosure["dangling"]!;
        checks.Add(new Check("深链 20 · fail-closed（判非法且悬空非空）",
            !deepResult.Legal && dangling.Count > 0,
            $"legal={deepResult.Legal} · dangling={dangling.Count} 条 · 模块 {deepResult.Certificate["module_count"]}"));

        // 未知包
        var unknownPack = Combinator.Build(deep, new[] { "NoSuchPack" });
        var unknownList = (List<object?>)unknownPack.Certificate["unknown_packs"]!;
        checks.Add(new Check("未知包 · 判非法且列入 unknown_packs",
            !unknownPack.Legal && unknownList.Contains("NoSuchPack"),
            $"unknown_packs={unknownList.Count} 项"));

        // 悬空依赖
        var danglingRoot = Path.Combine(work, "dangling");
        WritePack(danglingRoot, "PackD", "P96", new[] { "DG:M01" },
            ("d.md", "DG:M01", "P40", new[] { "NOPE:M99" }, Array.Empty<string>(), Array.Empty<string>()));
        var danglingResult = Combinator.Build(danglingRoot, new[] { "PackD" });
        var dangles = (List<object?>)((Dictionary<string, object?>)danglingResult.Certificate["dependency_closure"]!)["dangling"]!;
        checks.Add(new Check("悬空依赖 · 判非法且 dangling 非空",
            !danglingResult.Legal && dangles.Count > 0, $"dangling={dangles.Count} 条"));

        // 未桥接事件
        var unbridgedRoot = Path.Combine(work, "unbridged");
        WritePack(unbridgedRoot, "PackE", "P95", new[] { "EB:M01" },
            ("e.md", "EB:M01", "P40", Array.Empty<string>(), Array.Empty<string>(), new[] { "evt_unbridged_x" }));
        var unbridgedResult = Combinator.Build(unbridgedRoot, new[] { "PackE" });
        var unbridged = (List<object?>)((Dictionary<string, object?>)unbridgedResult.Certificate["event_closure"]!)["unbridged"]!;
        checks.Add(new Check("未桥接事件 · 判非法且 unbridged 非空",
            !unbridgedResult.Legal && unbridged.Count > 0, $"unbridged={unbridged.Count} 项"));
    }

    // ---------------------------------------------------------------- ② / ③ 篡改负例

    private static void TamperCases(List<Check> checks, string root, string work)
    {
        // ②a 协议回执：改记录里的 digest
        var receiptsDoc = JsonNode.Parse(File.ReadAllBytes(Path.Combine(root, "protocol/RECEIPTS.json")))!;
        receiptsDoc["entries"]![0]!["digest"] = new string('f', 64);
        using (var mutated = JsonIo.Parse(receiptsDoc.ToJsonString()))
        {
            var result = Receipts.VerifyProtocolReceipts(root, mutated);
            checks.Add(new Check("篡改·协议回执记录摘要 → 必须报红",
                !result.Ok && result.Issues.Any(i => i.Contains("条目摘要不一致", StringComparison.Ordinal)),
                $"{result.Issues.Count} 条问题"));
        }

        // ②b 透明链：改一个链节的 chain 值
        var chainDoc = JsonNode.Parse(File.ReadAllBytes(Path.Combine(root, "protocol/generated/receipt_chain.json")))!;
        chainDoc["links"]![0]!["chain"] = new string('a', 64);
        using (var mutatedChain = JsonIo.Parse(chainDoc.ToJsonString()))
        using (var receipts = JsonIo.ReadFile(Path.Combine(root, "protocol/RECEIPTS.json")))
        {
            var result = Receipts.VerifyTransparencyChain(root, mutatedChain, receipts);
            checks.Add(new Check("篡改·透明链链节 → 必须报红",
                !result.Ok && result.Issues.Any(i => i.Contains("chain 不一致", StringComparison.Ordinal)),
                $"{result.Issues.Count} 条问题"));
        }

        // ②c 组合证书：改一条证书的 modules
        var certDoc = JsonNode.Parse(File.ReadAllBytes(Path.Combine(root, "protocol/combo_certificates.json")))!;
        certDoc["certificates"]![0]!["modules"] = new JsonArray("SYNTH:FAKE");
        using (var mutatedCerts = JsonIo.Parse(certDoc.ToJsonString()))
        {
            var rows = CertificateVerifier.VerifyAll(root, mutatedCerts);
            var bad = rows.Count(r => r.Issues.Count > 0);
            checks.Add(new Check("篡改·组合证书字段 → 必须报红",
                bad > 0 && rows.Any(r => r.Issues.Any(i => i.Contains("字段不一致：modules", StringComparison.Ordinal))),
                $"{bad}/{rows.Count} 条证书报红"));
        }

        // ③ 文件字节篡改：馆藏副本改一字节
        var libRoot = Path.Combine(work, "libcopy");
        Directory.CreateDirectory(Path.Combine(libRoot, "library"));
        foreach (var file in Directory.GetFiles(Path.Combine(root, "library")))
        {
            File.Copy(file, Path.Combine(libRoot, "library", Path.GetFileName(file)), overwrite: true);
        }
        var target = Path.Combine(libRoot, "library", "NF-1.md");
        if (File.Exists(target))
        {
            File.AppendAllText(target, "\n<!-- tampered -->\n");
            var result = Receipts.VerifyLibraryReceipts(libRoot);
            checks.Add(new Check("篡改·馆藏条目文件字节 → 必须报红（真源口径：根不一致 + 条目内容已变）",
                !result.Ok && result.Issues.Any(i => i.Contains("条目内容已变", StringComparison.Ordinal))
                && result.Issues.Any(i => i.Contains("根不一致：记录=", StringComparison.Ordinal)),
                $"{result.Issues.Count} 条问题：{string.Join(" | ", result.Issues).Substring(0, Math.Min(120, string.Join(" | ", result.Issues).Length))}"));
        }
        else
        {
            checks.Add(new Check("篡改·馆藏条目文件字节 → 必须报红", false, "找不到 library/NF-1.md，用例未执行"));
        }
    }

    // ---------------------------------------------------------------- fixture 写入

    /// <summary>严格相干模式在**干净语料**上必须与默认模式逐字节一致（否则不能作为 CI 开关使用）。</summary>
    private static void StrictModeIsSafe(List<Check> checks, string root)
    {
        using var doc = JsonIo.ReadFile(Path.Combine(root, "protocol/combo_certificates.json"));
        var mismatched = 0;
        var total = 0;
        foreach (var cert in doc.RootElement.GetProperty("certificates").EnumerateArray())
        {
            var packs = cert.GetProperty("packs").EnumerateArray().Select(x => x.GetString()!).ToList();
            var extra = cert.GetProperty("extra_modules").EnumerateArray().Select(x => x.GetString()!).ToList();
            var relaxed = Combinator.Build(root, packs, extra);
            var strict = Combinator.Build(root, packs, extra, strictCoherence: true);
            total++;
            if (PythonJson.CanonicalizeGraph(relaxed.Certificate) != PythonJson.CanonicalizeGraph(strict.Certificate))
            {
                mismatched++;
            }
        }
        checks.Add(new Check("严格相干模式在干净语料上与默认模式逐字节一致",
            mismatched == 0,
            $"{total} 条证书 · 不一致 {mismatched}"));
    }

    // ---------------------------------------------------------------- ④ 失败卫生（破坏输入）

    /// <summary>
    /// 破坏输入自检：损坏的输入**要么受控失败、要么与 Python 等价**，
    /// 绝不允许"静默改变判定却自称通过"。每个用例在独立临时根上构造，不触碰被检仓库。
    /// </summary>
    private static void FuzzCases(List<Check> checks, string root, string work)
    {
        // ④a 破坏 JSON：组合证书 / 断言表 / 协议回执 / 透明链
        var badJson = Path.Combine(work, "badjson");
        Directory.CreateDirectory(Path.Combine(badJson, "protocol", "generated"));
        File.WriteAllText(Path.Combine(badJson, "protocol", "combo_certificates.json"), "{\"certificates\": [ {\"packs\"");
        File.WriteAllText(Path.Combine(badJson, "protocol", "assertions.json"), "");
        File.WriteAllText(Path.Combine(badJson, "protocol", "RECEIPTS.json"), "{\"root\": \"x\"");
        File.WriteAllText(Path.Combine(badJson, "protocol", "generated", "receipt_chain.json"), "not json at all");

        checks.Add(Guarded("破坏输入·损坏 JSON → 受控失败（不许静默通过）", () =>
        {
            var controlled = 0;
            if (Controlled(() => CertificateVerifier.VerifyAll(badJson).All(r => r.Issues.Count == 0))) controlled++;
            if (Controlled(() => Assertions.Run(badJson).Issues.Count > 0)) controlled++;
            if (Controlled(() => !Receipts.VerifyProtocolReceipts(badJson).Ok)) controlled++;
            if (Controlled(() => !Receipts.VerifyTransparencyChain(badJson).Ok)) controlled++;
            return (controlled == 4, $"四项中受控失败 {controlled}/4");
        }));

        // ④b 截断 protocol.yaml：与 Python 等价的 fail-open（该包贡献 0 模块，组合仍判合法）
        //     实测（2026-09-26）：Python 同一破坏根得 module_count=0 / legal=True / digest f43f92dd…
        var truncated = Path.Combine(work, "truncated");
        WritePack(truncated, "FuzzPackA", "P90", new[] { "FZ:M01" },
            ("a.md", "FZ:M01", "P40", Array.Empty<string>(), Array.Empty<string>(), Array.Empty<string>()));
        WritePack(truncated, "FuzzPackB", "P91", new[] { "FZ:M02" },
            ("b.md", "FZ:M02", "P60", Array.Empty<string>(), Array.Empty<string>(), Array.Empty<string>()));
        foreach (var pack in new[] { "FuzzPackA", "FuzzPackB" })
        {
            var path = Path.Combine(truncated, "community", pack, "protocol.yaml");
            var text = File.ReadAllText(path);
            File.WriteAllText(path, text[..Math.Min(60, text.Length)]);
        }
        checks.Add(Guarded("破坏输入·截断 protocol.yaml → fail-open 且两次同值（与 Python 等价）", () =>
        {
            var first = Combinator.Build(truncated, new[] { "FuzzPackA", "FuzzPackB" });
            var second = Combinator.Build(truncated, new[] { "FuzzPackA", "FuzzPackB" });
            var modules = (List<object?>)first.Certificate["modules"]!;
            var stable = first.Digest == second.Digest;
            return (modules.Count == 0 && first.Legal && stable,
                $"模块={modules.Count} · legal={first.Legal} · 摘要稳定={stable}");
        }));

        // ④c 未闭合 machine_contract 围栏 → 契约取不到 → module_missing_contract（fail-closed）
        var brokenFence = Path.Combine(work, "brokenfence");
        WritePack(brokenFence, "FuzzPackC", "P92", new[] { "FZ:M03" },
            ("c.md", "FZ:M03", "P40", Array.Empty<string>(), Array.Empty<string>(), Array.Empty<string>()));
        File.WriteAllText(Path.Combine(brokenFence, "community", "FuzzPackC", "modules", "c.md"),
            "```yaml\nmachine_contract:\n  id: FZ:M03\n");   // 围栏未闭合
        checks.Add(Guarded("破坏输入·未闭合围栏 → module_missing_contract（fail-closed）", () =>
        {
            var result = Combinator.Build(brokenFence, new[] { "FuzzPackC" });
            var missing = (List<object?>)result.Certificate["module_missing_contract"]!;
            return (missing.Count > 0 && !result.Legal, $"missing_contract={missing.Count} · legal={result.Legal}");
        }));

        // ④d 空根目录 → 空画像，不崩
        var emptyRoot = Path.Combine(work, "emptyroot");
        Directory.CreateDirectory(emptyRoot);
        checks.Add(Guarded("破坏输入·空根目录 → 空画像且不崩", () =>
        {
            var profiles = PackProfiles.Build(emptyRoot);
            var result = Combinator.Build(emptyRoot, Array.Empty<string>());
            return (profiles.Count == 0 && result.Legal, $"画像={profiles.Count} · legal={result.Legal}");
        }));

        // ④e 真源未被污染
        checks.Add(Guarded("破坏输入·被检仓库未被污染（真源仍全绿）", () =>
        {
            var receipts = Receipts.VerifyProtocolReceipts(root);
            var decisions = Decisions.Verify(root);
            return (receipts.Ok && decisions.Issues.Count == 0 && decisions.Projection.Count == 0,
                $"回执 {receipts.Count} 条 · 决策问题 {decisions.Issues.Count}");
        }));
    }

    /// <summary>受控 = 抛出托管异常，或返回明确的失败判定；静默成功（返回 true 且无异常）不算受控。</summary>
    private static bool Controlled(Func<bool> probe)
    {
        try
        {
            return !probe();
        }
        catch (Exception)
        {
            return true;
        }
    }

    /// <summary>并行/串行不变性：广度是引擎里唯一的并行路径，两种执行方式必须产出同一统计。</summary>
    private static void ParallelInvariance(List<Check> checks, string root)
    {
        checks.Add(Guarded("并行/串行不变性·广度统计逐字节一致", () =>
        {
            var parallel = PythonJson.CanonicalizeGraph(
                Breadth.RunSelfContained(root, parallel: true, triples: 60, quads: 30, quints: 20, sexts: 10));
            var serial = PythonJson.CanonicalizeGraph(
                Breadth.RunSelfContained(root, parallel: false, triples: 60, quads: 30, quints: 20, sexts: 10));
            return (parallel == serial,
                $"并行与串行统计一致={parallel == serial} · 输出 {parallel.Length} 字节");
        }));
    }

    // ------------------------------------------------- ④ 一致性契约负例（含正向对照）

    /// <summary>
    /// 已移植的一致性契约要「该红的必须红」。三条负例各打一个不同的判据面（泄漏 / 投影 /
    /// 取代链），另加一条**正向对照**——否则「一律判红」也能骗过负例自检。
    /// </summary>
    private static void ConformanceCases(List<Check> checks, string work)
    {
        var leak = Path.Combine(work, "conf-public");
        WriteFile(leak, "desktop/tests/fixtures/external/leak.md", "见 C:\\Users\\某人\\私有件.md\n");
        checks.Add(Guarded("一致性契约·公开面泄漏绝对路径 → 判 FAIL", () =>
        {
            var (ok, detail, _) = Conformance.RunOne("public-surface", leak);
            return (!ok && detail.Contains("含绝对路径", StringComparison.Ordinal), detail);
        }));

        var drift = Path.Combine(work, "conf-patterns");
        WriteFile(drift, "src/示例.cs", "// 占位（让 applies_to 可证，使首条问题落在投影上）\n");
        WriteFile(drift, "patterns/alpha/PATTERN.md", PatternDoc("alpha"));
        WriteFile(drift, "patterns/INDEX.md",
            "<!-- BEGIN GENERATED: patterns-index -->\n手改的表\n<!-- END GENERATED: patterns-index -->\n");
        checks.Add(Guarded("一致性契约·实践包投影被手改 → 判 FAIL", () =>
        {
            var (ok, detail, _) = Conformance.RunOne("patterns", drift);
            return (!ok && detail.Contains("不一致", StringComparison.Ordinal), detail);
        }));

        var cycle = Path.Combine(work, "conf-rfc");
        WriteFile(cycle, "protocol/rfc_index.json", string.Join("\n", new[]
        {
            "{",
            "  \"status_vocabulary\": [\"Active\", \"Superseded\"],",
            "  \"docs\": [",
            "    {\"rfc\": \"NF-0001\", \"path\": \"a.md\", \"category\": \"Standards Track\"},",
            "    {\"rfc\": \"NF-0002\", \"path\": \"b.md\", \"category\": \"Standards Track\"}",
            "  ]",
            "}",
        }) + "\n");
        WriteFile(cycle, "a.md", RfcDoc("NF-0001", "NF-0002"));
        WriteFile(cycle, "b.md", RfcDoc("NF-0002", "NF-0001"));
        checks.Add(Guarded("一致性契约·取代链成环 → 判 FAIL", () =>
        {
            var (ok, detail, _) = Conformance.RunOne("rfc-heads", cycle);
            return (!ok && detail.Contains("成环", StringComparison.Ordinal), detail);
        }));

        var clean = Path.Combine(work, "conf-clean");
        WriteFile(clean, "src/示例.cs", "// 占位\n");
        WriteFile(clean, "patterns/alpha/PATTERN.md", PatternDoc("alpha"));
        WriteFile(clean, "patterns/INDEX.md", Patterns.RenderIndex(clean));
        WriteFile(clean, "protocol/rfc_index.json", string.Join("\n", new[]
        {
            "{",
            "  \"status_vocabulary\": [\"Active\"],",
            "  \"docs\": [",
            "    {\"rfc\": \"NF-0001\", \"path\": \"a.md\", \"category\": \"Standards Track\"}",
            "  ]",
            "}",
        }) + "\n");
        WriteFile(clean, "a.md", RfcDoc("NF-0001", "—"));
        WriteFile(clean, "desktop/tests/fixtures/external/ok.md", "# 干净产物\n");
        checks.Add(Guarded("一致性契约·干净语料三面全绿（正向对照）", () =>
        {
            var rows = new[] { "patterns", "rfc-heads", "public-surface" }
                .Select(id => (Id: id, Row: Conformance.RunOne(id, clean))).ToList();
            var bad = rows.Where(r => !r.Row.Ok).Select(r => r.Id + "：" + r.Row.Detail).ToList();
            return (bad.Count == 0, bad.Count == 0
                ? "patterns / rfc-heads / public-surface 三面均判 PASS"
                : string.Join("; ", bad));
        }));
    }

    // --------------------------------------------- ⑤ 签名锚方案：fail-closed 的回归钉

    /// <summary>
    /// 差分模糊发现过的真 bug：**未知锚方案曾被记成 WARN**（fail-open），而 Python 侧判 FAIL。
    /// 这里钉住三个分支——未知方案 / sigstore → **FAIL**；hmac 缺密钥 → **只在 WARN**（不许误伤成 FAIL）。
    /// </summary>
    private static void AnchorSchemeCases(List<Check> checks, string work)
    {
        var anchor = Path.Combine(work, "anchor");
        WriteFile(anchor, "library/NF-9.md", AnchorDoc(new string('0', 64), "rsa-sig"));
        // attestation 先落真值：摘要剔除 attestation/anchor_* 行，故与方案无关，可复用
        var digest = Receipts.LibraryEntryDigest(anchor, "library/NF-9.md");

        checks.Add(Guarded("锚方案·未知方案 → 判 FAIL（缺验证器不得静默通过）", () =>
        {
            WriteFile(anchor, "library/NF-9.md", AnchorDoc(digest, "rsa-sig"));
            var issues = Library.Verify(anchor).Issues;
            var hit = issues.FirstOrDefault(i => i.Contains("未知锚方案：rsa-sig", StringComparison.Ordinal));
            return (hit is not null, hit ?? "未报「未知锚方案」（fail-open？）");
        }));

        checks.Add(Guarded("锚方案·sigstore → 判 FAIL（需外部验证器，不判通过）", () =>
        {
            WriteFile(anchor, "library/NF-9.md", AnchorDoc(digest, "sigstore-keyless"));
            var issues = Library.Verify(anchor).Issues;
            var hit = issues.FirstOrDefault(i => i.Contains("sigstore 锚需外部验证器", StringComparison.Ordinal));
            return (hit is not null, hit ?? "未报 sigstore 不可校验");
        }));

        checks.Add(Guarded("锚方案·hmac 缺密钥 → 只记 WARN（不误判 FAIL）", () =>
        {
            WriteFile(anchor, "library/NF-9.md", AnchorDoc(digest, "hmac-sha256"));
            var result = Library.Verify(anchor);
            var warned = result.Warns.Any(w => w.Contains("未提供密钥", StringComparison.Ordinal));
            var failed = result.Issues.Any(i => i.Contains("签名锚校验失败", StringComparison.Ordinal));
            return (warned && !failed, $"WARN={warned} · FAIL={failed}");
        }));
    }

    private static string AnchorDoc(string attestation, string scheme) => string.Join("\n", new[]
    {
        "---", "id: NF-9", "type: 锚方案用例", "title: 锚方案分支回归", "status: active",
        $"attestation: {attestation}", "attested_at: 2026-09-26", $"anchor_scheme: {scheme}",
        "---", "", "正文。", "",
    });

    // ------------------------------------------------------------ ⑥ 敌意输入

    /// <summary>
    /// 两条回归钉，都来自敌意输入探针的实测：
    /// ① JSON 深度容忍度**对齐 Python**（CPython 到 ~995 层才 RecursionError；引擎原自设 64，
    ///    会在 65 层就单方面判死合法输入）；
    /// ② MCP 循环**单条坏消息不许杀会话**（同 core/mcp_runtime.py：解析失败 → -32700 且继续，
    ///    单条异常 → -32603 且继续）。
    /// </summary>
    private static void HostileCases(List<Check> checks, string work)
    {
        checks.Add(Guarded("敌意输入·JSON 深度 200 可读（对齐 Python，不自设 64）", () =>
        {
            var deep = new string('[', 200) + new string(']', 200);
            using var doc = JsonIo.Parse(deep);
            return (doc.RootElement.GetArrayLength() == 1, $"深度 200 解析成功（MaxDepth={JsonIo.MaxDepth}）");
        }));

        checks.Add(Guarded("敌意输入·JSON 深度超上限仍 fail-closed", () =>
        {
            var deeper = new string('[', JsonIo.MaxDepth + 50) + new string(']', JsonIo.MaxDepth + 50);
            try
            {
                using var doc = JsonIo.Parse(deeper);
                return (false, "超上限竟然解析成功（上限失效）");
            }
            catch (JsonException)
            {
                return (true, $"深度 {JsonIo.MaxDepth + 50} → JsonException（受控）");
            }
        }));

        var mcpRoot = Path.Combine(work, "hostile-mcp");
        (Directory.CreateDirectory(Path.Combine(mcpRoot, "protocol"))).Create();
        checks.Add(Guarded("敌意输入·MCP 单条坏消息不杀循环（坏 JSON / 工具异常后仍应答）", () =>
        {
            var input = new StringReader(string.Join("\n", new[]
            {
                "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\",\"params\":{}}",
                "{这不是 JSON",
                "{\"jsonrpc\":\"2.0\",\"id\":3,\"method\":\"tools/call\",\"params\":{\"name\":\"spec_list\",\"arguments\":{}}}",
                "{\"jsonrpc\":\"2.0\",\"id\":4,\"method\":\"ping\"}",
            }) + "\n");
            var output = new StringWriter();
            var code = McpServer.ServeStdio(mcpRoot, input, output);
            var parsed = output.ToString().Split('\n', StringSplitOptions.RemoveEmptyEntries)
                .Select(line => JsonIo.Parse(line)).ToList();
            var pingAnswered = parsed.Any(p =>
                p.RootElement.TryGetProperty("id", out var id) && id.ValueKind == JsonValueKind.Number
                && id.GetInt32() == 4 && p.RootElement.TryGetProperty("result", out _));
            var internalError = parsed.Any(p =>
                p.RootElement.TryGetProperty("error", out var e)
                && e.GetProperty("code").GetInt32() == -32603);
            var detail = $"exit={code} · 响应 {parsed.Count} 条 · 末条 ping 有答={pingAnswered} · 工具异常转 -32603={internalError}";
            return (code == 0 && pingAnswered && internalError, detail);
        }));

        var outsidePipelines = Path.Combine(work, "outside-pipelines", "pipelines");
        Directory.CreateDirectory(outsidePipelines);
        var outsidePipeline = Path.Combine(outsidePipelines, "secret.md");
        File.WriteAllText(outsidePipeline, "# 仓外金丝雀\n不得读取。\n");
        checks.Add(Guarded("敌意输入·.NET MCP 路径工具拒绝绝对路径越界", () =>
        {
            var pipelineArg = outsidePipeline.Replace('\\', '/');
            using var pipelineDoc = JsonIo.Parse(JsonSerializer.Serialize(new
            {
                jsonrpc = "2.0", id = 601, method = "tools/call",
                @params = new { name = "pipeline_read", arguments = new { pipeline = pipelineArg } },
            }));
            var pipelineResp = McpServer.Handle(mcpRoot, pipelineDoc.RootElement);
            var pipelineCode = (pipelineResp?["error"] as Dictionary<string, object?>)?["code"] as int?;

            using var stDoc = JsonIo.Parse(JsonSerializer.Serialize(new
            {
                jsonrpc = "2.0", id = 602, method = "tools/call",
                @params = new { name = "nf_st_validate", arguments = new { path = pipelineArg } },
            }));
            var stResp = McpServer.Handle(mcpRoot, stDoc.RootElement);
            var stCode = (stResp?["error"] as Dictionary<string, object?>)?["code"] as int?;

            using var adsDoc = JsonIo.Parse(JsonSerializer.Serialize(new
            {
                jsonrpc = "2.0", id = 603, method = "tools/call",
                @params = new { name = "nf_st_validate",
                    arguments = new { path = "docs/examples/card.json:hidden" } },
            }));
            var adsResp = McpServer.Handle(mcpRoot, adsDoc.RootElement);
            var adsCode = (adsResp?["error"] as Dictionary<string, object?>)?["code"] as int?;
            return (pipelineCode == -32602 && stCode == -32602 && adsCode == -32602,
                    $"pipeline_read={pipelineCode} · nf_st_validate={stCode} · ADS={adsCode}"
                    + "（均须 -32602）");
        }));

        checks.Add(Guarded("敌意输入·.NET 批准对象拒绝路径逃逸", () =>
        {
            try
            {
                Approval.SubjectDigest(mcpRoot, "../secret.md");
                return (false, "越界 subject 未被拒绝");
            }
            catch (ArgumentException)
            {
                return (true, "../secret.md → ArgumentException");
            }
        }));
    }
}
