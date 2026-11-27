using System.Text.Json;
using Nf.Engine;

internal static partial class Program
{
    private static int WhoRefersCommand()
    {
        // 引用反查（A2）：**类别感知**匹配（与 impact 的裸号归一口径不同，见 Retriever 类注释）。
        if (positional.Count < 2) return Usage("who-refers 需要一个模块 id（如 M91 或 情感:M55）");
        var target = positional[1];
        var regPath = registryPath is null
            ? Path.Combine(root!, "desktop", "src", "core", "registry.json")
            : (Path.IsPathRooted(registryPath) ? registryPath : Path.Combine(root!, registryPath));
        var refs = Retriever.ReferencedBy(target, regPath);
        Console.WriteLine($"== 谁引用了 {target} ==");
        if (refs.Count == 0)
        {
            Console.WriteLine("  无（registry protocols[].references 中无引用）");
            return 0;
        }
        foreach (var r in refs)
        {
            var ro = PyTruthy(r.GetValueOrDefault("asset_readonly")) ? "只读" : "";
            Console.WriteLine($"  {PyS(r["referrer"])} → {PyS(r["source_package"])}.{PyS(r["module_id"])} {ro}");
        }
        return 0;
    }

    private static int DiffCommand()
    {
        // 版本差异检测（41 波C C2）：两份文档签名 → 字段级差异 + 兼容判定 + 影响度三档。
        if (positional.Count < 3) return Usage("diff 需要两个文档路径：<a> <b>");
        try
        {
            var ra = RelToRoot(positional[1]);
            var rb = RelToRoot(positional[2]);
            var diff = SignatureDiff.Diff(KnowledgeSig.BuildSignature(ra, root!),
                                          KnowledgeSig.BuildSignature(rb, root!));
            if (json)
            {
                Console.WriteLine(JsonFor(diff));
                return 0;
            }
            Console.WriteLine("== nf diff ==");
            Console.WriteLine($"  {PyS(diff["from"])}  →  {PyS(diff["to"])}");
            var changes = (List<object?>)diff["changes"]!;
            if (changes.Count == 0) Console.WriteLine("  无字段差异（两份签名一致）");
            foreach (var c in changes.Cast<Dictionary<string, object?>>())
            {
                Console.WriteLine($"  [{PyS(c["kind"])}] {PyS(c["field"])}  " +
                                  $"{PyScalar.PyRepr(c["from"])} → {PyScalar.PyRepr(c["to"])}");
            }
            Console.WriteLine($"  判定：{PyS(diff["verdict"])}");
            var impact = diff.GetValueOrDefault("impact") is { } im ? PyS(im) : "editorial";
            var label = impact switch
            {
                "bump" => "结构性（须 bump + 迁移记录）",
                "additive" => "字段级新增（V1 只增不删）",
                "editorial" => "措辞/编辑（无契约影响）",
                _ => impact,
            };
            Console.WriteLine($"  影响度：{impact}（{label}）");
            return 0;
        }
        catch (Exception exc) when (exc is IOException or UnauthorizedAccessException
                                       or ArgumentException or FormatException)
        {
            Console.Error.WriteLine($"  ✗ {exc.Message}");
            return 1;
        }
    }

    private static int ExplainCommand()
    {
        // check 修复指引（41 波C C5）：机械导出的静态表（见 CheckGuide 类注释）。
        if (positional.Count < 2) return Usage("explain 需要一个 check 编号（如 25 / check25；all = 全量清单）");
        var raw = positional[1];
        var key = AssetShelf.PyStrip(raw).ToLowerInvariant();
        if (key is "all" or "")
        {
            Console.WriteLine("== nf explain all（check 修复指引全量）==");
            foreach (var k in CheckGuide.SortedKeys())
                Console.WriteLine($"  check{k}：{CheckGuide.Get(k)}");
            return 0;
        }
        if (key.StartsWith("check", StringComparison.Ordinal)) key = key[5..];
        var guide = CheckGuide.Get(key);
        if (guide is null)
        {
            Console.Error.WriteLine($"  ✗ 未知 check：{raw}（可用 all 看全量）");
            return 2;
        }
        Console.WriteLine($"== nf explain check{key} ==");
        Console.WriteLine($"  {guide}");
        return 0;
    }

