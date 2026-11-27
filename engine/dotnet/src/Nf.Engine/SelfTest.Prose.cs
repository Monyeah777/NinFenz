using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text;
using System.Text.RegularExpressions;

namespace Nf.Engine;

/// <summary>散文 lint / 自动修复 / 许可证门 / 文本卫生 / 文档完备 / 核心注册表 / 市场分级负例。</summary>
public static partial class SelfTest
{
    /// <summary>
    /// check33 第 5 / 12 面（正文 lint + 文档命令面）三钉：真仓命令面（72 文档 / 277 处 / 零问题）
    /// + 合成命令面（坏子命令与未登记 MCP 工具各判出）+ 合成正文 lint（八类规则全覆盖）。
    /// 摘要金标由 probes/prose_lint_probe.py（真源模块原文导入）产出。
    /// </summary>
    private static void ProseLintCases(List<Check> checks, string work, string repoRoot)
    {
        const string RealGoldenDigest = "84c6dcebe29d26231197c1c42468c273";
        const string SyntheticFaceGoldenDigest = "f49f9632490448f1df6f7afba7d561ce";
        const string SyntheticLintGoldenDigest = "174fe1ed64ad984ec8e05bc096290f89";

        var real = ProseLint.CommandFace(repoRoot);
        var pinned = IsPinnedSnapshot(repoRoot);
        checks.Add(new Check("文档面·真仓命令面（零问题 · 导出态断 78 文档/433 处与金标摘要 / 工作区态断语义）",
            real.Ok
            && Convert.ToInt64(real.Stats["cli_commands"]) == 109
            && Convert.ToInt64(real.Stats["mcp_tools"]) == 12
            && (!pinned || (DigestOf(CommandFaceLog(real)) == RealGoldenDigest
                            && Convert.ToInt64(real.Stats["docs"]) == 78
                            && Convert.ToInt64(real.Stats["commands_checked"]) == 433)),
            $"docs {real.Stats["docs"]} · checked {real.Stats["commands_checked"]} · cli {real.Stats["cli_commands"]}"
            + $" · mcp {real.Stats["mcp_tools"]} · FAIL {real.Issues.Count} · 摘要 {DigestOf(CommandFaceLog(real))}"
            + $"（真源金标 {RealGoldenDigest}）"
            + $" · 模式={(pinned ? "导出快照·断金标" : "工作区·断语义（金标摘要锚定 HEAD 983741b）")}"));

        // MCP 工具表镜像核验：真源那 10 个基名必须仍在引擎的 MCP 工具面里（否则命令面判据会偏松）
        var engineTools = McpServer.ToolNames.ToHashSet(StringComparer.Ordinal);
        var missingTools = ProseLint.SourceMcpToolNames.Where(t => !engineTools.Contains(t)).ToList();
        checks.Add(new Check("文档面·MCP 工具表镜像（真源 12 基名 ⊆ 引擎 MCP 工具面）",
            missingTools.Count == 0 && engineTools.Count >= 28,
            $"引擎工具 {engineTools.Count} 个 · 真源基名缺 {missingTools.Count} 个"));

        var root = Path.Combine(work, "prose-lint");
        Fresh(root);
        foreach (var (rel, b64) in ProseLintSyntheticFiles) WriteBase64(root, rel, b64);
        var synth = ProseLint.CommandFace(root);
        var synthLog = CommandFaceLog(synth);
        var synthText = string.Join(" | ", synth.Issues);
        checks.Add(new Check("文档面·合成命令面（坏子命令 ×2 + 未登记 MCP 工具 ×1 判出 · 与真源原文逐字节同摘要）",
            !synth.Ok && synth.Issues.Count == 3 && DigestOf(synthLog) == SyntheticFaceGoldenDigest
            && synthText.Contains("README.md 命令面：`nf nope` 不是 CLI 子命令")
            && synthText.Contains("README.md 命令面：`nf bogus-cmd` 不是 CLI 子命令")
            && synthText.Contains("README.md 命令面：not_a_tool 不是已登记 MCP 工具")
            && Convert.ToInt64(synth.Stats["docs"]) == 2
            && Convert.ToInt64(synth.Stats["commands_checked"]) == 7
            && Convert.ToInt64(synth.Stats["cli_commands"]) == 2
            && Convert.ToInt64(synth.Stats["mcp_tools"]) == 12,
            $"docs {synth.Stats["docs"]} · checked {synth.Stats["commands_checked"]} · FAIL {synth.Issues.Count}"
            + $" · 摘要 {DigestOf(synthLog)}（真源金标 {SyntheticFaceGoldenDigest}）"));

        var prosePath = Path.Combine(root, "prose_sample.md");
        var findings = ProseLint.LintText(File.ReadAllText(prosePath, new UTF8Encoding(false)));
        var lintLog = LintTextLog(findings);
        var rules = findings.Select(f => f.Rule).Distinct(StringComparer.Ordinal).OrderBy(x => x, StringComparer.Ordinal).ToList();
        checks.Add(new Check("文档面·合成正文 lint（八类规则全覆盖 · 与真源原文逐字节同摘要）",
            findings.Count == 9 && DigestOf(lintLog) == SyntheticLintGoldenDigest && rules.Count == 8
            && findings[0].Rule == "hedge_overuse" && findings[0].Line == 0
            && findings.Any(f => f.Rule == "repeat_connector" && f.Line == 15)
            && findings.Any(f => f.Rule == "triple_adj" && f.Snippet.Contains("统筹兼顾、稳中求进、进退有据")),
            $"findings {findings.Count} · 规则 {rules.Count} 类 · 摘要 {DigestOf(lintLog)}（真源金标 {SyntheticLintGoldenDigest}）"));
    }

