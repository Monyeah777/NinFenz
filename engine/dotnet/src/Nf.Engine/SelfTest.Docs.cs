using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text;
using System.Text.RegularExpressions;

namespace Nf.Engine;

/// <summary>文档型 / 数字与 YAML 边界 / 治理 / 端点 / 机读契约 / 知识层负例。</summary>
public static partial class SelfTest
{
    // ------------------------------------------------------ ⑦ 文档四型（镜像表自洽）

    /// <summary>
    /// `doc-kinds` 的三张表是从 <c>core/doc_hygiene.py</c> 机械导出的镜像——最容易出的错是
    /// **抄漏/抄歪**（漏一件、型名打错）。这两条钉住镜像本身的健康：清单内每件都必须有合法归属；
    /// 缺件只跳过、不误报。表若漂移，双跑对账会立刻报不一致。
    /// </summary>
    private static void DocKindCases(List<Check> checks, string work)
    {
        checks.Add(Guarded("文档四型·镜像表自洽（清单内每件都有合法归属）", () =>
        {
            var issues = DocHygiene.KindCoverage(work);
            return (issues.Count == 0,
                issues.Count == 0
                    ? $"清单内 {DocHygiene.CoveredCount} 件四型归属齐（取值 {string.Join("/", DocHygiene.KindVocabulary)}）"
                    : string.Join("; ", issues.Take(2)));
        }));

        var empty = Path.Combine(work, "dockinds-empty");
        Directory.CreateDirectory(empty);
        checks.Add(Guarded("文档四型·缺件不误报（写法判据只判在盘件）", () =>
        {
            var warns = DocHygiene.KindRulesFor(empty);
            return (warns.Count == 0, $"空树上 WARN {warns.Count} 条");
        }));
    }

    // ------------------------------------- ⑧ 数字保真 + YAML 子集语义（今日抓到的真 bug）

    /// <summary>
    /// 三条钉，全部来自本轮实测暴露的缺陷：
    /// ① JSON 整数被三元表达式**静默转成浮点**（`cond ? long : double` 会统一成 double），
    ///    以前被「1.0 渲染成 1」掩盖——现在整数必须仍是整数、浮点必须带小数点（Python repr 形态）；
    /// ② YAML 标量定型按 PyYAML：`3`→int、`true`→bool、`010`→八进制 8、`2026-09-08`→date、
    ///    `2026-9-8`→字符串（PyYAML 的纯日期要求两位月日）；
    /// ③ YAML 结构语义：非空流映射、序列项是映射、带引号的键、键里含冒号（`通用:M10: untyped`）。
    /// </summary>
    private static void NumberAndYamlCases(List<Check> checks)
    {
        checks.Add(Guarded("数字保真·JSON 整数不转浮点、浮点按 Python repr 写", () =>
        {
            using var doc = JsonIo.Parse("{\"i\":1,\"big\":1234567890123,\"f\":1.0,\"g\":1e16,\"h\":1e-5}");
            var text = PythonJson.Compact(PythonJson.ToGraph(doc.RootElement));
            const string expected = "{\"big\":1234567890123,\"f\":1.0,\"g\":1e+16,\"h\":1e-05,\"i\":1}";
            return (text == expected, text == expected ? text : $"期望 {expected} 实得 {text}");
        }));

        checks.Add(Guarded("YAML·标量定型对齐 PyYAML（int/bool/八进制/日期/伪日期）", () =>
        {
            var map = MiniYaml.Parse("a: 3\nb: true\nc: 010\nd: 2026-09-08\ne: 2026-9-8\nf: 1.0e5\n");
            var detail = $"a={PyScalar.TypeName(map["a"])} b={PyScalar.TypeName(map["b"])} " +
                         $"c={map["c"]} d={PyScalar.TypeName(map["d"])} e={map["e"]} f={PyScalar.TypeName(map["f"])}";
            var ok = map["a"] is 3L && map["b"] is true && map["c"] is 8L
                     && map["d"] is PyScalar.Timestamp { Kind: "date" } && map["e"] is "2026-9-8"
                     && map["f"] is "1.0e5";     // PyYAML 的指数要求显式符号，无符号仍是字符串
            return (ok, detail);
        }));

        checks.Add(Guarded("YAML·结构语义（流映射 / 映射序列项 / 引号键 / 键含冒号）", () =>
        {
            var flow = MiniYaml.Parse("layers:\n  P40: {default: [M01], available: []}\n");
            var seq = MiniYaml.Parse("mods:\n  - id: \"M01\"\n    desc: 甲\n  - id: \"M02\"\n");
            var quoted = MiniYaml.Parse("io:\n  'P:M01': untyped\n");
            var colonKey = MiniYaml.Parse("io:\n  通用:M10: untyped\n");
            var flowOk = flow["layers"] is Dictionary<string, object?> layer
                         && layer["P40"] is Dictionary<string, object?> entry
                         && entry["default"] is List<object?> def && def.Count == 1 && (string?)def[0] == "M01"
                         && entry["available"] is List<object?> avail && avail.Count == 0;
            var seqOk = seq["mods"] is List<object?> mods && mods.Count == 2
                        && mods[0] is Dictionary<string, object?> first && (string?)first["id"] == "M01"
                        && (string?)first["desc"] == "甲"
                        && mods[1] is Dictionary<string, object?> second && (string?)second["id"] == "M02";
            var quotedOk = quoted["io"] is Dictionary<string, object?> qi && qi.ContainsKey("P:M01");
            var colonKeyOk = colonKey["io"] is Dictionary<string, object?> qc
                             && qc.ContainsKey("通用:M10") && (string?)qc["通用:M10"] == "untyped";
            var ok = flowOk && seqOk && quotedOk && colonKeyOk;
            return (ok, $"流映射={flowOk} 映射序列项={seqOk} 引号键={quotedOk} 键含冒号={colonKeyOk}");
        }));
    }

