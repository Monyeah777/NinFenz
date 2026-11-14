using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Encodings.Web;

// 独立 C# 实现：对冻结 trust 向量复算六族（canonical/domain/pae/merkle/process/level）。
// 不引用 Python/Node 实现；entity 族需完整 JSON Schema 引擎，显式跳过。
internal static class Program
{
    private const string Zero = "0000000000000000000000000000000000000000000000000000000000000000";
    private static readonly string[] Levels = { "T0", "T1", "T2", "T3", "T4" };
    private static readonly Dictionary<string, string> FactOfLevel = new()
    {
        ["T1"] = "signature", ["T2"] = "time_token",
        ["T3"] = "transparency_sth", ["T4"] = "public_anchor"
    };
    private static readonly Dictionary<string, string> MissingCode = new()
    {
        ["T1"] = "SIGNATURE-MISSING", ["T2"] = "ANCHOR-MISSING",
        ["T3"] = "WITNESS-MISSING", ["T4"] = "PUBLIC-ANCHOR-MISSING"
    };
    private static readonly string[] StepFields =
    {
        "schema", "process_id", "step", "prev", "actor", "authorization",
        "input_refs", "output_refs", "state_digest", "type"
    };

    private static string Hex(byte[] data) => Convert.ToHexString(data).ToLowerInvariant();
    private static string ShaHex(byte[] data) => Hex(SHA256.HashData(data));

    private static void RejectFloat(JsonElement node, string path)
    {
        switch (node.ValueKind)
        {
            case JsonValueKind.Number:
                if (!node.TryGetInt64(out _)) throw new InvalidOperationException(path + ": FLOAT-FORBIDDEN");
                return;
            case JsonValueKind.Object:
                if (node.TryGetProperty("nonfinite", out var nf) && nf.ValueKind == JsonValueKind.String
                    && nf.GetString() == "NaN") throw new InvalidOperationException(path + ": NONFINITE-FORBIDDEN");
                foreach (var p in node.EnumerateObject()) RejectFloat(p.Value, path + "." + p.Name);
                return;
            case JsonValueKind.Array:
                var i = 0;
                foreach (var item in node.EnumerateArray()) RejectFloat(item, path + "[" + i++ + "]");
                return;
            case JsonValueKind.String:
            case JsonValueKind.True:
            case JsonValueKind.False:
            case JsonValueKind.Null:
                return;
            default:
                throw new InvalidOperationException(path + ": unsupported type");
        }
    }

    private static string Canonical(JsonElement node)
    {
        switch (node.ValueKind)
        {
            case JsonValueKind.Null: return "null";
            case JsonValueKind.True: return "true";
            case JsonValueKind.False: return "false";
            case JsonValueKind.Number: return node.GetInt64().ToString(System.Globalization.CultureInfo.InvariantCulture);
            case JsonValueKind.String: return Escape(node.GetString() ?? "");
            case JsonValueKind.Array: return "[" + string.Join(",", node.EnumerateArray().Select(Canonical)) + "]";
            case JsonValueKind.Object:
                var props = node.EnumerateObject().OrderBy(p => p.Name, StringComparer.Ordinal);
                return "{" + string.Join(",", props.Select(p =>
                    Escape(p.Name) + ":" + Canonical(p.Value))) + "}";
            default: throw new InvalidOperationException("unsupported canonical");
        }
    }

    private static string Escape(string value)
    {
        var sb = new StringBuilder("\"");
        foreach (var ch in value)
        {
            switch (ch)
            {
                case '"': sb.Append("\\\""); break;
                case '\\': sb.Append("\\\\"); break;
                case '\b': sb.Append("\\b"); break;
                case '\f': sb.Append("\\f"); break;
                case '\n': sb.Append("\\n"); break;
                case '\r': sb.Append("\\r"); break;
                case '\t': sb.Append("\\t"); break;
                default:
                    if (ch < 0x20) sb.Append("\\u").Append(((int)ch).ToString("x4"));
                    else sb.Append(ch);
                    break;
            }
        }
        return sb.Append('"').ToString();
    }

    private static byte[] CanonicalBytes(JsonElement node) => Encoding.UTF8.GetBytes(Canonical(node));
    private static string DigestOf(JsonElement node) => ShaHex(CanonicalBytes(node));