    /// <summary>机械修复面（check33 第 4 面）：真仓关键/指令档零待办 + 合成负例四类各判出。</summary>
    private static void AutofixCases(List<Check> checks, string work, string repoRoot)
    {
        var (pending, targets) = Autofix.ScanGateTargets(repoRoot);
        var pinnedRoot = IsPinnedSnapshot(repoRoot);
        checks.Add(new Check("机械修复面·真仓（关键/指令档零待办 · 导出态另断 46 档）",
            pending.Count == 0 && (pinnedRoot ? targets == 46 : targets > 0),
            $"目标档 {targets} 个（REQUIRED ∪ INSTRUCTION 里在盘者）· 待办 {pending.Count} 个"
            + $" · 模式={(pinnedRoot ? "导出快照（金标 46 档）" : "工作区·断语义")}"));

        var root = Path.Combine(work, "autofix");
        Fresh(root);
        var required = DocHygiene.RequiredDocPaths[0];
        // 取**只属指令档**的那一件（指令档大多同时是关键档，两者都判会多出「缺最后更新」，干扰本钉的判别）
        var instruction = DocHygiene.InstructionDocPaths.First(p => !DocHygiene.RequiredDocPaths.Contains(p));
        var writeRequired = Path.Combine(root, required.Replace('/', Path.DirectorySeparatorChar));
        Directory.CreateDirectory(Path.GetDirectoryName(writeRequired)!);
        File.WriteAllText(writeRequired, "# 关键档\n\n正文带行尾空白   \n最后一行无换行", new UTF8Encoding(false));
        var writeInstruction = Path.Combine(root, instruction.Replace('/', Path.DirectorySeparatorChar));
        Directory.CreateDirectory(Path.GetDirectoryName(writeInstruction)!);
        File.WriteAllText(writeInstruction, "# 指令档\n\n正文\n", new UTF8Encoding(false));
        var other = Path.Combine(root, "普通件.md");
        File.WriteAllText(other, "# 普通件\n\n正文", new UTF8Encoding(false));

        var requiredFindings = Autofix.LintRules(root, required,
            File.ReadAllText(writeRequired, new UTF8Encoding(false)));
        var instructionFindings = Autofix.LintRules(root, instruction,
            File.ReadAllText(writeInstruction, new UTF8Encoding(false)));
        var otherFindings = Autofix.LintRules(root, "普通件.md",
            File.ReadAllText(other, new UTF8Encoding(false)));
        checks.Add(new Check("机械修复面·合成负例（关键档缺「最后更新」/ 行尾空白 / 末缺换行 · 指令档缺标识 · 普通件只判机械面）",
            requiredFindings.Count == 3
            && requiredFindings.Select(f => f.Rule).SequenceEqual(new[] { "last_updated", "trailing_ws", "final_newline" })
            && instructionFindings.Count == 1 && instructionFindings[0].Rule == "instruction_mark"
            && otherFindings.Count == 1 && otherFindings[0].Rule == "final_newline",
            $"关键档 {requiredFindings.Count} 项 · 指令档 {instructionFindings.Count} 项 · 普通件 {otherFindings.Count} 项"
            + "（写面 apply_rules 明确不移植：只读门不说「我改过」）"));
    }

    private static List<string> CommandFaceLog(ProseLint.CommandFaceResult result)
    {
        var lines = result.Issues.Select(i => "[FAIL] " + i).ToList();
        lines.Add("[STAT] docs=" + Convert.ToInt64(result.Stats["docs"])
                  + " commands_checked=" + Convert.ToInt64(result.Stats["commands_checked"])
                  + " cli_commands=" + Convert.ToInt64(result.Stats["cli_commands"])
                  + " mcp_tools=" + Convert.ToInt64(result.Stats["mcp_tools"]));
        return lines;
    }

    private static List<string> LintTextLog(List<ProseLint.Finding> findings)
    {
        var lines = findings
            .Select(f => $"[FIND] {f.Rule} line={f.Line} {f.Message} | {f.Snippet}")
            .ToList();
        lines.Add("[STAT] findings=" + findings.Count);
        return lines;
    }

    private static string DigestOf(IEnumerable<string> lines) => Convert.ToHexString(
        System.Security.Cryptography.SHA256.HashData(
            Encoding.UTF8.GetBytes(string.Join("\n", lines)))).ToLowerInvariant()[..32];

    private static readonly (string Rel, string B64)[] ProseLintSyntheticFiles =
    {
        ("scripts/nf.py", "IiIi5o6i6ZKI5ZCI5oiQ6K+t5paZ77ya5Y+q5o+Q5L6bIGFkZF9wYXJzZXIg5rOo5YaM5ZCN77yM5L6bIGNvbW1hbmRfZmFjZSDmir3lj5bjgIIiIiIKaW1wb3J0IGFyZ3BhcnNlCgpzdWIgPSBhcmdwYXJzZS5Bcmd1bWVudFBhcnNlcigpLmFkZF9zdWJwYXJzZXJzKCkKcCA9IHN1Yi5hZGRfcGFyc2VyKCJhc3NlbWJsZSIpCnAgPSBzdWIuYWRkX3BhcnNlcigidmVyaWZ5IikK"),
        ("README.md", "IyDlkIjmiJDor63mlpkgwrcg5YWl5Y+j5paH5qGjCgrnlKggYG5mIGFzc2VtYmxlYCDoo4XphY3kuIDkuKrnu4TlkIjljIXjgIIKCueUqCBgbmYgbm9wZWAg5piv5LiN5a2Y5Zyo55qE5a2Q5ZG95Luk77yI5bqU5Yik5Ye677yJ44CCCgpgcmVnaXN0cnlfc2VhcmNo77yITUNQIOW3peWFt++8iWAg5Zyo5YaM77ybYG5vdF9hX3Rvb2zvvIhNQ1Ag5bel5YW377yJYCDkuI3lnKjlhozvvIjlupTliKTlh7rvvInjgIIKCmBgYGJhc2gKbmYgdmVyaWZ5IC0tYWxsCm5mIGJvZ3VzLWNtZApgYGAK"),
        ("docs/x.md", "IyDlkIjmiJDor63mlpkgwrcgZG9jcyDpnaIKCuaVo+aWh+mHjOWGmSBuZiDkuI3luKblj43lvJXlj7fkuI3nrpflkb3ku6TpnaLvvIjmnKzooYzkuI3or6XooqvliKTvvInjgIIKCmBuZiBhc3NlbWJsZWAg5Zyo5YaM77yI5LiN6K+l6KKr5Yik77yJ44CCCg=="),
        ("prose_sample.md", "IyDlkIjmiJDor63mlpkgwrcg5q2j5paHIGxpbnQKCuWcqOi/meS4qumXrumimOS4iu+8jOaIkeS7rOmcgOimgeiwqOaFjuOAggoK5oC76ICM6KiA5LmL77yM5oiR5Lus5bqU6K+l57un57ut44CCCgrov5nkuI3mmK/pgJ/luqbpl67popjvvIzogIzmmK/mlrnlkJHpl67popjjgIIKCue7n+etueWFvOmhvuOAgeeos+S4reaxgui/m+OAgei/m+mAgOacieaNruWcsOaOqOi/m+OAggoK6L+Z5piv5LiA5Y+l5Lit5paHLOW4puiLseaWh+mAl+WPt+OAggoK54S26ICM5oOF5Ya15YWI5Y+Y5LqG44CCCgrnhLbogIzml7bpl7Tlj4jkuI3lpJ/jgIIKCuS5n+iuuOWkp+amguaIluiuuOS8vOS5juS7v+S9m+WPr+iDveafkOenjeeoi+W6puS4iu+8jOS6i+aDhei/mOaciei9rOacuuOAggo="),
    };