    // ------------------------------------------- ⑨ IDL 子集校验器（schema-clean）

    /// <summary>
    /// `schema-clean` 的判据是「自实现 JSON-Schema 子集」——最容易出错的两处：
    /// ① **子集越界不许静默忽略**（白名单外的关键字必须 FAIL，否则就是假绿）；
    /// ② 未知字段 / 枚举 / 键名模式这些分支要真的报，且报的文案与 Python 同形。
    /// 另钉一条：缺 `protocol/schema/` 目录时报「未落盘」，不是空过。
    /// </summary>
    private static void SchemaLintCases(List<Check> checks, string work)
    {
        var schema = MiniYaml.Parse(string.Join("\n", new[]
        {
            "type: object",
            "additionalProperties: false",
            "propertyNames: {pattern: '^[a-z_]+$', type: string}",
            "required: [id]",
            "properties:",
            "  id: {type: string, enum: [M01, M02]}",
        }));

        checks.Add(Guarded("IDL·未知字段与键名模式都要报（不许静默放过）", () =>
        {
            var instance = MiniYaml.Parse("id: M01\nBadKey: 1\n");
            var issues = SchemaLint.SubsetValidate(instance, schema, "x");
            var unknown = issues.Any(i => i.Contains("未知字段 BadKey", StringComparison.Ordinal));
            var badKey = issues.Any(i => i.Contains("（键名）", StringComparison.Ordinal));
            return (unknown && badKey, string.Join(" | ", issues));
        }));

        checks.Add(Guarded("IDL·枚举与必填都要报", () =>
        {
            var issues = SchemaLint.SubsetValidate(MiniYaml.Parse("id: M99\n"), schema, "x");
            var enumHit = issues.Any(i => i.Contains("不在枚举", StringComparison.Ordinal));
            var required = SchemaLint.SubsetValidate(MiniYaml.Parse("other: 1\n"), schema, "x");
            var missing = required.Any(i => i.Contains("缺必填字段 id", StringComparison.Ordinal));
            return (enumHit && missing, string.Join(" | ", issues.Concat(required)));
        }));

        checks.Add(Guarded("IDL·子集越界关键字必须报（防假绿）", () =>
        {
            var beyond = MiniYaml.Parse("type: object\noneOf: []\nproperties:\n  a: {type: string, format: email}\n");
            var issues = SchemaLint.SubsetKeyViolations(beyond, "s.schema.json");
            var oneOf = issues.Any(i => i.Contains("未实现的关键字 oneOf", StringComparison.Ordinal));
            var nested = issues.Any(i => i.Contains("properties/a", StringComparison.Ordinal)
                                         && i.Contains("format", StringComparison.Ordinal));
            return (issues.Count == 2 && oneOf && nested, string.Join(" | ", issues));
        }));

        var bare = Path.Combine(work, "schema-empty");
        Directory.CreateDirectory(bare);
        checks.Add(Guarded("IDL·缺 protocol/schema/ 判「未落盘」而非空过", () =>
        {
            var result = SchemaLint.Scan(bare);
            var hit = result.Issues.Any(i => i.Contains("协议层 IDL 未落盘", StringComparison.Ordinal));
            return (hit, string.Join(" | ", result.Issues.Take(2)));
        }));
    }

    // ------------------------------------------- ⑩ 治理族契约（声明 / 排布 / 包装 / 制卡）