    private static byte[] LeafHash(byte[] data)
    {
        var buf = new byte[1 + data.Length];
        buf[0] = 0;
        data.CopyTo(buf, 1);
        return SHA256.HashData(buf);
    }

    private static byte[] NodeHash(byte[] left, byte[] right)
    {
        var buf = new byte[1 + left.Length + right.Length];
        buf[0] = 1;
        left.CopyTo(buf, 1);
        right.CopyTo(buf, 1 + left.Length);
        return SHA256.HashData(buf);
    }

    private static byte[] MerkleRoot(List<byte[]> leaves)
    {
        if (leaves.Count == 0) throw new InvalidOperationException("empty leaves");
        if (leaves.Count == 1) return leaves[0];
        var mid = 1;
        while (mid * 2 < leaves.Count) mid *= 2;
        return NodeHash(MerkleRoot(leaves.GetRange(0, mid)), MerkleRoot(leaves.GetRange(mid, leaves.Count - mid)));
    }

    private static List<Dictionary<string, string>> InclusionProof(List<byte[]> leaves, int index)
    {
        if (index < 0 || index >= leaves.Count) throw new InvalidOperationException("INDEX-OUT-OF-RANGE");
        var proof = new List<Dictionary<string, string>>();
        void Walk(List<byte[]> sub, int i)
        {
            if (sub.Count <= 1) return;
            var mid = 1;
            while (mid * 2 < sub.Count) mid *= 2;
            var left = sub.GetRange(0, mid);
            var right = sub.GetRange(mid, sub.Count - mid);
            if (i < mid)
            {
                Walk(left, i);
                proof.Add(new Dictionary<string, string>
                {
                    ["side"] = "right", ["hash"] = Hex(MerkleRoot(right))
                });
            }
            else
            {
                Walk(right, i - mid);
                proof.Add(new Dictionary<string, string>
                {
                    ["side"] = "left", ["hash"] = Hex(MerkleRoot(left))
                });
            }
        }
        Walk(leaves, index);
        return proof;
    }

    private static string FoldProof(string leafHex, List<Dictionary<string, string>> proof)
    {
        var cur = Convert.FromHexString(leafHex);
        foreach (var step in proof)
        {
            var sib = Convert.FromHexString(step["hash"]);
            cur = step["side"] == "left" ? NodeHash(sib, cur) : NodeHash(cur, sib);
        }
        return Hex(cur);
    }

    private static byte[] Pae(byte[] ptype, byte[] payload)
    {
        if (ptype.Length == 0) throw new InvalidOperationException("PAE-EMPTY-TYPE");
        var head = Encoding.UTF8.GetBytes("DSSEv1 " + ptype.Length + " ");
        var mid = Encoding.UTF8.GetBytes(" " + payload.Length + " ");
        var buf = new byte[head.Length + ptype.Length + mid.Length + payload.Length];
        var pos = 0;
        head.CopyTo(buf, pos); pos += head.Length;
        ptype.CopyTo(buf, pos); pos += ptype.Length;
        mid.CopyTo(buf, pos); pos += mid.Length;
        payload.CopyTo(buf, pos);
        return buf;
    }

    private static bool IsDigest(string? value) =>
        value is { Length: 64 } && value.All(ch => (ch >= '0' && ch <= '9') || (ch >= 'a' && ch <= 'f'));

    private static string StepDigest(JsonElement step)
    {
        foreach (var field in StepFields)
            if (!step.TryGetProperty(field, out _)) throw new InvalidOperationException("STEP-MISSING-FIELD");
        var body = new SortedDictionary<string, JsonElement>(StringComparer.Ordinal);
        foreach (var p in step.EnumerateObject())
            if (p.Name != "digest") body[p.Name] = p.Value;
        var json = "{" + string.Join(",", body.Select(kv =>
            Escape(kv.Key) + ":" + Canonical(kv.Value))) + "}";
        var payload = Encoding.UTF8.GetBytes(json);
        var tag = Encoding.UTF8.GetBytes("nf:process:v1:step");
        var buf = new byte[tag.Length + 1 + payload.Length];
        tag.CopyTo(buf, 0); buf[tag.Length] = 0; payload.CopyTo(buf, tag.Length + 1);
        return ShaHex(buf);
    }

