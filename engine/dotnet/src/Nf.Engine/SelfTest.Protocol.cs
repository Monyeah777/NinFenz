using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text;
using System.Text.RegularExpressions;

namespace Nf.Engine;

/// <summary>协议金标 / 决策层 / 退出面 / 回归 / 工作流 / 地理导出 / 装配 / 语料戳 / 馆藏回执负例。</summary>
public static partial class SelfTest
{
    // ---------------------------------------------------------------- ②⁹ᵏ 协议生成物 golden（第 77 片 · check31）

    private static void ProtocolGoldenCases(List<Check> checks, string work, string repoRoot)
    {
        // ① 真材料：真仓生成物 == 实时重算（**这一条绿就等价于两个生成物逐字节一致**）+ 统计数
        var (realIssues, realStats) = ProtocolGolden.VerifyGolden(repoRoot);
        checks.Add(new Check("协议生成物 golden·真仓（check31：生成物 == 实时重算 · 摘要 %s 字节 / schema %s 份）",
            realIssues.Count == 0 && Convert.ToInt64(realStats["schema_ids"]) == 9
            && Convert.ToInt64(realStats["report_bytes"]) > 50000,
            $"问题 {realIssues.Count} · report {realStats["report_bytes"]} 字节 · schema {realStats["schema_ids"]} 份"));

        // ② 合成：生成物缺失 → 两条「缺失」；生成物被篡改 → 两条「过期」（含人读摘要——真源注释点明它曾"只渲染不校验"）
        var root = Path.Combine(work, "protocol-golden");
        if (Directory.Exists(root)) Directory.Delete(root, recursive: true);
        Directory.CreateDirectory(Path.Combine(root, "protocol", "generated"));
        var (missingIssues, _) = ProtocolGolden.VerifyGolden(root);
        var missingText = string.Join(" | ", missingIssues);
        File.WriteAllText(Path.Combine(root, "protocol", "generated", ProtocolGolden.ReportName), "{}\n");
        File.WriteAllText(Path.Combine(root, "protocol", "generated", ProtocolGolden.SummaryName), "# 手改摘要\n");
        var (staleIssues, _) = ProtocolGolden.VerifyGolden(root);
        var staleText = string.Join(" | ", staleIssues);
        checks.Add(new Check("协议生成物 golden·合成（缺件两条 · 篡改两条「过期」· 人读摘要也在判）",
            missingText.Contains($"{ProtocolGolden.GeneratedDir}/{ProtocolGolden.ReportName} 缺失")
            && missingText.Contains($"{ProtocolGolden.GeneratedDir}/{ProtocolGolden.SummaryName} 缺失")
            && staleText.Contains($"{ProtocolGolden.GeneratedDir}/{ProtocolGolden.ReportName} 过期")
            && staleText.Contains($"{ProtocolGolden.GeneratedDir}/{ProtocolGolden.SummaryName} 过期"),
            $"缺件问题 {missingIssues.Count} · 篡改问题 {staleIssues.Count}"));

        // ③ 事件闭包（closure_scan）：只报告不设闸（issues 恒空）+ 三份事件集互斥划分
        var (closureIssues, closureStats) = ClosureScan.Scan(repoRoot);
        var linked = ConceptGraph.PyList(closureStats["linked_events"]).Count;
        var subOnly = ConceptGraph.PyList(closureStats["sub_only_events"]).Count;
        var pubOnly = ConceptGraph.PyList(closureStats["pub_only_events"]).Count;
        checks.Add(new Check("事件闭包扫描（只报告不设闸 · 三集互斥 · 模块数在册）",
            closureIssues.Count == 0 && Convert.ToInt64(closureStats["modules"]) > 0
            && linked + subOnly + pubOnly > 0,
            $"模块 {closureStats["modules"]} · 相连 {linked} · 仅订阅 {subOnly} · 仅发布 {pubOnly}"));
    }

    /// <summary>
    /// <summary>
    /// 决策层面（check33 第 15 条）三钉：真仓（声明完整 + stub 确定 + fail-closed 全绿）
    /// + 篡改声明（适配器缺 note · 候选 pulled=true 缺 local 三字段）+ 无声明件（summary 抛 KeyError →
    /// 按 check33 的 except 打成「不可用」）。金标由 probes/decision_layer_probe.py（真源模块原文）产出。
    /// </summary>
    private static void DecisionLayerCases(List<Check> checks, string work, string repoRoot)
    {
        const string RealGoldenDigest = "23314f1104ca53e07a7fc70acfb09760";
        const string TamperedGoldenDigest = "fff4d4a11b4240fcc10cad379bf019eb";
        const string AbsentGoldenDigest = "27c616bbc2385e1993c1909ca2121f18";

        var real = DecisionLayer.Scan(repoRoot);
        checks.Add(new Check("决策层·真仓（声明完整 + stub 确定性 + fail-closed · 与真源模块原文逐字节同摘要）",
            real.Ok && real.Issues.Count == 0 && real.LogDigest == RealGoldenDigest
            && Convert.ToInt64(real.Stats["primitives"]) == 3
            && Convert.ToInt64(real.Stats["adapters"]) == 3
            && Convert.ToInt64(real.Stats["candidates"]) == 3
            && real.Stats["issueless_stub"] is true,
            $"{real.SummaryLine} · 摘要 {real.LogDigest}（真源金标 {RealGoldenDigest}）"
            ));

        var tamperedRoot = Path.Combine(work, "decision-tampered");
        Fresh(tamperedRoot);
        Directory.CreateDirectory(Path.Combine(tamperedRoot, "protocol"));
        foreach (var (rel, b64) in DecisionLayerTamperedFiles) WriteBase64(tamperedRoot, rel, b64);
        var tampered = DecisionLayer.Scan(tamperedRoot);
        var text = string.Join(" | ", tampered.Issues);
        checks.Add(new Check("决策层·篡改声明（适配器缺 note · 候选 pulled=true 缺 local 三字段 = 4 条判出）",
            !tampered.Ok && tampered.Issues.Count == 4 && tampered.LogDigest == TamperedGoldenDigest
            && text.Contains("适配器 stub 缺 note（能力与边界须自述）")
            && text.Contains("候选 laya-multilingual 声明 pulled=true 却缺 local.how")
            && text.Contains("候选 laya-multilingual 声明 pulled=true 却缺 local.runtime")
            && text.Contains("候选 laya-multilingual 声明 pulled=true 却缺 local.served_by"),
            $"FAIL {tampered.Issues.Count} · 摘要 {tampered.LogDigest}（真源金标 {TamperedGoldenDigest}）"));

        var absentRoot = Path.Combine(work, "decision-absent");
        Fresh(absentRoot);
        var absent = DecisionLayer.Scan(absentRoot);
        checks.Add(new Check("决策层·无声明件（报缺声明 · summary 按 check33 的 except 打成「不可用」）",
            !absent.Ok && absent.Issues.Count == 1 && absent.LogDigest == AbsentGoldenDigest
            && absent.Issues[0] == "缺决策层声明 protocol/decision_layer.json（修复指引：补声明件再跑门禁）"
            && absent.Log[^1] == "决策层面：不可用",
            $"FAIL {absent.Issues.Count} · 末行 {absent.Log[^1]} · 摘要 {absent.LogDigest}"
            + $"（真源金标 {AbsentGoldenDigest}）"));
    }