    /// <summary>
    /// 四件治理契约各钉一条**该红的必须红**（都取自差分模糊里已实测同判的变异形态）：
    /// ① 条件先行：状态块没前置；
    /// ② 一致性声明：排除项与 scope 重叠（同一条不能既在范围又排除）；
    /// ③ 包装声明：声明工具面与运行时不一致（上架材料会漂移）；
    /// ④ ST 制卡：V2 初始值含未声明变量。
    /// </summary>
    private static void GovernanceCases(List<Check> checks, string work)
    {
        checks.Add(Guarded("治理·条件先行：状态块未前置必须报（且只报这一条）", () =>
        {
            var bad = StateFront.CheckOrder("# 件\n\n## 资料\n\n## 状态块（条件先行摘要）\n\n正文\n");
            var good = StateFront.CheckOrder("# 件\n\n## 状态块（条件先行摘要）\n\n## 资料\n");
            return (bad.Count == 1 && bad[0].Contains("状态块未前置", StringComparison.Ordinal) && good.Count == 0,
                $"bad={string.Join("|", bad)} · good={good.Count} 条");
        }));

        var declRoot = Path.Combine(work, "gov-decl");
        WriteFile(declRoot, "protocol/CONFORMANCE.md", string.Join("\n", new[]
        {
            "# 一致性声明", "", "## 声明", "",
            "| 规范 | 版本 | 真源 |", "|---|---|---|",
            "| IDL schema 集 | `0 件` | protocol/schema/ |", "",
            "## 范围", "", "- `明示目录`", "",
            "## 排除", "", "| 路径 | 理由 |", "|---|---|",
            "| `明示目录/子件` | 重叠用例 |", "",
        }));
        checks.Add(Guarded("治理·声明：排除项与 scope 重叠必须报", () =>
        {
            var (issues, _) = ConformanceDecl.Scan(declRoot);
            var hit = issues.FirstOrDefault(i => i.Contains("scope 与排除重叠", StringComparison.Ordinal));
            return (hit is not null, hit ?? $"未报重叠（共 {issues.Count} 条问题）");
        }));

        var mcpRoot = Path.Combine(work, "gov-mcp");
        WriteFile(mcpRoot, "protocol/mcp_package.json", string.Join("\n", new[]
        {
            "{",
            "  \"schema\": \"nf-mcp-package/1\",",
            "  \"status\": \"active\",",
            "  \"category_vocabulary\": [\"content-creation\", \"developer-tools\", \"knowledge-management\"],",
            "  \"red_lines\": [\"只读\"],",
            "  \"package\": {",
            "    \"name_candidates\": [\"甲\"], \"one_liner_candidates\": [\"乙\"],",
            "    \"category\": \"content-creation\", \"targets\": [],",
            "    \"tools\": [\"pipeline_list\"], \"prompts\": [\"assemble_guide\"]",
            "  }",
            "}",
        }) + "\n");
        checks.Add(Guarded("治理·包装声明：工具面与运行时不一致必须报", () =>
        {
            var (ok, detail) = McpPackage.Contract(mcpRoot);
            return (!ok && detail.Contains("工具面与运行时不一致", StringComparison.Ordinal), detail);
        }));

        var stqRoot = Path.Combine(work, "gov-stq");
        WriteFile(stqRoot, "docs/examples/mvu-output/mvu_variables.json",
            "{\"variables\": [{\"name\": \"甲\"}], \"initial\": {\"甲\": 0, \"幽灵变量\": 1}}\n");
        checks.Add(Guarded("治理·ST 制卡：V2 初始值含未声明变量必须报", () =>
        {
            using var doc = JsonIo.ReadFile(Path.Combine(stqRoot, "docs/examples/mvu-output/mvu_variables.json"));
            var graph = (Dictionary<string, object?>)PythonJson.ToGraph(doc.RootElement)!;
            var names = ((List<object?>)graph["variables"]!).Cast<Dictionary<string, object?>>()
                .Select(v => (string)v["name"]!).ToHashSet(StringComparer.Ordinal);
            var initial = (Dictionary<string, object?>)graph["initial"]!;
            var extra = initial.Keys.Where(k => !names.Contains(k)).OrderBy(k => k, StringComparer.Ordinal).ToList();
            return (extra.Count == 1 && extra[0] == "幽灵变量",
                $"未声明变量={string.Join("、", extra)}（V2 判据：initial 键须 ⊆ 变量名集）");
        }));
    }

    // ------------------------------- ⑪ 治理文档族（接力 / 复盘 / 审计）