    private static Dictionary<string, object?> VerifyChain(JsonElement steps)
    {
        if (steps.ValueKind != JsonValueKind.Array || steps.GetArrayLength() == 0)
            return new() { ["valid"] = false, ["reason"] = "STEPS-EMPTY" };
        var digests = new List<string>();
        var head = Zero;
        var index = 0;
        foreach (var step in steps.EnumerateArray())
        {
            if (step.ValueKind != JsonValueKind.Object)
                return new() { ["valid"] = false, ["reason"] = "STEP-NOT-OBJECT" };
            var prev = step.TryGetProperty("prev", out var pv) && pv.ValueKind == JsonValueKind.String ? pv.GetString() : null;
            if (!IsDigest(prev)) return new() { ["valid"] = false, ["reason"] = "PREV-FORMAT" };
            if (!step.TryGetProperty("step", out var sv) || !sv.TryGetInt32(out var seq) || seq != index + 1)
                return new() { ["valid"] = false, ["reason"] = "SEQ-ORDER" };
            if (prev != head) return new() { ["valid"] = false, ["reason"] = "PREV-MISMATCH" };
            head = StepDigest(step);
            digests.Add(head);
            index++;
        }
        return new() { ["valid"] = true, ["digests"] = digests, ["head"] = head };
    }

    private static Dictionary<string, object?> Decide(JsonElement facts, string required, bool policyOk)
    {
        if (!Levels.Contains(required)) throw new InvalidOperationException("required_level 非法");
        if (!policyOk) return new() { ["achieved"] = "none", ["exit_code"] = 2,
                                      ["missing"] = new List<string> { "POLICY-INVALID" } };
        if (!facts.TryGetProperty("hash", out var h) || h.GetString() != "ok")
            return new() { ["achieved"] = "none", ["exit_code"] = 1, ["missing"] = new List<string>() };
        foreach (var level in Levels.Skip(1))
        {
            if (facts.TryGetProperty(FactOfLevel[level], out var fv) && fv.GetString() == "invalid")
                return new() { ["achieved"] = "none", ["exit_code"] = 1, ["missing"] = new List<string>() };
        }
        var achieved = "T0";
        foreach (var level in Levels.Skip(1))
        {
            if (!facts.TryGetProperty(FactOfLevel[level], out var fv) || fv.GetString() != "ok") break;
            achieved = level;
        }
        if (Array.IndexOf(Levels, achieved) >= Array.IndexOf(Levels, required))
            return new() { ["achieved"] = achieved, ["exit_code"] = 0, ["missing"] = new List<string>() };
        var missing = new List<string>();
        for (var i = Array.IndexOf(Levels, achieved) + 1; i <= Array.IndexOf(Levels, required); i++)
            missing.Add(MissingCode[Levels[i]]);
        return new() { ["achieved"] = achieved, ["exit_code"] = 2, ["missing"] = missing };
    }

    private static bool Eq(JsonElement expected, object? got)
    {
        var options = new JsonSerializerOptions
        {
            Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping
        };
        var gotJson = JsonSerializer.Serialize(got, options);
        using var e = JsonDocument.Parse(expected.GetRawText());
        using var g = JsonDocument.Parse(gotJson);
        return DeepEq(e.RootElement, g.RootElement);
    }

    private static bool DeepEq(JsonElement a, JsonElement b)
    {
        if (a.ValueKind != b.ValueKind) return false;
        switch (a.ValueKind)
        {
            case JsonValueKind.Object:
                var pa = a.EnumerateObject().OrderBy(p => p.Name, StringComparer.Ordinal).ToList();
                var pb = b.EnumerateObject().OrderBy(p => p.Name, StringComparer.Ordinal).ToList();
                if (pa.Count != pb.Count) return false;
                for (var i = 0; i < pa.Count; i++)
                    if (pa[i].Name != pb[i].Name || !DeepEq(pa[i].Value, pb[i].Value)) return false;
                return true;
            case JsonValueKind.Array:
                if (a.GetArrayLength() != b.GetArrayLength()) return false;
                for (var i = 0; i < a.GetArrayLength(); i++)
                    if (!DeepEq(a[i], b[i])) return false;
                return true;
            default:
                return a.GetRawText() == b.GetRawText();
        }
    }

