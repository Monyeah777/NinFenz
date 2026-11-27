using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;

namespace Nf.Engine;

/// <summary>
/// 互操作导出面（复刻 <c>core/interop_export.py</c>）：把既有声明件**纯派生**为外部标准工具可读的文档。
///
/// 定位纪律：**不新增真源**——所有字段从既有声明件实时算出；门禁断言的是「覆盖完整 + 形状合法 + 确定性」。
/// 本件按片推进：已移植的形状在 <see cref="PortedKinds"/> 里列明；未移植的 <see cref="Render"/> 会**明确抛出**
/// （不静默给半个面、不冒充等价）——与 `purity-clean` 的范围裁定同一条纪律。
/// </summary>
public static partial class Interop
{
    public const string ContractRel = "protocol/endpoint_contract.json";
    public const string EventsRel = "protocol/event_registry.json";
    public const string ExternalEventsRel = "protocol/external_events.json";
    public const string ReceiptsRel = "protocol/RECEIPTS.json";
    public const string LicenseName = "MIT";

    /// <summary>12 种导出形状（键序 = 真源 <c>KINDS</c> 的声明序，<c>--list</c> 逐行按此序）。</summary>
    public static readonly (string Id, string Label)[] Kinds =
    {
        ("openapi", "OpenAPI 3.1 服务端点文档"),
        ("asyncapi", "AsyncAPI 3.0 事件通道文档（含 CloudEvents 属性）"),
        ("intoto", "in-toto Statement v1（协议层回执）"),
        ("sbom", "SPDX 2.3 SBOM（依赖登记面）"),
        ("slsa", "SLSA Provenance v1（本地门禁构建声明）"),
        ("a2a", "A2A Agent Card（能力面投影）"),
        ("prov", "PROV-O 溯源图（资产 / 馆藏 / 消化 / 回执）"),
        ("cyclonedx", "CycloneDX 1.5 SBOM（与 SPDX 面同源）"),
        ("vc", "W3C VC 2.0 形状（未签名，含状态注记）"),
        ("c2pa", "C2PA JSON 清单形状（未封装/未签名）"),
        ("cid", "CIDv1 内容寻址索引（multiformats）"),
        ("decisions", "决策面（决策能力 + 公开裁决索引；工单不入公开面）"),
    };

    /// <summary>已移植的导出形状（未列的 kind 在 <see cref="Render"/> 里明确拒绝）。</summary>
    public static readonly string[] PortedKinds =
    {
        "openapi", "asyncapi", "intoto", "sbom", "slsa", "a2a", "prov",
        "cyclonedx", "vc", "c2pa", "cid", "decisions",
    };

    private static readonly System.Text.UTF8Encoding StrictUtf8 = new(false, throwOnInvalidBytes: true);
    private static readonly Regex DateRe = new(@"20\d\d-\d\d-\d\d", RegexOptions.CultureInvariant);
    private static readonly Regex VerifyVersionRe = new(@"# 版本\s*:\s*(v[0-9.]+)", RegexOptions.CultureInvariant);
    private static readonly Regex Sha256Re = new(@"^[0-9a-f]{64}$", RegexOptions.CultureInvariant);
    private static readonly Regex ExpectedChecksRe = new(@"^\s*EXPECTED_CHECKS\s*=\s*([0-9]+)", RegexOptions.Multiline);
    private static readonly Regex ExpectedPassRe = new(@"^\s*EXPECTED_PASS\s*=\s*([0-9]+)", RegexOptions.Multiline);
    private static readonly Regex PinnedRequirementRe = new(
        @"^([^#=\s]+)\s*==\s*([^#;\\]+)", RegexOptions.CultureInvariant);
    private static readonly Regex PinnedTomlRe = new(
        @"""([A-Za-z0-9_.-]+)(?:\[[^\]]+\])?==([^""]+)""", RegexOptions.CultureInvariant);
    private static readonly Dictionary<string, string> DependencyAliases =
        new(StringComparer.Ordinal) { ["yaml"] = "pyyaml" };

    /// <summary>确定性渲染（键排序 + UTF-8 + LF 尾）——同输入两次调用逐字节一致。</summary>
    public static byte[] Render(string kind, string root)
        => Encoding.UTF8.GetBytes(PythonJson.Indented(Document(kind, root)) + "\n");