    /// <summary>
    /// 三件治理文档契约各钉一条核心判据（都取自差分模糊里已实测同判的变异形态）：
    /// ① 接力：未决项缺「判据」必须报（空未决 = 不合格交接的姊妹条款）；
    /// ② 复盘：命中指责词必须报，且根因段不含机制词也要报（对事不对人 + 指向机制）；
    /// ③ 审计：被审对象 digest 一变，旧审计立即失效。
    /// </summary>
    private static void GovernanceDocCases(List<Check> checks, string work)
    {
        var hoRoot = Path.Combine(work, "gov-ho");
        WriteFile(hoRoot, "verify.sh", "check35(){\n  :\n}\n");
        WriteFile(hoRoot, "protocol/handover.json", string.Join("\n", new[]
        {
            "{", "  \"schema\": \"nf-handover/1\",",
            "  \"sections\": [\"情境\", \"背景\", \"评估\", \"建议\", \"未决项\"],",
            "  \"required_fields\": [\"id\", \"date\", \"from\", \"to\", \"status\", \"refs\"],",
            "  \"status_vocabulary\": [\"open\", \"closed\"],", "  \"rules\": [\"规矩\"]", "}", "",
        }));
        WriteFile(hoRoot, "handovers/HO-9999-用例.md", string.Join("\n", new[]
        {
            "---", "id: HO-9999", "date: 2026-09-26", "from: 甲", "to: 乙", "status: open",
            "refs:", "  - verify.sh", "---", "",
            "## 情境", "", "## 背景", "", "## 评估", "", "## 建议", "",
            "## 未决项", "", "- 待办一（说明：怎么算完）", "",
        }));
        checks.Add(Guarded("治理·接力：未决项缺「判据」必须报（空未决/无判据同一纪律）", () =>
        {
            var (issues, stats) = Handover.CheckDoc(hoRoot, "handovers/HO-9999-用例.md");
            var hit = issues.FirstOrDefault(i => i.Contains("未决项缺判据", StringComparison.Ordinal));
            return (hit is not null && stats["pending"] is 1,
                hit ?? $"未报缺判据（共 {issues.Count} 条问题 · pending={stats.GetValueOrDefault("pending")}）");
        }));

        var poRoot = Path.Combine(work, "gov-po");
        WriteFile(poRoot, "verify.sh", "check35(){\n  :\n}\n");
        WriteFile(poRoot, "protocol/postmortem.json", string.Join("\n", new[]
        {
            "{", "  \"schema\": \"nf-postmortem/1\",",
            "  \"sections\": [\"现象\", \"影响\", \"根因\", \"行动项\"],",
            "  \"required_fields\": [\"id\", \"date\", \"trigger\", \"status\", \"refs\"],",
            "  \"status_vocabulary\": [\"open\", \"closed\"],",
            "  \"blame_tokens\": [\"个人失误\"], \"root_cause_tokens\": [\"机制\", \"流程\"],",
            "  \"rules\": [\"规矩\"]", "}", "",
        }));
        WriteFile(poRoot, "postmortems/PO-9999-用例.md", string.Join("\n", new[]
        {
            "---", "id: PO-9999", "date: 2026-09-26", "trigger: check35", "status: open",
            "refs:", "  - verify.sh", "---", "",
            "## 现象", "", "甲。", "## 影响", "", "乙（个人失误。）。", "## 根因", "",
            "丙（沟通不畅。）。", "## 行动项", "",
            "- 修一：**负责人** = 甲；**判据** = 绿。", "",
        }));
        checks.Add(Guarded("治理·复盘：指责词与「根因未指向机制」都必须报", () =>
        {
            var (issues, _) = Postmortem.CheckDoc(poRoot, "postmortems/PO-9999-用例.md");
            var blame = issues.Any(i => i.Contains("命中指责性归因词", StringComparison.Ordinal));
            var root = issues.Any(i => i.Contains("根因段未指向机制", StringComparison.Ordinal));
            return (blame && root, string.Join(" | ", issues));
        }));

        var auditRoot = Path.Combine(work, "gov-audit");
        WriteFile(auditRoot, "protocol/audit.json", string.Join("\n", new[]
        {
            "{", "  \"schema\": \"nf-audit/1\",",
            "  \"required_fields\": [\"id\", \"date\", \"scope\", \"verdict\", \"auditor\", \"subjects\"],",
            "  \"verdict_vocabulary\": [\"pass\", \"fail\", \"warn\"],", "  \"rules\": [\"规矩\"]", "}", "",
        }));
        WriteFile(auditRoot, "target.md", "原样\n");
        var digest = Convert.ToHexString(
            System.Security.Cryptography.SHA256.HashData(
                System.Text.Encoding.UTF8.GetBytes("原样\n"))).ToLowerInvariant();
        WriteFile(auditRoot, "results/audit/AUD-9999-用例.md", string.Join("\n", new[]
        {
            "---", "id: AUD-9999", "date: 2026-09-26", "scope: 用例", "verdict: pass",
            "auditor: 甲", "subjects:", $"  - target.md:{digest}", "---", "", "正文。", "",
        }));
        checks.Add(Guarded("治理·审计：对象一改旧审计立即失效（digest 绑定）", () =>
        {
            var clean = Audit.CheckDoc(auditRoot, "results/audit/AUD-9999-用例.md");
            WriteFile(auditRoot, "target.md", "改过了\n");
            var dirty = Audit.CheckDoc(auditRoot, "results/audit/AUD-9999-用例.md");
            var ok = clean.Issues.Count == 0
                     && dirty.Issues.Any(i => i.Contains("被审对象已变，旧审计失效", StringComparison.Ordinal));
            return (ok, $"干净={clean.Issues.Count} 条 · 改动后={string.Join(" | ", dirty.Issues)}");
        }));
    }

    // ------------------------------------------- ⑫ 端点契约（契约不许指向空气）