    /// <summary>
    /// check33 第 6 面（图书馆许可证门）两钉：真材料（真仓登记零 FAIL + WARN 台账 + 与真源原文逐字节同摘要）
    /// + 合成负例（五类 FAIL + 三类 WARN 各命中）。
    /// </summary>
    private static void LicenseGateCases(List<Check> checks, string work, string repoRoot)
    {
        // 金标来源：probes/license_gate_probe.py 导入**快照里那份**真源 core/license_gate.py 原文执行，
        // 统一渲染规则（[FAIL]/[WARN]/[STAT]）见探针头；摘要见 _fixtures/_license_gate_golden.json。
        const string RealGoldenDigest = "ee4bb55acf6688bf0e6cb8621fd1b979";
        const string SyntheticGoldenDigest = "ec3b4ca338650df71a93c8c476acad79";

        var real = LicenseGate.Scan(repoRoot);
        var pinned = IsPinnedSnapshot(repoRoot);
        checks.Add(new Check("许可证门·真仓（登记零 FAIL · 越词表/缺内联/双源不一致必须为 0 · 导出态另断金标摘要）",
            real.Ok && real.UnknownIds.Count == 0 && real.NoInlineIds.Count == 0 && real.MismatchedIds.Count == 0
            && (!pinned || (real.LogDigest == RealGoldenDigest
                            && Convert.ToInt64(real.Stats["entries"]) == 3
                            && Convert.ToInt64(real.Stats["declared"]) == 2)),
            $"登记 {real.Stats["entries"]} 条（声明 {real.Stats["declared"]}）· FAIL {real.Issues.Count} · WARN {real.Warnings.Count}"
            + $" · 摘要 {real.LogDigest}（真源金标 {RealGoldenDigest}）"
            + $" · 模式={(pinned ? "导出快照·断金标" : "工作区·断语义（未声明允许 ≤1，真仓为 1）")}"));

        var root = Path.Combine(work, "license-gate");
        Fresh(root);
        foreach (var (rel, b64) in LicenseGateSyntheticFiles) WriteBase64(root, rel, b64);
        var synth = LicenseGate.Scan(root);
        var text = string.Join(" | ", synth.Issues) + " || " + string.Join(" | ", synth.Warnings);
        checks.Add(new Check("许可证门·合成负例（越词表 / 无许可列 / 运算符缺操作数 / 括号不配平 / 非法字符五类 FAIL + 未声明/缺内联/双源不一致三类 WARN）",
            !synth.Ok && synth.Issues.Count == 5 && synth.Warnings.Count == 4
            && synth.LogDigest == SyntheticGoldenDigest
            && text.Contains("许可取值不合规：NF-BADID-1 = GPL-3.0-only（许可 id 不在词表：GPL-3.0-only")
            && text.Contains("登记行缺「许可」列值：NF-EMPTY-1")
            && text.Contains("运算符 AND 前缺少操作数")
            && text.Contains("括号不配平")
            && text.Contains("含非法字符")
            && text.Contains("许可未声明（待投稿人确认）：NF-UNDECL-1")
            && text.Contains("条目文件缺内联许可声明：NF-REF-1")
            && text.Contains("许可双源不一致：NF-EXPR-1 登记=MIT OR Apache-2.0 文件=MIT")
            && Convert.ToInt64(synth.Stats["entries"]) == 10 && Convert.ToInt64(synth.Stats["declared"]) == 5
            && synth.UndeclaredIds.SequenceEqual(new[] { "NF-UNDECL-1" })
            && synth.MismatchedIds.SequenceEqual(new[] { "NF-EXPR-1", "NF-MISMATCH-1" })
            && synth.UnknownIds.SequenceEqual(new[] { "NF-BADID-1", "NF-BADOP-1", "NF-PAREN-1", "NF-CHAR-1" }),
            $"登记 {synth.Stats["entries"]} 条 · FAIL {synth.Issues.Count} · WARN {synth.Warnings.Count}"
            + $" · 摘要 {synth.LogDigest}（真源金标 {SyntheticGoldenDigest}）"));
    }

