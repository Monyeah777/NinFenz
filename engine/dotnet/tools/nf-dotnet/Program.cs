using System.Text.Json;
using Nf.Engine;

// nf-dotnet · NF 工业引擎 CLI（只读子集，输出面与 Python 侧 nf 对齐）
// 用法：nf-dotnet [--root <dir>] [--json] <command> [options]
//   verify                                  聚合校验（协议回执 + 馆藏回执 + 透明链 + 组合证书）
//   receipts [--scope protocol|library]     回执复算
//   transparency                            透明链复算
//   combine verify                          组合证书 T4 复算
//   combine plan --packs a,b [--extra-modules x,y] [--strict-coherence]
//   conformance                             一致性报告（部分实现：已移植契约逐条给 ok/detail/digest）

internal static partial class Program
{
    private const string Version = "0.1.0";

    private static string? root = null;
    private static string scope = "protocol";
    private static bool scopeSet = false;
    private static string? samplesPath = null;
    private static string? benchBaselinePath = null;
    private static string? benchWritePath = null;
    private static double tolerance = 2.0;
    private static bool pairsOnly = false;
    private static bool kindsOnly = false;
    private static bool backlogOnly = false;
    private static bool pipelineAll = false;
    private static string? pipelineName = null;
    private static bool stateFrontCheck = false;
    private static bool stateFrontAb = false;
    private static string stateFrontMode = "front";
    // 通用 `--out` 值：state-front 侧是写面（未移植，明确拒绝）；st-validate 侧是报告输出路径（同 Python）
    private static string? outPath = null;
    private static bool writeRequested = false;
    private static string? tracePath = null;
    private static string? interopKind = null;
    private static bool interopList = false;
    private static bool interopCheck = false;
    private static bool interopAll = false;
    private static bool worldModelRun = false;
    private static bool worldModelWalk = false;
    private static string? worldModelState = null;
    private static bool impactCheck = false;
    // 构建回路（workloop）面的开关：候选数 / 来源限定 / 适配器；--close 与 --write 是写面（明确拒绝）
    private static int topCount = 5;
    private static string? sourceFlag = null;
    private static string adapterFlag = "stub";
    private static bool workloopList = false;
    private static string closeFlag = "";
    // 回归评分（score）面的开关：基线路径可覆盖；--write-baseline 是写面
    private static string scoreBaselinePath = "";
    private static bool scoreWriteBaseline = false;
    private static double? scoreTolerance = null;   // 真源 `nf score --tolerance` 缺省 0.0（与 bench 的 2.0 不同）
    // 决策层（decide）面的开关：状态文本 / 问题件 / 端点类参数（非 stub 走 fail-closed 边界）
    private static string? decideStatePath = null;
    private static string decideStateText = "";
    private static string? questionsPath = null;
    private static string endpointFlag = "";
    private static string modelFlag = "";
    private static bool decideDryRun = false;
    private static int limitCount = 0;    // 同 `--limit` 开关：review 只审前 N 行候选（0 = 全量）
    private static int batchCount = 8;    // review 每批行数（真源缺省 8）
    private static string? diffPath = null;   // `extension --diff <文件|->`：调用方供 `git diff HEAD` 的标准统一 diff
    // 需求 → 装配计划（assemble）面：`--answer` 可重复；`--check` 复用既有开关（成品 md 走位置参数）；
    // session/save/trace/rounds 都是写面或未移植面 → 明确拒绝。
    private static List<string> assemblyAnswers = new List<string>();
    private static bool assembleCheck = false;
    private static string assembleSessionPath = "";
    private static string assembleSavePath = "";
    private static string assembleTracePath = "";
    private static bool assembleRounds = false;
    private static string? registryPath = null;
    private static string? marketTier = null;
    private static bool marketList = false;
    private static string? assetsRootFlag = null;
    private static string assetPkg = "";
    private static string assetTier = "";
    private static string assetStatus = "";
    private static bool strictRequested = false;
    private static bool refreshRequested = false;
    private static string outputCategory = "";
    private static string outputPackage = "";
    private static string? closureAsset = null;
    private static string closureTarget = "C22";
    private static string closureLoaded = "";
    private static string closureBranch = "";
    private static string closureOrder = "";
    private static bool closureList = false;
    private static bool closureReadyList = false;
    private static bool closureGaps = false;
    private static bool closureCheck = false;
    private static int closureLimit = 20;
    private static string knowledgeClearance = "";
    private static List<string> packs = new List<string>();
    private static List<string> extraModules = new List<string>();
    // ISA v1 C1′「撞号即 DENY」：默认与 Python 同口径（静默塌陷），加了开关才判死。
    private static bool strictCoherence = false;
    private static List<string> flags = new List<string>();
    private static List<string> positional = new List<string>();
    private static bool json;