    /// <summary>导出形状的对象图（供渲染与机读面共用；未移植形状明确抛出）。</summary>
    public static Dictionary<string, object?> Document(string kind, string root)
    {
        return kind switch
        {
            "openapi" => Openapi(root),
            "asyncapi" => Asyncapi(root),
            "intoto" => Intoto(root),
            "sbom" => Sbom(root),
            "slsa" => Slsa(root),
            "a2a" => A2a(root),
            "prov" => Prov(root),
            "cyclonedx" => Cyclonedx(root),
            "vc" => Vc(root),
            "c2pa" => C2pa(root),
            "cid" => Cid(root),
            "decisions" => Decisions(root),
            _ => throw new InvalidOperationException(
                $"interop 形状 {kind} 未移植（已移植：{string.Join(" / ", PortedKinds)}）——" +
                "本引擎不提供半个面，也不冒充等价；未移植形状见覆盖率矩阵"),
        };
    }

    // ------------------------------------------------------------------ 形状（逐字节对齐 Python）

    /// <summary>
    /// 门禁：**覆盖完整 + 形状合法 + 确定性**（复刻 <c>interop_export.verify</c>）。
    /// fail-closed：真源缺失 = 无从校验（不是"空导出面"，是"没有可导出的东西"）。
    /// </summary>
    public static (List<string> Issues, Dictionary<string, object?> Stats) Verify(string root)
    {
        var issues = new List<string>();
        var contract = ReadJson(root, ContractRel);
        var reg = ReadJson(root, EventsRel);
        var ext = ReadJson(root, ExternalEventsRel);
        var rec = ReadJson(root, ReceiptsRel);
        foreach (var rel in new[] { ContractRel, EventsRel, ReceiptsRel })
        {
            if (!File.Exists(Path.Combine(root, rel.Replace('/', Path.DirectorySeparatorChar))))
                issues.Add($"缺派生真源 {rel}（修复指引：先落声明件——导出面只做纯派生，不自造真源）");
        }

        // OpenAPI ↔ 端点契约
        var oa = Openapi(root);
        var wantPaths = Endpoints(contract).Select(e => PyText(e.GetValueOrDefault("path"))).ToHashSet(StringComparer.Ordinal);
        var oaPaths = oa.GetValueOrDefault("paths") as Dictionary<string, object?> ?? new(StringComparer.Ordinal);
        var gotPaths = oaPaths.Keys.ToHashSet(StringComparer.Ordinal);
        if (!wantPaths.SetEquals(gotPaths))
        {
            issues.Add("OpenAPI 派生面与服务端点契约不一致：缺 " +
                       $"{PyList(wantPaths.Except(gotPaths))} / 多 {PyList(gotPaths.Except(wantPaths))}");
        }
        foreach (var (path, opsNode) in oaPaths)
        {
            if (opsNode is not Dictionary<string, object?> ops) continue;
            foreach (var (method, opNode) in ops)
            {
                if (opNode is not Dictionary<string, object?> op) continue;
                if (!PyTruthy(op.GetValueOrDefault("operationId")))
                    issues.Add($"OpenAPI {method.ToUpperInvariant()} {path} 缺 operationId（修复指引：端点 id 必填）");
                var responses = op.GetValueOrDefault("responses") as Dictionary<string, object?> ?? new(StringComparer.Ordinal);
                if (!responses.ContainsKey("200"))
                    issues.Add($"OpenAPI {method.ToUpperInvariant()} {path} 缺 200 响应（修复指引：每端点须声明成功形状）");
            }
        }
        var schemas = ((oa.GetValueOrDefault("components") as Dictionary<string, object?>)
                       ?.GetValueOrDefault("schemas") as Dictionary<string, object?>) ?? new(StringComparer.Ordinal);
        if (!schemas.ContainsKey("NfError"))
            issues.Add("OpenAPI 缺 NfError 错误形状（修复指引：错误面须可机读）");
        var errMap = oa.GetValueOrDefault("x-nf-error-mapping") as Dictionary<string, object?> ?? new(StringComparer.Ordinal);
        if (!PyTruthy(errMap.GetValueOrDefault("title")))
            issues.Add("OpenAPI 缺 RFC 9457 字段映射（修复指引：声明 error.message ↔ title/detail）");

        // AsyncAPI ↔ 事件登记
        var aa = Asyncapi(root);
        var wantEvents = new HashSet<string>(StringComparer.Ordinal);
        foreach (var src in new[] { reg, ext })
        {
            if (src.GetValueOrDefault("events") is Dictionary<string, object?> map)
                foreach (var key in map.Keys) wantEvents.Add(key);
        }
        var aaChannels = aa.GetValueOrDefault("channels") as Dictionary<string, object?> ?? new(StringComparer.Ordinal);
        var gotEvents = aaChannels.Keys.Select(k => k.Contains('/') ? k[(k.IndexOf('/') + 1)..] : k)
            .ToHashSet(StringComparer.Ordinal);
        if (!wantEvents.SetEquals(gotEvents))
            issues.Add("AsyncAPI 派生面与事件登记不一致：缺 " +
                       $"{PyList(wantEvents.Except(gotEvents))} / 多 {PyList(gotEvents.Except(wantEvents))}");
        var ceTypes = aaChannels.Values.OfType<Dictionary<string, object?>>()
            .Select(c => (c.GetValueOrDefault("x-nf-cloudevents") as Dictionary<string, object?>)
                         ?.GetValueOrDefault("type")).ToList();
        if (ceTypes.Count != ceTypes.Distinct().Count())
            issues.Add("CloudEvents type 派生重复（修复指引：事件名须全库唯一，见 01 §1.1 事件名唯一 + 词法纪律）");

        // in-toto ↔ 协议层回执
        var st = Intoto(root);
        var wantSubjects = Entries(rec).Select(e => Str(e, "path")).ToHashSet(StringComparer.Ordinal);
        var stSubjects = (st.GetValueOrDefault("subject") as List<object?> ?? new List<object?>())
            .OfType<Dictionary<string, object?>>().ToList();
        var gotSubjects = stSubjects.Select(s => PyText(s.GetValueOrDefault("name"))).ToHashSet(StringComparer.Ordinal);
        if (!wantSubjects.SetEquals(gotSubjects))
            issues.Add($"in-toto subject 与协议层回执不一致：缺 {wantSubjects.Except(gotSubjects).Count()} / " +
                       $"多 {gotSubjects.Except(wantSubjects).Count()}");
        foreach (var s in stSubjects)
        {
            var digest = (s.GetValueOrDefault("digest") as Dictionary<string, object?>)?.GetValueOrDefault("sha256");
            if (!Sha256Re.IsMatch(PyText(digest)))
                issues.Add($"in-toto subject 缺合规 sha256：{PyText(s.GetValueOrDefault("name"))}" +
                           "（修复指引：回执 digest 须 64 位小写十六进制）");
        }
        if (st.GetValueOrDefault("_type") as string != "https://in-toto.io/Statement/v1")
            issues.Add("in-toto Statement 类型头不合法（修复指引：_type 须为 Statement/v1）");

        // SPDX SBOM
        var sb = Sbom(root);
        var sbPackages = (sb.GetValueOrDefault("packages") as List<object?> ?? new List<object?>())
            .OfType<Dictionary<string, object?>>().ToList();
        var spdxIds = sbPackages.Select(p => p.GetValueOrDefault("SPDXID")).ToList();
        if (spdxIds.Count != spdxIds.Distinct().Count())
            issues.Add("SBOM 包 SPDXID 重复（修复指引：每依赖一个唯一 SPDXID）");
        if (!sbPackages.Any(p => PyText(p.GetValueOrDefault("name")) == "NinFenz"))
            issues.Add("SBOM 缺本项目包（修复指引：SBOM 须自述本仓）");
        var relationships = (sb.GetValueOrDefault("relationships") as List<object?> ?? new List<object?>())
            .OfType<Dictionary<string, object?>>().ToList();
        if (!relationships.Any(r => PyText(r.GetValueOrDefault("relationshipType")) == "DESCRIBES"))
            issues.Add("SBOM 缺 DESCRIBES 关系（修复指引：文档须描述本仓包）");
        var created = ((sb.GetValueOrDefault("creationInfo") as Dictionary<string, object?>)
                       ?.GetValueOrDefault("created"));
        if (!Regex.IsMatch(PyText(created), @"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"))
            issues.Add($"SBOM 的 creationInfo.created 缺失或非 ISO 8601 UTC：{PyScalar.PyRepr(created)}" +
                       "（修复指引：SPDX 2.3 要求必填；本仓取「仓内声明日期最大值」保确定性）");

        // 确定性：同输入两次渲染必须逐字节一致
        foreach (var (kind, _) in Kinds)
        {
            if (!Render(kind, root).SequenceEqual(Render(kind, root)))
                issues.Add($"导出面不确定性：{kind} 两次渲染不一致（修复指引：禁止引入时间戳/随机源）");
        }

        // SLSA：subject 同源 + 不虚标等级 + 基线句与 quality_baseline 同源
        var sl = Slsa(root);
        if (sl.GetValueOrDefault("predicateType") as string != "https://slsa.dev/provenance/v1")
            issues.Add("SLSA 派生面 predicateType 不合法（修复指引：须为 slsa.dev/provenance/v1）");
        var slSubjects = (sl.GetValueOrDefault("subject") as List<object?> ?? new List<object?>()).Count;
        if (slSubjects != Entries(rec).Count)
            issues.Add($"SLSA 派生面 subject 数与回执不一致：{slSubjects} vs {Entries(rec).Count}");
        var predicate = sl.GetValueOrDefault("predicate") as Dictionary<string, object?> ?? new(StringComparer.Ordinal);
        var runDetails = predicate.GetValueOrDefault("runDetails") as Dictionary<string, object?> ?? new(StringComparer.Ordinal);
        var slNote = ((runDetails.GetValueOrDefault("metadata") as Dictionary<string, object?>)
                      ?.GetValueOrDefault("note")) as string ?? "";
        if (!slNote.Contains("不构成 SLSA 等级声明"))
            issues.Add("SLSA 派生面缺「不作等级声明」注记（修复指引：本地门禁不得虚标 SLSA 等级）");
        var buildDef = predicate.GetValueOrDefault("buildDefinition") as Dictionary<string, object?> ?? new(StringComparer.Ordinal);
        var extParams = buildDef.GetValueOrDefault("externalParameters") as Dictionary<string, object?> ?? new(StringComparer.Ordinal);
        var declared = PyText(extParams.GetValueOrDefault("declaredBaseline"));
        var mBase = Regex.Match(declared, @"^check1-(\d+) PASS=(\d+)$");
        if (!mBase.Success || mBase.Groups[1].Value == "0" || mBase.Groups[2].Value == "0")
        {
            issues.Add($"SLSA 派生面基线句非法或为 0：{PyScalar.PyRepr(declared)}（修复指引：基线取自 " +
                       "core.quality_baseline 期望值——写 0 等于虚报门禁口径）");
        }
        else
        {
            var (wantChecks, wantPass) = Baseline(root);
            if (wantChecks != 0 || wantPass != 0)
            {
                if (long.Parse(mBase.Groups[1].Value) != wantChecks || long.Parse(mBase.Groups[2].Value) != wantPass)
                    issues.Add($"SLSA 派生面基线句与 quality_baseline 期望值不一致：{declared}（修复指引：两处须同源）");
            }
        }

        // A2A 卡片 ↔ 端点契约
        var card = A2a(root);
        var cardSkills = (card.GetValueOrDefault("skills") as List<object?> ?? new List<object?>())
            .OfType<Dictionary<string, object?>>().ToList();
        if (cardSkills.Count != Endpoints(contract).Count)
            issues.Add("A2A 卡片 skills 数与端点契约不一致（修复指引：卡片能力面须与契约同源）");
        if (PyText(contract.GetValueOrDefault("status")) != "implemented"
            && !PyText(card.GetValueOrDefault("x-nf-note")).Contains("未实装"))
        {
            issues.Add("A2A 卡片未声明「服务未实装」（修复指引：不得据此宣称在线能力）");
        }
        foreach (var sk in cardSkills)
        {
            if (!PyTruthy(sk.GetValueOrDefault("id")) || !PyTruthy(sk.GetValueOrDefault("description")))
                issues.Add("A2A 卡片 skill 缺 id/description（修复指引：能力面须自述）");
        }

        // PROV-O 溯源图
        var pv = Prov(root);
        var pvGraph = (pv.GetValueOrDefault("@graph") as List<object?> ?? new List<object?>())
            .OfType<Dictionary<string, object?>>().ToList();
        var pvIds = pvGraph.Select(n => n.GetValueOrDefault("@id")).ToList();
        if (pvIds.Count != pvIds.Distinct().Count())
            issues.Add("PROV 图存在重复节点 id（修复指引：实体/活动/代理同一 id 只出现一次）");
        var known = pvIds.Select(PyText).ToHashSet(StringComparer.Ordinal);
        foreach (var n in pvGraph)
        {
            foreach (var rel in new[] { "prov:used", "prov:generated", "prov:wasAssociatedWith" })
            {
                var target = n.GetValueOrDefault(rel);
                if (PyTruthy(target) && !known.Contains(PyText(target)))
                    issues.Add($"PROV 图关系 {rel} 指向不在册节点：{PyText(target)}（修复指引：被引用节点须在图内）");
            }
        }
        var provSrc = ReadJson(root, "05_资产库/provenance.json");
        var wantAssets = (provSrc.GetValueOrDefault("assets") as List<object?> ?? new List<object?>())
            .OfType<Dictionary<string, object?>>().Select(a => $"nf:asset/{PyText(a.GetValueOrDefault("key"))}")
            .ToHashSet(StringComparer.Ordinal);
        if (!wantAssets.IsSubsetOf(known))
            issues.Add($"PROV 图缺资产实体：{PyList(wantAssets.Except(known))}（修复指引：资产台账每条须有实体节点）");
        if (!pvGraph.Any(n => PyText(n.GetValueOrDefault("@type")) == "prov:Entity"))
            issues.Add("PROV 图无实体节点（修复指引：溯源图至少一个被证对象）");

        // CycloneDX
        var cdx = Cyclonedx(root);
        if (PyText(cdx.GetValueOrDefault("bomFormat")) != "CycloneDX" || PyText(cdx.GetValueOrDefault("specVersion")) != "1.5")
            issues.Add($"CycloneDX 头非法：{PyScalar.PyRepr(cdx.GetValueOrDefault("bomFormat"))}/" +
                       $"{PyScalar.PyRepr(cdx.GetValueOrDefault("specVersion"))}（修复指引：bomFormat=CycloneDX、specVersion=1.5）");
        var cdxComponents = (cdx.GetValueOrDefault("components") as List<object?> ?? new List<object?>())
            .OfType<Dictionary<string, object?>>().ToList();
        var bomRefs = cdxComponents.Select(c => c.GetValueOrDefault("bom-ref")).ToList();
        if (bomRefs.Count != bomRefs.Distinct().Count())
            issues.Add("CycloneDX 组件 bom-ref 重复（修复指引：每依赖一个唯一 bom-ref）");
        if (!Regex.IsMatch(PyText(cdx.GetValueOrDefault("serialNumber")), @"^urn:uuid:[0-9a-f-]{36}$"))
            issues.Add($"CycloneDX serialNumber 非 urn:uuid 形态：{PyScalar.PyRepr(cdx.GetValueOrDefault("serialNumber"))}" +
                       "（修复指引：由声明摘要派生，勿用随机 UUID）");
        var hardSet = cdxComponents.Where(c => PyText(c.GetValueOrDefault("scope")) == "required")
            .Select(c => PyText(c.GetValueOrDefault("name"))).ToHashSet(StringComparer.Ordinal);
        var wantHard = PurityTables.Entries.Hard.Keys.ToHashSet(StringComparer.Ordinal);
        if (wantHard.Count > 0 && !hardSet.SetEquals(wantHard))
            issues.Add($"CycloneDX 硬依赖集与登记面不一致：{PyList(hardSet)}（期望 {PyList(wantHard)}）" +
                       "（修复指引：两形同源——都读 purity_scan 登记面）");

        // VC
        var vc = Vc(root);
        var vcContext = (vc.GetValueOrDefault("@context") as List<object?> ?? new List<object?>()).Select(PyText).ToList();
        if (!vcContext.Contains("https://www.w3.org/ns/credentials/v2"))
            issues.Add("VC 缺 v2 上下文（修复指引：@context 须含 https://www.w3.org/ns/credentials/v2）");
        var vcTypes = (vc.GetValueOrDefault("type") as List<object?> ?? new List<object?>()).Select(PyText).ToList();
        if (!vcTypes.Contains("VerifiableCredential")) issues.Add("VC type 缺 VerifiableCredential");
        if (!PyTruthy(vc.GetValueOrDefault("issuer"))
            || !Regex.IsMatch(PyText(vc.GetValueOrDefault("validFrom")), @"^\d{4}-\d{2}-\d{2}$"))
        {
            issues.Add("VC 缺 issuer 或 validFrom（修复指引：自 protocol/approvals/* 取批准人与批准日）");
        }
        var subj = vc.GetValueOrDefault("credentialSubject") as Dictionary<string, object?> ?? new(StringComparer.Ordinal);
        if (!Sha256Re.IsMatch(PyText(subj.GetValueOrDefault("receiptRoot"))))
            issues.Add($"VC credentialSubject.receiptRoot 非 sha256：{PyScalar.PyRepr(subj.GetValueOrDefault("receiptRoot"))}" +
                       "（修复指引：凭证须绑定内容摘要）");
        if (!vc.ContainsKey("proof") && !PyText(vc.GetValueOrDefault("x-nf-proof-status")).Contains("unsigned"))
            issues.Add("VC 无 proof 却未声明未签名状态（修复指引：x-nf-proof-status 须写明——形状可读 ≠ 可验证）");

        // C2PA
        var c2 = C2pa(root);
        if (!PyText(c2.GetValueOrDefault("claim_generator")).StartsWith("NinFenz", StringComparison.Ordinal))
            issues.Add("C2PA 缺 claim_generator（修复指引：须自述生成器）");
        var c2Assertions = (c2.GetValueOrDefault("assertions") as List<object?> ?? new List<object?>())
            .OfType<Dictionary<string, object?>>().ToList();
        var labels = c2Assertions.Select(a => PyText(a.GetValueOrDefault("label"))).ToHashSet(StringComparer.Ordinal);
        if (!labels.Contains("c2pa.hash.data") || !labels.Contains("c2pa.actions"))
            issues.Add($"C2PA 断言面不全（修复指引：须含 c2pa.hash.data 与 c2pa.actions）：{PyList(labels)}");
        var hd = c2Assertions.FirstOrDefault(a => PyText(a.GetValueOrDefault("label")) == "c2pa.hash.data")
                 ?.GetValueOrDefault("data") as Dictionary<string, object?>;
        if (!Sha256Re.IsMatch(PyText(hd?.GetValueOrDefault("hash"))))
            issues.Add("C2PA hash.data 非 sha256（修复指引：硬绑定摘要须 64 位小写十六进制）");
        if (!PyText(c2.GetValueOrDefault("x-nf-package-status")).Contains("未封装"))
            issues.Add("C2PA 未声明封装/签名状态（修复指引：JSON 清单 ≠ 生产级 C2PA 包）");

        // CID
        var ci = Cid(root);
        var ciEntries = (ci.GetValueOrDefault("entries") as List<object?> ?? new List<object?>())
            .OfType<Dictionary<string, object?>>().ToList();
        if (ciEntries.Count != Entries(rec).Count)
            issues.Add($"CID 索引条目数与回执不一致：{ciEntries.Count} vs {Entries(rec).Count}");
        foreach (var e in ciEntries)
        {
            if (!Regex.IsMatch(PyText(e.GetValueOrDefault("cid")), @"^b[a-z2-7]{50,}$"))
            {
                issues.Add($"CID 形态非法：{PyText(e.GetValueOrDefault("path"))}（修复指引：CIDv1 multibase base32 小写，" +
                           "前缀 b + raw codec 0x71 + sha2-256 multihash）");
                break;
            }
        }

        // 决策面
        var ds = Decisions(root);
        var declDl = ReadJson(root, "protocol/decision_layer.json");
        var dsAdapters = (ds.GetValueOrDefault("adapters") as List<object?> ?? new List<object?>()).Count;
        var declAdapters = (declDl.GetValueOrDefault("adapters") as List<object?> ?? new List<object?>()).Count;
        if (dsAdapters != declAdapters)
            issues.Add($"决策面适配器数与声明不一致：{dsAdapters} vs {declAdapters}");
        var dsCandidates = (ds.GetValueOrDefault("candidates") as List<object?> ?? new List<object?>()).Count;
        var declCandidates = (declDl.GetValueOrDefault("candidates") as List<object?> ?? new List<object?>()).Count;
        if (dsCandidates != declCandidates)
            issues.Add($"决策面候选数与声明不一致：{dsCandidates} vs {declCandidates}");
        if (!PyText(ds.GetValueOrDefault("x-nf-internal")).Contains("不随本面发布"))
            issues.Add("决策面缺「工单不入公开面」声明（修复指引：写明内部档案边界，不得让外部以为逐次决策已公开）");
        if ((ds.GetValueOrDefault("publicDecisionIndex") as List<object?> ?? new List<object?>()).Count == 0)
            issues.Add("决策面缺公开裁决索引（修复指引：results/audit/*.md 的 frontmatter 可派生）");

        var stats = new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["openapi_paths"] = (long)oaPaths.Count,
            ["asyncapi_channels"] = (long)aaChannels.Count,
            ["intoto_subjects"] = (long)stSubjects.Count,
            ["sbom_packages"] = (long)sbPackages.Count,
            ["slsa_subjects"] = (long)slSubjects,
            ["a2a_skills"] = (long)cardSkills.Count,
            ["prov_nodes"] = (long)pvGraph.Count,
            ["prov_counts"] = pv.GetValueOrDefault("x-nf-counts") ?? new Dictionary<string, object?>(StringComparer.Ordinal),
            ["cyclonedx_components"] = (long)cdxComponents.Count,
            ["vc_type"] = vcTypes.Count > 0 ? vcTypes[0] : "",
            ["c2pa_assertions"] = (long)c2Assertions.Count,
            ["cid_entries"] = (long)ciEntries.Count,
            ["decision_adapters"] = (long)dsAdapters,
            ["decision_candidates"] = (long)dsCandidates,
            ["decision_audits"] = (long)((ds.GetValueOrDefault("publicDecisionIndex") as List<object?>)
                                          ?? new List<object?>()).Count,
            ["issues"] = (long)issues.Count,
        };
        return (issues, stats);
    }

    /// <summary>门禁摘要句（等价 <c>interop_export.summary</c>）。</summary>
    public static string Summary(Dictionary<string, object?> stats)
        => $"OpenAPI 路径 {stats.GetValueOrDefault("openapi_paths")} / AsyncAPI 通道 {stats.GetValueOrDefault("asyncapi_channels")} / " +
           $"in-toto subject {stats.GetValueOrDefault("intoto_subjects")} / SBOM 包 {stats.GetValueOrDefault("sbom_packages")} / " +
           $"SLSA subject {stats.GetValueOrDefault("slsa_subjects")} / A2A skills {stats.GetValueOrDefault("a2a_skills")} / " +
           $"PROV 节点 {stats.GetValueOrDefault("prov_nodes")} / 决策面 适配器 {stats.GetValueOrDefault("decision_adapters")}" +
           $"（裁决索引 {stats.GetValueOrDefault("decision_audits")}）";

    private static List<Dictionary<string, object?>> Endpoints(Dictionary<string, object?> contract)
        => (contract.GetValueOrDefault("endpoints") as List<object?> ?? new List<object?>())
            .OfType<Dictionary<string, object?>>().ToList();

    /// <summary>Python <c>sorted(...)</c> 的 repr 形态（消息里用）。</summary>
    private static string PyList(IEnumerable<string> items)
        => PyScalar.PyRepr(items.OrderBy(x => x, StringComparer.Ordinal).Cast<object?>().ToList());

    // ------------------------------------------------------------------ 工具

    /// <summary>
    /// 与 <c>interop_export._pinned_versions</c> 同口径：先读 <c>.github/requirements-*.txt</c>，
    /// 再由 <c>pyproject.toml</c> 的钉版字符串补齐；只取已声明版本，不猜 latest。
    /// </summary>
    private static Dictionary<string, string> PinnedVersions(string root)
    {
        var result = new Dictionary<string, string>(StringComparer.Ordinal);
        var github = Path.Combine(root, ".github");
        if (Directory.Exists(github))
        {
            foreach (var path in Directory.GetFiles(github, "requirements-*.txt")
                         .OrderBy(p => p, StringComparer.Ordinal))
            {
                IEnumerable<string> lines;
                try
                {
                    lines = File.ReadAllLines(path, StrictUtf8);
                }
                catch (Exception)
                {
                    continue;
                }
                foreach (var raw in lines)
                {
                    var body = raw.Split('#', 2)[0].Trim();
                    if (body.Length == 0 || body.StartsWith('-') || !body.Contains("==", StringComparison.Ordinal))
                        continue;
                    var match = PinnedRequirementRe.Match(body);
                    if (!match.Success) continue;
                    var name = match.Groups[1].Value.Trim().ToLowerInvariant();
                    var bracket = name.IndexOf('[');
                    if (bracket >= 0) name = name[..bracket].Trim();
                    var version = match.Groups[2].Value.Split(';', 2)[0].Trim().TrimEnd('\\').Trim();
                    if (name.Length > 0 && version.Length > 0) result.TryAdd(name, version);
                }
            }
        }

        // Python 用 tomllib 读取 optional-dependencies。这里提取形如 "pkg==ver" 的 TOML 字符串，
        // 覆盖项目既有钉版形态，且不会把注释中的示例误当依赖。
        var pyproject = Path.Combine(root, "pyproject.toml");
        if (File.Exists(pyproject))
        {
            foreach (Match match in PinnedTomlRe.Matches(File.ReadAllText(pyproject, StrictUtf8)))
            {
                var name = match.Groups[1].Value.Trim().ToLowerInvariant();
                var version = match.Groups[2].Value.Trim();
                if (name.Length > 0 && version.Length > 0) result.TryAdd(name, version);
            }
        }
        return result;
    }

    private static void AddPinnedMetadata(
        Dictionary<string, object?> target, string dependency, Dictionary<string, string> pinned, bool spdx)
    {
        var lower = dependency.ToLowerInvariant();
        var project = DependencyAliases.GetValueOrDefault(lower, lower);
        if (!pinned.TryGetValue(project, out var version) || version.Length == 0) return;
        if (spdx)
        {
            target["versionInfo"] = version;
            target["externalRefs"] = new List<object?>
            {
                new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["referenceCategory"] = "PACKAGE-MANAGER",
                    ["referenceType"] = "purl",
                    ["referenceLocator"] = $"pkg:pypi/{project}@{version}",
                },
            };
            return;
        }
        target["version"] = version;
        target["purl"] = $"pkg:pypi/{project}@{version}";
    }

    /// <summary>仓内声明日期的最大值（YYYY-MM-DD）；取不到返回空串。</summary>
    public static string DeclaredMaxDate(string root)
    {
        var dates = new List<string>();
        foreach (var rel in new[] { "protocol/score_baseline.json", "05_资产库/provenance.json" })
        {
            var path = Path.Combine(root, rel.Replace('/', Path.DirectorySeparatorChar));
            if (!File.Exists(path)) continue;
            dates.AddRange(DateRe.Matches(StrictUtf8.GetString(File.ReadAllBytes(path))).Select(m => m.Value));
        }
        var adir = Path.Combine(root, "protocol", "approvals");
        if (Directory.Exists(adir))
        {
            foreach (var name in Directory.GetFiles(adir, "*.json").Select(f => Path.GetFileName(f) ?? "")
                         .OrderBy(n => n, StringComparer.Ordinal))
            {
                var path = Path.Combine(adir, name);
                dates.AddRange(DateRe.Matches(StrictUtf8.GetString(File.ReadAllBytes(path))).Select(m => m.Value));
            }
        }
        return dates.Count > 0 ? dates.Max(StringComparer.Ordinal)! : "";
    }

    /// <summary>基线真源 = <c>quality_baseline.EXPECTED_CHECKS / EXPECTED_PASS</c>（按同源常量解析）。</summary>
    public static (long Checks, long Pass) Baseline(string root)
    {
        var path = Path.Combine(root, "desktop", "src", "core", "quality_baseline.py");
        if (!File.Exists(path)) return (0, 0);
        var text = StrictUtf8.GetString(File.ReadAllBytes(path));
        var c = ExpectedChecksRe.Match(text);
        var p = ExpectedPassRe.Match(text);
        return (c.Success ? long.Parse(c.Groups[1].Value, CultureInfo.InvariantCulture) : 0,
                p.Success ? long.Parse(p.Groups[1].Value, CultureInfo.InvariantCulture) : 0);
    }

    private static List<Dictionary<string, object?>> Entries(Dictionary<string, object?> rec)
        => (rec.GetValueOrDefault("entries") as List<object?> ?? new List<object?>())
            .OfType<Dictionary<string, object?>>().ToList();

    private static string Str(Dictionary<string, object?> map, string key)
        => map.TryGetValue(key, out var v) && v is string s ? s : "";

    private static long ToLong(object? v) => v is null ? 0L : Convert.ToInt64(v, CultureInfo.InvariantCulture);

    private static string Short(string s, int n) => s.Length <= n ? s : s[..n];

    /// <summary>读 JSON（缺件 / 解析失败 → 空表；等价 Python <c>_read_json</c>）。</summary>
    public static Dictionary<string, object?> ReadJson(string root, string rel)
    {
        var path = Path.Combine(root, rel.Replace('/', Path.DirectorySeparatorChar));
        if (!File.Exists(path)) return new Dictionary<string, object?>(StringComparer.Ordinal);
        try
        {
            using var doc = JsonIo.ReadFile(path);
            return PythonJson.ToGraph(doc.RootElement) as Dictionary<string, object?> ?? new(StringComparer.Ordinal);
        }
        catch (Exception exc) when (exc is System.Text.Json.JsonException or IOException)
        {
            return new Dictionary<string, object?>(StringComparer.Ordinal);
        }
    }
}