    /// <summary>
    /// 端点契约的核心是「**不许指向空气**」：`maps_to` 必须指向现存 CLI 子命令或 MCP 工具；
    /// 另外幂等语义**不许沉默**（重试安全的前提）。两条钉都用合成树，CLI 注册表现扫 <c>scripts/nf.py</c>。
    /// </summary>
    private static void EndpointCases(List<Check> checks, string work)
    {
        var root = Path.Combine(work, "endpoint");
        WriteFile(root, "scripts/nf.py", "sub.add_parser(\"assemble\", help=\"…\")\nsub.add_parser(\"bench\", help=\"…\")\n");
        WriteFile(root, "protocol/endpoint_contract.json", string.Join("\n", new[]
        {
            "{",
            "  \"schema\": \"nf-endpoint/1\", \"status\": \"proposed\",",
            "  \"conventions\": {\"streaming\": \"SSE\", \"idempotency\": \"默认幂等\"},",
            "  \"endpoints\": [",
            "    {\"id\": \"a.plan\", \"method\": \"POST\", \"path\": \"/a/plan\", \"maps_to\": \"nf assemble\"},",
            "    {\"id\": \"bad\", \"method\": \"POST\", \"path\": \"/bad\", \"maps_to\": \"nf 不存在的命令\"}",
            "  ]",
            "}", "",
        }));
        checks.Add(Guarded("端点契约·maps_to 指向不存在的 CLI 子命令必须报（不许指向空气）", () =>
        {
            var (issues, _, stats) = EndpointContract.Scan(root);
            var hit = issues.FirstOrDefault(i => i.Contains("无法解析为现存 CLI 子命令或 MCP 工具", StringComparison.Ordinal));
            return (hit is not null && stats["cli_commands"] is 2, hit ?? $"未报（CLI 表 {stats.GetValueOrDefault("cli_commands")} 条）");
        }));

        WriteFile(root, "protocol/endpoint_contract.json", string.Join("\n", new[]
        {
            "{",
            "  \"schema\": \"nf-endpoint/1\", \"status\": \"proposed\",",
            "  \"conventions\": {\"streaming\": \"SSE\"},",
            "  \"endpoints\": [",
            "    {\"id\": \"a.plan\", \"method\": \"POST\", \"path\": \"/a/plan\", \"maps_to\": \"nf assemble\"}",
            "  ]",
            "}", "",
        }));
        checks.Add(Guarded("端点契约·幂等语义沉默必须报（重试安全的前提）", () =>
        {
            var (issues, _, _) = EndpointContract.Scan(root);
            var hit = issues.FirstOrDefault(i => i.Contains("未声明幂等语义", StringComparison.Ordinal));
            return (hit is not null, hit ?? "未报幂等沉默");
        }));
    }

    // --------------------------------- ⑬ 机读契约族（边界签名 / 事件背书）

    /// <summary>
    /// 两组判据各自的**两个方向**都要钉：
    /// ① 模块边界签名——改了边界字段必须报漂移；**只改非边界文本（name/description）不该报**
    ///    （否则"冻结"会变成"任何改动都红"的噪音门）；
    /// ② 事件背书——订阅无人发布必须 FAIL；登记进外部通道后只 WARN；跨包发布只 WARN（不把跨包当断链）。
    /// </summary>
    private static void MachineContractCases(List<Check> checks, string work)
    {
        var root = Path.Combine(work, "machine-contract");
        WriteFile(root, "04_模块库/世界类/M90_用例.md", ModuleDoc("M90", "  inputs: [通用:M10]"));
        var digest = ModuleSignature.Signatures(root)["M90"].Digest;
        WriteFile(root, "protocol/module_signatures.json", string.Join("\n", new[]
        {
            "{", "  \"schema\": \"nf-module-signatures/1\", \"count\": 1,",
            "  \"modules\": {", $"    \"M90\": {{\"digest\": \"{digest}\", \"path\": \"04_模块库/世界类/M90_用例.md\"}}",
            "  }", "}", "",
        }));

        checks.Add(Guarded("机读契约·边界字段一变即报漂移（冻结纪律）", () =>
        {
            WriteFile(root, "04_模块库/世界类/M90_用例.md", ModuleDoc("M90", "  inputs: [通用:M99]"));
            var (issues, _, _) = ModuleSignature.Verify(root);
            var hit = issues.FirstOrDefault(i => i.Contains("边界漂移：M90", StringComparison.Ordinal));
            return (hit is not null, hit ?? "未报边界漂移");
        }));

        checks.Add(Guarded("机读契约·只改非边界文本不该报漂移（边界只取七字段）", () =>
        {
            WriteFile(root, "04_模块库/世界类/M90_用例.md",
                ModuleDoc("M90", "  inputs: [通用:M10]").Replace("  name: 用例\n", "  name: 用例（改名）\n"));
            var (issues, _, _) = ModuleSignature.Verify(root);
            return (issues.Count == 0, issues.Count == 0 ? "改名后仍零漂移" : string.Join(" | ", issues));
        }));

        var eventRoot = Path.Combine(work, "machine-events");
        WriteFile(eventRoot, "04_模块库/世界类/M90_用例.md",
            ModuleDoc("M90", "  inputs: []\n  events:\n    publish: []\n    subscribe: [幽灵事件]"));
        checks.Add(Guarded("机读契约·订阅无人发布即 FAIL；登记外部通道后只 WARN", () =>
        {
            var (issues, _, _) = EventBacking.Scan(eventRoot);
            var hard = issues.Any(i => i.Contains("事件背书缺口：幽灵事件", StringComparison.Ordinal));
            WriteFile(eventRoot, "protocol/external_events.json",
                "{\"schema\": \"nf-external-events/1\", \"events\": {\"幽灵事件\": {\"why\": \"外部通道\"}}}\n");
            var (issues2, warns2, _) = EventBacking.Scan(eventRoot);
            var still = issues2.Any(i => i.Contains("事件背书缺口", StringComparison.Ordinal));
            var allowWarn = warns2.Any(w => w.Contains("已挂账为外部通道", StringComparison.Ordinal));
            return (hard && !still && allowWarn,
                $"未挂账=FAIL {hard} · 挂账后无 FAIL {!still} · 有挂账 WARN {allowWarn}");
        }));
    }