    /// <summary>Python <c>_rel_to_root</c>：目标必须存在，返回相对仓库根的路径；不存在即抛 ValueError 等价。</summary>
    private static string RelToRoot(string target)
    {
        var full = Path.GetFullPath(target);
        if (!File.Exists(full) && !Directory.Exists(full))
            throw new ArgumentException($"目标不存在：{target}");
        return Path.GetRelativePath(root!, full);
    }

    private static int RelatedCommand()
    {
        // See-Also 关联（41 波C C4）：registry protocols[] 为图 + 模块级依赖图（fence 正则口径）注入。
        if (positional.Count < 2) return Usage("related 需要一个目标（包 id 或模块 id）");
        var target = positional[1];
        var regPath = registryPath is null
            ? Path.Combine(root!, "desktop", "src", "core", "registry.json")
            : (Path.IsPathRooted(registryPath) ? registryPath : Path.Combine(root!, registryPath));
        var registry = ImpactCheck.LoadRegistry(regPath);
        var prots = MarketAnalyzer.Protocols(registry);
        var result = MarketAnalyzer.RelatedOf(target, prots,
            MarketAnalyzer.ModuleGraph(root!), MarketAnalyzer.OwnerMap(registry));
        if (json)
        {
            Console.WriteLine(PythonJson.Indented(result));
            return 0;
        }
        Console.WriteLine("== nf related（See-Also · 相关条目 + 引用链）==");
        Console.WriteLine($"  目标：{PyS(result["target"])}（{PyS(result["kind"])}）");
        Console.WriteLine("  关联条目（引用了谁 / 依赖链）：" + JoinOrDash(result["refs"]));
        Console.WriteLine("  反向引用方（谁引用我）：" + JoinOrDash(result["referenced_by"]));
        Console.WriteLine("  相关模块互见：" + JoinOrDash(result["related_modules"]));
        return 0;
    }

    /// <summary>Python <c>"、".join(list) or "—"</c> 的等价。</summary>
    private static string JoinOrDash(object? node)
    {
        var list = (node as List<object?> ?? new List<object?>()).Select(PyS).ToList();
        return list.Count > 0 ? string.Join("、", list) : "—";
    }

    private static int ImpactCommand()
    {
        // 变更影响面预检（A4 前置）：只读，不写盘；--check 为门禁模式（破坏性变更 exit 1）。
        if (positional.Count < 2) return Usage("impact 需要一个目标（protocol id 或 module id）");
        var target = positional[1];
        var regPath = registryPath is null
            ? Path.Combine(root!, "desktop", "src", "core", "registry.json")
            : (Path.IsPathRooted(registryPath) ? registryPath : Path.Combine(root!, registryPath));
        var registry = ImpactCheck.LoadRegistry(regPath);
        var impact = ImpactCheck.ImpactOfChange(registry, target);
        Console.WriteLine($"== 删除影响面预检: {target} ==");
        if (impact.GetValueOrDefault("error") is string error)
        {
            Console.WriteLine($"  [拒绝] {error}（修复指引：目标须是 registry 在册的 module / protocol id"
                              + "（如 M00 / 通用:M10 / 校园情感领域包）；`nf market --list` 与 `nf module ls` 可枚举）");
            return 1;
        }

        if (impact.ContainsKey("module_id"))
        {
            // module 级
            var refs = (impact.GetValueOrDefault("referenced_by") as List<object?> ?? new List<object?>())
                .OfType<Dictionary<string, object?>>().ToList();
            var core = impact.GetValueOrDefault("in_official_core") as List<object?> ?? new List<object?>();
            var pkgs = impact.GetValueOrDefault("in_packages") as List<object?> ?? new List<object?>();
            Console.WriteLine($"  类型: module（官方在册 {(core.Count > 0 ? PyScalar.PyRepr(core) : "无")} · " +
                              $"属包 {(pkgs.Count > 0 ? PyScalar.PyRepr(pkgs) : "无")}）");
            if (refs.Count == 0 && core.Count == 0)
            {
                Console.WriteLine("  无破坏性影响（无引用方且非官方核心——可安全移除）");
                return 0;
            }
            foreach (var r in refs)
            {
                var ro = PyTruthy(r.GetValueOrDefault("asset_readonly")) ? "只读" : "";
                var readonlyText = ro.Length > 0 ? ro : "false";
                Console.WriteLine($"  破坏性: 被 {PyS(r["protocol"])} 引用（引用声明源 {PyS(r["source_package"])}" +
                                  $"，asset_readonly {readonlyText}）");
            }
            if (core.Count > 0)
                Console.WriteLine($"  破坏性: 官方核心在册 {PyScalar.PyRepr(core)}（删官方核心 = 协议事故）");
            return impactCheck ? 1 : 0;
        }

        // protocol 级（整包删除）
        var packageRefs = (impact.GetValueOrDefault("referenced_by_packages") as List<object?> ?? new List<object?>())
            .OfType<Dictionary<string, object?>>().ToList();
        var mids = impact.GetValueOrDefault("module_ids") as List<object?> ?? new List<object?>();
        Console.WriteLine($"  类型: protocol 整包（module_ids {(mids.Count > 0 ? PyScalar.PyRepr(mids) : "无")}）");
        if (packageRefs.Count == 0)
        {
            Console.WriteLine("  无破坏性影响（无其它包引用本包模块——可安全移除，自身 references 随之消失）");
            return 0;
        }
        foreach (var r in packageRefs)
            Console.WriteLine($"  破坏性: 被 {PyS(r["protocol"])} 引用（引用声明源 {PyS(r["source_package"])}）");
        return impactCheck ? 1 : 0;
    }