    private static int Main(string[] args)
    {

        for (var i = 0; i < args.Length; i++)
        {
            switch (args[i])
            {
                case "--root":
                    if (++i >= args.Length) return Usage("--root 需要一个目录参数");
                    root = args[i];
                    break;
                case "--scope":
                    if (++i >= args.Length) return Usage("--scope 需要 protocol|library");
                    scope = args[i];
                    scopeSet = true;
                    break;
                case "--packs":
                    if (++i >= args.Length) return Usage("--packs 需要逗号分隔的包名");
                    packs = args[i].Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries).ToList();
                    break;
                case "--samples":
                    if (++i >= args.Length) return Usage("--samples 需要 Python 导出的样本集 JSON");
                    samplesPath = args[i];
                    break;
                case "--pairs-only":
                    pairsOnly = true;
                    break;
                case "--kinds":
                    kindsOnly = true;
                    break;
                case "--backlog":
                    backlogOnly = true;
                    break;
                case "--all":
                    pipelineAll = true;
                    interopAll = true;   // 同一 --all 开关：pipeline 与 interop 各自读取
                    break;
                case "--pipeline":
                    if (++i >= args.Length) return Usage("--pipeline 需要管线路径");
                    pipelineName = args[i];
                    break;
                case "--check":
                    stateFrontCheck = true;
                    interopCheck = true;   // 同一 --check 开关：state-front 与 interop 各自读取
                    impactCheck = true;    // 同一 --check 开关：impact 读它（门禁模式）
                    closureCheck = true;   // 同一 --check 开关：domain-closure 自检读它
                    assembleCheck = true;  // 同一 --check 开关：assemble 读它（成品 md 路径走位置参数）
                    break;
                case "--answer":
                    if (++i >= args.Length) return Usage("--answer 需要一条澄清回填");
                    assemblyAnswers.Add(args[i]);
                    break;
                case "--session-path":
                    if (++i >= args.Length) return Usage("--session-path 需要路径");
                    assembleSessionPath = args[i];
                    break;
                case "--save-path":
                    if (++i >= args.Length) return Usage("--save-path 需要路径");
                    assembleSavePath = args[i];
                    break;
                case "--trace-path":
                    if (++i >= args.Length) return Usage("--trace-path 需要路径");
                    assembleTracePath = args[i];
                    break;
                case "--rounds":
                    assembleRounds = true;
                    break;
                case "--registry":
                    if (++i >= args.Length) return Usage("--registry 需要一个 registry.json 路径");
                    registryPath = args[i];
                    break;
                case "--ab":
                    stateFrontAb = true;
                    break;
                case "--mode":
                    if (++i >= args.Length) return Usage("--mode 需要 front|back|none");
                    stateFrontMode = args[i];
                    break;
                case "--out":
                    if (++i >= args.Length) return Usage("--out 需要输出路径");
                    outPath = args[i];
                    break;
                case "--write":
                    writeRequested = true;
                    break;
                case "--trace":
                    if (++i >= args.Length) return Usage("--trace 需要一个 trace 文件路径");
                    tracePath = args[i];
                    break;
                case "--run":
                    worldModelRun = true;
                    break;
                case "--walk":
                    worldModelWalk = true;
                    break;
                case "--state":
                    if (++i >= args.Length) return Usage("--state 需要一个状态文件路径");
                    worldModelState = args[i];
                    decideStatePath = args[i];   // 同一 --state 开关：worldmodel 取状态 id、decide 取状态文本文件
                    break;
                case "--state-text":
                    if (++i >= args.Length) return Usage("--state-text 需要状态文本");
                    decideStateText = args[i];
                    break;
                case "--questions":
                    if (++i >= args.Length) return Usage("--questions 需要问题 JSON 文件路径");
                    questionsPath = args[i];
                    break;
                case "--endpoint":
                    if (++i >= args.Length) return Usage("--endpoint 需要适配器端点");
                    endpointFlag = args[i];
                    break;
                case "--model":
                    if (++i >= args.Length) return Usage("--model 需要模型名（openai-json 适配器）");
                    modelFlag = args[i];
                    break;
                case "--dry-run":
                    decideDryRun = true;
                    break;
                case "--kind":
                    if (++i >= args.Length) return Usage("--kind 需要一个导出形状");
                    interopKind = args[i];
                    break;
                case "--list":
                    interopList = true;
                    marketList = true;   // 同一 --list 开关：interop 与 market 各自读取
                    closureList = true;   // 同一 --list 开关：domain-closure 条目键全表
                    workloopList = true;   // 同一 --list 开关：workloop 列候选工作项
                    break;
                case "--top":
                    if (++i >= args.Length) return Usage("--top 需要整数（候选工作项数）");
                    if (!int.TryParse(args[i], System.Globalization.NumberStyles.Integer,
                            System.Globalization.CultureInfo.InvariantCulture, out topCount))
                        return Usage("--top 需要整数（候选工作项数）");
                    break;
                case "--source":
                    if (++i >= args.Length) return Usage("--source 需要来源限定（type-backlog / pipeline-advisory / capability-gaps）");
                    sourceFlag = args[i];
                    break;
                case "--adapter":
                    if (++i >= args.Length) return Usage("--adapter 需要适配器 id（stub / systemone-http / openai-json）");
                    adapterFlag = args[i];
                    break;
                case "--close":
                    if (++i >= args.Length) return Usage("--close 需要工单号");
                    closeFlag = args[i];
                    break;
                case "--tier":
                    if (++i >= args.Length) return Usage("--tier 需要 official|community|experimental");
                    marketTier = args[i];
                    assetTier = marketTier;   // 同一 --tier 开关：market --list 与 asset ls 各自读取
                    break;
                case "--assets-root":
                    if (++i >= args.Length) return Usage("--assets-root 需要一个扫描根路径");
                    assetsRootFlag = args[i];
                    break;
                case "--pkg":
                    if (++i >= args.Length) return Usage("--pkg 需要一个包名");
                    assetPkg = args[i];
                    break;
                case "--category":
                    if (++i >= args.Length) return Usage("--category 需要一个形态类别 id");
                    outputCategory = args[i];
                    break;
                case "--package":
                    if (++i >= args.Length) return Usage("--package 需要一个包名");
                    outputPackage = args[i];
                    break;
                case "--asset":
                    if (++i >= args.Length) return Usage("--asset 需要一个概念图资产路径");
                    closureAsset = args[i];
                    break;
                case "--target":
                    if (++i >= args.Length) return Usage("--target 需要一个目标概念");
                    closureTarget = args[i];
                    break;
                case "--loaded":
                    if (++i >= args.Length) return Usage("--loaded 需要逗号分隔的已装载概念集");
                    closureLoaded = args[i];
                    break;
                case "--branch":
                    if (++i >= args.Length) return Usage("--branch 需要一个分支 id");
                    closureBranch = args[i];
                    break;
                case "--order":
                    if (++i >= args.Length) return Usage("--order 需要一个序 id");
                    closureOrder = args[i];
                    break;
                case "--ready-list":
                    closureReadyList = true;
                    break;
                case "--gaps":
                    closureGaps = true;
                    break;
                case "--limit":
                    if (++i >= args.Length) return Usage("--limit 需要一个整数（--gaps 行数上限）");
                    if (!int.TryParse(args[i], out closureLimit)) return Usage("--limit 需要一个整数");
                    limitCount = closureLimit;   // 同一 --limit 开关：domain-closure --gaps 与 review 各自读取
                    break;
                case "--batch":
                    if (++i >= args.Length) return Usage("--batch 需要整数（review 每批行数）");
                    if (!int.TryParse(args[i], out batchCount)) return Usage("--batch 需要整数（review 每批行数）");
                    break;
                case "--diff":
                    if (++i >= args.Length) return Usage("--diff 需要统一 diff 文件路径（或 - 读 stdin）");
                    diffPath = args[i];
                    break;
                case "--status":
                    if (++i >= args.Length) return Usage("--status 需要 active|deprecated|retired");
                    assetStatus = args[i];
                    break;
                case "--as":
                    if (++i >= args.Length) return Usage("--as 需要 public|internal|restricted");
                    knowledgeClearance = args[i];
                    break;
                case "--baseline":
                    if (++i >= args.Length) return Usage("--baseline 需要基线 JSON 路径");
                    benchBaselinePath = args[i];
                    scoreBaselinePath = args[i];   // 同一 --baseline 开关：bench 与 score 各自读取
                    break;
                case "--write-baseline":
                    // 真源两义：`nf bench --write-baseline <f>` 取路径；`nf score --write-baseline` 是布尔（写面）。
                    if (positional.Count > 0 && positional[0] == "score")
                    {
                        scoreWriteBaseline = true;
                        break;
                    }
                    if (++i >= args.Length) return Usage("--write-baseline 需要输出 JSON 路径");
                    benchWritePath = args[i];
                    break;
                case "--tolerance":
                    if (++i >= args.Length) return Usage("--tolerance 需要数值（如 2.0）");
                    if (!double.TryParse(args[i], System.Globalization.NumberStyles.Float,
                            System.Globalization.CultureInfo.InvariantCulture, out tolerance))
                        return Usage("--tolerance 需要数值（如 2.0）");
                    scoreTolerance = tolerance;   // 同一 --tolerance 开关：bench 与 score 各自读取
                    break;
                case "--extra-modules":
                    if (++i >= args.Length) return Usage("--extra-modules 需要逗号分隔的模块 id");
                    extraModules = args[i].Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries).ToList();
                    break;
                case "--strict-coherence":
                    strictCoherence = true;
                    break;
                case "--strict":
                    // nf asset usage --strict：零引用键存在即 exit 1（键消费证明进门禁）。真源只有这一个 --strict。
                    strictRequested = true;
                    break;
                case "--refresh":
                    // nf asset ledger --refresh 是写面（重生成键表投影）——只读门据此明确拒绝。
                    refreshRequested = true;
                    break;
                case "--json":
                case "--otlp":
                case "--help":
                case "-h":
                case "--version":
                    flags.Add(args[i]);
                    break;
                default:
                    positional.Add(args[i]);
                    break;
            }
        }

        if (flags.Contains("--version")) { Console.WriteLine("nf-dotnet " + Version); return 0; }
        if (flags.Contains("--help") || flags.Contains("-h") || positional.Count == 0) return Usage(null);

        // 输出口径对齐 Python 文本模式：Python 把**每一个** '\n' 都翻成宿主换行（Windows = CRLF），
        // 而 .NET 默认只在 WriteLine 边界写 CRLF——多行 JSON / 正文里内嵌的 '\n' 会与 Python 差一拍。
        // 统一在此处翻译：Windows 上等价把裸 '\n' 补成 CRLF；Linux 上 Environment.NewLine == "\n"（恒等）。
        Console.SetOut(new NewlineNormalizingWriter(Console.Out));
        json = flags.Contains("--json");
        root ??= ".";
        if (!Directory.Exists(Path.Combine(root, "protocol"))) return Fail("根目录不含 protocol/：" + Path.GetFullPath(root));

        // 受控失败：任何非致命异常都必须变成"可读错误 + 退出码 2"，不许崩栈（工业级失败卫生）
        try
        {
            return Dispatch();
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"错误（受控失败）：{ex.GetType().Name}: {ex.Message}");
            return 2;
        }
    }

    private static int Dispatch()
    {
        switch (positional[0])
        {
            case "receipts":
                return ReceiptsCommand();
            case "transparency":
                return TransparencyCommand();
            case "combine" when positional.Count >= 2 && positional[1] == "verify":
                return CombineVerifyCommand();
            case "combine" when positional.Count >= 2 && positional[1] == "plan":
                return CombinePlanCommand();
            case "combine" when positional.Count >= 2 && positional[1] == "breadth":
                return CombineBreadthCommand();
            case "verify":
                return AggregateCommand();
            case "assertions":
                return AssertionsCommand();
        case "decisions":
            return DecisionsCommand();
        case "cognition":
            return CognitionCommand();
        case "library":
            return LibraryCommand();
        case "bench":
            return BenchCommand();
        case "model":
            return ModelCommand();
        case "conformance":
            return ConformanceCommand();
        case "lint":
            return LintCommand();
        case "module":
            return ModuleCommand();
        case "pipeline":
            return PipelineCommand();
        case "handover":
            return GovernanceCommand("handover");
        case "postmortem":
            return GovernanceCommand("postmortem");
        case "audit":
            return GovernanceCommand("audit");
        case "state-front":
            return StateFrontCommand();
        case "knowledge":
            return KnowledgeCommand();
            case "sig":
                return SigCommand();
            case "patterns":
                return PatternsCommand();
            case "rfc":
                return RfcCommand();
            case "endpoint":
                return EndpointCommand();
            case "events":
                return EventsCommand();
            case "toolface":
                return ToolFaceCommand();
            case "st-validate":
                return StValidateCommand();
            case "stats":
                return StatsCommand();
            case "telemetry":
                return TelemetryCommand();
            case "driver":
                return DriverCommand();
        case "interop":
            return InteropCommand();
        case "workloop":
            return WorkloopCommand();
        case "license":
            return LicenseCommand();
        case "score":
            return ScoreCommand();
        case "decide":
            return DecideCommand();
        case "doctor":
            return DoctorCommand();
        case "spec":
            return SpecCommand();
        case "review":
            return ReviewCommand();
        case "extension":
            return ExtensionCommand();
        case "corpus":
            return CorpusCommand();
        case "assemble":
            return AssembleCommand();
            case "worldmodel":
                return WorldModelCommand();
            case "impact":
                return ImpactCommand();
            case "who-refers":
                return WhoRefersCommand();
            case "diff":
                return DiffCommand();
            case "explain":
                return ExplainCommand();
            case "output":
                return OutputCommand();
            case "domain-closure":
                return DomainClosureCommand();
            case "related":
                return RelatedCommand();
            case "market":
                return MarketCommand();
            case "asset":
                return AssetCommand();
            case "serve":
                return McpServer.ServeStdio(root!, Console.In, Console.Out);
            case "selftest":
                return SelfTestCommand();
            case "daemon":
                // 真源在 348577d 新增 `nf daemon`（执行层常驻守护：start/stop/status/exec/shell-init/bench）。
                // 按本线端口边界（ADR-0005 §决策 2）：**运行层/写面不实现**——故**显式拒绝**，
                // 而不是让它掉进"未知命令"（那会把"设计边界"误报成"拼错命令"）。
                return Fail("daemon 是执行层常驻守护（起进程 / 落 <NF_HOME>/daemon.json）——本引擎是只读门，不提供运行层");
            // 执行层 / 交互层（真源有）：本引擎是只读判据门，不提供运行层——**显式拒绝**，
            // 不让它掉进"未知命令"（那会把"设计边界"误报成"拼错命令"，与 daemon 分支同一条纪律）。
            // 纪律：**每个标签只放一个命令词**——cli_surface_probe 按「标签 + 单引号命令词」逐个抽静态面，
            // 若一个标签用 or 串多个词，只有第一个词进静态面，其余会变成"帮助里列了却分派不到"的幽灵命令假红。
            // （注意：该判据连**注释文本**一起扫，注释里也不要写出「标签 + 命令词」的字面样式。）
            case "shell":
            case "terminal":
            case "lsp":
            case "completion":
            case "demo":
            case "run":
            case "help":
                return Fail("执行层/交互层命令（shell / terminal / lsp / completion / demo / run / help）——本引擎只读，不提供运行层；引擎用法见 --help");
            // 写面 / 工厂（真源有）：本线端口边界（ADR-0005 §决策 2）不实现写面。
            case "register":
            case "rename":
            case "import":
            case "approve":
            case "attest":
            case "design":
            case "domain":
                return Fail("该命令属写面/工厂（register / rename / import / approve / attest / design / domain）——本引擎只做只读判据面");
            // 读面但**未移植**：如实声明边界，避免与"已覆盖"混淆（覆盖矩阵命令级一节登记）。
            case "layers":
            case "release":
                return Fail("该读面未移植到引擎：layers（真源 protocol/LAYERS.json · 与 check27 R7 同源）/ release（verify + doctor 组合）");
            default:
                return Usage("未知命令：" + string.Join(' ', positional));
        }
    }

}

/// <summary>
/// 把交给 stdout 的裸 '\n' 翻成宿主换行（等价 Python 文本模式 <c>newline=None</c> 的写侧翻译）。
/// 已经是 CRLF 的序列原样透传（<c>_last == '\r'</c> 时不再补），故不会写出 CRCRLF。
/// </summary>
internal sealed class NewlineNormalizingWriter(TextWriter inner) : TextWriter
{
    private char _last;

    public override System.Text.Encoding Encoding => inner.Encoding;

    public override void Write(char value)
    {
        if (value == '\n' && _last != '\r')
        {
            inner.Write(Environment.NewLine);   // Windows: "\r\n"；Linux: "\n"（恒等）
        }
        else
        {
            inner.Write(value);
        }
        _last = value;
    }

    public override void Write(string? value)
    {
        if (string.IsNullOrEmpty(value)) return;
        foreach (var ch in value) Write(ch);
    }

    public override void Flush() => inner.Flush();
}