    /// <summary>合成模块文档（machine_contract 围栏；<paramref name="extra"/> 追加边界字段）。</summary>
    private static string ModuleDoc(string id, string extra) => string.Join("\n", new[]
    {
        "---", $"id: {id}", "title: 用例", "---", "",
        "```yaml", "machine_contract:", "  schema: \"1\"", $"  id: {id}", "  name: 用例",
        "  category: 世界", "  layer: P40", extra, "  outputs: []", "  interfaces: []", "```", "",
    });

    // -------------------------------------- ⑭ 类型积压台账（防"台账当装饰"）

    /// <summary>
    /// 台账纪律的两面都要钉：**untyped 必须带 note**（不许无声增长），
    /// **在盘台账必须等于实时重算**（改一处类型而不同步台账 → 立刻判过期）。
    /// </summary>
    private static void TypeBacklogCases(List<Check> checks, string work)
    {
        var root = Path.Combine(work, "type-backlog");
        Registry(root, "untyped", "正文证据字段名；类型待核");
        WriteFile(root, "protocol/type_backlog.json", "{\"schema\": \"nf-type-backlog/1\", \"count\": 1}\n");
        checks.Add(Guarded("类型积压·台账与实时重算一致时零问题（正向对照）", () =>
        {
            var (issues, stats) = TypeBacklog.VerifyBacklog(root);
            return (issues.Count == 0 && stats["untyped"] is 1,
                issues.Count == 0 ? $"untyped {stats["untyped"]} 项 · 台账同步" : string.Join(" | ", issues));
        }));

        checks.Add(Guarded("类型积压·untyped 缺 note 即 FAIL（无声增长）", () =>
        {
            Registry(root, "untyped", "");
            var (issues, _) = TypeBacklog.VerifyBacklog(root);
            var hit = issues.FirstOrDefault(i => i.Contains("无声增长", StringComparison.Ordinal));
            return (hit is not null, hit ?? "未报无声增长");
        }));

        checks.Add(Guarded("类型积压·类型被收窄但台账未同步 → 判过期（台账不当装饰）", () =>
        {
            Registry(root, "string", "已收窄");
            var (issues, stats) = TypeBacklog.VerifyBacklog(root);
            var hit = issues.FirstOrDefault(i => i.Contains("台账过期", StringComparison.Ordinal));
            return (hit is not null && stats["untyped"] is 0, hit ?? "未报台账过期");
        }));
    }

    /// <summary>合成事件注册表（单事件单字段）。</summary>
    private static void Registry(string root, string type, string note)
        => WriteFile(root, "protocol/event_registry.json", string.Join("\n", new[]
        {
            "{", "  \"events\": {", "    \"ev_one\": {",
            "      \"fields\": { \"field_a\": {",
            $"        \"type\": \"{type}\", \"note\": \"{note}\"", "      } }", "    }", "  }", "}", "",
        }));

    // ------------------------------- ⑮ I/O 类型面（可证才判，未收窄只 WARN）

    /// <summary>
    /// 类型面的判据是**只判可证的**：取值越词表、消费方期望的产物类型提供方没声明 → FAIL；
    /// 而 io_types.outputs 与 outputs 键集不一致、整块未标 → 只 WARN。两个方向都要钉，
    /// 否则"类型面"会退化成"任何未收窄都红"的噪音门。
    /// </summary>
    private static void IoTypeCases(List<Check> checks, string work)
    {
        var root = Path.Combine(work, "io-types");
        WriteFile(root, "04_模块库/甲/M01_提供.md", IoDoc("M01", "[alpha]", "[]",
            "    outputs:\n      alpha: number\n    inputs: {}"));
        WriteFile(root, "04_模块库/乙/M02_消费.md", IoDoc("M02", "[]", "[M01]",
            "    outputs: {}\n    inputs:\n      M01: number"));
        checks.Add(Guarded("I/O 类型面·期望与提供一致时零问题（正向对照）", () =>
        {
            var (issues, _, stats) = IoTypes.Scan(root);
            return (issues.Count == 0 && stats["typed_fields"] is 2,
                issues.Count == 0 ? $"typed={stats["typed_fields"]} untyped={stats["untyped_fields"]}" : string.Join(" | ", issues));
        }));

        checks.Add(Guarded("I/O 类型面·可证不匹配必须 FAIL（期望 boolean，提供方只有 number）", () =>
        {
            WriteFile(root, "04_模块库/乙/M02_消费.md", IoDoc("M02", "[]", "[M01]",
                "    outputs: {}\n    inputs:\n      M01: boolean"));
            var (issues, _, _) = IoTypes.Scan(root);
            var hit = issues.FirstOrDefault(i => i.Contains("类型不匹配：M02", StringComparison.Ordinal));
            return (hit is not null, hit ?? "未报类型不匹配");
        }));

        checks.Add(Guarded("I/O 类型面·取值越词表必须 FAIL；键集不一致只 WARN（不该误判）", () =>
        {
            WriteFile(root, "04_模块库/甲/M01_提供.md", IoDoc("M01", "[alpha]", "[]",
                "    outputs:\n      alpha: 字符串\n      beta: number\n    inputs: {}"));
            var (issues, warns, _) = IoTypes.Scan(root);
            var kindOut = issues.Any(i => i.Contains("类型越词表", StringComparison.Ordinal));
            var keyset = warns.Any(w => w.Contains("键集不一致", StringComparison.Ordinal));
            return (kindOut && keyset && !issues.Any(i => i.Contains("键集不一致", StringComparison.Ordinal)),
                $"越词表=FAIL {kindOut} · 键集不一致=WARN {keyset} · FAIL 数 {issues.Count}");
        }));
    }