    private static readonly (string Rel, string B64)[] LicenseGateSyntheticFiles =
    {
        ("library/INDEX.md", "IyDkupHnq6/lm77kuabppobntKLlvJXvvIjmjqLpkojlkIjmiJDor63mlpnvvIkKCnwg57yW5Y+3IHwg5qCH6aKYIHwg5b2i5oCBL+mihuWfnyB8IOaKleeov+S6uiB8IOWFpeW6k+aXpeacnyB8IOiuuOWPryB8IOWIhue6pyB8IOeKtuaAgSB8IOS4gOWPpeivnSB8CnwtLS18LS0tfC0tLXwtLS18LS0tfC0tLXwtLS18LS0tfC0tLXwKfCBORi1PSy0xIHwg5qC35L6L5LiAIHwg5LiW55WMIHwgYSB8IDIwMjYtMDEtMDEgfCBNSVQgfCB0ZWVuIHwgYWN0aXZlIHwg5ZCI6KeEIHwKfCBORi1FWFBSLTEgfCDmoLfkvovkuowgfCDkuJbnlYwgfCBiIHwgMjAyNi0wMS0wMiB8IE1JVCBPUiBBcGFjaGUtMi4wIHwgdGVlbiB8IGFjdGl2ZSB8IOihqOi+vuW8jyB8CnwgTkYtUkVGLTEgfCDmoLfkvovkuIkgfCDkuJbnlYwgfCBjIHwgMjAyNi0wMS0wMyB8IExpY2Vuc2VSZWYtQ3VzdG9tLTEgfCB0ZWVuIHwgYWN0aXZlIHwg6Ieq6YCgIGlkIHwKfCBORi1VTkRFQ0wtMSB8IOagt+S+i+WbmyB8IOS4lueVjCB8IGQgfCAyMDI2LTAxLTA0IHwg5pyq5aOw5piOIHwgZ2VuZXJhbCB8IGFjdGl2ZSB8IOacquWjsOaYjiB8CnwgTkYtTUlTTUFUQ0gtMSB8IOagt+S+i+S6lCB8IOS4lueVjCB8IGUgfCAyMDI2LTAxLTA1IHwgTUlUIHwgZ2VuZXJhbCB8IGFjdGl2ZSB8IOWPjOa6kOS4jeS4gOiHtCB8CnwgTkYtQkFESUQtMSB8IOagt+S+i+WFrSB8IOS4lueVjCB8IGYgfCAyMDI2LTAxLTA2IHwgR1BMLTMuMC1vbmx5IHwgZ2VuZXJhbCB8IGFjdGl2ZSB8IOi2iuivjeihqCB8CnwgTkYtRU1QVFktMSB8IOagt+S+i+S4gyB8IOS4lueVjCB8IGcgfCAyMDI2LTAxLTA3IHwgeCB8CnwgTkYtQkFET1AtMSB8IOagt+S+i+WFqyB8IOS4lueVjCB8IGggfCAyMDI2LTAxLTA4IHwgTUlUIEFORCBBTkQgQXBhY2hlLTIuMCB8IGdlbmVyYWwgfCBhY3RpdmUgfCDov5DnrpfnrKbnvLrmk43kvZzmlbAgfAp8IE5GLVBBUkVOLTEgfCDmoLfkvovkuZ0gfCDkuJbnlYwgfCBpIHwgMjAyNi0wMS0wOSB8IChNSVQgT1IgQXBhY2hlLTIuMCB8IGdlbmVyYWwgfCBhY3RpdmUgfCDmi6zlj7fkuI3phY3lubMgfAp8IE5GLUNIQVItMSB8IOagt+S+i+WNgSB8IOS4lueVjCB8IGogfCAyMDI2LTAxLTEwIHwgTUlUIMKpIHwgZ2VuZXJhbCB8IGFjdGl2ZSB8IOmdnuazleWtl+espiB8Cg=="),
        ("library/NF-OK-1.md", "IyDmoLfkvovkuIAKCj4g6K645Y+v77yaTUlUCg=="),
        ("library/NF-EXPR-1.md", "IyDmoLfkvovkuowKCj4g6K645Y+v77yaTUlUIE9SIEFwYWNoZS0yLjAK"),
        ("library/NF-REF-1.md", "IyDmoLfkvovkuIkKCu+8iOaXoOWGheiBlOiuuOWPr+WjsOaYjuKAlOKAlOW6lOiusCBXQVJO77yJCg=="),
        ("library/NF-UNDECL-1.md", "IyDmoLfkvovlm5sKCj4g6K645Y+v77ya5pyq5aOw5piOCg=="),
        ("library/NF-MISMATCH-1.md", "IyDmoLfkvovkupQKCj4g6K645Y+v77yaQXBhY2hlLTIuMAo="),
    };

    /// <summary>
    /// check33 第 9 面（编码卫生）三钉：**真材料**（真仓 2765 件零问题 + 计数在册 + 与真源原文逐字节同摘要）
    /// + **合成负例**（七条规则各命中一次，含排除目录/排除文件/二进制哨兵三条负对照）
    /// + **坏 UTF-8 不可约尾**（条数与问题前缀同判）。
    /// </summary>
    private static void TextHygieneCases(List<Check> checks, string work, string repoRoot)
    {
        // 金标来源：probes/text_hygiene_probe.py 把真源 core/text_hygiene.py **原文复制后执行**
        // （真源 __main__ 同一段代码），逐字节 stdout 摘要见 _fixtures/_text_hygiene_golden.json。
        // 合成树以 base64 记录 → 两侧比的是**同一棵树**。
        const string RealGoldenDigest = "2330be8837eca8ee25191bdc42ec27fb";
        const string MixedGoldenDigest = "62705da4c6d1a6647f46aef038689209";
        const string BadUtf8Prefix = "c_bad.txt 不是合法 UTF-8：";

        var real = TextHygiene.Scan(repoRoot);
        var pinned = IsPinnedSnapshot(repoRoot);
        checks.Add(new Check("编码卫生·真仓（零问题 · 导出态另断 3858/1146/251702/111 与金标摘要）",
            real.Ok && Convert.ToInt64(real.Stats["versions_checked"]) > 0
            && (!pinned || (real.LogDigest == RealGoldenDigest
                            && Convert.ToInt64(real.Stats["text"]) == 3858
                            && Convert.ToInt64(real.Stats["json"]) == 1146
                            && Convert.ToInt64(real.Stats["keys_checked"]) == 251702
                            && Convert.ToInt64(real.Stats["versions_checked"]) == 111)),
            $"{real.SummaryLine} · 摘要 {real.LogDigest}（真源金标 {RealGoldenDigest}）"
            + $" · 模式={(pinned ? "导出快照·断金标" : "工作区·断语义")}"));

        var mixedRoot = Path.Combine(work, "text-hygiene-mixed");
        Fresh(mixedRoot);
        foreach (var (rel, b64) in TextHygieneMixedFiles) WriteBase64(mixedRoot, rel, b64);
        var mixed = TextHygiene.Scan(mixedRoot);
        var mixedText = string.Join(" | ", mixed.Issues);
        checks.Add(new Check("编码卫生·合成负例（七条规则各命中一次 · 与真源原文逐字节同摘要）",
            !mixed.Ok && mixed.Issues.Count == 7 && mixed.LogDigest == MixedGoldenDigest
            && mixedText.Contains("未声明 `* text=auto eol=lf`")
            && mixedText.Contains("a_bom.md 以 UTF-8 BOM 开头")
            && mixedText.Contains("b_crlf.md 含 CRLF 行尾")
            && mixedText.Contains("d_dup.json JSON 重复键 'a'")
            && mixedText.Contains("e_key.json JSON 键 '好\\xa0键' 违规：含隐形/同形字符 不换行空格(NBSP)（U+00A0）")
            // 注意：这一行的键是**分解形**（`e` + U+0301，可打印故 repr 原样输出）——断言不能写成预组合 `é`。
            && mixedText.Contains("f_non_nfc.json JSON 键 ") && mixedText.Contains("违规：非 NFC 规范化形态")
            && mixedText.Contains("community/示例包/protocol.yaml 的版本值 '1.0' 违规：缺补丁号")
            && Convert.ToInt64(mixed.Stats["text"]) == 9 && Convert.ToInt64(mixed.Stats["keys_checked"]) == 5
            && !mixedText.Contains("_cov_tmp.json") && !mixedText.Contains("h_binary.bin"),
            $"{mixed.SummaryLine} · 摘要 {mixed.LogDigest}（真源金标 {MixedGoldenDigest}）"));

        var badRoot = Path.Combine(work, "text-hygiene-bad-utf8");
        Fresh(badRoot);
        foreach (var (rel, b64) in TextHygieneBadUtf8Files) WriteBase64(badRoot, rel, b64);
        var badUtf8 = TextHygiene.Scan(badRoot);
        checks.Add(new Check("编码卫生·坏UTF8（1 条 · 前缀与真源同判；行尾文案属各自编解码器=不可约）",
            !badUtf8.Ok && badUtf8.Issues.Count == 1
            && badUtf8.Issues[0].StartsWith(BadUtf8Prefix, StringComparison.Ordinal),
            $"问题 {badUtf8.Issues.Count} 条 · 前缀 `{BadUtf8Prefix}` · 尾为 .NET 解码器文案（真源为 Python 编解码器文案）"));
    }