    private static readonly (string Rel, string B64)[] DecisionLayerTamperedFiles =
    {
        ("protocol/decision_layer.json", "ewogICJhZGFwdGVycyI6IFsKICAgIHsKICAgICAgImNhbGlicmF0ZWQiOiBmYWxzZSwKICAgICAgImlkIjogInN0dWIiLAogICAgICAiaW5fZ2F0ZV9wYXRoIjogdHJ1ZSwKICAgICAgImtpbmQiOiAib2ZmbGluZS1kZXRlcm1pbmlzdGljIgogICAgfSwKICAgIHsKICAgICAgImNhbGlicmF0ZWQiOiB0cnVlLAogICAgICAiZW5kcG9pbnQiOiAiaHR0cDovLzEyNy4wLjAuMTo8cG9ydD4vdjEvc3lzdGVtb25lIiwKICAgICAgImlkIjogInN5c3RlbW9uZS1odHRwIiwKICAgICAgImluX2dhdGVfcGF0aCI6IGZhbHNlLAogICAgICAia2luZCI6ICJsb2NhbC1odHRwIiwKICAgICAgIm5vdGUiOiAi5a+55o6l5pys5ZywIHR5cGVkLWRlY2lzaW9uIOacjeWKoe+8m+WPquivu+iwg+eUqO+8jOacjeWKoeS4jeaJp+ihjOWKqOS9nCIsCiAgICAgICJwcm90b2NvbCI6ICJQT1NUIHtzdGF0ZSwgcXVlc3Rpb25zfSDihpIge2RlY2xhcmVkIGtleXM6IHByb2JhYmlsaXRpZXN977yISmV2IC8gTGF5YSDns7sgU3lzdGVtLTEg5pyN5Yqh5Y+j5b6E77yJIgogICAgfSwKICAgIHsKICAgICAgImNhbGlicmF0ZWQiOiBmYWxzZSwKICAgICAgImlkIjogIm9wZW5haS1qc29uIiwKICAgICAgImluX2dhdGVfcGF0aCI6IGZhbHNlLAogICAgICAia2luZCI6ICJyZW1vdGUtaHR0cCIsCiAgICAgICJub3RlIjogIuS7u+S4gOiBiuWkqeaooeWei+S7peWPl+mZkCBKU09OIOS9nOetlO+8myoq5YW26Ieq5oql5qaC546H5LiN5piv5qCh5YeG5qaC546HKirvvIjml6AgcHJvcGVyIHNjb3JpbmcgcnVsZSDkv53or4HvvInvvIzmlYUgY2FsaWJyYXRlZD1mYWxzZSIKICAgIH0KICBdLAogICJib3VuZGFyaWVzIjogWwogICAgIuWPque7meWGs+etluS4juamgueOh++8jOS4jeaJp+ihjOWKqOS9nO+8iOacjeWKoeerr+S4jiBORiDkvqflnYfkuI3okL3lnLDliqjkvZzvvIkiLAogICAgIuS4jeeUn+aIkOato+aWh++8muWGs+etluWxgumdnuiHquWbnuW9ku+8jOWGheWuueS7jeeUseWGheWuueWlkee6puWxgu+8iOWNj+iuriArIOaooeWdlyArIOi1hOS6p++8ieaJv+aLhSIsCiAgICAi5qih5Z6L5LiN5YWl6Zeo56aB6Lev5b6E77ya6Zeo56aB5b+F6aG756a757q/56Gu5a6a77yIc3R1YiDkuYvlpJbkuIDlvovpnZ7pl6jnpoHku7vliqHvvIkiLAogICAgIuamgueOh+eahOS9v+eUqOeUseiwg+eUqOaWueiHquivgeagoeWHhu+8iOacrOWxguS4jeabv+iwg+eUqOaWueaJv+aLheWGs+etluWQjuaenO+8iSIsCiAgICAi5YCZ6YCJ5qih5Z6L5Y+q5ZyoKirmmL7lvI/mi4nlj5YqKuWQjuWPr+eUqO+8iHB1bGxlZD1mYWxzZSDljbPmnKrkuIvovb3vvJtORiDkuI3mm7/kvZzogIXlhrPlrprkuIvovb3mlbDljYEgR0Ig5p2D6YeN77yJIgogIF0sCiAgImNhbmRpZGF0ZXMiOiBbCiAgICB7CiAgICAgICJjYWxpYnJhdGVkX2RlY2lzaW9ucyI6IHRydWUsCiAgICAgICJjb250ZXh0IjogMTAyNCwKICAgICAgImVuY29kZXIiOiAiYW5zd2VyZG90YWkvTW9kZXJuQkVSVC1sYXJnZSIsCiAgICAgICJldmlkZW5jZSI6ICIyMDI2LTA5LTIxIOWPluWbnuaooeWei+WNoeS4jumFjee9ruWunua1i++8mmFjY3VyYWN5IDAuNzY2IC8gQnJpZXIgMC4wNjIgLyBFQ0UgMC4yMTMgLyBzY29yZSBNQUUgMC4yNDLvvJvlm5vnp40gd29ya2Zsb3cg5LiT55So77yIYWdlbnQtdHJhY2UgLyBjdXN0b21lci1zZXJ2aWNlIC8gaW52b2ljZSAvIHNlY3VyaXR577yJ77yb5L2c6ICF6Ieq6L+wIHNwZWNpYWxpc3TvvIjli7/kvZzpnZnpu5jpu5jorqTvvInjgIHoi7HmlofkuJPnlKjjgIHpgInpobnmlbDlu7rorq4gPDIwIiwKICAgICAgImlkIjogImxheWEtdHlwZWQtZGVjaXNpb25zIiwKICAgICAgImxhbmd1YWdlIjogWwogICAgICAgICJlbiIKICAgICAgXSwKICAgICAgImxpY2Vuc2UiOiAiYXBhY2hlLTIuMCIsCiAgICAgICJwYXJhbXMiOiAiNDIxTSIsCiAgICAgICJwdWxsZWQiOiBmYWxzZSwKICAgICAgInNvdXJjZSI6ICJoZjpjb252YWlpbm5vdmF0aW9ucy9sYXlhLXR5cGVkLWRlY2lzaW9ucyIKICAgIH0sCiAgICB7CiAgICAgICJjYWxpYnJhdGVkX2RlY2lzaW9ucyI6IHRydWUsCiAgICAgICJjb250ZXh0IjogMTAyNCwKICAgICAgImVuY29kZXIiOiAibW1CRVJULWJhc2UiLAogICAgICAiZXZpZGVuY2UiOiAiMjAyNi0wOS0yMSDlj5blm57mqKHlnovljaHlrp7mtYvvvJrkuI4gYmFzZSDlkIzml4/nmoTlgZrlpJror63pnaLvvIhORiDkuK3mlocgc3RhdGUg5bqU5LyY5YWI5q2k5Y+Y5L2T77yM6ICM6Z2e6Iux5paH5LiT55SoIGNoZWNrcG9pbnTvvIkiLAogICAgICAiaWQiOiAibGF5YS1tdWx0aWxpbmd1YWwiLAogICAgICAibGFuZ3VhZ2UiOiBbCiAgICAgICAgIjEwMCsgbGFuZ3VhZ2Vz77yI5ZCr5Lit5paH77yJIgogICAgICBdLAogICAgICAibGljZW5zZSI6ICJhcGFjaGUtMi4wIiwKICAgICAgInBhcmFtcyI6ICIzMjJNIiwKICAgICAgInB1bGxlZCI6IHRydWUsCiAgICAgICJzb3VyY2UiOiAiaGY6Y29udmFpaW5ub3ZhdGlvbnMvbGF5YS1tdWx0aWxpbmd1YWwiCiAgICB9LAogICAgewogICAgICAiYmFzZV9tb2RlbCI6ICJRd2VuL1F3ZW4zLjUtOUIiLAogICAgICAiYmFzZV9yZXZpc2lvbiI6ICJjMjAyMjM2MjM1NzYyZTFjODcxYWQwY2NiNjBjOGVlNWJhMzM3YjlhIiwKICAgICAgImNhbGlicmF0ZWRfZGVjaXNpb25zIjogdHJ1ZSwKICAgICAgImV2aWRlbmNlIjogIjIwMjYtMDktMjEg5Y+W5Zue5qih5Z6L5Y2h5LiOIGFkYXB0ZXJfY29uZmlnIOWunua1i++8mumdnuiHquWbnuW9kuOAgeWPquivhOiwg+eUqOaWuee7meeahOWAmemAie+8m+S4ieWOn+ivrSBjaG9pY2Uvbm91bC9zY29yZe+8m+mcgOS4iua4uCBiYXNlIOeyvuehriByZXZpc2lvbiArIE9wZW4tSmV2IGxvYWRlciArIEdQVe+8m0F1dG9QZWZ0TW9kZWwg55u06LCD5LiN5a6e546w6K+l5o6l5Y+jIiwKICAgICAgImlkIjogIm9wZW4tamV2LTliIiwKICAgICAgImtpbmQiOiAiTG9SQSBhZGFwdGVyICsgc2NhbGFyIGRlY2lzaW9uIGhlYWQiLAogICAgICAibGljZW5zZSI6ICJhcGFjaGUtMi4wIiwKICAgICAgInB1bGxlZCI6IGZhbHNlLAogICAgICAic2VydmUiOiAicHl0aG9uIC1tIGpldi5zZXJ2ZXIgLS1jaGVja3BvaW50IC4vY2hlY2twb2ludHMvb3Blbi1qZXYtOWIvcGFja2FnZS9jaGVja3BvaW50IC0tZGV2aWNlIGN1ZGE6MCAtLW1heC1sZW5ndGggNDA5NiAtLWJhdGNoLXNpemUgMSAtLWhvc3QgMTI3LjAuMC4xIC0tcG9ydCA4NzkxIiwKICAgICAgInNvdXJjZSI6ICJoZjpaZWZhbkNhaS9PcGVuLUpldi05QiIKICAgIH0KICBdLAogICJub3RlIjogIuWGs+etluWxguerr+WPo++8iOacuuWItuWAn+mJtO+8mumdnuiHquWbnuW9kiB0eXBlZC1kZWNpc2lvbiDmqKHlnovnmoQgY2hvaWNlIC8gbm91bCAvIHNjb3JlIOS4ieWOn+ivreKAlOKAlOWGs+etliA9IOWcqCoq6LCD55So5pa557uZ5a6aKirnmoTlgJnpgInpm4bkuIrmiqXmpoLnjofliIbluIPkuI4gYXJnbWF477yM5LiN55Sf5oiQ5q2j5paH44CB5LiN5omn6KGM5Yqo5L2c77yJ44CCTkYg5L6n5Y+q5YGa5LiJ5Lu25LqL77ya5a6a5LmJ6Zeu6aKY5LiO562U5qGI55qE5b2i54q244CB5oqK5qih5Z6L5pS+5Zyo6Zeo56aB5LmL5aSW44CB5oqK5LiN5Y+v55So5oOF5b2iIGZhaWwtY2xvc2VkIOaIkCBhYnN0YWluZWTjgIIiLAogICJwcmltaXRpdmVzIjogewogICAgImNob2ljZSI6ICLlnKjosIPnlKjmlrnnu5nlrprnmoTlgJnpgInpm4bkuIrmiqXmpoLnjofliIbluIMgKyBhcmdtYXjvvJvlgJnpgInpm4bnlLHosIPnlKjmlrnmj5DkvpvvvIzmqKHlnovkuI3lvpfoh6rpgKDlgJnpgIkiLAogICAgIm5vdWwiOiAi5a+55piv6Z2e6Zeu6aKY5oql5qaC546HIHAodHJ1ZSkiLAogICAgInNjb3JlIjogIuWvueiwg+eUqOaWuee7meWumueahOacieW6j+etiee6p+aKpeamgueOh+WIhuW4gyArIOacn+acm+WAvCIKICB9LAogICJyZWxhdGVkIjogWwogICAgInByb3RvY29sL1dPUkxEX01PREVMLm1k77yI56Gu5a6a5oCn54q25oCB5aWR57qm77ya5Yaz562W5bGC55qEIHN0YXRlIOmdoueUseWug+e7me+8iSIsCiAgICAiMDJf6IGU5Yqo5rOo5YaM6KGoLm1kIMKnOO+8iFA0MCDooYzkuLrlhrPnrZblsYLkvY3vvJrlhrPnrZblsYLmnI3liqHnmoToo4XphY3mp73kvY3vvIkiCiAgXSwKICAicmVzcG9uc2VfY29udHJhY3QiOiB7CiAgICAiYWJzdGFpbl9ydWxlIjogImFkYXB0ZXIg5LiN5Y+v55So44CB6LaF5pe25oiW6L6T5Ye65LiN5ZCIIHNjaGVtYSDihpIgc3RhdHVzPWFic3RhaW5lZCArIHJlYXNvbu+8iOS4peemgeeMnOa1i+ihpem9kO+8muWGs+etluWxgueahOayiem7mOavlOe8lumAoOWuieWFqO+8iSIsCiAgICAiYW5zd2VycyI6ICJuYW1lIOKGkiB7dHlwZSwgcHJvYnM/OiBbZmxvYXRdLCBvcHRpb25zPzogW3N0cmluZ10sIGFyZ21heD86IHN0cmluZ3xpbnQsIHA/OiBmbG9hdCwgdmFsdWU/OiBmbG9hdH3vvJtwcm9icyDmsYLlkozpobsg4omIIDHvvIjlrrnlt64gMWUtNu+8ie+8jOmVv+W6pumhu+etieS6jiBvcHRpb25zL2xldmVscyDplb/luqYiLAogICAgIm1ldGEiOiAiYWRhcHRlciAvIGNhbGlicmF0ZWTvvIjmmK/lkKbmoKHlh4bmpoLnjofvvIkvIG5vbl9nYXRlOiB0cnVlIC8gc2NoZW1h77ybc3lzdGVtb25lLWh0dHAg5Y+m5pyJIG1vZGVsIOWtl+autSIsCiAgICAicmVxdWlyZWQiOiBbCiAgICAgICJzY2hlbWEiLAogICAgICAic3RhdHVzIiwKICAgICAgImFuc3dlcnMiLAogICAgICAibWV0YSIKICAgIF0sCiAgICAic3RhdHVzX3ZvY2FidWxhcnkiOiBbCiAgICAgICJvayIsCiAgICAgICJhYnN0YWluZWQiCiAgICBdCiAgfSwKICAic2NoZW1hIjogIm5mLWRlY2lzaW9uLWxheWVyLzEiLAogICJzdGF0dXMiOiAiYWN0aXZlIiwKICAid29ya2xvb3AiOiB7CiAgICAiZW50cnkiOiAicHl0aG9uIHNjcmlwdHMvbmYucHkgd29ya2xvb3AgWy0tYWRhcHRlciBzdHVifHN5c3RlbW9uZS1odHRwXSBbLS10b3AgTl0gWy0td3JpdGVdIiwKICAgICJub25fbmVnb3RpYWJsZXMiOiBbCiAgICAgICLlhrPnrZblsYLkuI3nlJ/miJDlhoXlrrnvvIhMYXlhIOaYr+e8lueggeWZqOWIhuexu+OAgU9wZW4tSmV2IOmdnuiHquWbnuW9kuWGs+etluWktOKAlOKAlOmDveS4jeS8muWGmeS7o+eggeaIluato+aWh++8iSIsCiAgICAgICLlt6XljZXlj6rokL3lhoXpg6jmoaPmoYjvvIjorqHliJLnsbvkuqflk4HlhoXpg6jmtojljJbvvJvlhazlvIDku5Plj6rmlLbnu5PmnpwgKyBhdWRpdO+8iSIsCiAgICAgICLokL3nrJTmlrnlv4XpobvmmK8gd29ya2Vy77yM5Yaz562W5qih5Z6L5Y+q5o+Q5L6b6YCJ5oup5LiO5qaC546HIiwKICAgICAgIumqjOaUtuWPquiupOmXqOemge+8iHZlcmlmeS5zaCDlhajnu78gKyBuZiBjb25mb3JtYW5jZSBjb25mb3JtYW5077yJIgogICAgXSwKICAgICJyb2xlIjogIuWGs+etluWxgumpseWKqOeahOaehOW7uuWbnui3r++8muWGs+etluaooeWei+aMkea0uyAvIOWIpOmjjumZqSAvIOWumuOAjOiDveWQpuWcqOS4jeeisOWbnuaJp+mUmuWumuS7tuadoeS7tuS4i+WujOaIkOOAje+8m+eUn+aIkOW8jyB3b3JrZXLvvIjkurogLyBDb2RleCAvIOeUn+aIkOW8j+aooeWei++8ieiQveeslO+8m05GIOmXqOemgemqjOaUtiIsCiAgICAic291cmNlcyI6IFsKICAgICAgInByb3RvY29sL3R5cGVfYmFja2xvZy5qc29u77yI5pyq5a6a5Z6L5LqL5Lu25a2X5q6177yJIiwKICAgICAgInByb3RvY29sL3BpcGVsaW5lX2Fkdmlzb3J5Lmpzb27vvIjnrqHnur8gYWR2aXNvcnnvvIkiCiAgICBdCiAgfQp9"),
    };

    /// <summary>
    /// 出口/派生面五钉：**他证通道**（check38 第二腿 · 真源 scripts/interop_thirdparty_kit.check）
    /// 真仓 / 篡改（sha 非 64 位十六进制 + 状态表缺面 = 2 条判出）/ 缺件；**入仓一致**
    /// （check33 第 14 条）真仓 / 篡改（改一字符 → 恰好一个 kind 判漂移）。两腿都以真源代码为
    /// oracle，金标由 probes/exit_faces_probe.py 产出。
    /// </summary>
    private static void ExitFacesCases(List<Check> checks, string work, string repoRoot)
    {
        const string TpRealGolden = "a28aa09cf3a4c6e657b67340980c1333";
        const string TpTamperedGolden = "97ca0615c602922e0d7dfbbe259f3e3f";
        const string TpAbsentGolden = "bb97a48d037a3fd6c16b1582237ab6ff";
        const string InRepoRealGolden = "e3b0c44298fc1c149afbf4c8996fb924";
        const string InRepoTamperedGolden = "2700a1029685e421b9ac050c6d813302";

        var real = ExitFaces.ThirdPartyCheck(repoRoot);
        var realDigest = real.LogDigest();
        checks.Add(new Check("出口面·他证通道·真仓（14 面全在行 · 与真源脚本 check() 逐字节同摘要）",
            real.Ok && realDigest == TpRealGolden
            && Convert.ToInt64(real.Stats["faces"]) == 14 && Convert.ToInt64(real.Stats["rows"]) == 14
            && Convert.ToInt64(real.Stats["filled"]) == 13 && Convert.ToInt64(real.Stats["unfilled"]) == 1,
            $"FAIL {real.Issues.Count} · 面 {real.Stats["faces"]} · 行 {real.Stats["rows"]} · 已填 {real.Stats["filled"]}"
            + $" · 摘要 {realDigest}（真源金标 {TpRealGolden}）"));

        // 篡改：整行删掉 ccv3（缺面）+ 首个带 sha 的行改成非 64 位十六进制
        var tamperedRoot = Path.Combine(work, "exit-thirdparty-tampered");
        Fresh(tamperedRoot);
        foreach (var (rel, b64) in ThirdPartyTamperedFiles) WriteBase64(tamperedRoot, rel, b64);
        var docSrc = Path.Combine(repoRoot, ExitFaces.ThirdPartyDocRel.Replace('/', Path.DirectorySeparatorChar));
        if (File.Exists(docSrc))
        {
            var docDst = Path.Combine(tamperedRoot, ExitFaces.ThirdPartyDocRel.Replace('/', Path.DirectorySeparatorChar));
            Directory.CreateDirectory(Path.GetDirectoryName(docDst)!);
            File.Copy(docSrc, docDst, overwrite: true);
        }
        var tampered = ExitFaces.ThirdPartyCheck(tamperedRoot);
        var tamperedText = string.Join(" | ", tampered.Issues);
        checks.Add(new Check("出口面·他证通道·篡改（sha256 非 64 位十六进制 + 状态表缺面 = 2 条判出）",
            !tampered.Ok && tampered.Issues.Count == 2 && tampered.LogDigest() == TpTamperedGolden
            && tamperedText.Contains("的 output_sha256 不是 64 位十六进制（不可用「看起来通过」代替）")
            && tamperedText.Contains("状态表缺面：ccv3（每个互操作面都必须有一行，含 not-applicable）"),
            $"FAIL {tampered.Issues.Count} · 摘要 {tampered.LogDigest()}（真源金标 {TpTamperedGolden}）"));

        var absentRoot = Path.Combine(work, "exit-thirdparty-absent");
        Fresh(absentRoot);
        var absent = ExitFaces.ThirdPartyCheck(absentRoot);
        checks.Add(new Check("出口面·他证通道·缺件（缺回填状态表 → 单条 FAIL，不静默放过）",
            !absent.Ok && absent.Issues.Count == 1 && absent.LogDigest() == TpAbsentGolden
            && absent.Log()[^1] == "他证通道 子扫描：FAIL 1",
            $"FAIL {absent.Issues.Count} · 末行 {absent.Log()[^1]} · 摘要 {absent.LogDigest()}"
            + $"（真源金标 {TpAbsentGolden}）"));

        var inRepo = ExitFaces.InteropInRepoIssues(repoRoot);
        var inRepoDigest = ExitFaces.Digest32(inRepo.Select(i => "[FAIL] " + i));
        checks.Add(new Check("出口面·入仓一致·真仓（12 个 kind 均在盘且与实时派生逐字节一致）",
            inRepo.Count == 0 && inRepoDigest == InRepoRealGolden,
            $"FAIL {inRepo.Count} · 摘要 {inRepoDigest}（真源金标 {InRepoRealGolden}）"));

        var repoTree = Path.Combine(work, "exit-inrepo-tampered");
        Fresh(repoTree);
        CopyTree(repoRoot, repoTree);   // 入仓面比对要整棵源树在场（render 按 root 读源件）
        var sbom = Path.Combine(repoTree, ExitFaces.InteropDirRel.Replace('/', Path.DirectorySeparatorChar),
            "sbom.json");
        File.WriteAllBytes(sbom, ReplaceFirstBytes(File.ReadAllBytes(sbom),
            Encoding.UTF8.GetBytes("\"created\""), Encoding.UTF8.GetBytes("\"created_x\"")));
        var tamperedIn = ExitFaces.InteropInRepoIssues(repoTree);
        var tamperedInDigest = ExitFaces.Digest32(tamperedIn.Select(i => "[FAIL] " + i));
        checks.Add(new Check("出口面·入仓一致·篡改（sbom 改一字符 → 恰好一个 kind 判漂移）",
            tamperedIn.Count == 1 && tamperedInDigest == InRepoTamperedGolden
            && tamperedIn[0].Contains("互操作入仓面与实时派生不一致：sbom"),
            $"FAIL {tamperedIn.Count} · 摘要 {tamperedInDigest}（真源金标 {InRepoTamperedGolden}）"));
    }