    /// <summary>合成带 io_types 的模块文档。</summary>
    private static string IoDoc(string id, string outputs, string inputs, string ioBody) => string.Join("\n", new[]
    {
        "---", $"id: {id}", "title: 用例", "---", "",
        "```yaml", "machine_contract:", "  schema: \"1\"", $"  id: {id}", "  layer: P40",
        "  category: 通用", $"  outputs: {outputs}", $"  inputs: {inputs}",
        "  interfaces: []", "  io_types:", ioBody, "```", "",
    });

    // ------------------------------- ⑯ 管线抽象执行（hard / advisory 分层）

    /// <summary>
    /// 管线层的判据分层要能分开：**hard**（模块找不到 / 依赖落在更后层）必须红；
    /// **advisory**（同层依赖序 / 跨包外部）不判死；解析失败与 Python **同向抛异常**（不是给一条判定）。
    /// </summary>
    private static void PipelineDryrunCases(List<Check> checks, string work)
    {
        var root = Path.Combine(work, "pipeline-dryrun");
        Directory.CreateDirectory(Path.Combine(root, "desktop", "src", "core"));
        WriteFile(root, "desktop/src/core/registry.json", "{\"modules\": []}\n");
        WriteFile(root, "04_模块库/甲/M01_提供.md", IoDoc("M01", "[alpha]", "[]",
            "    outputs:\n      alpha: number\n    inputs: {}"));
        WriteFile(root, "04_模块库/乙/M02_消费.md", IoDoc("M02", "[]", "[M01]",
            "    outputs: {}\n    inputs:\n      M01: number"));
        WriteFile(root, "03_管线库/P99_用例.md", PipelineDoc("[M01]", "[M02]"));

        checks.Add(Guarded("管线执行·干净声明零 hard 缺陷（正向对照）", () =>
        {
            var result = PipelineDryrun.Graph("03_管线库/P99_用例.md", root);
            return (result.Issues.Count == 0 && (int)(result.Stats["modules"] ?? 0) == 2,
                $"hard={result.Issues.Count} · advisory={result.Notes.Count} · 模块 {result.Stats["modules"]}");
        }));

        checks.Add(Guarded("管线执行·模块未在仓库找到必须 FAIL", () =>
        {
            WriteFile(root, "03_管线库/P99_用例.md", PipelineDoc("[M01, 幽灵模块]", "[M02]"));
            var result = PipelineDryrun.Graph("03_管线库/P99_用例.md", root);
            var hit = result.Issues.FirstOrDefault(i => i.Contains("模块未在仓库找到：幽灵模块", StringComparison.Ordinal));
            return (hit is not null, hit ?? "未报模块缺失");
        }));

        checks.Add(Guarded("管线执行·前向依赖按 Python 口径记 advisory（不误判成 hard）", () =>
        {
            WriteFile(root, "03_管线库/P99_用例.md", PipelineDoc("[M01]", "[M02]"));
            WriteFile(root, "04_模块库/甲/M01_提供.md", IoDoc("M01", "[alpha]", "[M02]",
                "    outputs:\n      alpha: number\n    inputs: {}"));
            var result = PipelineDryrun.Graph("03_管线库/P99_用例.md", root);
            // 实测 Python：M01 依赖尚未执行的 M02 → 记「跨包/外部依赖」advisory，**不判 hard**
            // （hard 的门槛是「已执行但层位严格更后」；前向引用属执行模型待裁决项，不误伤）
            var note = result.Notes.FirstOrDefault(n => n.Category == "跨包/外部依赖"
                                                       && n.Detail.StartsWith("M01 ← M02", StringComparison.Ordinal));
            return (result.Issues.Count == 0 && note is not null,
                note is null ? $"未记前置依赖 advisory（hard={result.Issues.Count}）" : note.Detail);
        }));

        checks.Add(Guarded("管线执行·解析失败与 Python 同向抛异常（不是给判定）", () =>
        {
            WriteFile(root, "03_管线库/P99_用例.md",
                PipelineDoc("[M01]", "[M02]").Replace("```yaml\nPipeline:", "```yamz\nPipeline:"));
            try
            {
                var result = PipelineDryrun.Graph("03_管线库/P99_用例.md", root);
                return (false, $"未抛异常，反而给了 hard={result.Issues.Count} 的判定");
            }
            catch (InvalidOperationException exc)
            {
                return (exc.Message.Contains("管线解析失败", StringComparison.Ordinal), exc.Message);
            }
        }));
    }