/// <summary>
/// R5 依赖登记表的 C# 镜像（真源 = <c>core/purity_scan.py</c> 的 <c>HARD_ALLOW</c> / <c>SOFT_IMPORTS</c>）。
///
/// 纪律：这是**静态数据表**，不是代码分析——`purity-clean` 契约（AST 面）仍在范围外；
/// 本表按既有「镜像表机械导出」先例处理（导出件留 `_purity_tables.json.txt` 可复核）。
/// </summary>
public static class PurityTables
{
    public static (Dictionary<string, string> Hard, Dictionary<string, string> Soft) Entries { get; } =
        (new Dictionary<string, string>(StringComparer.Ordinal)
        {
            ["yaml"] = "PyYAML（仓库既有依赖；check16/28 同源解析，见 CONTRIBUTING §4.2 例外）",
        },
        new Dictionary<string, string>(StringComparer.Ordinal)
        {
            ["jsonschema"] = "IDL 标准实现交叉验证（可选对照；缺依赖则跳过该面）",
            ["PySide6"] = "CCV3 卡面占位图写入（缺依赖须给明确修复指引，不得裸 ImportError）",
            ["nf_pyengine"] = "PyO3 扩展（engine/rust/pyo3 构建）为可选进程内原语加速；" +
                              "缺扩展时 rust_pyext 回退 hashlib/repr，不把 Rust 工具链变成运行前提",
            ["laya"] = "决策层本地服务（scripts/serve_decision_model.py）的模型运行时；软导入 + 缺依赖给修复指引",
        });
}