    private static readonly (string Rel, string B64)[] TextHygieneMixedFiles =
    {
        (".gitattributes", "KiB0ZXh0PWF1dG8gZW9sPWNybGYK"),
        ("a_bom.md", "77u/5q2j5paHCg=="),
        ("b_crlf.md", "6KGM5LiADQrooYzkuowNCg=="),
        ("d_dup.json", "eyJhIjoxLCJhIjoyLCJrIjozfQo="),
        ("e_key.json", "eyLlpb3CoOmUriI6MX0K"),
        ("f_non_nfc.json", "eyJlzIEiOjF9Cg=="),
        ("g_ok.json", "eyJnb29kX2tleSI6MX0K"),
        ("h_binary.bin", "AAECYmluYXJ5LWlzaAo="),
        ("_cov_tmp.json", "eyJleGNsdWRlZOOAgGtleSI6MX0K"),
        (".git/inside.md", "5o6S6Zmk55uu5b2V6YeM55qE5Lu25LiN6K+l6KKr5omrCg=="),
        ("community/示例包/protocol.yaml", "aWQ6IOekuuS+i+WMhQp2ZXJzaW9uOiAxLjAK"),
        ("community/示例包/modules/M01.md", "IyDmqKHlnZcgTTAxIMK3IOekuuS+iwo="),
    };

    private static readonly (string Rel, string B64)[] TextHygieneBadUtf8Files =
    {
        (".gitattributes", "KiB0ZXh0PWF1dG8gZW9sPWxmCg=="),
        ("c_bad.txt", "//5BQgo="),
    };

    private static void WriteBase64(string root, string rel, string b64)
    {
        var path = Path.Combine(root, rel.Replace('/', Path.DirectorySeparatorChar));
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        File.WriteAllBytes(path, Convert.FromBase64String(b64));
    }

    /// <summary>
    /// check20（文档完整性）两钉：**真材料**（真仓官方 13 件强校验全过 + 社区统计）+ **合成负例**
    /// （官方四类问题各报出 / 社区有契约者强校验 / 未完备者只进 WARN 不进 errs）。
    /// </summary>
    private static void DocCompletenessCases(List<Check> checks, string work, string repoRoot)
    {
        // 金标来源：probes/doc_completeness_probe.py 把 verify.sh check20 的**内联 Python 原文**抽出后执行，
        // 摘要在 _fixtures/_doc_completeness_golden.json（真仓 294d2e18… / 合成 76e4ffcf…）。
        // 合成树的规格与探针里 SYNTH_FILES **逐字节相同**——两边跑同一棵树才有可比性。
        const string SyntheticGoldenDigest = "76e4ffcfd4746a0b7d95606ee6cb58b1";

        // ① 真材料：真仓官方 13 件强校验全过 + 社区机读完备件强校验 + 未完备存量只进 WARN 统计（不阻断）
        var real = DocCompleteness.Check(repoRoot);
        checks.Add(new Check("check20·真仓（官方 13 件强校验全过 · 社区机读完备强校验 · 未完备只 WARN 统计）",
            real.Ok && real.CoreCount == 13 && real.CommunityCount > 0,
            $"官方 {real.CoreCount} · 社区 {real.CommunityCount} · 未完备 WARN {real.IncompleteCount}"
            + $" · FAIL {real.Issues.Count} · 摘要 {real.LogDigest}（真源金标 294d2e18c7ab8aba89e56f182986b13b @ HEAD 983741b）"));

        // ② 合成树：官方 2 件（1 合规 / 1 缺机器契约 + 标题坏 + 缺元数据 + 缺章节）+ 社区 2 件（1 有契约缺键 / 1 未完备）
        var root = Path.Combine(work, "doc-completeness");
        Fresh(root);
        var coreDir = Path.Combine(root, "04_模块库", "通用类");
        Directory.CreateDirectory(coreDir);
        File.WriteAllText(Path.Combine(coreDir, "M00_好模块.md"),
            "# 模块 M00 · 数据结构\n> 类别：通用\n> 来源：核心\n> 挂载点：P00\n> 依赖：无\n\n## 职责\n正文\n\n"
            + "```yaml\nmachine_contract:\n  id: M00\n```\n", new UTF8Encoding(false));
        File.WriteAllText(Path.Combine(coreDir, "M99_坏.md"),
            "# 坏标题\n正文没有元数据也没有章节\n", new UTF8Encoding(false));
        var commDir = Path.Combine(root, "community", "示例包", "modules");
        Directory.CreateDirectory(commDir);
        File.WriteAllText(Path.Combine(commDir, "C01_完备但缺键.md"),
            "# 模块 C01 · 示例\n\n```yaml\nmachine_contract:\n  id: C01\n```\n\n## 职责\n正文\n",
            new UTF8Encoding(false));
        File.WriteAllText(Path.Combine(commDir, "C02_未完备.md"), "not a module doc\n", new UTF8Encoding(false));

        var synth = DocCompleteness.Check(root);
        var text = string.Join(" | ", synth.Issues);
        checks.Add(new Check("check20·合成负例（官方四类问题各报出 · 社区有契约者强校验 · 未完备者只进 WARN 不进 errs）",
            !synth.Ok && synth.CoreCount == 2 && synth.CommunityCount == 2 && synth.IncompleteCount == 1
            && synth.LogDigest == SyntheticGoldenDigest
            && text.Contains("[官方] M99_坏.md 缺 machine_contract")
            && text.Contains("[官方] M99_坏.md 标题格式异常")
            && text.Contains("[官方] M99_坏.md 元数据缺 类别")
            && text.Contains("[官方] M99_坏.md 缺 职责/核心逻辑 章节")
            && text.Contains("[社区] C01_完备但缺键.md 元数据缺 类别")
            && !text.Contains("C02_未完备.md")
            && synth.IncompleteBases.Contains("C02_未完备.md")
            && synth.Head5.Contains("文档完整性扫描：官方 2 件 + 社区 2 件"),
            $"官方 {synth.CoreCount} · 社区 {synth.CommunityCount} · 未完备 {synth.IncompleteCount}"
            + $" · FAIL {synth.Issues.Count} · 摘要 {synth.LogDigest}（真源金标 {SyntheticGoldenDigest}，逐字节同）"));
    }