    /// <summary>合成管线文档（两层：P10 装 layerA、P20 装 layerB——顺序即依赖序）。</summary>
    private static string PipelineDoc(string layerA, string layerB) => string.Join("\n", new[]
    {
        "# 管线 P99", "", "```yaml", "Pipeline:", "  id: P99", "  name: 用例管线",
        "  structure:", "    type: linear", "  layers:",
        "    - id: P10", "      name: 甲层", "      description: 甲", "      optional: false",
        $"      default_modules: {layerA}",
        "    - id: P20", "      name: 乙层", "      description: 乙", "      optional: false",
        $"      default_modules: {layerB}", "```", "",
    });

    // ------------------------------------------- ⑰ 双源知识层（knowledge-sources）

    /// <summary>
    /// 知识层的三条硬判据各钉一条：**locator 必须指向真实件**（防纸面源）、
    /// **查询有序**（合同级必须全部排在参考级之前）、**幽灵频次**（频率台账含未声明的源）。
    /// 另钉一处易错：缺键字段的文案按 Python `str(s.get(k))` 渲染成 `None`（不是空串）。
    /// </summary>
    private static void KnowledgeCases(List<Check> checks, string work)
    {
        var root = Path.Combine(work, "knowledge");
        WriteFile(root, "library/RECEIPTS.json", "{}\n");
        // 认知裁剪模块必须在册（knowledge 的 _module_ids 正则扫模块文档找 id）
        WriteFile(root, "04_模块库/通用类/M23_可见性边界.md", IoDoc("M23", "[]", "[]",
            "    outputs: {}\n    inputs: {}"));
        WriteFile(root, "protocol/transform_log.json", "{\"schema\": \"nf-transform-log/1\", \"entries\": []}\n");
        WriteFile(root, "protocol/knowledge_usage.json",
            "{\"schema\": \"nf-knowledge-usage/1\", \"counts\": {}, \"total\": 0}\n");
        checks.Add(Guarded("知识层·声明齐备时零问题（正向对照）", () =>
        {
            WriteFile(root, "protocol/knowledge_sources.json", KnowledgeDecl("library", true));
            var (issues, _, stats) = KnowledgeSources.Scan(root);
            return (issues.Count == 0 && stats["contract"] is 1 && stats["reference"] is 1,
                issues.Count == 0 ? $"源 {stats["sources"]}（合同 1 / 参考 1）" : string.Join(" | ", issues));
        }));

        checks.Add(Guarded("知识层·locator 指向不存在的件必须 FAIL（防纸面源）", () =>
        {
            WriteFile(root, "protocol/knowledge_sources.json", KnowledgeDecl("不存在的目录", true));
            var (issues, _, _) = KnowledgeSources.Scan(root);
            var hit = issues.FirstOrDefault(i => i.Contains("locator 不存在", StringComparison.Ordinal));
            return (hit is not null, hit ?? "未报纸面源");
        }));

        checks.Add(Guarded("知识层·查询有序被破坏必须 FAIL（合同级须全部在前）", () =>
        {
            WriteFile(root, "protocol/knowledge_sources.json", KnowledgeDecl("library", true, reverseOrder: true));
            var (issues, _, _) = KnowledgeSources.Scan(root);
            var hit = issues.FirstOrDefault(i => i.Contains("查询有序被破坏", StringComparison.Ordinal));
            return (hit is not null, hit ?? "未报查询无序");
        }));

        checks.Add(Guarded("知识层·幽灵频次必须 FAIL；缺键文案按 Python 渲染成 None", () =>
        {
            WriteFile(root, "protocol/knowledge_sources.json", KnowledgeDecl("library", false));
            var (declIssues, _, _) = KnowledgeSources.Scan(root);
            var noneText = declIssues.Any(i => i.Contains("kind 越词表：None", StringComparison.Ordinal));
            WriteFile(root, "protocol/knowledge_sources.json", KnowledgeDecl("library", true));
            WriteFile(root, "protocol/knowledge_usage.json",
                "{\"schema\": \"nf-knowledge-usage/1\", \"counts\": {\"幽灵源\": 1}, \"total\": 1}\n");
            var (usageIssues, _, _) = KnowledgeSources.VerifyUsage(root);
            var ghost = usageIssues.Any(i => i.Contains("含未声明的源：幽灵源", StringComparison.Ordinal));
            return (noneText && ghost, $"缺键渲染 None={noneText} · 幽灵频次={ghost}");
        }));
    }
}