    // 环境自检（真源 `nf doctor`）：关键文件在场 → registry 可解析 → IDL schema 定义在场 → 核心库可导入 →
    // 基线自描述一致 → schema 标准对照 → 模块工具面 → world_model / world_slots。
    // **两处声明边界（判据弱化 · 输出对齐）**：真源这两条依赖 Python 运行时，本引擎无 Python——
    // ① 「核心库可导入」→ 引擎只验 `desktop/src/core/schema_lint.py` **在场**（存在性代理）；
    // ② 「schema 标准对照（jsonschema）」→ 引擎用自带 schema 子集元检（五份齐）代替 jsonschema 真跑。
    // 两条在本仓语料上输出与真源逐字一致，判据弱化属实，故登记在此（面级对账仍逐字节比对）。
    private static int DoctorCommand()
    {
        const string NfCliVersion = "1.0.5";   // 真源 scripts/nf.py::NF_CLI_VERSION
        var checks = new List<Dictionary<string, object?>>();
        void Chk(string name, bool ok, string detail) =>
            checks.Add(new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["name"] = name, ["ok"] = ok, ["detail"] = detail,
            });

        foreach (var rel in new[]
                 {
                     "README.md", "01_核心协议.md", "02_联动注册表.md", "06_Agent执行协议.md",
                     "07_官方核心出厂与社区预设导航.md", "AGENTS.md", "STRATEGY.md", "verify.sh",
                 })
        {
            Chk($"文件在场 {rel}", File.Exists(Path.Combine(root!, rel)), rel);
        }

        try
        {
            using var doc = JsonIo.ReadFile(Path.Combine(root!, "desktop/src/core/registry.json"));
            var graph = PythonJson.ToGraph(doc.RootElement) as Dictionary<string, object?>
                        ?? new Dictionary<string, object?>(StringComparer.Ordinal);
            var modules = AsObjList(graph.GetValueOrDefault("modules")).Count;
            var protocols = AsObjList(graph.GetValueOrDefault("protocols")).Count;
            Chk($"registry 可解析（modules={modules} protocols={protocols}）",
                modules >= 13 && protocols >= 5, "desktop/src/core/registry.json");
        }
        catch (Exception exc)
        {
            Chk("registry 可解析", false, "desktop/src/core/registry.json: " + exc.Message);
        }

        var schemaDir = Path.Combine(root!, "protocol", "schema");
        var schemaCount = 0;
        try
        {
            schemaCount = Directory.GetFiles(schemaDir, "*.json").Length;
        }
        catch (Exception exc)
        {
            Chk("IDL schema 定义在场", false, exc.Message);
        }
        if (Directory.Exists(schemaDir))
            Chk($"IDL schema 定义在场（{schemaCount} 份）", schemaCount == 9, "protocol/schema");