    /// <summary>
    /// check13（协议版本一致性 + 迁移完整性）六钉：**真材料**（真仓三条全绿）+ **合成负例**（版本不一致 /
    /// §9.3 缺步 / 模块表双向差集各一）+ **受控化**（缺 registry.json 给判定而非崩溃）。
    /// </summary>
    private static void CoreRegistryCases(List<Check> checks, string work, string repoRoot)
    {
        // ① 真材料：真仓 ①版本一致 + ②§9.3 四步在场 + ③13 件模块全等（三条都读真件，无合成成分）
        var real = CoreRegistry.Check(repoRoot);
        checks.Add(new Check("check13·真仓（协议版本两处一致 · §9.3 四步齐备 · 模块表 13 件集合全等）",
            real.Ok && real.DocVersion == real.RegVersion && real.DocVersion.Length > 0
            && real.DocRows == CoreRegistry.ExpectedModules && real.RegRows == CoreRegistry.ExpectedModules
            && real.OnlyDoc.Count == 0 && real.OnlyReg.Count == 0,
            $"版本 {real.DocVersion}/{real.RegVersion} · 模块 {real.DocRows}/{real.RegRows} · 步骤 {real.Steps.Count} · 问题 {real.Issues.Count}"));

        var docPath = Path.Combine(repoRoot, CoreRegistry.DocRel);
        var regPath = Path.Combine(repoRoot, CoreRegistry.RegistryRel.Replace('/', Path.DirectorySeparatorChar));
        var docText = File.ReadAllText(docPath);
        var regText = File.ReadAllText(regPath);

        // ② 合成负例 A/B：版本不一致（首位版本号 2 → 1）+ §9.3 迁移关键词缺步（删掉全部「校验回读」行）
        var rootA = Path.Combine(work, "core-registry-version");
        Fresh(rootA);
        var needle = "registry_schema_version: \"2\"";
        var flip = docText.IndexOf(needle, StringComparison.Ordinal);
        var docA = flip >= 0
            ? docText[..flip] + "registry_schema_version: \"1\"" + docText[(flip + needle.Length)..]
            : docText;
        WriteCase(rootA, docA, regText);
        var resA = CoreRegistry.Check(rootA);
        var textA = string.Join(" | ", resA.Issues);
        checks.Add(new Check("check13·合成负例（版本不一致报错：02=\"1\" desktop=\"2\"）",
            !resA.Ok && flip >= 0 && textA.Contains("协议版本不一致：02=\"1\" desktop=\"2\""),
            $"问题 {resA.Issues.Count} · {First(resA)}"));

        var rootB = Path.Combine(work, "core-registry-migration");
        Fresh(rootB);
        var docB = string.Join("\n", docText.Split('\n').Where(l => !l.Contains("校验回读", StringComparison.Ordinal)));
        WriteCase(rootB, docB, regText);
        var resB = CoreRegistry.Check(rootB);
        var textB = string.Join(" | ", resB.Issues);
        checks.Add(new Check("check13·合成负例（§9.3 迁移缺步：删掉「校验回读」后报缺步）",
            !resB.Ok && textB.Contains("迁移记录缺步： 校验回读"),
            $"问题 {resB.Issues.Count} · {First(resB)}"));

        // ③ 合成负例 C/D：模块表双向差集——02 §2 少一行 / registry.json modules 少一个
        var rootC = Path.Combine(work, "core-registry-doc-short");
        Fresh(rootC);
        WriteCase(rootC, DropFirstModuleRow(docText), regText);
        var resC = CoreRegistry.Check(rootC);
        var textC = string.Join(" | ", resC.Issues);
        checks.Add(new Check("check13·合成负例（02 §2 少一行：行数 12 + registry 有而 02 缺）",
            !resC.Ok && resC.DocRows == CoreRegistry.ExpectedModules - 1
            && textC.Contains("02 §2 模块表行数=12")
            && textC.Contains("registry.json 有而 02 缺："),
            $"02 行 {resC.DocRows} · registry 行 {resC.RegRows} · 仅 registry {resC.OnlyReg.Count}"));

        var rootD = Path.Combine(work, "core-registry-reg-short");
        Fresh(rootD);
        var node = System.Text.Json.Nodes.JsonNode.Parse(regText)!;
        var modulesNode = node["modules"]!.AsArray();
        var droppedId = modulesNode[0]!["id"]!.GetValue<string>();
        modulesNode.RemoveAt(0);
        WriteCase(rootD, docText, node.ToJsonString());
        var resD = CoreRegistry.Check(rootD);
        var textD = string.Join(" | ", resD.Issues);
        checks.Add(new Check("check13·合成负例（registry.json 少一个 module：数 12 + 02 有而 registry 缺）",
            !resD.Ok && resD.RegRows == CoreRegistry.ExpectedModules - 1
            && textD.Contains("registry.json modules 数=12")
            && textD.Contains("02 有而 registry.json 缺：" + droppedId),
            $"registry 行 {resD.RegRows} · 仅 02 {resD.OnlyDoc.Count} · 丢 {droppedId}"));

        // ④ 受控化：registry.json 缺件（真源在 json.load 上崩、traceback 进 log；本件给判定）
        var rootE = Path.Combine(work, "core-registry-no-registry");
        Fresh(rootE);
        Directory.CreateDirectory(Path.Combine(rootE, Path.GetDirectoryName(CoreRegistry.RegistryRel)!
            .Replace('/', Path.DirectorySeparatorChar)));
        File.WriteAllText(Path.Combine(rootE, CoreRegistry.DocRel.Replace('/', Path.DirectorySeparatorChar)), docText);
        var resE = CoreRegistry.Check(rootE);
        var textE = string.Join(" | ", resE.Issues);
        checks.Add(new Check("check13·受控化（缺 registry.json 给判定而非崩溃：缺件 + 版本字段缺失）",
            !resE.Ok && textE.Contains("registry.json 缺件")
            && textE.Contains("版本字段缺失") && resE.Steps.Count == 3,
            $"问题 {resE.Issues.Count} · 步骤 {resE.Steps.Count} · {First(resE)}"));
    }