    /// <summary>篡改后的他证通道状态表（真源口径：删 ccv3 整行 + 首个带 sha 的行写成 deadbeef）。</summary>
    private static readonly (string Rel, string B64)[] ThirdPartyTamperedFiles =
    {
        ("results/interop-thirdparty-status.md", "IyDkupLmk43kvZzmgKcgwrcg5LuW6K+B5Zue5aGr54q25oCB6KGoCgo+IOeUsSBgcHl0aG9uIHNjcmlwdHMvaW50ZXJvcF90aGlyZHBhcnR5X2tpdC5weSAtLWVtaXRgIOeUn+aIkOmqqOaetu+8m+eUseesrOS4ieaWueWbnuWhq+WPs+S+p+Wtl+auteOAggo+IOWIneWniyBgdmVyZGljdGAgPSBg5pyq5Zue5aGr77yI6YCa6YGT5bCx57uq77yJYO+8iOihqOekuumAmumBk+Wwsee7quOAgSoq5pyq6KKr5Lu75L2V56ys5LiJ5pa56LeR6L+HKirvvInjgIIKCnwgZmFjZSB8IGtpbmQgfCDlr7nnq6/lt6XlhbcgfCDlronoo4UgfCDlkb3ku6Tljp/mlocgfCB0b29sX3ZlcnNpb24gfCBydW5fYnkgfCBydW5fYXQgfCBvdXRwdXRfc2hhMjU2IHwgdmVyZGljdCB8IG5vdGUgfAp8LS0tfC0tLXwtLS18LS0tfC0tLXwtLS18LS0tfC0tLXwtLS18LS0tfC0tLXwKfCBgbWNwYCB8IHBlZXItY29uc3VtcHRpb24gfCDku7vmhI8gTUNQIOWuouaIt+err++8iENsYXVkZSBEZXNrdG9wIC8gbWNwLWluc3BlY3RvciDnrYnvvIkgfCDlr7nnq6/oh6rpgInvvJvmnI3liqHnq6/vvJpgcHl0aG9uIHNjcmlwdHMvbmYucHkgcnVuIC0tZm10IG1jcCAtLWRlc3Qgb3V0YCDkuqflh7ogbWNwLmpzb24g5b+r54WnIHwgYG5weCAteSBAbW9kZWxjb250ZXh0cHJvdG9jb2wvaW5zcGVjdG9yIC0tY2xpIHB5dGhvbiBzY3JpcHRzL25mLnB5IHNlcnZlIDxtY3AuanNvbj4gLS1tZXRob2QgdG9vbHMvbGlzdGAgfCBucHgg5pyA5paw56iz5a6a77yILXkg5ouJ5Y+W77yJIHwg5omn6KGM6ICF77yI5pys5py6IENvZGV4IOS8muivne+8icK3IOW3peWFt+S4uuesrOS4ieaWueWumOaWueWunueOsCB8IDIwMjYtMDktMjQgKEFzaWEvU2hhbmdoYWkpIHwgZGVhZGJlZWYgfCBQQVNT77yI5a+556uv5a6i5oi356uv5LiJ5pa55rOV5YWo6YOo5oiQ5Yqf77yJIHwg5b+r54Wn55SxIGBuZiBydW4gLS1waXBlbGluZSAwM1/nrqHnur/lupMvUDkwX+aKgOacr+aWh+aho+eUn+aIkOeuoee6vy5tZCAtLW1vZHVsZXMg6YCa55So57G7Ok0wMCzpgJrnlKjnsbs6TTgwIC0tZm10IG1jcCAtLXNlZWRgIOS6p+WHuu+8m0luc3BlY3RvciBDTEkg5LiN5pSv5oyBIHNlcnZlci9kaXNjb3Zlcu+8iOWFtuaUr+aMgeWIl+ihqOWQqyBpbml0aWFsaXplL3Rvb2xzL2xpc3QvcmVzb3VyY2VzL2xpc3QvcHJvbXB0cy9saXN0IOetie+8ie+8jOaVheS7peS4ieexu+WIl+ihqOS4uuivgeaNruOAgiB8CnwgYG9wZW5hcGlgIHwgb2ZmaWNpYWwtY2xpIHwgb3BlbmFwaS1zcGVjLXZhbGlkYXRvcu+8iOWumOaWueeUn+aAgeagoemqjOWZqO+8iSB8IHBpcCBpbnN0YWxsIG9wZW5hcGktc3BlYy12YWxpZGF0b3IgfCBgQzpcdG1wXG5mX2F1ZGl0XHZlbnZcU2NyaXB0c1xweXRob24uZXhlIC1tIG9wZW5hcGlfc3BlY192YWxpZGF0b3IgcmVzdWx0cy9pbnRlcm9wL29wZW5hcGkuanNvbmAgfCAwLjkuMCB8IOaJp+ihjOiAhe+8iOacrOacuiBDb2RleCDkvJror53vvInCtyDlt6XlhbfkuLrnrKzkuInmlrnlrpjmlrnlrp7njrAgfCAyMDI2LTA5LTI0IChBc2lhL1NoYW5naGFpKSB8IDVmZTljMTcyN2NhYTQyZmMxMTczMTYxZDhhMTgxMWUzYTYwNjk1NTE1ZDA5ZDU2YTliYmI4OGFlMjJmNDBjZDggfCBQQVNT77yI56ys5LiJ5pa55qCh6aqM5Zmo6YCa6L+H77yJIHwg6YCA5Ye656CBIDAgfAp8IGBhc3luY2FwaWAgfCBvZmZpY2lhbC1jbGkgfCBAYXN5bmNhcGkvY2xp77yI5a6Y5pa5IENMSe+8iSB8IG5wbSBpIC1nIEBhc3luY2FwaS9jbGkgfCBgbnB4IC15IEBhc3luY2FwaS9jbGkgdmFsaWRhdGUgcmVzdWx0cy9pbnRlcm9wL2FzeW5jYXBpLmpzb25gIHwgbnB4IOacgOaWsOeos+Wumu+8iC15IOaLieWPlu+8iSB8IOaJp+ihjOiAhe+8iOacrOacuiBDb2RleCDkvJror53vvInCtyDlt6XlhbfkuLrnrKzkuInmlrnlrpjmlrnlrp7njrAgfCAyMDI2LTA5LTI0IChBc2lhL1NoYW5naGFpKSB8IGQ4NDg1NTMwNGQxY2FlNmMzYjM2N2NhNzhkYjMxNGVhODk4ZjY5NTJmZWQ3NDg3MTA3YjkxZDJmMTcwZmQyODcgfCBQQVNT77yI5a6Y5pa5IENMSe+8mjAgZXJyb3LvvIkgfCDku5bor4HmipPlh7rnmoTnnJ/nvLrpmbflt7Lkv67vvJrpgJrpgZPplK7lkKsgYC9gIOacquaMiSBSRkMgNjkwMSDovazkuYkg4oaSIDQ0MyDmnaEgaW52YWxpZC1yZWbvvJvnjrAgMCBlcnJvcu+8iOS7heS/oeaBr+e6p++8muWumOaWueW7uuiuriBBc3luY0FQSSAzLjHvvInjgIIgfAp8IGBzYm9tYCB8IG9mZmljaWFsLWNsaSB8IHNwZHgtdG9vbHPvvIhTUERYIOWumOaWueW3peWFt++8iSB8IHBpcCBpbnN0YWxsIHNwZHgtdG9vbHMgfCBgcHlzcGR4dG9vbHMgLWkgcmVzdWx0cy9pbnRlcm9wL3Nib20uanNvbmAgfCA/IHwg5omn6KGM6ICF77yI5pys5py6IENvZGV4IOS8muivne+8icK3IOW3peWFt+S4uuesrOS4ieaWueWumOaWueWunueOsCB8IDIwMjYtMDktMjQgKEFzaWEvU2hhbmdoYWkpIHwgODViNTFiYjQ3MjczYmYzNThhNjkwZmE2ZjFmNWRkNjkwZjAyNjVlMGY0ZDRlNzQ0YTI2Njg2NTMwYTEyZTAyNCB8IFBBU1PvvIjlrpjmlrnlrp7njrDop6PmnpDpgJrov4fvvIkgfCDpgIDlh7rnoIEgMCB8CnwgYGN5Y2xvbmVkeGAgfCBvZmZpY2lhbC1jbGkgfCBjeWNsb25lZHgtY2xp77yI5a6Y5pa5IENMSe+8iSB8IOS4i+i9vSBjeWNsb25lZHgtY2xpIOWPkeihjOeJiO+8iEdpdEh1YiBSZWxlYXNlc++8iSB8IGBweXRob24gLWMgImpzb25zY2hlbWEudmFsaWRhdGUoY3ljbG9uZWR4Lmpzb24sIDxjeWNsb25lZHgtcHl0aG9uLWxpYj4vc2NoZW1hL19yZXMvYm9tLTEuNS5TTkFQU0hPVC5zY2hlbWEuanNvbikiYCB8IDExLjEyLjAgfCDmiafooYzogIXvvIjmnKzmnLogQ29kZXgg5Lya6K+d77yJwrcg5bel5YW35Li656ys5LiJ5pa55a6Y5pa55a6e546wIHwgMjAyNi0wOS0yNCAoQXNpYS9TaGFuZ2hhaSkgfCBlM2Q1MjI2OWViYjJjZTI4N2E0ZjIyYjc3YWRmZGVkOWU3MDUwOTAwOGY2ZTY2NmM2N2ZjY2U0MjY1NDlhMjVhIHwgUEFTU++8iOWumOaWuSBzY2hlbWEg5qCh6aqM6YCa6L+H77yJIHwg5a6Y5pa5IENMSe+8iGN5Y2xvbmVkeC1jbGkvLk5FVO+8ieacrOacuuS4jeWPr+W+l++8iOaXoCBHaXRIdWIg55u06L+e77yJ77yM5pS555So5a6Y5pa5IFB5dGhvbiDlupPlhoXnva4gc2NoZW1h77yb6L6T5Ye677yadmFsaWRhdGVkIGFnYWluc3QgYm9tLTEuNS5TTkFQU0hPVC5zY2hlbWEuanNvbu+8iOWumOaWueW6k+WGhee9ru+8jOWQqyBzcGR4IOW8leeUqO+8jOacrOWcsOino+aekO+8iSB8CnwgYHNsc2FgIHwgc2hhcGUtb25seSB8IHNsc2EtdmVyaWZpZXIgLyBDVUUg5bel5YW36ZO+77yI5a6Y5pa577yJIHwgZ28gaW5zdGFsbCBnaXRodWIuY29tL3Nsc2EtZnJhbWV3b3JrL3Nsc2EtdmVyaWZpZXIvdjIvY2xpL3Nsc2EtdmVyaWZpZXJAbGF0ZXN0IHwgYO+8iOingSBub3Rl77yJYCB8IC0gfCDmiafooYzogIXvvIjmnKzmnLogQ29kZXgg5Lya6K+d77yJwrcg5bel5YW35Li656ys5LiJ5pa55a6Y5pa55a6e546wIHwgMjAyNi0wOS0yNCAoQXNpYS9TaGFuZ2hhaSkgfCAyY2JiNjc5MjY0N2E4OTIxMWMyZDI1NjVmNzQ0ZjMwNmIxMDgzYTZjZTNiMTNkY2I4ZGExZjZlOGNiNzNjYWY4IHwg5LiN6YCC55So77yI5peg54us56uL5a6e546w5Y+v6LeR77yJIHwgc2xzYS12ZXJpZmllciDpnIAgZ28vZG9ja2Vy77yI5pys5py65LiN5Y+v5b6X77yJ5LiUIEdpdEh1YiDnm7Tov57kuI3lj6/ovr7vvJvmnKzpnaLnu7TmjIEgc2hhcGUtb25seSDliKTmja7vvIjlrpjmlrnmlofmnKzmoLjlr7nvvInvvIzkuI3orqHlhaXku5bor4HpgJrov4fmlbDjgIIgfAp8IGBpbnRvdG9gIHwgc2hhcGUtb25seSB8IGluLXRvdG/vvIjlrpjmlrnlrp7njrDvvIkgfCBwaXAgaW5zdGFsbCBpbi10b3RvIHwgYO+8iOingSBub3Rl77yJYCB8IC0gfCDmiafooYzogIXvvIjmnKzmnLogQ29kZXgg5Lya6K+d77yJwrcg5bel5YW35Li656ys5LiJ5pa55a6Y5pa55a6e546wIHwgMjAyNi0wOS0yNCAoQXNpYS9TaGFuZ2hhaSkgfCAyY2JiNjc5MjY0N2E4OTIxMWMyZDI1NjVmNzQ0ZjMwNmIxMDgzYTZjZTNiMTNkY2I4ZGExZjZlOGNiNzNjYWY4IHwg5LiN6YCC55So77yI5peg54us56uL5a6e546w5Y+v6LeR77yJIHwgaW4tdG90byAzLjEg5a6Y5pa55a6e546w6Z2i5ZCRIERTU0UgZW52ZWxvcGXvvIjml6Agc3RhdGVtZW50IOe6p+agoemqjOWFpeWPo++8ie+8m+acrOmdoue7tOaMgSBzaGFwZS1vbmx5IOWIpOaNru+8iOWumOaWueaWh+acrOaguOWvue+8ie+8jOS4jeiuoeWFpeS7luivgemAmui/h+aVsOOAgiB8CnwgYHZjYCB8IHNoYXBlLW9ubHkgfCBXM0MgVkMg5pWw5o2u5qih5Z6L5qCh6aqM5bqTIC8gSlNPTi1MRCDlpITnkIblmaggfCBwaXAgaW5zdGFsbCBweWxkIHwgYO+8iOingSBub3Rl77yJYCB8IC0gfCDmiafooYzogIXvvIjmnKzmnLogQ29kZXgg5Lya6K+d77yJwrcg5bel5YW35Li656ys5LiJ5pa55a6Y5pa55a6e546wIHwgMjAyNi0wOS0yNCAoQXNpYS9TaGFuZ2hhaSkgfCAyY2JiNjc5MjY0N2E4OTIxMWMyZDI1NjVmNzQ0ZjMwNmIxMDgzYTZjZTNiMTNkY2I4ZGExZjZlOGNiNzNjYWY4IHwg5LiN6YCC55So77yI5peg54us56uL5a6e546w5Y+v6LeR77yJIHwgcHlsZCDpnIDogZTnvZHlj5blrpjmlrnkuIrkuIvmlocgaHR0cHM6Ly93d3cudzMub3JnL25zL2NyZWRlbnRpYWxzL3Yy77yI5pys5py65Y+W5LiN5Yiw77yMSFRUUCAwMDDvvInvvJvnprvnur/ml6DkuIrkuIvmloflia/mnKwg4oaSIOaXoOazleWBmueLrOeri+WxleW8gO+8jOacrOmdouS4jeiuoeWFpeS7luivgemAmui/h+aVsO+8m+acrOmdoue7tOaMgSBzaGFwZS1vbmx5IOWIpOaNru+8iOWumOaWueaWh+acrOaguOWvue+8ie+8jOS4jeiuoeWFpeS7luivgemAmui/h+aVsOOAgiB8CnwgYHByb3ZgIHwgc2hhcGUtb25seSB8IFBST1Yg5bel5YW36ZO+IC8gSlNPTi1MRCDlpITnkIblmaggfCBwaXAgaW5zdGFsbCBweWxkIHwgYHB5dGhvbiAtYyAianNvbmxkLmV4cGFuZChyZXN1bHRzL2ludGVyb3AvcHJvdi5qc29uKSJgIHwgcHlsZCAocGlwKSB8IOaJp+ihjOiAhe+8iOacrOacuiBDb2RleCDkvJror53vvInCtyDlt6XlhbfkuLrnrKzkuInmlrnlrpjmlrnlrp7njrAgfCAyMDI2LTA5LTI0IChBc2lhL1NoYW5naGFpKSB8IGVkMDcwZGI1Y2E2MDEwMTM2Njc1YjFlNWM2ODY5N2E0ZTQwZjVkZjM2ZmQ1MTY4NDIyOWE5YzNkZDg5Y2Q4NjcgfCBQQVNT77yI5LiK5LiL5paH5Y+v5bGV5byA77yJIHwgUFJPVi1PIOWumOaWuSBwcm92Lmpzb25sZCDmnKzova7lj5blgLzlj5fpmZDvvIhIVFRQIDMwMO+8ie+8jOaVheS7pSBKU09OLUxEIOWxleW8gCArIOWbvuiKgueCueiuoeaVsOS4uuWHhuOAgui+k+WHuu+8mmdyYXBoIG5vZGVzIDAgfAp8IGBhMmFgIHwgbm90LWFwcGxpY2FibGUgfCBBMkEg5a6i5oi356uv77yI5aaC5a6Y5pa5IFNES++8iSB8IOWvueerr+iHquijhSB8IGDvvIjkuI3pgILnlKjvvIlgIHwgLSB8IOaJp+ihjOiAhe+8iOacrOacuiBDb2RleCDkvJror53vvInCtyDlt6XlhbfkuLrnrKzkuInmlrnlrpjmlrnlrp7njrAgfCAyMDI2LTA5LTI0IChBc2lhL1NoYW5naGFpKSB8IGYzMzM0MDMxNWM5NzM1YjE0NzgwYTU3ZjMyMjAwNDUwOWY3Yjk2YzcyOTlmNjVmZjQyODkzYjA1YThmMWY0ZGQgfCDkuI3pgILnlKjvvIjlt7LlnKjljaHniYflo7DmmI7nkIbnlLHvvIkgfCDmnKzku5Plj6rlr7zlh7ogQWdlbnQgQ2FyZCDlvaLnirbjgIHkuI3ov5DooYwgQTJBIOerr+eCuSDihpIg5peg5a+556uv5Y+v5raI6LS5IHwKfCBgYzJwYWAgfCBub3QtYXBwbGljYWJsZSB8IGMycGEtcnPvvIjlrpjmlrnlrp7njrDvvIkgfCDlr7nnq6/oh6roo4UgfCBg77yI5LiN6YCC55So77yJYCB8IC0gfCDmiafooYzogIXvvIjmnKzmnLogQ29kZXgg5Lya6K+d77yJwrcg5bel5YW35Li656ys5LiJ5pa55a6Y5pa55a6e546wIHwgMjAyNi0wOS0yNCAoQXNpYS9TaGFuZ2hhaSkgfCBhNzc5MTdlZjg2NTFmOGM5Y2EyMjc5Y2EzMWJiODMwMzM2Mjg0MWJiMmY2MDliMDgzN2JhNTc3MTlkMTI0ZTk0IHwg5LiN6YCC55So77yI5bey5Zyo5Y2h54mH5aOw5piO55CG55Sx77yJIHwg5pys5LuT5LiN5YGaIENCT1IvSlVNQkYg5a655Zmo5bCB6KOFIOKGkiBjMnBhLXJzIOaXoOWvueixoeWPr+mqjCB8CnwgYGNpZGAgfCBvZmZpY2lhbC1jbGkgfCBtdWx0aWZvcm1hdHMg5Y+C54Wn5a6e546wIC8g5bey55+l5ZCR6YeP5aSN566XIHwg5peg6ZyA5a6J6KOF77yIc2hhMjU2ICsgYmFzZTMyIOWkjeeul++8iSB8IGBweXRob24gLWMgIjzlr7kgY2lkLmpzb24g5q+P5p2hIHBhdGgg6YeN566XIENJRHYxKGNvZGVjIDB4NzEpK3NoYTI1NiDlubbmr5Tlr7k+ImAgfCBzaGEyNTYrYjMy77yI5peg5aSW6YOo5L6d6LWW77yJIHwg5omn6KGM6ICF77yI5pys5py6IENvZGV4IOS8muivne+8icK3IOW3peWFt+S4uuesrOS4ieaWueWumOaWueWunueOsCB8IDIwMjYtMDktMjQgKEFzaWEvU2hhbmdoYWkpIHwgNzQyMTBmYWE1OTc2ZjdjYzIxMWQ4Y2Y3MDU3ZTNjZTM3Mjc3MWRlNGMxYjY5ODkzMmRmZjU4NmI0OTNiMDRhZCB8IFBBU1PvvIhlbnRyaWVzIDQ5IG1pc21hdGNoIDAgbWlzc2luZyAw77yJIHwg5aSN566X5Y+j5b6E77yaQ0lEdjEgKyBjb2RlYyAweDcxICsgc2hhMi0yNTYgKyBtdWx0aWJhc2UgYmFzZTMybG93ZXIgfAp8IGBkZWNpc2lvbnNgIHwgbm90LWFwcGxpY2FibGUgfCDigJQgfCDigJQgfCBg77yI5LiN6YCC55So77yJYCB8IC0gfCDmiafooYzogIXvvIjmnKzmnLogQ29kZXgg5Lya6K+d77yJwrcg5bel5YW35Li656ys5LiJ5pa55a6Y5pa55a6e546wIHwgMjAyNi0wOS0yNCAoQXNpYS9TaGFuZ2hhaSkgfCAzMTMyMGQzYjg5NDliNjdlMjhjZGE1YWY1ODc1YjBhMGU5MDhkZjc4MDYyYTZlZTEzMGMyNzViYzViZjQzNGM1IHwg5LiN6YCC55So77yI5bey5Zyo5Y2h54mH5aOw5piO55CG55Sx77yJIHwg5Yaz562W6Z2i5pivIE5GIOiHquacieW9oueKtu+8jOaXoOWklumDqOWvueerr+S4juWklumDqCBzY2hlbWEgfAo="),
    };