    private static object? CheckVector(JsonElement vec)
    {
        var family = vec.GetProperty("family").GetString();
        var expected = vec.GetProperty("expected");
        var input = vec.GetProperty("input");
        try
        {
            switch (family)
            {
                case "canonical":
                    if (!expected.GetProperty("valid").GetBoolean())
                    {
                        var reason = expected.TryGetProperty("reason", out var r) ? r.GetString() : "";
                        try { RejectFloat(input.GetProperty("value"), "$"); return new { id = vec.GetProperty("id").GetString(), ok = false, detail = "期望拒绝但通过" }; }
                        catch (InvalidOperationException exc) { return new { id = vec.GetProperty("id").GetString(), ok = exc.Message.Contains(reason ?? ""), detail = exc.Message }; }
                    }
                    {
                        var text = Canonical(input.GetProperty("value"));
                        var got = new SortedDictionary<string, object?>
                        {
                            ["canonical_utf8"] = text,
                            ["sha256"] = ShaHex(Encoding.UTF8.GetBytes(text)),
                            ["valid"] = true
                        };
                        return new { id = vec.GetProperty("id").GetString(), ok = Eq(expected, got), detail = got };
                    }
                case "domain":
                    {
                        var tag = input.GetProperty("tag").GetString() ?? "";
                        var payload = Encoding.UTF8.GetBytes(input.GetProperty("payload_utf8").GetString() ?? "");
                        if (!expected.GetProperty("tag_ok").GetBoolean())
                        {
                            try { DomainDigest(tag, payload); return new { id = vec.GetProperty("id").GetString(), ok = false, detail = "期望 TAG-FORMAT 拒绝" }; }
                            catch (InvalidOperationException exc) { return new { id = vec.GetProperty("id").GetString(), ok = exc.Message == "TAG-FORMAT", detail = exc.Message }; }
                        }
                        var got = new SortedDictionary<string, object?> { ["digest"] = DomainDigest(tag, payload), ["tag_ok"] = true };
                        if (expected.TryGetProperty("distinct_from", out _))
                        {
                            var alt = tag.EndsWith(":leaf") ? tag[..^5] + ":root" : tag[..^5] + ":leaf";
                            got["distinct_from"] = DomainDigest(alt, payload);
                        }
                        return new { id = vec.GetProperty("id").GetString(), ok = Eq(expected, got), detail = got };
                    }
                case "pae":
                    {
                        var ptype = Encoding.UTF8.GetBytes(input.GetProperty("payload_type_utf8").GetString() ?? "");
                        var payload = Convert.FromBase64String(input.GetProperty("payload_b64").GetString() ?? "");
                        if (!expected.GetProperty("valid").GetBoolean())
                        {
                            var reason = expected.TryGetProperty("reason", out var r) ? r.GetString() : "";
                            try { Pae(ptype, payload); return new { id = vec.GetProperty("id").GetString(), ok = false, detail = "期望拒绝但通过" }; }
                            catch (InvalidOperationException exc) { return new { id = vec.GetProperty("id").GetString(), ok = exc.Message == reason, detail = exc.Message }; }
                        }
                        var raw = Pae(ptype, payload);
                        var got = new SortedDictionary<string, object?>
                        {
                            ["pae_b64"] = Convert.ToBase64String(raw),
                            ["pae_sha256"] = ShaHex(raw),
                            ["valid"] = true
                        };
                        return new { id = vec.GetProperty("id").GetString(), ok = Eq(expected, got), detail = got };
                    }
                case "merkle":
                    {
                        var leaves = input.GetProperty("leaves_utf8").EnumerateArray()
                            .Select(x => LeafHash(Encoding.UTF8.GetBytes(x.GetString() ?? ""))).ToList();
                        if (!expected.GetProperty("valid").GetBoolean())
                        {
                            var reason = expected.TryGetProperty("reason", out var r) ? r.GetString() : "";
                            try { InclusionProof(leaves, input.GetProperty("index").GetInt32()); return new { id = vec.GetProperty("id").GetString(), ok = false, detail = "期望拒绝但通过" }; }
                            catch (InvalidOperationException exc) { return new { id = vec.GetProperty("id").GetString(), ok = exc.Message == reason, detail = exc.Message }; }
                        }
                        var root = MerkleRoot(leaves);
                        var proofs = new List<object>();
                        for (var i = 0; i < leaves.Count; i++)
                        {
                            var proof = InclusionProof(leaves, i);
                            proofs.Add(new SortedDictionary<string, object?>
                            {
                                ["index"] = i, ["proof"] = proof,
                                ["fold_root"] = FoldProof(Hex(leaves[i]), proof)
                            });
                        }
                        var got = new SortedDictionary<string, object?>
                        {
                            ["valid"] = true,
                            ["leaf_hashes"] = leaves.Select(Hex).ToList(),
                            ["root"] = Hex(root),
                            ["proofs"] = proofs
                        };
                        return new { id = vec.GetProperty("id").GetString(), ok = Eq(expected, got), detail = got };
                    }
                case "process":
                    {
                        var got = VerifyChain(input.GetProperty("steps"));
                        return new { id = vec.GetProperty("id").GetString(), ok = Eq(expected, got), detail = got };
                    }
                case "level":
                    {
                        var got = Decide(input.GetProperty("facts"), input.GetProperty("required_level").GetString() ?? "",
                                         input.TryGetProperty("policy_ok", out var po) ? po.GetBoolean() : true);
                        return new { id = vec.GetProperty("id").GetString(), ok = Eq(expected, got), detail = got };
                    }
                default:
                    return new { id = vec.GetProperty("id").GetString(), ok = true, skipped = family };
            }
        }
        catch (Exception exc)
        {
            return new { id = vec.GetProperty("id").GetString(), ok = false,
                         detail = "异常：" + exc.Message };
        }
    }