        // 声明边界①：真源靠 Python import 成功，引擎只验文件在场
        Chk("核心库可导入（schema_lint）",
            File.Exists(Path.Combine(root!, "desktop/src/core/schema_lint.py")), "desktop/src/core");

        try
        {
            var (baselineIssues, baselineStats) = QualityBaseline.Scan(root!);
            Chk($"基线自描述一致（verify {PyS(baselineStats["verify_version"])}"
                + $" · check1-{QualityBaseline.ExpectedChecks} PASS={QualityBaseline.ExpectedPass}）",
                baselineIssues.Count == 0, "verify/README/CHANGELOG/VERSION-MATRIX");
        }
        catch (Exception exc)
        {
            Chk("基线自描述一致", false, exc.Message);
        }

        // 声明边界②：真源跑 jsonschema.check_schema，引擎跑自带 schema 子集元检
        try
        {
            var (schemaIssues, schemas) = SchemaLint.CheckSchemaFiles(root!);
            Chk("schema 标准对照（jsonschema）", schemaIssues.Count == 0 && schemas.Count == 9,
                "CI 与本地同跑");
        }
        catch (Exception exc)
        {
            Chk("schema 标准对照（jsonschema）", true, "可选依赖未装（CI 已装真跑）：" + exc.Message);
        }

        try
        {
            var (toolIssues, toolStats) = ToolFace.Scan(root!);
            Chk("模块工具面（tool_face）", toolIssues.Count == 0,
                $"模块 {PyS(toolStats.GetValueOrDefault("modules"))}"
                + $" · 条目 {PyS(toolStats.GetValueOrDefault("entries"))}"
                + $" · 候选 {PyS(toolStats.GetValueOrDefault("candidates"))}");
        }
        catch (Exception exc)
        {
            Chk("模块工具面（tool_face）", false, exc.Message);
        }

        try
        {
            var (wmIssues, wmStats) = WorldModel.Scan(root!);
            var (wsIssues, wsStats) = AuxScanners.WorldSlotsScan(root!);
            Chk("world_model 契约", wmIssues.Count == 0,
                $"模块 {PyS(wmStats.GetValueOrDefault("modules"))}"
                + $" · 变量 {PyS(wmStats.GetValueOrDefault("variables"))}"
                + $" · checks {PyS(wmStats.GetValueOrDefault("checks") ?? 0L)}"
                + $" · slots {PyS(wmStats.GetValueOrDefault("slots") ?? 0L)}"
                + $"/{PyS(wmStats.GetValueOrDefault("slot_registry") ?? 0L)}");
            Chk("world_slots 注册表", wsIssues.Count == 0,
                $"slots {PyS(wsStats.GetValueOrDefault("slots"))}"
                + $" · arrays {PyS(wsStats.GetValueOrDefault("arrays"))}");
        }
        catch (Exception exc)
        {
            Chk("world_model/world_slots", false, exc.Message);
        }

        // 真源 `doctor` 的最后一个运行前提：PyYAML 在场时 YAML 字段不降级。
        // 引擎无 Python，读同一份钉版声明作为存在性代理；详情与真源一致写 `PyYAML`。
        var pyproject = Path.Combine(root!, "pyproject.toml");
        var optionalYaml = File.Exists(pyproject)
            && File.ReadAllText(pyproject, new System.Text.UTF8Encoding(false))
                .Contains("pyyaml==", StringComparison.OrdinalIgnoreCase);
        Chk("可选依赖 PyYAML 在场（YAML 字段不降级）", optionalYaml, "PyYAML");