    /// <summary>
    /// 回归面七钉：**分值**（check33 第 3 条：五信号复算 + 可复算子集归一分 + <c>purity_clean</c> 边界）
    /// + **比对口径**（<c>compare()</c> 纯函数六例）+ **信号源三面**（conformance_scan / quality_depth_scan
    /// 聚合 / doc_hygiene.check_markers）。两处合成语料（虚标分级 / 缺标识）按真源输出锚定摘要——
    /// 真仓全绿时单靠真材料证明不了判据会红，合成语料才是判据的证伪面。
    /// 金标由 probes/regression_score_probe.py（真源模块原文）产出。
    /// </summary>
    private static void RegressionCases(List<Check> checks, string work, string repoRoot)
    {
        const string CscReal = "9519e11e210362720ff3ef9523ac39ec";
        const string CscNegative = "1ac028549cd02b6764acc75a3eadf7ac";
        const string DepthReal = "6258b79e9313ea3fac4cceb8f6eccfb6";
        const string MarkersReal = "405738e515e30e94ce29d5ccf59b01e2";
        const string MarkersNegative = "c699a73cf3863d9e3c1809dce4860bbb";
        const string ScoreReal = "9ffe6f5ce4088211a35880403abeea8e";
        const string CompareGolden = "e27d94b51aa676d41137b0657afd011d";

        var real = ConformanceScan.Scan(repoRoot);
        checks.Add(new Check("回归面·conformance·真仓（机读块 248 / 协议包 111 / 导出面 4 · 零虚标）",
            real.Issues.Count == 0 && real.LogDigest() == CscReal
            && Convert.ToInt64(real.Stats["modules_mc"]) == 248
            && Convert.ToInt64(real.Stats["packages"]) == 111
            && Convert.ToInt64(real.Stats["export_items"]) == 4,
            $"FAIL {real.Issues.Count} · 摘要 {real.LogDigest()}（真源金标 {CscReal}）"));

        var cscNegativeRoot = Path.Combine(work, "reg-csc-negative");
        Fresh(cscNegativeRoot);
        foreach (var (rel, b64) in ConformanceNegativeFiles) WriteBase64(cscNegativeRoot, rel, b64);
        var cscNegative = ConformanceScan.Scan(cscNegativeRoot);
        var cscText = string.Join(" | ", cscNegative.Issues);
        checks.Add(new Check("回归面·conformance·合成虚标（L3>L1 虚标 · L0 非法 · 包不在册 · 导出面缺证据/门禁 · mc.id 重复）",
            cscNegative.Issues.Count == 8 && cscNegative.LogDigest() == CscNegative
            && cscText.Contains("conformance 虚标 L3 > 可证 L1（'M99' 不在装配在册证据）")
            && cscText.Contains("conformance 虚标 L2 > 可证 L1（包不在 registry protocols[]）")
            && cscText.Contains("证据文件缺失 missing.txt")
            && cscText.Contains("证据门禁 check99 在 verify.sh 无 check 定义")
            && cscText.Contains("导出面 y: conformance 应为 L3（导出门禁锁定面）")
            && cscText.Contains("模块 id 与"),   // 真源 348577d 新增的重复 id 判据（D3）在这份合成语料上必须命中
            $"FAIL {cscNegative.Issues.Count} · 摘要 {cscNegative.LogDigest()}（真源金标 {CscNegative}）"));

        var depth = QualityDepth.Scan(repoRoot);
        checks.Add(new Check("回归面·纵深聚合·真仓（14 件子扫描器接线 · 真源 quality_depth_scan.scan）",
            depth.Issues.Count == 0 && depth.LogDigest() == DepthReal
            && depth.Stats.Count == QualityDepth.SubScannerOrder.Length,
            $"FAIL {depth.Issues.Count} · stats {depth.Stats.Count} · 摘要 {depth.LogDigest()}"
            + $"（真源金标 {DepthReal}）"));

        var markersReal = DocHygiene.CheckMarkers(repoRoot);
        checks.Add(new Check("回归面·文档卫生·真仓（关键档「最后更新」位 + 指令档标识头 · 零缺口）",
            markersReal.Count == 0
            && ExitFaces.Digest32(DocHygiene.MarkersLog(repoRoot)) == MarkersReal,
            $"FAIL {markersReal.Count} · 摘要 {ExitFaces.Digest32(DocHygiene.MarkersLog(repoRoot))}"
            + $"（真源金标 {MarkersReal}）"));

        var markersRoot = Path.Combine(work, "reg-markers-negative");
        Fresh(markersRoot);
        foreach (var (rel, b64) in MarkersNegativeFiles) WriteBase64(markersRoot, rel, b64);
        var markersNegative = DocHygiene.CheckMarkers(markersRoot);
        var markersText = string.Join(" | ", markersNegative);
        checks.Add(new Check("回归面·文档卫生·合成缺标识（无「最后更新」位 + 指令档缺标识 + 清单内缺件逐件报）",
            markersNegative.Count == 45
            && ExitFaces.Digest32(DocHygiene.MarkersLog(markersRoot)) == MarkersNegative
            && markersText.Contains("01_核心协议.md 缺「最后更新」位（头部 2 行内）")
            && markersText.Contains("docs/ai-menu.md 缺「⛔ 操作指令」标识头（指令类文档须全覆盖）")
            && markersText.Contains("02_联动注册表.md 缺失（须入 REQUIRED_DOCS 清单）"),
            $"FAIL {markersNegative.Count}"
            + $" · 摘要 {ExitFaces.Digest32(DocHygiene.MarkersLog(markersRoot))}（真源金标 {MarkersNegative}）"));

        var evaluation = RegressionScore.Evaluate(repoRoot);
        var signals = (evaluation["signals"] as List<object?> ?? new List<object?>())
            .OfType<Dictionary<string, object?>>().ToList();
        checks.Add(new Check("回归面·分值·真仓（五信号复算 + 可复算子集归一分 + purity_clean 记边界）",
            RegressionScore.LogDigest(evaluation) == ScoreReal
            && signals.Count == 5 && signals.All(s => Convert.ToDouble(s["value"]) == 1.0)
            && Convert.ToDouble(evaluation["score"]) == 100.0
            && (evaluation["issues"] as List<object?>)!.Count == 0
            && string.Join(",", RegressionScore.BoundarySignals) == "purity_clean",
            $"信号 {signals.Count} · 分 {evaluation["score"]}"
            + $" · 摘要 {RegressionScore.LogDigest(evaluation)}（真源金标 {ScoreReal}）"));

        using var pairsDoc = JsonDocument.Parse(Convert.FromBase64String(RegressionComparePairsB64));
        var pairs = (PythonJson.ToGraph(pairsDoc.RootElement) as List<object?> ?? new List<object?>())
            .OfType<Dictionary<string, object?>>().ToList();
        var compareDigest = RegressionScore.CompareLogDigest(pairs);
        checks.Add(new Check("回归面·比对口径（compare() 六例：无回归/信号回落/整体下降/容差内/审计例外/无基线）",
            pairs.Count == 6 && compareDigest == CompareGolden
            && RegressionScore.CompareLog(pairs)[1].Contains("回归（信号回落）：schema_clean")
            && RegressionScore.CompareLog(pairs)[2].Contains("回归（整体分下降 10.00 > 容差 0.00）")
            && RegressionScore.CompareLog(pairs)[4].Contains("通过（含 1 项审计例外）")
            && RegressionScore.CompareLog(pairs)[5].Contains("无基线（只报当前分值，未做回归判定）"),
            $"例数 {pairs.Count} · 摘要 {compareDigest}（真源金标 {CompareGolden}）"));
    }

    /// <summary>
    /// 构建回路（check33 第 16 条 · `core/workloop.py`）三钉：真仓（待办 1229 项 / 适配器 3 /
    /// stub 工单确定）· 合成语料（CLI ↔ 声明件漏同步 → deepen 候选、工单成形）· 空树（待办真源为空
    /// → 问题面为空，逐条判出）。判据面 = `scan` + `summary`；`write_order` / `close` 是写 `.rivet/`
    /// 内部档案的写面，**不移植**（只读门不落盘）。金标由 probes/workloop_probe.py 产出。
    /// </summary>
    private static void WorkloopCases(List<Check> checks, string work, string repoRoot)
    {
        const string Real = "d579529100e3474ea5b131fc1d204d80";
        const string Syn = "440b2a6a5f4c1b597dd5c9e54755c028";
        const string Empty = "acfeff33bd0f55d5315fecf706575719";

        var real = Workloop.Scan(repoRoot);
        checks.Add(new Check("构建回路·真仓（待办 1244 项 · 适配器 3 · stub 工单确定 · 与真源原文逐字节同摘要）",
            real.Ok && real.LogDigest == Real
            && Convert.ToInt64(real.Stats["items"]) == 1244
            && Convert.ToInt64(real.Stats["untyped"]) == 101
            && Convert.ToInt64(real.Stats["advisories"]) == 1142
            && Convert.ToInt64(real.Stats["adapters"]) == 3
            && PyScalar.PyRepr(real.Stats["pulled_candidates"]) == "['laya-multilingual']",
            $"FAIL {real.Issues.Count} · 项 {real.Stats["items"]} · 摘要 {real.LogDigest}"
            + $"（真源金标 {Real}）"));

        var synRoot = Path.Combine(work, "workloop-synthetic");
        Fresh(synRoot);
        foreach (var (rel, b64) in WorkloopSyntheticFiles) WriteBase64(synRoot, rel, b64);
        var syn = Workloop.Scan(synRoot);
        checks.Add(new Check("构建回路·合成语料（CLI↔声明件漏同步 → deepen 候选 · 工单成形 · 与真源原文同摘要）",
            syn.Ok && syn.LogDigest == Syn
            && Convert.ToInt64(syn.Stats["items"]) == 5 && Convert.ToInt64(syn.Stats["adapters"]) == 1
            && PyScalar.PyRepr(syn.Stats["pulled_candidates"]) == "['合成候选']",
            $"FAIL {syn.Issues.Count} · 项 {syn.Stats["items"]} · 摘要 {syn.LogDigest}（真源金标 {Syn}）"));

        var emptyRoot = Path.Combine(work, "workloop-empty");
        Fresh(emptyRoot);
        var empty = Workloop.Scan(emptyRoot);
        checks.Add(new Check("构建回路·空树（待办真源为空 + 问题面为空 → 逐条判出，不静默放过）",
            !empty.Ok && empty.Issues.Count == 2 && empty.LogDigest == Empty
            && empty.Issues[0].StartsWith("待办真源为空", StringComparison.Ordinal),
            $"FAIL {empty.Issues.Count} · 摘要 {empty.LogDigest}（真源金标 {Empty}）"));
    }

