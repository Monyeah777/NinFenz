using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace Nf.Engine;

/// <summary>DSSE v1.0.2 PAE and JSON-envelope primitives (HMAC-SHA256 baseline).</summary>
public static class DSSE
{
    public const string PayloadTypeHeader = "DSSEv1";
    private static readonly Regex StdB64 = new(@"^[A-Za-z0-9+/]+={0,2}$", RegexOptions.CultureInvariant);
    private static readonly Regex UrlB64 = new(@"^[A-Za-z0-9_-]+={0,2}$", RegexOptions.CultureInvariant);

    public sealed record Signature(string Keyid, byte[] Sig);
    public sealed record Envelope(string PayloadType, byte[] Payload, IReadOnlyList<Signature> Signatures);
    public sealed record Verified(string PayloadType, byte[] Payload, IReadOnlyList<string> AcceptedKeyids);

    public static byte[] Pae(string payloadType, byte[] payload)
    {
        var type = Encoding.UTF8.GetBytes(payloadType);
        var head = Encoding.ASCII.GetBytes($"DSSEv1 {type.Length} ");
        var middle = Encoding.ASCII.GetBytes($" {payload.Length} ");
        var output = new byte[head.Length + type.Length + middle.Length + payload.Length];
        head.CopyTo(output, 0);
        type.CopyTo(output, head.Length);
        middle.CopyTo(output, head.Length + type.Length);
        payload.CopyTo(output, head.Length + type.Length + middle.Length);
        return output;
    }

    public static string B64Encode(byte[] value) => Convert.ToBase64String(value);

    public static byte[] B64Decode(string value)
    {
        if (value.Length == 0) return Array.Empty<byte>();
        if (value.Length % 4 != 0)
            throw new InvalidDataException("Base64 缺少合法 padding（修复指引：按 RFC 4648 补齐 '='）");
        var standard = StdB64.IsMatch(value);
        var urlsafe = UrlB64.IsMatch(value);
        if (!standard && !urlsafe)
            throw new InvalidDataException("Base64 含非法字符或混用了标准/URL-safe 字母表");
        var normalized = value.Replace('-', '+').Replace('_', '/');
        var raw = Convert.FromBase64String(normalized);
        var canonical = standard ? Convert.ToBase64String(raw) : UrlEncode(raw);
        if (value != canonical)
            throw new InvalidDataException("Base64 不是规范表示（修复指引：重新编码，勿依赖非零 pad bits）");
        return raw;
    }

    private static string UrlEncode(byte[] raw) =>
        Convert.ToBase64String(raw).TrimEnd('=').Replace('+', '-').Replace('/', '_')
            + new string('=', (3 - raw.Length % 3) % 3);

    public static Dictionary<string, object?> Sign(string payloadType, byte[] payload,
        byte[] key, string keyid = "")
    {
        if (string.IsNullOrEmpty(payloadType))
            throw new InvalidDataException("payloadType 必须是非空字符串");
        if (key.Length == 0) throw new InvalidDataException("HMAC-SHA256 密钥不能为空");
        var sig = HMACSHA256.HashData(key, Pae(payloadType, payload));
        var row = new Dictionary<string, object?>(StringComparer.Ordinal) { ["sig"] = B64Encode(sig) };
        if (!string.IsNullOrEmpty(keyid)) row["keyid"] = keyid;
        return new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["payload"] = B64Encode(payload),
            ["payloadType"] = payloadType,
            ["signatures"] = new List<object?> { row },
        };
    }

    public static Verified Verify(JsonElement document, string keyid, byte[] key,
        int threshold = 1, string? expectedPayloadType = null)
    {
        if (document.ValueKind != JsonValueKind.Object)
            throw new InvalidDataException("DSSE envelope 顶层必须是对象");
        if (threshold < 1) throw new InvalidDataException("threshold 必须 ≥ 1");
        if (key.Length == 0) throw new InvalidDataException("至少需要一个受信密钥（--key-file）");
        var top = Properties(document, "envelope");
        foreach (var required in new[] { "payload", "payloadType", "signatures" })
            if (!top.ContainsKey(required)) throw new InvalidDataException($"DSSE envelope 缺必填字段 {required}");
        if (top["payloadType"].ValueKind != JsonValueKind.String)
            throw new InvalidDataException("payloadType 必须是字符串");
        var payloadType = top["payloadType"].GetString()!;
        var payload = B64Decode(RequireString(top["payload"], "payload"));
        if (top["signatures"].ValueKind != JsonValueKind.Array)
            throw new InvalidDataException("signatures 必须是数组");
        var authenticated = Pae(payloadType, payload);
        var accepted = new List<string>();
        var seen = new HashSet<string>(StringComparer.Ordinal);
        var fingerprint = Convert.ToHexString(SHA256.HashData(key));
        var index = 0;
        foreach (var item in top["signatures"].EnumerateArray())
        {
            if (item.ValueKind != JsonValueKind.Object)
                throw new InvalidDataException($"signatures[{index}] 必须是对象");
            var row = Properties(item, $"signatures[{index}]");
            if (!row.ContainsKey("sig"))
                throw new InvalidDataException($"signatures[{index}] 缺必填字段 sig");
            var sigKeyid = "";
            if (row.TryGetValue("keyid", out var keyidNode) && keyidNode.ValueKind != JsonValueKind.Null)
                sigKeyid = RequireString(keyidNode, $"signatures[{index}].keyid");
            if (string.IsNullOrEmpty(sigKeyid) || sigKeyid == keyid)
            {
                var sig = B64Decode(RequireString(row["sig"], $"signatures[{index}].sig"));
                if (sig.Length == 32)
                {
                    var expected = HMACSHA256.HashData(key, authenticated);
                    if (CryptographicOperations.FixedTimeEquals(expected, sig)
                        && seen.Add(fingerprint))
                        accepted.Add(keyid);
                }
            }
            if (accepted.Count >= threshold) break;
            index++;
        }
        if (accepted.Count < threshold)
            throw new InvalidDataException($"没有达到阈值的有效 DSSE 签名（需要唯一受信密钥 {threshold} 个）");
        if (expectedPayloadType is not null && payloadType != expectedPayloadType)
            throw new InvalidDataException($"payloadType 不受支持：'{payloadType}'（支持：{expectedPayloadType}）");
        return new Verified(payloadType, payload, accepted);
    }

    public static byte[] NormalizeKey(byte[] raw)
    {
        var start = 0;
        var end = raw.Length;
        while (start < end && IsAsciiWhitespace(raw[start])) start++;
        while (end > start && IsAsciiWhitespace(raw[end - 1])) end--;
        return raw[start..end];
    }

    private static bool IsAsciiWhitespace(byte value) =>
        value is (byte)' ' or (byte)'\t' or (byte)'\r' or (byte)'\n';

    private static string RequireString(JsonElement node, string field)
    {
        if (node.ValueKind != JsonValueKind.String)
            throw new InvalidDataException($"{field} 必须是字符串");
        return node.GetString()!;
    }

    private static Dictionary<string, JsonElement> Properties(JsonElement obj, string where)
    {
        var output = new Dictionary<string, JsonElement>(StringComparer.Ordinal);
        foreach (var prop in obj.EnumerateObject())
        {
            if (!output.TryAdd(prop.Name, prop.Value))
                throw new InvalidDataException($"{where} 含 JSON 重复键：{prop.Name}");
        }
        return output;
    }
}