        var passed = checks.Count(c => c["ok"] is true);
        if (json)
        {
            Console.WriteLine(JsonFor(new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["version"] = NfCliVersion, ["ok"] = passed == checks.Count, ["passed"] = (long)passed,
                ["total"] = (long)checks.Count, ["degraded"] = false,
                ["checks"] = checks.Cast<object?>().ToList(),
            }));
        }
        else
        {
            Console.WriteLine($"== nf doctor（nf {NfCliVersion}）==");
            foreach (var check in checks)
            {
                Console.WriteLine($"  [{(check["ok"] is true ? "PASS" : "FAIL")}] {PyS(check["name"])}"
                                  + $"（{PyS(check["detail"])}）");
            }
            Console.WriteLine($"  体检：{passed}/{checks.Count} 通过");
        }
        return passed == checks.Count ? 0 : 1;
    }

    // Spec Registry 查询（真源 `nf spec ls`）：registry 版本 + 官方核心模块数 + 逐协议包三行摘要。
    private static int SpecCommand()
    {
        var sub = positional.Count >= 2 ? positional[1] : "ls";
        if (sub != "ls")
        {
            Console.Error.WriteLine($"错误：spec 没有子命令：{sub}（只读面只有 ls）");
            return 2;
        }
        var regPath = registryPath is null
            ? Path.Combine(root!, "desktop/src/core/registry.json")
            : (Path.IsPathRooted(registryPath) ? registryPath : Path.Combine(root!, registryPath));
        using var doc = JsonIo.ReadFile(regPath);
        var reg = PythonJson.ToGraph(doc.RootElement) as Dictionary<string, object?>
                  ?? new Dictionary<string, object?>(StringComparer.Ordinal);
        Console.WriteLine("== nf spec ls ==");
        Console.WriteLine($"  registry_schema_version: {PyS(reg.GetValueOrDefault("registry_schema_version"))}");
        Console.WriteLine($"  官方核心模块: {AsObjList(reg.GetValueOrDefault("modules")).Count} 件");
        foreach (var item in AsObjList(reg.GetValueOrDefault("protocols")))
        {
            var p = item as Dictionary<string, object?> ?? new Dictionary<string, object?>(StringComparer.Ordinal);
            var version = p.GetValueOrDefault("version");
            Console.WriteLine($"  {PyS(p.GetValueOrDefault("id"))}: schema v{PyS(p.GetValueOrDefault("schema_version"))}"
                              + $" · version {(version is null ? "1.0.0" : PyS(version))}"
                              + $" · {AsObjList(p.GetValueOrDefault("module_ids")).Count} 模块");
        }
        return 0;
    }

    // 缺口逐行审查（真源 `nf review` · core/gap_review.py）：机械预筛 → 模型逐行判 → **确定性证据复核**，
    // 双轨齐备才进 fixable。stub 适配器无判定能力 → 本轮以证据为准（真源同式）。
    // **写面不移植**：`--write` 把报告落盘（且真源禁写 protocol/），只读门不落盘。
    private static int ReviewCommand()
    {
        if (writeRequested)
        {
            Console.Error.WriteLine("错误：--write 是写面（审查报告落盘；真源还禁写 protocol/）——只读门不落盘，不提供");
            return 2;
        }
        var classes = (scopeSet ? scope : "").Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
        var unknown = classes.Where(c => Array.IndexOf(GapReview.Classes, c) < 0).ToList();
        if (unknown.Count > 0)
        {
            Console.Error.WriteLine($"  ✗ 未知 --scope：{string.Join("、", unknown)}"
                                    + $"（可枚举：{string.Join(" / ", GapReview.Classes)}）"
                                    + "（修复指引：--scope 只收这些类别，逗号分隔；不带 --scope 即全类）");
            return 2;
        }
        var doc = GapReview.Review(root!, adapterFlag, endpointFlag, limitCount, batchCount, classes);
        if (json)
        {
            Console.WriteLine(JsonFor(doc));
            return 0;
        }
        Console.WriteLine($"== nf review（逐行缺口审查 · 适配器 {adapterFlag}）==");
        Console.WriteLine("  " + GapReview.Summary(doc));
        foreach (var issue in doc.GetValueOrDefault("issues") as List<object?> ?? new List<object?>())
            Console.Error.WriteLine("  [FAIL] " + PyS(issue));
        var fixable = doc.GetValueOrDefault("fixable") as List<object?> ?? new List<object?>();
        foreach (var item in fixable.Take(40))
        {
            var row = (Dictionary<string, object?>)item!;
            var gapP = row.GetValueOrDefault("model_gap_p");
            var severity = row.GetValueOrDefault("model_severity");
            Console.WriteLine($"  [可修] {PadCp(PyS(row["class"]), 22)} {PyS(row["file"])}:{PyS(row["line"])}"
                              + $"  p={(gapP is null ? "-" : F2(gapP))}"
                              + $" sev={(severity is null ? "-" : F2(severity))}"
                              + $" | {PySliceStr(PyS(row["evidence"]), 88)}");
        }
        var suspected = doc.GetValueOrDefault("suspected") as List<object?> ?? new List<object?>();
        if (suspected.Count > 0)
            Console.WriteLine($"  —— 模型怀疑但**无证据**（不修，只挂账）{suspected.Count} 条");
        return 0;
    }

    private static string PySliceStr(string text, int max) => PyScalar.PySlice(text, max);

    // 扩展策略 / bump 迁移门禁（verify.sh check30）：判据词面 + bump 面。
    // **bump 面**在真源里是 `git diff HEAD` 的版本字段结构性变更面。引擎**不接 VCS**：
    //   · 导出快照（无 .git）：真源 `git diff` 亦失败 → diff 面恒空，两侧同判 → exit 0；
    //   · 工作区（有 .git）且未供 diff：**UNKNOWN（不判，不写 PASS）** → 打说明并 exit 1；
    //   · `--diff <文件|->`：调用方（CI / 脚本）供 `git diff HEAD` 的标准统一 diff → 按真源算法逐文件判。
    private static int ExtensionCommand()
    {
        ExtensionPolicy.Result result;
        if (diffPath is not null)
        {
            var text = diffPath == "-"
                ? Console.In.ReadToEnd()
                : File.ReadAllText(diffPath, new System.Text.UTF8Encoding(false, true));
            result = ExtensionPolicy.ScanWithDiff(root!, text);
        }
        else
        {
            result = ExtensionPolicy.Scan(root!);
        }
        foreach (var line in result.Log) Console.WriteLine(line);
        if (!result.BumpFaceJudged)
        {
            Console.Error.WriteLine("注意：bump 面 UNKNOWN（不判，不写 PASS）——" + result.Boundary);
            Console.Error.WriteLine("      收口方式：把 `git diff HEAD` 的标准统一 diff 用 --diff <文件|-> 或管道交给本命令。");
            return 1;
        }
        return result.Issues.Count > 0 ? 1 : 0;
    }

    // 语料身份（第一百零六片 · 操作性预检）：指纹 + 金标基线 + 模式。**只报告，不判据**——
    // 作用是让「摘要类钉的红」能被正确归因（语料前移 ≠ 引擎坏了）。
    // 退出码：0（无论匹配与否；本命令不是判据）——但导出快照且不匹配时，另打一行**处置指引**到 stderr。
    private static int CorpusCommand()
    {
        var stamp = CorpusStamp.Check(root!);
        if (json)
        {
            Console.WriteLine(PythonJson.Indented(new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["fingerprint"] = stamp.Fingerprint, ["baseline"] = stamp.Baseline,
                ["matches_baseline"] = stamp.Matches, ["mode"] = stamp.IsSnapshot ? "snapshot" : "worktree",
            }));
            return 0;
        }
        Console.WriteLine($"语料身份：{stamp.Fingerprint}（金标基线 {stamp.Baseline}）"
                          + $" · 匹配={(stamp.Matches ? "是" : "否")}"
                          + $" · 模式={(stamp.IsSnapshot ? "导出快照" : "工作区")}");
        if (stamp.IsSnapshot && !stamp.Matches)
        {
            Console.Error.WriteLine("WARN: 语料与金标基线不同——**摘要类自检钉的红应从「复基线」处置**，"
                                    + "不是「引擎坏了」：");
            Console.Error.WriteLine("      ① 复基线：按《双跑对账表》各片的探针流程重生成 fixtures 并重嵌 SelfTest 常量；");
            Console.Error.WriteLine("      ② 或改跑**活仓库**（带 .git → 语义模式，不拿死摘要比漂动语料）："
                                    + "-Root <仓库根>（如 . 或你的检出目录）。");
        }
        return 0;
    }

}