    private static string DomainDigest(string tag, byte[] payload)
    {
        if (!System.Text.RegularExpressions.Regex.IsMatch(tag,
                "^nf:[a-z0-9-]+:v[1-9][0-9]*:[a-z0-9-]+$"))
            throw new InvalidOperationException("TAG-FORMAT");
        var tagBytes = Encoding.UTF8.GetBytes(tag);
        var buf = new byte[tagBytes.Length + 1 + payload.Length];
        tagBytes.CopyTo(buf, 0); buf[tagBytes.Length] = 0; payload.CopyTo(buf, tagBytes.Length + 1);
        return ShaHex(buf);
    }

    private static int Main(string[] args)
    {
        var vectorsPath = "results/trust/trust_vectors.json";
        for (var i = 0; i < args.Length; i++)
            if (args[i] == "--vectors" && i + 1 < args.Length) vectorsPath = args[i + 1];
        using var doc = JsonDocument.Parse(File.ReadAllText(vectorsPath));
        if (doc.RootElement.GetProperty("schema").GetString() != "nf-trust-vectors/1")
        {
            Console.WriteLine("{\"ok\": false, \"error\": \"schema 不是 nf-trust-vectors/1\"}");
            return 2;
        }
        var checkedCounts = new SortedDictionary<string, int>(StringComparer.Ordinal);
        var skipped = new SortedSet<string>(StringComparer.Ordinal);
        var mismatches = new List<object?>();
        var total = 0;
        foreach (var vec in doc.RootElement.GetProperty("vectors").EnumerateArray())
        {
            total++;
            var result = CheckVector(vec);
            var kind = result?.GetType();
            var skippedFamily = kind?.GetProperty("skipped")?.GetValue(result) as string;
            if (skippedFamily != null) { skipped.Add(skippedFamily); continue; }
            var family = vec.GetProperty("family").GetString() ?? "";
            checkedCounts[family] = checkedCounts.GetValueOrDefault(family) + 1;
            var ok = kind?.GetProperty("ok")?.GetValue(result) as bool? ?? false;
            if (!ok) mismatches.Add(result);
        }
        var report = new SortedDictionary<string, object?>
        {
            ["ok"] = mismatches.Count == 0,
            ["checked"] = checkedCounts.ToDictionary(kv => kv.Key, kv => kv.Value),
            ["skipped"] = skipped.ToList(),
            ["mismatches"] = mismatches,
            ["total"] = total
        };
        Console.WriteLine(JsonSerializer.Serialize(report, new JsonSerializerOptions { WriteIndented = true }));
        return report["ok"] is true ? 0 : 1;
    }
}