    /// <summary>
    /// 单组自检的**异常围栏**：一组抛异常不该让整套挂掉——此前一处异常会终止整个 Run，
    /// 把其余几百条结果一起藏掉（第八十八～九十片引入多组新钉后踩到）。围栏把异常变成
    /// **一条失败钉**，并带上类型 + 首个 Nf.Engine 栈帧，便于定位。
    /// </summary>
    private static void Safe(List<Check> checks, string group, Action action)
    {
        try
        {
            action();
        }
        catch (Exception exc)
        {
            var frame = (exc.StackTrace ?? "").Split('\n')
                .Select(line => line.Trim())
                .FirstOrDefault(line => line.Contains("Nf.Engine", StringComparison.Ordinal)) ?? "";
            checks.Add(new Check($"{group}·**自检组自身抛异常**（围栏兜住，不静默）", false,
                $"{exc.GetType().Name}：{exc.Message} · {frame}"));
        }
    }

    private static void Fresh(string dir)
    {
        if (Directory.Exists(dir)) Directory.Delete(dir, recursive: true);
        Directory.CreateDirectory(dir);
    }

    /// <summary>
    /// **测量模式判别**：<c>&lt;root&gt;/.git</c> 在场 = **工作区**（内容随提交漂移），不在场 = **导出快照**。
    ///
    /// 为什么需要：本工程的金标摘要**锚定具体 HEAD**（第八十～八十六片的快照 = <c>983741b</c>）。
    /// 导出态断「金标摘要逐字节一致」（最强）；工作区态改断**语义不变量**——拿一份被并发编辑过的
    /// 语料去比死摘要，只会把「语料漂了」误报成「引擎错了」（第八十六片实测：一键门直接打活仓库时
    /// 文档命令面与扩展策略面各红一条，而两者都只是 HEAD 前移/带 .git 所致）。
    /// </summary>
    private static bool IsPinnedSnapshot(string root) => !Directory.Exists(Path.Combine(root, ".git"));

    private static void WriteCase(string root, string doc, string registryJson)
    {
        File.WriteAllText(Path.Combine(root, CoreRegistry.DocRel.Replace('/', Path.DirectorySeparatorChar)),
            doc, new UTF8Encoding(false));
        var reg = Path.Combine(root, CoreRegistry.RegistryRel.Replace('/', Path.DirectorySeparatorChar));
        Directory.CreateDirectory(Path.GetDirectoryName(reg)!);
        File.WriteAllText(reg, registryJson, new UTF8Encoding(false));
    }

    /// <summary>在 02 §2 段内删掉第一条模块行（真源口径：5 格、首格非表头非分隔线）。</summary>
    private static string DropFirstModuleRow(string doc)
    {
        var start = doc.IndexOf("## 2. 官方核心模块表", StringComparison.Ordinal);
        if (start < 0) return doc;
        var end = doc.IndexOf("\n## 3.", start, StringComparison.Ordinal);
        if (end < 0) return doc;
        var segment = doc[start..end];
        var lines = segment.Split('\n').ToList();
        for (var i = 0; i < lines.Count; i++)
        {
            var cells = lines[i].Trim().Trim('|').Split('|').Select(c => c.Trim()).ToList();
            if (cells.Count == 5 && cells[0] != "模块ID" && cells[0] != "---" && cells[0].Length > 0)
            {
                lines.RemoveAt(i);
                break;
            }
        }
        return doc[..start] + string.Join("\n", lines) + doc[(start + segment.Length)..];
    }

    private static string First(CoreRegistry.Result result) =>
        result.Issues.Count > 0 ? result.Issues[0] : (result.Steps.Count > 0 ? result.Steps[0].Detail : "");