    /// <summary>
    /// GEO 出口（check38 子扫描 3 · `scripts/geo_export.py`）四钉：真仓（370 条标准 / 70 条被绑定 /
    /// 8 件生成物，**引擎重算须逐字节命中盘上原件**）· 合成语料（真源 `write()` 写出的盘上原件 →
    /// 引擎重算同样命中，证明渲染器不是只对真仓凑巧）· 合成漂移（删一个索引锚点 → 漂移 + 锚点集合
    /// 各报一条）· 缺生成物（8 件逐件报缺 + 锚点集合报差）。金标由 probes/geo_export_probe.py 产出。
    /// </summary>
    private static void GeoExportCases(List<Check> checks, string work, string repoRoot)
    {
        const string Real = "b7305f442f3e92b988103ebbca5e5514";
        const string OkDigest = "b7305f442f3e92b988103ebbca5e5514";
        const string Tampered = "229b81beeded32f15b79669db2d6d2b1";
        const string Absent = "4aa7946fa0a0edc6ccf8e560949dc5bb";

        var real = GeoExport.Check(repoRoot);
        checks.Add(new Check("GEO 出口·真仓（370 条标准 / 70 条被绑定 / 8 件生成物 · 重算逐字节命中）",
            real.Ok && real.LogDigest() == Real
            && Convert.ToInt64(real.Stats["standards"]) == 370
            && Convert.ToInt64(real.Stats["bound_standards"]) == 70
            && Convert.ToInt64(real.Stats["files"]) == 8,
            $"FAIL {real.Issues.Count} · 标准 {real.Stats["standards"]} · 摘要 {real.LogDigest()}"
            + $"（真源金标 {Real}）"));

        var okRoot = Path.Combine(work, "geo-synthetic-ok");
        Fresh(okRoot);
        foreach (var (rel, b64) in GeoSyntheticOkFiles) WriteBase64(okRoot, rel, b64);
        var ok = GeoExport.Check(okRoot);
        checks.Add(new Check("GEO 出口·合成语料（真源 write() 盘上原件 → 引擎重算逐字节命中）",
            ok.Ok && ok.LogDigest() == OkDigest && Convert.ToInt64(ok.Stats["standards"]) == 2,
            $"FAIL {ok.Issues.Count} · 摘要 {ok.LogDigest()}（真源金标 {OkDigest}）"));

        var tamperedRoot = Path.Combine(work, "geo-synthetic-tampered");
        Fresh(tamperedRoot);
        foreach (var (rel, b64) in GeoSyntheticTamperedFiles) WriteBase64(tamperedRoot, rel, b64);
        var tampered = GeoExport.Check(tamperedRoot);
        var tamperedText = string.Join(" | ", tampered.Issues);
        checks.Add(new Check("GEO 出口·合成漂移（删一个索引锚点 → 漂移 + 锚点集合各报一条）",
            !tampered.Ok && tampered.Issues.Count == 2 && tampered.LogDigest() == Tampered
            && tamperedText.Contains("docs/standards/index.md 与标准目录不一致")
            && tamperedText.Contains("索引锚点集合 ≠ 目录 id 集合（缺 1 / 多 0）"),
            $"FAIL {tampered.Issues.Count} · 摘要 {tampered.LogDigest()}（真源金标 {Tampered}）"));

        var absentRoot = Path.Combine(work, "geo-synthetic-absent");
        Fresh(absentRoot);
        foreach (var (rel, b64) in GeoSyntheticAbsentFiles) WriteBase64(absentRoot, rel, b64);
        var absent = GeoExport.Check(absentRoot);
        checks.Add(new Check("GEO 出口·缺生成物（8 件逐件报缺 + 锚点集合报差，不静默放过）",
            !absent.Ok && absent.Issues.Count == 9 && absent.LogDigest() == Absent
            && absent.Issues[0].StartsWith("缺生成物 docs/standards/index.md", StringComparison.Ordinal),
            $"FAIL {absent.Issues.Count} · 摘要 {absent.LogDigest()}（真源金标 {Absent}）"));
    }