    private static void MarketCases(List<Check> checks)
    {
        // ①' 包视图三件：闭包（叶越界 / 嵌套 references / 源包不可读）· 挂载冲突 · 登记三要件
        var pkgProts = new Dictionary<string, Dictionary<string, object?>>(StringComparer.Ordinal)
        {
            ["组合包"] = new(StringComparer.Ordinal)
            {
                ["module_ids"] = new List<object?> { "合成:M01" },
                ["references"] = new List<object?>
                {
                    new Dictionary<string, object?>(StringComparer.Ordinal)
                    {
                        ["source_package"] = "源包", ["module_id"] = "源:M07",
                    },
                    new Dictionary<string, object?>(StringComparer.Ordinal)
                    {
                        ["source_package"] = "幽灵包", ["module_id"] = "M09",
                    },
                },
            },
        };
        var data = new Dictionary<string, Dictionary<string, object?>>(StringComparer.Ordinal)
        {
            ["组合包"] = new(StringComparer.Ordinal)
            {
                ["package"] = new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["id"] = "组合包",
                    ["dependencies"] = new Dictionary<string, object?>(StringComparer.Ordinal)
                    {
                        ["core_modules"] = new List<object?> { "M00" },
                    },
                    ["mount_layers"] = new Dictionary<string, object?>(StringComparer.Ordinal)
                    {
                        ["P40 行为决策"] = new Dictionary<string, object?>(StringComparer.Ordinal)
                        {
                            ["default"] = new List<object?> { "组合:M01" },
                        },
                    },
                },
            },
            ["源包"] = new(StringComparer.Ordinal)
            {
                ["package"] = new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["id"] = "源包",
                    ["dependencies"] = new Dictionary<string, object?>(StringComparer.Ordinal)
                    {
                        ["core_modules"] = new List<object?> { "M00", "M99" },   // M99 越界官方 13
                    },
                    ["references"] = new List<object?>                                    // 嵌套 references
                    {
                        new Dictionary<string, object?>(StringComparer.Ordinal)
                        {
                            ["source_package"] = "幽灵包", ["module_id"] = "M09",
                        },
                    },
                    ["mount_layers"] = new Dictionary<string, object?>(StringComparer.Ordinal)
                    {
                        ["P40 行为约束"] = new Dictionary<string, object?>(StringComparer.Ordinal)
                        {
                            ["default"] = new List<object?> { "组合:M01" },       // 同层 default 冲突
                        },
                    },
                },
            },
        };
        var (seen, depIssues) = MarketAnalyzer.Dependencies("组合包", pkgProts, data);
        var conflicts = MarketAnalyzer.Conflicts("组合包", pkgProts, data);
        var depJoined = string.Join(" | ", depIssues);
        checks.Add(new Check("包视图·依赖闭包与挂载冲突（叶越界 / 嵌套 references / 源包不可读 / 同层 default 冲突）",
            seen.Contains("源包") && depJoined.Contains("叶节点越界官方核心 13 件: M99")
            && depJoined.Contains("源包嵌套 references") && depJoined.Contains("源包不可读: 幽灵包")
            && conflicts.Count == 1 && conflicts[0].Contains("挂载层 P40 default 冲突"),
            $"闭包源 {seen.Count} · 依赖问题 {depIssues.Count} 条 · 冲突 {conflicts.Count} 条"));

        // ①'' 登记三要件：缺件 / 缺 package 段 / 02 §8 未在册
        var tmp = Path.Combine(Path.GetTempPath(), "nf-market-fix-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(tmp);
        var missing = MarketAnalyzer.CheckRegisterable(Path.Combine(tmp, "不存在"), "### 8.1 x\n## 9. y\n");
        var noPkgDir = Path.Combine(tmp, "无package");
        Directory.CreateDirectory(noPkgDir);
        File.WriteAllText(Path.Combine(noPkgDir, "protocol.yaml"), "protocol:\n  schema_version: \"2\"\n");
        var noPkg = MarketAnalyzer.CheckRegisterable(noPkgDir, "### 8.1 x\n## 9. y\n");
        var pkgDir = Path.Combine(tmp, "未在册");
        Directory.CreateDirectory(pkgDir);
        File.WriteAllText(Path.Combine(pkgDir, "protocol.yaml"),
            "protocol:\n  schema_version: \"2\"\npackage:\n  id: 未在册包\n");
        var notRegistered = MarketAnalyzer.CheckRegisterable(pkgDir, "### 8.1 别的包\n## 9. y\n");
        checks.Add(new Check("包视图·登记三要件（缺件 / 缺 package 段 / 不在 02 §8 在册）",
            missing.Any(x => x.Contains("protocol.yaml 缺失")) && noPkg.Any(x => x.Contains("缺 package 段"))
            && notRegistered.Any(x => x.Contains("不在 02 §8 在册")),
            $"缺件={missing.Count} · 缺段={noPkg.Count} · 未在册={notRegistered.Count} 条问题"));
        try { Directory.Delete(tmp, recursive: true); } catch (IOException) { /* 清理失败不影响判定（best-effort 显式忽略） */ }

        // ① 分级：官方 13 件比**完整 id**（事件:M22 官方 vs 情感:M22 社区同号段）；M91-M99 按裸号判实验（best-effort 显式忽略）
        var grades = new (string Id, string Want)[]
        {
            ("M50", "official"), ("事件:M22", "official"), ("情感:M22", "community"),
            ("通用:M10", "official"), ("M91", "experimental"), ("甲:M91", "experimental"),
            ("甲:M01", "community"),
        };
        var gradeOk = grades.All(g => MarketAnalyzer.GradeOfModule(g.Id) == g.Want);
        checks.Add(new Check("市场分级·官方比完整 id（同号段前缀不误判）+ M91-M99 实验段",
            gradeOk,
            string.Join(" · ", grades.Select(g => $"{g.Id}→{MarketAnalyzer.GradeOfModule(g.Id)}"))));

        // ② 目录视图：模块先、包后；包级 grading（全实验段 → experimental）；tier 过滤
        var reg = PythonJson.ToGraph(System.Text.Json.JsonDocument.Parse("""
        {"modules": [{"id": "M00", "name": "数据结构"}],
         "protocols": [
           {"id": "实验包", "name": "实验", "module_ids": ["甲:M91", "甲:M92"]},
           {"id": "社区包", "name": "社区", "version": "3.1.0", "module_ids": ["M01"]}]}
        """).RootElement) as Dictionary<string, object?>;
        var all = MarketAnalyzer.ListMarket(reg!);
        var experimental = MarketAnalyzer.ListMarket(reg!, "experimental");
        checks.Add(new Check("市场目录·全量顺序与分级 + tier 过滤（全实验段包 → experimental）",
            all.Count == 3
            && (all[0].GetValueOrDefault("kind") as string) == "module"
            && (all[0].GetValueOrDefault("grade") as string) == "official"
            && (all[1].GetValueOrDefault("grade") as string) == "experimental"
            && (all[2].GetValueOrDefault("version") as string) == "3.1.0"
            && experimental.Count == 1 && (experimental[0].GetValueOrDefault("id") as string) == "实验包",
            $"全量 {all.Count} 项（{string.Join("/", all.Select(x => x.GetValueOrDefault("grade")))}）· " +
            $"tier=experimental → {experimental.Count} 项"));

        // ③ See-Also：包目标（refs + 模块依赖图命中 + 反向引用方）与模块目标
        var prots = MarketAnalyzer.Protocols(reg!);
        var graph = new Dictionary<string, HashSet<string>>(StringComparer.Ordinal)
        {
            ["M01"] = new(StringComparer.Ordinal) { "M00" },
        };
        var asPackage = MarketAnalyzer.RelatedOf("社区包", prots, graph, null);
        var asModule = MarketAnalyzer.RelatedOf("M00", prots, graph, null);
        var pkgRefs = (asPackage.GetValueOrDefault("refs") as List<object?> ?? new List<object?>()).Count;
        checks.Add(new Check("See-Also·包/模块两态（依赖图注入：模块 M01→M00 形成互见）",
            (asPackage.GetValueOrDefault("kind") as string) == "package" && pkgRefs >= 1
            && (asModule.GetValueOrDefault("kind") as string) == "module"
            && (asModule.GetValueOrDefault("referenced_by") as List<object?> ?? new List<object?>()).Count >= 1,
            $"包态 refs={pkgRefs} · 模块态反向引用=" +
            $"{(asModule.GetValueOrDefault("referenced_by") as List<object?>)?.Count}"));
    }
}