    /// <summary>
    /// 需求 → 装配计划（`nf assemble` · `core/assemble_plan.py`）四钉：**预设命中**（西幻生存 → 包 / 管线 /
    /// 取件非空 / 允许集 ⊇ 官方核心）· **自定义流**（未命中且含自定义线索 → `custom` · 可借用包 = 全库包名 ·
    /// 允许集 = 官方 + 全部社区模块）· **澄清漏斗**（空需求 / 无线索需求 → 三点问句；含线索 → ready）·
    /// **成品验收**（合成 md：八段齐 + 编号在允许集 + 决策句带引用 → 通过；缺段 / 越界编号 / 无引用决策句逐条判出）。
    /// 前两钉断**语义结构**（语料规模随仓库变，不锚死数字），后两钉在**合成语料**上断，与仓库无关。
    /// 金标由 probes/face_parity_probe.py 的 assemble 六面（逐字节）另行钉住 CLI 输出。
    /// </summary>
    private static void AssembleCases(List<Check> checks, string work, string repoRoot)
    {
        var preset = AssemblePlan.Plan(repoRoot, "西幻生存");
        var core = AssemblePlan.OfficialCoreIds(repoRoot);
        var allowed = (preset.GetValueOrDefault("allowed_module_ids") as List<object?> ?? new List<object?>())
            .Select(x => x as string ?? "").ToHashSet(StringComparer.Ordinal);
        checks.Add(new Check("装配面·预设命中（西幻生存 → 包/管线 · 取件非空 · 允许集 ⊇ 官方核心）",
            preset.GetValueOrDefault("matched") is true
            && preset.GetValueOrDefault("package") as string == "西幻生存领域包"
            && preset.GetValueOrDefault("pipeline") as string == "P03"
            && (preset.GetValueOrDefault("fetch_modules") as List<object?> ?? new List<object?>()).Count > 0
            && core.Count > 0 && core.All(allowed.Contains)
            && preset.GetValueOrDefault("status") as string == "preset",
            $"包 {preset.GetValueOrDefault("package")} · 管线 {preset.GetValueOrDefault("pipeline")}"
            + $" · 取件 {(preset.GetValueOrDefault("fetch_modules") as List<object?> ?? new List<object?>()).Count}"
            + $" · 允许集 {allowed.Count}（官方核心 {core.Count} 全含）"));

        var customPlan = AssemblePlan.Plan(repoRoot, "自定义权谋宫廷");
        var packages = AssemblePlan.PackageModuleSets(repoRoot);
        var known = (customPlan.GetValueOrDefault("known_packages") as List<object?> ?? new List<object?>())
            .Select(x => x as string ?? "").ToList();
        var allRegistered = core.Concat(packages.Values.SelectMany(v => v))
            .ToHashSet(StringComparer.Ordinal);
        checks.Add(new Check("装配面·自定义流（未命中 → custom · 可借用包=全库 · 允许集=官方+全部社区模块）",
            customPlan.GetValueOrDefault("matched") is false
            && customPlan.GetValueOrDefault("status") as string == "custom"
            && known.Count == packages.Count
            && allowed.Count == allRegistered.Count
            && customPlan.GetValueOrDefault("fetch_modules") is List<object?> fetch && fetch.Count > 0,
            $"状态 {customPlan.GetValueOrDefault("status")} · 可借用包 {known.Count}/{packages.Count}"
            + $" · 允许集 {allowed.Count}/{allRegistered.Count}"));

        var emptyFunnel = AssemblePlan.Clarify(repoRoot, "   ");
        var vagueFunnel = AssemblePlan.Clarify(repoRoot, "帮我做个游戏");
        var cueFunnel = AssemblePlan.Clarify(repoRoot, "自定义权谋宫廷");
        checks.Add(new Check("装配面·澄清漏斗（空需求 / 无线索需求 → clarify；含自定义线索 → ready）",
            emptyFunnel.GetValueOrDefault("status") as string == "clarify"
            && (emptyFunnel.GetValueOrDefault("questions") as List<object?> ?? new List<object?>()).Count == 1
            && vagueFunnel.GetValueOrDefault("status") as string == "clarify"
            && (vagueFunnel.GetValueOrDefault("questions") as List<object?> ?? new List<object?>()).Count == 3
            && cueFunnel.GetValueOrDefault("status") as string == "ready"
            && cueFunnel.GetValueOrDefault("plan") is Dictionary<string, object?>,
            $"空需求 {(emptyFunnel.GetValueOrDefault("questions") as List<object?> ?? new List<object?>()).Count} 问"
            + $" · 无线索 {(vagueFunnel.GetValueOrDefault("questions") as List<object?> ?? new List<object?>()).Count} 问"
            + $" · 含线索 {cueFunnel.GetValueOrDefault("status")}"));

        var syntheticPlan = new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["allowed_module_ids"] = new List<object?> { "通用:M10", "M50" },
            ["package"] = "合成包", ["pipeline"] = "P99",
        };
        // 注意（照抄真源口径）：**决策句只在叙事段 ##0–##2 里判**，且跳过 `-`/`*`/`|` 开头的行——
        // 故合成语料要把决策句放进 ##1 段内（首版把它放在 ##7 之后，是**测试数据错**而非移植错）。
        var good = string.Join("\n", Enumerable.Range(0, 8).Select(i => $"## {i}. 段{i}")) + "\n";
        var (goodIssues, goodStats) = AssemblePlan.Check(good, syntheticPlan);
        var bad = "## 0. 段0\n## 1. 段1\n"
                  + "本段必须引用 §3.1 才能落地。\n"      // 决策句带引用 → 不算问题
                  + "本段必须不要引用。\n"                // 决策句无引用 → 判出
                  + "越界编号 M55 出现在这里。\n"        // 越界编号 → 判出
                  + string.Join("\n", Enumerable.Range(2, 6).Select(i => $"## {i}. 段{i}")) + "\n";
        var (badIssues, badStats) = AssemblePlan.Check(bad, syntheticPlan);
        var missingSeg = AssemblePlan.Check("## 0. 段0\n## 1. 段1\n", syntheticPlan);
        checks.Add(new Check("装配面·成品验收（八段齐 → 通过；缺段 / 越界编号 / 无引用决策句 → 逐条判出）",
            goodIssues.Count == 0 && goodStats["segments"] as long? == 8L
            && badIssues.Count == 2
            && badIssues.Any(i => i.StartsWith("编造/越界编号：M55", StringComparison.Ordinal))
            && badIssues.Any(i => i.StartsWith("无引用决策句：", StringComparison.Ordinal))
            && badStats["modules_mentioned"] as long? == 1L
            && missingSeg.Issues.Count == 1
            && missingSeg.Issues[0].StartsWith("八段骨架缺段：##", StringComparison.Ordinal),
            $"好件 {goodIssues.Count} 问题 · 坏件 {badIssues.Count} 问题（{string.Join(" / ", badIssues).Substring(0, Math.Min(90, string.Join(" / ", badIssues).Length))}）"
            + $" · 缺段 {missingSeg.Issues.Count}"));
    }

    /// <summary>
    /// 语料身份（**操作性预检**，不是判据）：把「被测语料」量成指纹，好让**摘要类钉的红**能被正确归因
    /// ——作者前移 HEAD 后重新导出快照再跑门，摘要钉会红，那是「**语料变了**」而不是「引擎坏了」。
    ///
    /// 三钉：① 真仓（**导出快照断金标基线** / 工作区态只断模式）——若拿**新快照**跑，本钉会红并直接把
    /// 归因写在 detail 里（第一百零六片实测：作者 7 提交后的 `nf-snap-h6` 指纹 `23a7922f…` ≠ 金标
    /// `66db1450…`，而当时**只有一条**摘要钉红、看不出原因）；② 确定性（同语料两遍同值）；
    /// ③ 一字节敏感（临时树改一个字节 → 指纹变）。
    /// </summary>
    private static void CorpusStampCases(List<Check> checks, string work, string repoRoot)
    {
        var stamp = CorpusStamp.Check(repoRoot);
        var pinned = IsPinnedSnapshot(repoRoot);
        checks.Add(new Check("语料身份·真仓（导出快照断金标基线 · 工作区态只报模式——摘要钉的红据此归因）",
            pinned ? stamp.Matches : !stamp.IsSnapshot,
            $"指纹 {stamp.Fingerprint} · 金标 {stamp.Baseline} · 匹配={(stamp.Matches ? "是" : "否")}"
            + $" · 模式={(stamp.IsSnapshot ? "导出快照" : "工作区")}"
            + (pinned && !stamp.Matches
                ? " ⚠ 语料与金标基线不同——**摘要类钉的红应从「复基线」处置**（重生成 fixtures 并重嵌常量），"
                  + "或改跑活仓库走语义模式；**不是引擎坏了**。"
                : "")));

        var small = Path.Combine(work, "corpus-stamp");
        Fresh(small);
        File.WriteAllText(Path.Combine(small, "a.md"), "一\n", new UTF8Encoding(false));
        Directory.CreateDirectory(Path.Combine(small, "sub"));
        File.WriteAllText(Path.Combine(small, "sub", "b.md"), "二\n", new UTF8Encoding(false));
        var first = CorpusStamp.Fingerprint(small);
        var second = CorpusStamp.Fingerprint(small);
        checks.Add(new Check("语料身份·确定性（同语料两遍同值 · 且与金标基线不同）",
            first == second && first != CorpusStamp.Baseline && first.Length == 16,
            $"两遍 {first}/{second} · 金标 {CorpusStamp.Baseline}"));

        File.WriteAllText(Path.Combine(small, "a.md"), "一\n", new UTF8Encoding(false));   // 同内容 → 同指纹
        var sameAfterRewrite = CorpusStamp.Fingerprint(small) == first;
        File.WriteAllText(Path.Combine(small, "a.md"), "一!\n", new UTF8Encoding(false));  // 改一字节 → 变
        var changed = CorpusStamp.Fingerprint(small);
        checks.Add(new Check("语料身份·一字节敏感（同内容重写不变 · 改一字节即变）",
            sameAfterRewrite && changed != first,
            $"重写后 {(sameAfterRewrite ? "不变" : "**变了**（错）")} · 改字节后 {changed}（原 {first}）"));
    }

    /// <summary>
    /// 馆藏回执（`core/receipts.py` **馆藏作用域** · check35 第二条腿）七钉——真仓零缺口 + 六种破坏：
    /// 条目正文被改（根不一致 + 条目内容已变）· 回执少一条（`回执条数 2 ≠ 馆藏条数 3`）· 幽灵条目 ·
    /// schema 不匹配（真源**立刻返回**，不做折叠判定）· leaf 被改（包含证明不折叠到根）· 盘上多一条
    /// （根不一致 + 条数不等）。
    ///
    /// **本片修掉一处既有实现差异**：此前引擎按**文件路径**逐条比对（`缺文件：…` / `条目摘要不一致：…`），
    /// 真源是**从馆藏条目实时重建**（`build()` → 全馆根 + 逐条 inclusion proof），消息与判定面都与真源不同；
    /// 真仓语料两边都零问题，**只有破坏性语料才照得出来**。现按真源重写（`BuildLibrary` + `FoldProof`）。
    /// 金标由 probes/library_receipts_probe.py 产出。
    /// </summary>
    private static void LibraryReceiptsCases(List<Check> checks, string work, string repoRoot)
    {
        const string Real = "4e09bba9dfa80561029cc510865da206";
        const string EntryTampered = "8fbdadca49dd09a9b271ffb163119620";
        const string EntryRemoved = "19c7037d0116488470a6e6a5a311757a";
        const string GhostEntry = "aa14e1419ad17a83cceb04720d3f69a4";
        const string BadSchema = "c30c6d156dae65bc8b837bb9bc777867";
        const string ProofTampered = "c0bcb623f691e880111260ead2d7e3f5";
        const string NewEntry = "e734b5e13fda8494a565aa2757d0aa8e";

        Receipts.ArtifactResult Case(string name, (string Rel, string B64)[] files)
        {
            var dir = Path.Combine(work, name);
            Fresh(dir);
            foreach (var (rel, b64) in files) WriteBase64(dir, rel, b64);
            return Receipts.VerifyLibraryReceipts(dir);
        }

        var real = Receipts.VerifyLibraryReceipts(repoRoot);
        checks.Add(new Check("馆藏回执·真仓（3 条 · 逐条折叠到根 + 根与实时重算一致 · 与真源原文逐字节同摘要）",
            real.Ok && Receipts.LibraryLogDigest(real) == Real && real.Count == 3
            && real.Root.StartsWith("42e1522438c6", StringComparison.Ordinal),
            $"FAIL {real.Issues.Count} · 摘要 {Receipts.LibraryLogDigest(real)}（真源金标 {Real}）"));

        var tampered = Case("lib-entry-tampered", LibEntryTamperedFiles);
        var tamperedText = string.Join(" | ", tampered.Issues);
        checks.Add(new Check("馆藏回执·条目被改（根不一致 + 条目内容已变，均带真源修复指引）",
            !tampered.Ok && tampered.Issues.Count == 2
            && Receipts.LibraryLogDigest(tampered) == EntryTampered
            && tamperedText.Contains("根不一致：记录=") && tamperedText.Contains("（修复指引：馆藏改动后跑 nf library receipts --write）")
            && tamperedText.Contains("条目内容已变：NF-1（修复指引：重签该条并重建回执）"),
            $"FAIL {tampered.Issues.Count} · 摘要 {Receipts.LibraryLogDigest(tampered)}（真源金标 {EntryTampered}）"));

        var removed = Case("lib-entry-removed", LibEntryRemovedFiles);
        checks.Add(new Check("馆藏回执·回执少一条（回执条数 2 ≠ 馆藏条数 3）",
            !removed.Ok && removed.Issues.Count == 1 && Receipts.LibraryLogDigest(removed) == EntryRemoved
            && removed.Issues[0] == "回执条数 2 ≠ 馆藏条数 3",
            $"FAIL {removed.Issues.Count} · 摘要 {Receipts.LibraryLogDigest(removed)}（真源金标 {EntryRemoved}）"));

        var ghost = Case("lib-ghost-entry", LibGhostEntryFiles);
        checks.Add(new Check("馆藏回执·幽灵条目（回执指向不存在的条目：NF-999）",
            !ghost.Ok && ghost.Issues.Count == 1 && Receipts.LibraryLogDigest(ghost) == GhostEntry
            && ghost.Issues[0] == "回执指向不存在的条目：NF-999",
            $"FAIL {ghost.Issues.Count} · 摘要 {Receipts.LibraryLogDigest(ghost)}（真源金标 {GhostEntry}）"));

        var schema = Case("lib-schema", LibSchemaFiles);
        checks.Add(new Check("馆藏回执·schema 不匹配（真源立刻返回，不做折叠判定）",
            !schema.Ok && schema.Issues.Count == 1 && Receipts.LibraryLogDigest(schema) == BadSchema
            && schema.Issues[0] == "回执文件 schema 不匹配（期望 nf-receipts/1）" && schema.Count == 0,
            $"FAIL {schema.Issues.Count} · 摘要 {Receipts.LibraryLogDigest(schema)}（真源金标 {BadSchema}）"));

        var proof = Case("lib-proof-tampered", LibProofTamperedFiles);
        checks.Add(new Check("馆藏回执·leaf 被改（包含证明不折叠到根：NF-2）",
            !proof.Ok && proof.Issues.Count == 1 && Receipts.LibraryLogDigest(proof) == ProofTampered
            && proof.Issues[0] == "包含证明不折叠到根：NF-2",
            $"FAIL {proof.Issues.Count} · 摘要 {Receipts.LibraryLogDigest(proof)}（真源金标 {ProofTampered}）"));

        var added = Case("lib-new-entry", LibNewEntryFiles);
        checks.Add(new Check("馆藏回执·盘上多一条（根不一致 + 回执条数 3 ≠ 馆藏条数 4）",
            !added.Ok && added.Issues.Count == 2 && Receipts.LibraryLogDigest(added) == NewEntry
            && added.Issues[1] == "回执条数 3 ≠ 馆藏条数 4",
            $"FAIL {added.Issues.Count} · 摘要 {Receipts.LibraryLogDigest(added)}（真源金标 {NewEntry}）"));
    }

    /// <summary>馆藏回执合成语料（真源 build() 盘上原件 + 破坏；机械导出）。</summary>
    private static readonly (string Rel, string B64)[] LibEntryTamperedFiles =
    {
		("library/NF-1.md", "LS0tCmlkOiBORi0xCnR5cGU6IGd1aWRlCnRpdGxlOiDlkIjmiJDmnaHnm64xCmRlc2NyaXB0aW9uOiDlkIjmiJDppobol4/mnaHnm67vvIjmjqLpkojor63mlpnvvIkKbGljZW5zZTogTUlUCnN0YXR1czogYWN0aXZlCi0tLQoKIyDlkIjmiJDmnaHnm64gMQoK5q2j5paH56ysIDEg5p2h77yI5o6i6ZKI6K+t5paZ77yJ44CCCgrnr6HmlLnkuIDooYzjgIIK"),
		("library/NF-2.md", "LS0tCmlkOiBORi0yCnR5cGU6IGd1aWRlCnRpdGxlOiDlkIjmiJDmnaHnm64yCmRlc2NyaXB0aW9uOiDlkIjmiJDppobol4/mnaHnm67vvIjmjqLpkojor63mlpnvvIkKbGljZW5zZTogTUlUCnN0YXR1czogYWN0aXZlCi0tLQoKIyDlkIjmiJDmnaHnm64gMgoK5q2j5paH56ysIDIg5p2h77yI5o6i6ZKI6K+t5paZ77yJ44CCCg=="),
		("library/NF-3.md", "LS0tCmlkOiBORi0zCnR5cGU6IGd1aWRlCnRpdGxlOiDlkIjmiJDmnaHnm64zCmRlc2NyaXB0aW9uOiDlkIjmiJDppobol4/mnaHnm67vvIjmjqLpkojor63mlpnvvIkKbGljZW5zZTogTUlUCnN0YXR1czogYWN0aXZlCi0tLQoKIyDlkIjmiJDmnaHnm64gMwoK5q2j5paH56ysIDMg5p2h77yI5o6i6ZKI6K+t5paZ77yJ44CCCg=="),
		("library/RECEIPTS.json", "ewogICJhbGdvcml0aG0iOiAiUkZDNjk2Mi1zdHlsZSBzaGEyNTYgZG9tYWluLXNlcGFyYXRlZCIsCiAgImNvdW50IjogMywKICAiZW50cmllcyI6IFsKICAgIHsKICAgICAgImFuY2hvciI6IG51bGwsCiAgICAgICJkaWdlc3QiOiAiMTZlZTY0OTI3MDgzYjFiOGRmYzI0MTAxMTEyYjY3NmUyODNkMGEyYjY0YzVhYzE3Y2RjNTlmZjA1Mjk4YTU4MiIsCiAgICAgICJpZCI6ICJORi0xIiwKICAgICAgImxlYWYiOiAiNTJjMTk0YmRmMmQyNTFkOGEyNTM4ODVhM2MyZDYwYTNmN2NhZGZiMTg4OGIwN2QyNDFiZmI4MjYwOTQ2YzVhZSIsCiAgICAgICJwYXRoIjogImxpYnJhcnkvTkYtMS5tZCIsCiAgICAgICJwcm9vZiI6IFsKICAgICAgICB7CiAgICAgICAgICAiaGFzaCI6ICI5MjhkYWE2ZDFkOTg4MjczZWI1Y2Q3NWQwYzQxMjA5Yzk1MDdlN2ZhYjc5YWFkM2RhZDZlNjhiYTM4N2Y0Y2Q2IiwKICAgICAgICAgICJzaWRlIjogInJpZ2h0IgogICAgICAgIH0sCiAgICAgICAgewogICAgICAgICAgImhhc2giOiAiNmI1NDBmNzI2Zjg3MTBjMTkyMTBhMjA4NjQ4MGRlY2ZlMjJiOWFmNDVlZDlkNDRjMzlmM2MzN2I1ZGUzMzcxZSIsCiAgICAgICAgICAic2lkZSI6ICJyaWdodCIKICAgICAgICB9CiAgICAgIF0KICAgIH0sCiAgICB7CiAgICAgICJhbmNob3IiOiBudWxsLAogICAgICAiZGlnZXN0IjogIjcwYzk0MGI0NGI4Mjg1MTA2OTM1YjU3YTU4NWJkZWU4MWE4MzYyNzJiMmQ3NWZhN2E1NzFmY2VmZGM0MjYzZTMiLAogICAgICAiaWQiOiAiTkYtMiIsCiAgICAgICJsZWFmIjogIjkyOGRhYTZkMWQ5ODgyNzNlYjVjZDc1ZDBjNDEyMDljOTUwN2U3ZmFiNzlhYWQzZGFkNmU2OGJhMzg3ZjRjZDYiLAogICAgICAicGF0aCI6ICJsaWJyYXJ5L05GLTIubWQiLAogICAgICAicHJvb2YiOiBbCiAgICAgICAgewogICAgICAgICAgImhhc2giOiAiNTJjMTk0YmRmMmQyNTFkOGEyNTM4ODVhM2MyZDYwYTNmN2NhZGZiMTg4OGIwN2QyNDFiZmI4MjYwOTQ2YzVhZSIsCiAgICAgICAgICAic2lkZSI6ICJsZWZ0IgogICAgICAgIH0sCiAgICAgICAgewogICAgICAgICAgImhhc2giOiAiNmI1NDBmNzI2Zjg3MTBjMTkyMTBhMjA4NjQ4MGRlY2ZlMjJiOWFmNDVlZDlkNDRjMzlmM2MzN2I1ZGUzMzcxZSIsCiAgICAgICAgICAic2lkZSI6ICJyaWdodCIKICAgICAgICB9CiAgICAgIF0KICAgIH0sCiAgICB7CiAgICAgICJhbmNob3IiOiBudWxsLAogICAgICAiZGlnZXN0IjogIjM3YjFlYzMyMGVlMGQ5ZWI4NzI0YjkzYWZhNmYzZGY1YWE5ZGE4ZmI1Y2I0N2Q5YTI4NDUwMTk2NzIxZTRiMGIiLAogICAgICAiaWQiOiAiTkYtMyIsCiAgICAgICJsZWFmIjogIjZiNTQwZjcyNmY4NzEwYzE5MjEwYTIwODY0ODBkZWNmZTIyYjlhZjQ1ZWQ5ZDQ0YzM5ZjNjMzdiNWRlMzM3MWUiLAogICAgICAicGF0aCI6ICJsaWJyYXJ5L05GLTMubWQiLAogICAgICAicHJvb2YiOiBbCiAgICAgICAgewogICAgICAgICAgImhhc2giOiAiZDQ3OGJmOWU0MWI0YzUzNzExMDBiM2QxN2Y4NmM4NzkwNDU4YzZhYzI0YzE4MmU0ZjZmZmFlM2MyY2FhMjQ4OSIsCiAgICAgICAgICAic2lkZSI6ICJsZWZ0IgogICAgICAgIH0KICAgICAgXQogICAgfQogIF0sCiAgInJvb3QiOiAiYTljNWNlODQ5NWU0NmRhM2Y0OTBjOTk3YjFkMDU2MWI2MDg2NzgzODYwZjhkODIxNzE3NzM2NzNjOWI1ZWQyMCIsCiAgInNjaGVtYSI6ICJuZi1yZWNlaXB0cy8xIgp9Cg=="),
    };

    private static readonly (string Rel, string B64)[] LibEntryRemovedFiles =
    {
		("library/NF-1.md", "LS0tCmlkOiBORi0xCnR5cGU6IGd1aWRlCnRpdGxlOiDlkIjmiJDmnaHnm64xCmRlc2NyaXB0aW9uOiDlkIjmiJDppobol4/mnaHnm67vvIjmjqLpkojor63mlpnvvIkKbGljZW5zZTogTUlUCnN0YXR1czogYWN0aXZlCi0tLQoKIyDlkIjmiJDmnaHnm64gMQoK5q2j5paH56ysIDEg5p2h77yI5o6i6ZKI6K+t5paZ77yJ44CCCg=="),
		("library/NF-2.md", "LS0tCmlkOiBORi0yCnR5cGU6IGd1aWRlCnRpdGxlOiDlkIjmiJDmnaHnm64yCmRlc2NyaXB0aW9uOiDlkIjmiJDppobol4/mnaHnm67vvIjmjqLpkojor63mlpnvvIkKbGljZW5zZTogTUlUCnN0YXR1czogYWN0aXZlCi0tLQoKIyDlkIjmiJDmnaHnm64gMgoK5q2j5paH56ysIDIg5p2h77yI5o6i6ZKI6K+t5paZ77yJ44CCCg=="),
		("library/NF-3.md", "LS0tCmlkOiBORi0zCnR5cGU6IGd1aWRlCnRpdGxlOiDlkIjmiJDmnaHnm64zCmRlc2NyaXB0aW9uOiDlkIjmiJDppobol4/mnaHnm67vvIjmjqLpkojor63mlpnvvIkKbGljZW5zZTogTUlUCnN0YXR1czogYWN0aXZlCi0tLQoKIyDlkIjmiJDmnaHnm64gMwoK5q2j5paH56ysIDMg5p2h77yI5o6i6ZKI6K+t5paZ77yJ44CCCg=="),
		("library/RECEIPTS.json", "ewogICJhbGdvcml0aG0iOiAiUkZDNjk2Mi1zdHlsZSBzaGEyNTYgZG9tYWluLXNlcGFyYXRlZCIsCiAgImNvdW50IjogMywKICAiZW50cmllcyI6IFsKICAgIHsKICAgICAgImFuY2hvciI6IG51bGwsCiAgICAgICJkaWdlc3QiOiAiMTZlZTY0OTI3MDgzYjFiOGRmYzI0MTAxMTEyYjY3NmUyODNkMGEyYjY0YzVhYzE3Y2RjNTlmZjA1Mjk4YTU4MiIsCiAgICAgICJpZCI6ICJORi0xIiwKICAgICAgImxlYWYiOiAiNTJjMTk0YmRmMmQyNTFkOGEyNTM4ODVhM2MyZDYwYTNmN2NhZGZiMTg4OGIwN2QyNDFiZmI4MjYwOTQ2YzVhZSIsCiAgICAgICJwYXRoIjogImxpYnJhcnkvTkYtMS5tZCIsCiAgICAgICJwcm9vZiI6IFsKICAgICAgICB7CiAgICAgICAgICAiaGFzaCI6ICI5MjhkYWE2ZDFkOTg4MjczZWI1Y2Q3NWQwYzQxMjA5Yzk1MDdlN2ZhYjc5YWFkM2RhZDZlNjhiYTM4N2Y0Y2Q2IiwKICAgICAgICAgICJzaWRlIjogInJpZ2h0IgogICAgICAgIH0sCiAgICAgICAgewogICAgICAgICAgImhhc2giOiAiNmI1NDBmNzI2Zjg3MTBjMTkyMTBhMjA4NjQ4MGRlY2ZlMjJiOWFmNDVlZDlkNDRjMzlmM2MzN2I1ZGUzMzcxZSIsCiAgICAgICAgICAic2lkZSI6ICJyaWdodCIKICAgICAgICB9CiAgICAgIF0KICAgIH0sCiAgICB7CiAgICAgICJhbmNob3IiOiBudWxsLAogICAgICAiZGlnZXN0IjogIjcwYzk0MGI0NGI4Mjg1MTA2OTM1YjU3YTU4NWJkZWU4MWE4MzYyNzJiMmQ3NWZhN2E1NzFmY2VmZGM0MjYzZTMiLAogICAgICAiaWQiOiAiTkYtMiIsCiAgICAgICJsZWFmIjogIjkyOGRhYTZkMWQ5ODgyNzNlYjVjZDc1ZDBjNDEyMDljOTUwN2U3ZmFiNzlhYWQzZGFkNmU2OGJhMzg3ZjRjZDYiLAogICAgICAicGF0aCI6ICJsaWJyYXJ5L05GLTIubWQiLAogICAgICAicHJvb2YiOiBbCiAgICAgICAgewogICAgICAgICAgImhhc2giOiAiNTJjMTk0YmRmMmQyNTFkOGEyNTM4ODVhM2MyZDYwYTNmN2NhZGZiMTg4OGIwN2QyNDFiZmI4MjYwOTQ2YzVhZSIsCiAgICAgICAgICAic2lkZSI6ICJsZWZ0IgogICAgICAgIH0sCiAgICAgICAgewogICAgICAgICAgImhhc2giOiAiNmI1NDBmNzI2Zjg3MTBjMTkyMTBhMjA4NjQ4MGRlY2ZlMjJiOWFmNDVlZDlkNDRjMzlmM2MzN2I1ZGUzMzcxZSIsCiAgICAgICAgICAic2lkZSI6ICJyaWdodCIKICAgICAgICB9CiAgICAgIF0KICAgIH0KICBdLAogICJyb290IjogImE5YzVjZTg0OTVlNDZkYTNmNDkwYzk5N2IxZDA1NjFiNjA4Njc4Mzg2MGY4ZDgyMTcxNzczNjczYzliNWVkMjAiLAogICJzY2hlbWEiOiAibmYtcmVjZWlwdHMvMSIKfQo="),
    };

    private static readonly (string Rel, string B64)[] LibGhostEntryFiles =
    {
		("library/NF-1.md", "LS0tCmlkOiBORi0xCnR5cGU6IGd1aWRlCnRpdGxlOiDlkIjmiJDmnaHnm64xCmRlc2NyaXB0aW9uOiDlkIjmiJDppobol4/mnaHnm67vvIjmjqLpkojor63mlpnvvIkKbGljZW5zZTogTUlUCnN0YXR1czogYWN0aXZlCi0tLQoKIyDlkIjmiJDmnaHnm64gMQoK5q2j5paH56ysIDEg5p2h77yI5o6i6ZKI6K+t5paZ77yJ44CCCg=="),
		("library/NF-2.md", "LS0tCmlkOiBORi0yCnR5cGU6IGd1aWRlCnRpdGxlOiDlkIjmiJDmnaHnm64yCmRlc2NyaXB0aW9uOiDlkIjmiJDppobol4/mnaHnm67vvIjmjqLpkojor63mlpnvvIkKbGljZW5zZTogTUlUCnN0YXR1czogYWN0aXZlCi0tLQoKIyDlkIjmiJDmnaHnm64gMgoK5q2j5paH56ysIDIg5p2h77yI5o6i6ZKI6K+t5paZ77yJ44CCCg=="),
		("library/NF-3.md", "LS0tCmlkOiBORi0zCnR5cGU6IGd1aWRlCnRpdGxlOiDlkIjmiJDmnaHnm64zCmRlc2NyaXB0aW9uOiDlkIjmiJDppobol4/mnaHnm67vvIjmjqLpkojor63mlpnvvIkKbGljZW5zZTogTUlUCnN0YXR1czogYWN0aXZlCi0tLQoKIyDlkIjmiJDmnaHnm64gMwoK5q2j5paH56ysIDMg5p2h77yI5o6i6ZKI6K+t5paZ77yJ44CCCg=="),
		("library/RECEIPTS.json", "ewogICJhbGdvcml0aG0iOiAiUkZDNjk2Mi1zdHlsZSBzaGEyNTYgZG9tYWluLXNlcGFyYXRlZCIsCiAgImNvdW50IjogMywKICAiZW50cmllcyI6IFsKICAgIHsKICAgICAgImFuY2hvciI6IG51bGwsCiAgICAgICJkaWdlc3QiOiAiMTZlZTY0OTI3MDgzYjFiOGRmYzI0MTAxMTEyYjY3NmUyODNkMGEyYjY0YzVhYzE3Y2RjNTlmZjA1Mjk4YTU4MiIsCiAgICAgICJpZCI6ICJORi05OTkiLAogICAgICAibGVhZiI6ICI1MmMxOTRiZGYyZDI1MWQ4YTI1Mzg4NWEzYzJkNjBhM2Y3Y2FkZmIxODg4YjA3ZDI0MWJmYjgyNjA5NDZjNWFlIiwKICAgICAgInBhdGgiOiAibGlicmFyeS9ORi0xLm1kIiwKICAgICAgInByb29mIjogWwogICAgICAgIHsKICAgICAgICAgICJoYXNoIjogIjkyOGRhYTZkMWQ5ODgyNzNlYjVjZDc1ZDBjNDEyMDljOTUwN2U3ZmFiNzlhYWQzZGFkNmU2OGJhMzg3ZjRjZDYiLAogICAgICAgICAgInNpZGUiOiAicmlnaHQiCiAgICAgICAgfSwKICAgICAgICB7CiAgICAgICAgICAiaGFzaCI6ICI2YjU0MGY3MjZmODcxMGMxOTIxMGEyMDg2NDgwZGVjZmUyMmI5YWY0NWVkOWQ0NGMzOWYzYzM3YjVkZTMzNzFlIiwKICAgICAgICAgICJzaWRlIjogInJpZ2h0IgogICAgICAgIH0KICAgICAgXQogICAgfSwKICAgIHsKICAgICAgImFuY2hvciI6IG51bGwsCiAgICAgICJkaWdlc3QiOiAiNzBjOTQwYjQ0YjgyODUxMDY5MzViNTdhNTg1YmRlZTgxYTgzNjI3MmIyZDc1ZmE3YTU3MWZjZWZkYzQyNjNlMyIsCiAgICAgICJpZCI6ICJORi0yIiwKICAgICAgImxlYWYiOiAiOTI4ZGFhNmQxZDk4ODI3M2ViNWNkNzVkMGM0MTIwOWM5NTA3ZTdmYWI3OWFhZDNkYWQ2ZTY4YmEzODdmNGNkNiIsCiAgICAgICJwYXRoIjogImxpYnJhcnkvTkYtMi5tZCIsCiAgICAgICJwcm9vZiI6IFsKICAgICAgICB7CiAgICAgICAgICAiaGFzaCI6ICI1MmMxOTRiZGYyZDI1MWQ4YTI1Mzg4NWEzYzJkNjBhM2Y3Y2FkZmIxODg4YjA3ZDI0MWJmYjgyNjA5NDZjNWFlIiwKICAgICAgICAgICJzaWRlIjogImxlZnQiCiAgICAgICAgfSwKICAgICAgICB7CiAgICAgICAgICAiaGFzaCI6ICI2YjU0MGY3MjZmODcxMGMxOTIxMGEyMDg2NDgwZGVjZmUyMmI5YWY0NWVkOWQ0NGMzOWYzYzM3YjVkZTMzNzFlIiwKICAgICAgICAgICJzaWRlIjogInJpZ2h0IgogICAgICAgIH0KICAgICAgXQogICAgfSwKICAgIHsKICAgICAgImFuY2hvciI6IG51bGwsCiAgICAgICJkaWdlc3QiOiAiMzdiMWVjMzIwZWUwZDllYjg3MjRiOTNhZmE2ZjNkZjVhYTlkYThmYjVjYjQ3ZDlhMjg0NTAxOTY3MjFlNGIwYiIsCiAgICAgICJpZCI6ICJORi0zIiwKICAgICAgImxlYWYiOiAiNmI1NDBmNzI2Zjg3MTBjMTkyMTBhMjA4NjQ4MGRlY2ZlMjJiOWFmNDVlZDlkNDRjMzlmM2MzN2I1ZGUzMzcxZSIsCiAgICAgICJwYXRoIjogImxpYnJhcnkvTkYtMy5tZCIsCiAgICAgICJwcm9vZiI6IFsKICAgICAgICB7CiAgICAgICAgICAiaGFzaCI6ICJkNDc4YmY5ZTQxYjRjNTM3MTEwMGIzZDE3Zjg2Yzg3OTA0NThjNmFjMjRjMTgyZTRmNmZmYWUzYzJjYWEyNDg5IiwKICAgICAgICAgICJzaWRlIjogImxlZnQiCiAgICAgICAgfQogICAgICBdCiAgICB9CiAgXSwKICAicm9vdCI6ICJhOWM1Y2U4NDk1ZTQ2ZGEzZjQ5MGM5OTdiMWQwNTYxYjYwODY3ODM4NjBmOGQ4MjE3MTc3MzY3M2M5YjVlZDIwIiwKICAic2NoZW1hIjogIm5mLXJlY2VpcHRzLzEiCn0K"),
    };

    private static readonly (string Rel, string B64)[] LibSchemaFiles =
    {
		("library/NF-1.md", "LS0tCmlkOiBORi0xCnR5cGU6IGd1aWRlCnRpdGxlOiDlkIjmiJDmnaHnm64xCmRlc2NyaXB0aW9uOiDlkIjmiJDppobol4/mnaHnm67vvIjmjqLpkojor63mlpnvvIkKbGljZW5zZTogTUlUCnN0YXR1czogYWN0aXZlCi0tLQoKIyDlkIjmiJDmnaHnm64gMQoK5q2j5paH56ysIDEg5p2h77yI5o6i6ZKI6K+t5paZ77yJ44CCCg=="),
		("library/NF-2.md", "LS0tCmlkOiBORi0yCnR5cGU6IGd1aWRlCnRpdGxlOiDlkIjmiJDmnaHnm64yCmRlc2NyaXB0aW9uOiDlkIjmiJDppobol4/mnaHnm67vvIjmjqLpkojor63mlpnvvIkKbGljZW5zZTogTUlUCnN0YXR1czogYWN0aXZlCi0tLQoKIyDlkIjmiJDmnaHnm64gMgoK5q2j5paH56ysIDIg5p2h77yI5o6i6ZKI6K+t5paZ77yJ44CCCg=="),
		("library/NF-3.md", "LS0tCmlkOiBORi0zCnR5cGU6IGd1aWRlCnRpdGxlOiDlkIjmiJDmnaHnm64zCmRlc2NyaXB0aW9uOiDlkIjmiJDppobol4/mnaHnm67vvIjmjqLpkojor63mlpnvvIkKbGljZW5zZTogTUlUCnN0YXR1czogYWN0aXZlCi0tLQoKIyDlkIjmiJDmnaHnm64gMwoK5q2j5paH56ysIDMg5p2h77yI5o6i6ZKI6K+t5paZ77yJ44CCCg=="),
		("library/RECEIPTS.json", "ewogICJhbGdvcml0aG0iOiAiUkZDNjk2Mi1zdHlsZSBzaGEyNTYgZG9tYWluLXNlcGFyYXRlZCIsCiAgImNvdW50IjogMywKICAiZW50cmllcyI6IFsKICAgIHsKICAgICAgImFuY2hvciI6IG51bGwsCiAgICAgICJkaWdlc3QiOiAiMTZlZTY0OTI3MDgzYjFiOGRmYzI0MTAxMTEyYjY3NmUyODNkMGEyYjY0YzVhYzE3Y2RjNTlmZjA1Mjk4YTU4MiIsCiAgICAgICJpZCI6ICJORi0xIiwKICAgICAgImxlYWYiOiAiNTJjMTk0YmRmMmQyNTFkOGEyNTM4ODVhM2MyZDYwYTNmN2NhZGZiMTg4OGIwN2QyNDFiZmI4MjYwOTQ2YzVhZSIsCiAgICAgICJwYXRoIjogImxpYnJhcnkvTkYtMS5tZCIsCiAgICAgICJwcm9vZiI6IFsKICAgICAgICB7CiAgICAgICAgICAiaGFzaCI6ICI5MjhkYWE2ZDFkOTg4MjczZWI1Y2Q3NWQwYzQxMjA5Yzk1MDdlN2ZhYjc5YWFkM2RhZDZlNjhiYTM4N2Y0Y2Q2IiwKICAgICAgICAgICJzaWRlIjogInJpZ2h0IgogICAgICAgIH0sCiAgICAgICAgewogICAgICAgICAgImhhc2giOiAiNmI1NDBmNzI2Zjg3MTBjMTkyMTBhMjA4NjQ4MGRlY2ZlMjJiOWFmNDVlZDlkNDRjMzlmM2MzN2I1ZGUzMzcxZSIsCiAgICAgICAgICAic2lkZSI6ICJyaWdodCIKICAgICAgICB9CiAgICAgIF0KICAgIH0sCiAgICB7CiAgICAgICJhbmNob3IiOiBudWxsLAogICAgICAiZGlnZXN0IjogIjcwYzk0MGI0NGI4Mjg1MTA2OTM1YjU3YTU4NWJkZWU4MWE4MzYyNzJiMmQ3NWZhN2E1NzFmY2VmZGM0MjYzZTMiLAogICAgICAiaWQiOiAiTkYtMiIsCiAgICAgICJsZWFmIjogIjkyOGRhYTZkMWQ5ODgyNzNlYjVjZDc1ZDBjNDEyMDljOTUwN2U3ZmFiNzlhYWQzZGFkNmU2OGJhMzg3ZjRjZDYiLAogICAgICAicGF0aCI6ICJsaWJyYXJ5L05GLTIubWQiLAogICAgICAicHJvb2YiOiBbCiAgICAgICAgewogICAgICAgICAgImhhc2giOiAiNTJjMTk0YmRmMmQyNTFkOGEyNTM4ODVhM2MyZDYwYTNmN2NhZGZiMTg4OGIwN2QyNDFiZmI4MjYwOTQ2YzVhZSIsCiAgICAgICAgICAic2lkZSI6ICJsZWZ0IgogICAgICAgIH0sCiAgICAgICAgewogICAgICAgICAgImhhc2giOiAiNmI1NDBmNzI2Zjg3MTBjMTkyMTBhMjA4NjQ4MGRlY2ZlMjJiOWFmNDVlZDlkNDRjMzlmM2MzN2I1ZGUzMzcxZSIsCiAgICAgICAgICAic2lkZSI6ICJyaWdodCIKICAgICAgICB9CiAgICAgIF0KICAgIH0sCiAgICB7CiAgICAgICJhbmNob3IiOiBudWxsLAogICAgICAiZGlnZXN0IjogIjM3YjFlYzMyMGVlMGQ5ZWI4NzI0YjkzYWZhNmYzZGY1YWE5ZGE4ZmI1Y2I0N2Q5YTI4NDUwMTk2NzIxZTRiMGIiLAogICAgICAiaWQiOiAiTkYtMyIsCiAgICAgICJsZWFmIjogIjZiNTQwZjcyNmY4NzEwYzE5MjEwYTIwODY0ODBkZWNmZTIyYjlhZjQ1ZWQ5ZDQ0YzM5ZjNjMzdiNWRlMzM3MWUiLAogICAgICAicGF0aCI6ICJsaWJyYXJ5L05GLTMubWQiLAogICAgICAicHJvb2YiOiBbCiAgICAgICAgewogICAgICAgICAgImhhc2giOiAiZDQ3OGJmOWU0MWI0YzUzNzExMDBiM2QxN2Y4NmM4NzkwNDU4YzZhYzI0YzE4MmU0ZjZmZmFlM2MyY2FhMjQ4OSIsCiAgICAgICAgICAic2lkZSI6ICJsZWZ0IgogICAgICAgIH0KICAgICAgXQogICAgfQogIF0sCiAgInJvb3QiOiAiYTljNWNlODQ5NWU0NmRhM2Y0OTBjOTk3YjFkMDU2MWI2MDg2NzgzODYwZjhkODIxNzE3NzM2NzNjOWI1ZWQyMCIsCiAgInNjaGVtYSI6ICJuZi1yZWNlaXB0cy8yIgp9Cg=="),
    };

    private static readonly (string Rel, string B64)[] LibProofTamperedFiles =
    {
		("library/NF-1.md", "LS0tCmlkOiBORi0xCnR5cGU6IGd1aWRlCnRpdGxlOiDlkIjmiJDmnaHnm64xCmRlc2NyaXB0aW9uOiDlkIjmiJDppobol4/mnaHnm67vvIjmjqLpkojor63mlpnvvIkKbGljZW5zZTogTUlUCnN0YXR1czogYWN0aXZlCi0tLQoKIyDlkIjmiJDmnaHnm64gMQoK5q2j5paH56ysIDEg5p2h77yI5o6i6ZKI6K+t5paZ77yJ44CCCg=="),
		("library/NF-2.md", "LS0tCmlkOiBORi0yCnR5cGU6IGd1aWRlCnRpdGxlOiDlkIjmiJDmnaHnm64yCmRlc2NyaXB0aW9uOiDlkIjmiJDppobol4/mnaHnm67vvIjmjqLpkojor63mlpnvvIkKbGljZW5zZTogTUlUCnN0YXR1czogYWN0aXZlCi0tLQoKIyDlkIjmiJDmnaHnm64gMgoK5q2j5paH56ysIDIg5p2h77yI5o6i6ZKI6K+t5paZ77yJ44CCCg=="),
		("library/NF-3.md", "LS0tCmlkOiBORi0zCnR5cGU6IGd1aWRlCnRpdGxlOiDlkIjmiJDmnaHnm64zCmRlc2NyaXB0aW9uOiDlkIjmiJDppobol4/mnaHnm67vvIjmjqLpkojor63mlpnvvIkKbGljZW5zZTogTUlUCnN0YXR1czogYWN0aXZlCi0tLQoKIyDlkIjmiJDmnaHnm64gMwoK5q2j5paH56ysIDMg5p2h77yI5o6i6ZKI6K+t5paZ77yJ44CCCg=="),
		("library/RECEIPTS.json", "ewogICJhbGdvcml0aG0iOiAiUkZDNjk2Mi1zdHlsZSBzaGEyNTYgZG9tYWluLXNlcGFyYXRlZCIsCiAgImNvdW50IjogMywKICAiZW50cmllcyI6IFsKICAgIHsKICAgICAgImFuY2hvciI6IG51bGwsCiAgICAgICJkaWdlc3QiOiAiMTZlZTY0OTI3MDgzYjFiOGRmYzI0MTAxMTEyYjY3NmUyODNkMGEyYjY0YzVhYzE3Y2RjNTlmZjA1Mjk4YTU4MiIsCiAgICAgICJpZCI6ICJORi0xIiwKICAgICAgImxlYWYiOiAiNTJjMTk0YmRmMmQyNTFkOGEyNTM4ODVhM2MyZDYwYTNmN2NhZGZiMTg4OGIwN2QyNDFiZmI4MjYwOTQ2YzVhZSIsCiAgICAgICJwYXRoIjogImxpYnJhcnkvTkYtMS5tZCIsCiAgICAgICJwcm9vZiI6IFsKICAgICAgICB7CiAgICAgICAgICAiaGFzaCI6ICI5MjhkYWE2ZDFkOTg4MjczZWI1Y2Q3NWQwYzQxMjA5Yzk1MDdlN2ZhYjc5YWFkM2RhZDZlNjhiYTM4N2Y0Y2Q2IiwKICAgICAgICAgICJzaWRlIjogInJpZ2h0IgogICAgICAgIH0sCiAgICAgICAgewogICAgICAgICAgImhhc2giOiAiNmI1NDBmNzI2Zjg3MTBjMTkyMTBhMjA4NjQ4MGRlY2ZlMjJiOWFmNDVlZDlkNDRjMzlmM2MzN2I1ZGUzMzcxZSIsCiAgICAgICAgICAic2lkZSI6ICJyaWdodCIKICAgICAgICB9CiAgICAgIF0KICAgIH0sCiAgICB7CiAgICAgICJhbmNob3IiOiBudWxsLAogICAgICAiZGlnZXN0IjogIjcwYzk0MGI0NGI4Mjg1MTA2OTM1YjU3YTU4NWJkZWU4MWE4MzYyNzJiMmQ3NWZhN2E1NzFmY2VmZGM0MjYzZTMiLAogICAgICAiaWQiOiAiTkYtMiIsCiAgICAgICJsZWFmIjogIjAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAiLAogICAgICAicGF0aCI6ICJsaWJyYXJ5L05GLTIubWQiLAogICAgICAicHJvb2YiOiBbCiAgICAgICAgewogICAgICAgICAgImhhc2giOiAiNTJjMTk0YmRmMmQyNTFkOGEyNTM4ODVhM2MyZDYwYTNmN2NhZGZiMTg4OGIwN2QyNDFiZmI4MjYwOTQ2YzVhZSIsCiAgICAgICAgICAic2lkZSI6ICJsZWZ0IgogICAgICAgIH0sCiAgICAgICAgewogICAgICAgICAgImhhc2giOiAiNmI1NDBmNzI2Zjg3MTBjMTkyMTBhMjA4NjQ4MGRlY2ZlMjJiOWFmNDVlZDlkNDRjMzlmM2MzN2I1ZGUzMzcxZSIsCiAgICAgICAgICAic2lkZSI6ICJyaWdodCIKICAgICAgICB9CiAgICAgIF0KICAgIH0sCiAgICB7CiAgICAgICJhbmNob3IiOiBudWxsLAogICAgICAiZGlnZXN0IjogIjM3YjFlYzMyMGVlMGQ5ZWI4NzI0YjkzYWZhNmYzZGY1YWE5ZGE4ZmI1Y2I0N2Q5YTI4NDUwMTk2NzIxZTRiMGIiLAogICAgICAiaWQiOiAiTkYtMyIsCiAgICAgICJsZWFmIjogIjZiNTQwZjcyNmY4NzEwYzE5MjEwYTIwODY0ODBkZWNmZTIyYjlhZjQ1ZWQ5ZDQ0YzM5ZjNjMzdiNWRlMzM3MWUiLAogICAgICAicGF0aCI6ICJsaWJyYXJ5L05GLTMubWQiLAogICAgICAicHJvb2YiOiBbCiAgICAgICAgewogICAgICAgICAgImhhc2giOiAiZDQ3OGJmOWU0MWI0YzUzNzExMDBiM2QxN2Y4NmM4NzkwNDU4YzZhYzI0YzE4MmU0ZjZmZmFlM2MyY2FhMjQ4OSIsCiAgICAgICAgICAic2lkZSI6ICJsZWZ0IgogICAgICAgIH0KICAgICAgXQogICAgfQogIF0sCiAgInJvb3QiOiAiYTljNWNlODQ5NWU0NmRhM2Y0OTBjOTk3YjFkMDU2MWI2MDg2NzgzODYwZjhkODIxNzE3NzM2NzNjOWI1ZWQyMCIsCiAgInNjaGVtYSI6ICJuZi1yZWNlaXB0cy8xIgp9Cg=="),
    };

    private static readonly (string Rel, string B64)[] LibNewEntryFiles =
    {
		("library/NF-1.md", "LS0tCmlkOiBORi0xCnR5cGU6IGd1aWRlCnRpdGxlOiDlkIjmiJDmnaHnm64xCmRlc2NyaXB0aW9uOiDlkIjmiJDppobol4/mnaHnm67vvIjmjqLpkojor63mlpnvvIkKbGljZW5zZTogTUlUCnN0YXR1czogYWN0aXZlCi0tLQoKIyDlkIjmiJDmnaHnm64gMQoK5q2j5paH56ysIDEg5p2h77yI5o6i6ZKI6K+t5paZ77yJ44CCCg=="),
		("library/NF-2.md", "LS0tCmlkOiBORi0yCnR5cGU6IGd1aWRlCnRpdGxlOiDlkIjmiJDmnaHnm64yCmRlc2NyaXB0aW9uOiDlkIjmiJDppobol4/mnaHnm67vvIjmjqLpkojor63mlpnvvIkKbGljZW5zZTogTUlUCnN0YXR1czogYWN0aXZlCi0tLQoKIyDlkIjmiJDmnaHnm64gMgoK5q2j5paH56ysIDIg5p2h77yI5o6i6ZKI6K+t5paZ77yJ44CCCg=="),
		("library/NF-3.md", "LS0tCmlkOiBORi0zCnR5cGU6IGd1aWRlCnRpdGxlOiDlkIjmiJDmnaHnm64zCmRlc2NyaXB0aW9uOiDlkIjmiJDppobol4/mnaHnm67vvIjmjqLpkojor63mlpnvvIkKbGljZW5zZTogTUlUCnN0YXR1czogYWN0aXZlCi0tLQoKIyDlkIjmiJDmnaHnm64gMwoK5q2j5paH56ysIDMg5p2h77yI5o6i6ZKI6K+t5paZ77yJ44CCCg=="),
		("library/NF-4.md", "LS0tCmlkOiBORi00CnR5cGU6IGd1aWRlCnRpdGxlOiDlkIjmiJDmnaHnm640CmRlc2NyaXB0aW9uOiDlkIjmiJDppobol4/mnaHnm67vvIjmjqLpkojor63mlpnvvIkKbGljZW5zZTogTUlUCnN0YXR1czogYWN0aXZlCi0tLQoKIyDlkIjmiJDmnaHnm64gNAoK5q2j5paH56ysIDQg5p2h77yI5o6i6ZKI6K+t5paZ77yJ44CCCg=="),
		("library/RECEIPTS.json", "ewogICJhbGdvcml0aG0iOiAiUkZDNjk2Mi1zdHlsZSBzaGEyNTYgZG9tYWluLXNlcGFyYXRlZCIsCiAgImNvdW50IjogMywKICAiZW50cmllcyI6IFsKICAgIHsKICAgICAgImFuY2hvciI6IG51bGwsCiAgICAgICJkaWdlc3QiOiAiMTZlZTY0OTI3MDgzYjFiOGRmYzI0MTAxMTEyYjY3NmUyODNkMGEyYjY0YzVhYzE3Y2RjNTlmZjA1Mjk4YTU4MiIsCiAgICAgICJpZCI6ICJORi0xIiwKICAgICAgImxlYWYiOiAiNTJjMTk0YmRmMmQyNTFkOGEyNTM4ODVhM2MyZDYwYTNmN2NhZGZiMTg4OGIwN2QyNDFiZmI4MjYwOTQ2YzVhZSIsCiAgICAgICJwYXRoIjogImxpYnJhcnkvTkYtMS5tZCIsCiAgICAgICJwcm9vZiI6IFsKICAgICAgICB7CiAgICAgICAgICAiaGFzaCI6ICI5MjhkYWE2ZDFkOTg4MjczZWI1Y2Q3NWQwYzQxMjA5Yzk1MDdlN2ZhYjc5YWFkM2RhZDZlNjhiYTM4N2Y0Y2Q2IiwKICAgICAgICAgICJzaWRlIjogInJpZ2h0IgogICAgICAgIH0sCiAgICAgICAgewogICAgICAgICAgImhhc2giOiAiNmI1NDBmNzI2Zjg3MTBjMTkyMTBhMjA4NjQ4MGRlY2ZlMjJiOWFmNDVlZDlkNDRjMzlmM2MzN2I1ZGUzMzcxZSIsCiAgICAgICAgICAic2lkZSI6ICJyaWdodCIKICAgICAgICB9CiAgICAgIF0KICAgIH0sCiAgICB7CiAgICAgICJhbmNob3IiOiBudWxsLAogICAgICAiZGlnZXN0IjogIjcwYzk0MGI0NGI4Mjg1MTA2OTM1YjU3YTU4NWJkZWU4MWE4MzYyNzJiMmQ3NWZhN2E1NzFmY2VmZGM0MjYzZTMiLAogICAgICAiaWQiOiAiTkYtMiIsCiAgICAgICJsZWFmIjogIjkyOGRhYTZkMWQ5ODgyNzNlYjVjZDc1ZDBjNDEyMDljOTUwN2U3ZmFiNzlhYWQzZGFkNmU2OGJhMzg3ZjRjZDYiLAogICAgICAicGF0aCI6ICJsaWJyYXJ5L05GLTIubWQiLAogICAgICAicHJvb2YiOiBbCiAgICAgICAgewogICAgICAgICAgImhhc2giOiAiNTJjMTk0YmRmMmQyNTFkOGEyNTM4ODVhM2MyZDYwYTNmN2NhZGZiMTg4OGIwN2QyNDFiZmI4MjYwOTQ2YzVhZSIsCiAgICAgICAgICAic2lkZSI6ICJsZWZ0IgogICAgICAgIH0sCiAgICAgICAgewogICAgICAgICAgImhhc2giOiAiNmI1NDBmNzI2Zjg3MTBjMTkyMTBhMjA4NjQ4MGRlY2ZlMjJiOWFmNDVlZDlkNDRjMzlmM2MzN2I1ZGUzMzcxZSIsCiAgICAgICAgICAic2lkZSI6ICJyaWdodCIKICAgICAgICB9CiAgICAgIF0KICAgIH0sCiAgICB7CiAgICAgICJhbmNob3IiOiBudWxsLAogICAgICAiZGlnZXN0IjogIjM3YjFlYzMyMGVlMGQ5ZWI4NzI0YjkzYWZhNmYzZGY1YWE5ZGE4ZmI1Y2I0N2Q5YTI4NDUwMTk2NzIxZTRiMGIiLAogICAgICAiaWQiOiAiTkYtMyIsCiAgICAgICJsZWFmIjogIjZiNTQwZjcyNmY4NzEwYzE5MjEwYTIwODY0ODBkZWNmZTIyYjlhZjQ1ZWQ5ZDQ0YzM5ZjNjMzdiNWRlMzM3MWUiLAogICAgICAicGF0aCI6ICJsaWJyYXJ5L05GLTMubWQiLAogICAgICAicHJvb2YiOiBbCiAgICAgICAgewogICAgICAgICAgImhhc2giOiAiZDQ3OGJmOWU0MWI0YzUzNzExMDBiM2QxN2Y4NmM4NzkwNDU4YzZhYzI0YzE4MmU0ZjZmZmFlM2MyY2FhMjQ4OSIsCiAgICAgICAgICAic2lkZSI6ICJsZWZ0IgogICAgICAgIH0KICAgICAgXQogICAgfQogIF0sCiAgInJvb3QiOiAiYTljNWNlODQ5NWU0NmRhM2Y0OTBjOTk3YjFkMDU2MWI2MDg2NzgzODYwZjhkODIxNzE3NzM2NzNjOWI1ZWQyMCIsCiAgInNjaGVtYSI6ICJuZi1yZWNlaXB0cy8xIgp9Cg=="),
    };
}
