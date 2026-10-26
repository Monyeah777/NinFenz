// RFC 8785 (JCS) 规范化 JSON —— 独立 C# 实现（BCL-only）。
//
// 与 Rust 侧 engine/rust/canonical 是**同一规范的两份独立实现**（跨语言对拍的价值前提：
// 复用他方解析器只能证明「同一个库没变」）。规范面：
//   §3.2.3 键按 UTF-16 码元序（StringComparer.Ordinal）——**不是**码点序；
//   §3.2.2.3 数字走 ECMAScript Number::toString（最短往返 + ES 的定点/指数切换点）；
//   §3.2.2.2 字符串最小转义（仅 " \ 与 C0 控制字符）；
//   §3.2.1 对象/数组无空白。
//
// 不合法输入一律抛 JcsException（调用方转非零退出），**不静默降级**。
using System.Globalization;
using System.Text;
using System.Text.Json;

namespace Nf.Canonical;

/// <summary>规范化输入不合法（含重复键、未配对代理、非有限数）时抛出。</summary>
public sealed class JcsException : Exception
{
    public JcsException(string message) : base(message) { }
}

/// <summary>RFC 8785 规范化 JSON。</summary>
public static class Jcs
{
    private static readonly JsonDocumentOptions ParseOptions = new()
    {
        AllowTrailingCommas = false,
        CommentHandling = JsonCommentHandling.Disallow,
        MaxDepth = 256,
    };

    /// <summary>UTF-8 字节入 → UTF-8 规范化字节出（无尾换行）。</summary>
    public static byte[] Canonicalize(byte[] utf8)
    {
        string text;
        try
        {
            text = new UTF8Encoding(encoderShouldEmitUTF8Identifier: false, throwOnInvalidBytes: true)
                .GetString(utf8);
        }
        catch (DecoderFallbackException)
        {
            throw new JcsException("输入不是合法 UTF-8");
        }

        JsonDocument doc;
        try
        {
            doc = JsonDocument.Parse(text, ParseOptions);
        }
        catch (JsonException exc)
        {
            throw new JcsException("输入不是合法 JSON：" + exc.Message);
        }

        using (doc)
        {
            var sb = new StringBuilder();
            try
            {
                Emit(doc.RootElement, sb);
            }
            catch (JsonException exc)
            {
                // 未配对代理是在**取值**时才被 System.Text.Json 拒绝的（解析期放过原始文本）。
                throw new JcsException("输入不是合法 JSON：" + exc.Message);
            }
            catch (InvalidOperationException exc)
            {
                throw new JcsException("字符串含未配对代理（I-JSON 不许）：" + exc.Message);
            }
            return new UTF8Encoding(false).GetBytes(sb.ToString());
        }
    }

    private static void Emit(JsonElement el, StringBuilder sb)
    {
        switch (el.ValueKind)
        {
            case JsonValueKind.Null:
                sb.Append("null");
                return;
            case JsonValueKind.True:
                sb.Append("true");
                return;
            case JsonValueKind.False:
                sb.Append("false");
                return;
            case JsonValueKind.Number:
                sb.Append(EcmaNumber(el.GetRawText()));
                return;
            case JsonValueKind.String:
                EmitString(el.GetString() ?? string.Empty, sb);
                return;
            case JsonValueKind.Array:
            {
                sb.Append('[');
                bool first = true;
                foreach (JsonElement item in el.EnumerateArray())
                {
                    if (!first) { sb.Append(','); }
                    first = false;
                    Emit(item, sb);
                }
                sb.Append(']');
                return;
            }
            case JsonValueKind.Object:
            {
                var members = new List<KeyValuePair<string, JsonElement>>();
                var seen = new HashSet<string>(StringComparer.Ordinal);
                foreach (JsonProperty prop in el.EnumerateObject())
                {
                    if (!seen.Add(prop.Name))
                    {
                        throw new JcsException("重复键（I-JSON 不许）：" + prop.Name);
                    }
                    members.Add(new KeyValuePair<string, JsonElement>(prop.Name, prop.Value));
                }
                // JCS §3.2.3：UTF-16 码元序；Ordinal 正是逐码元比较。
                members.Sort(static (a, b) => string.CompareOrdinal(a.Key, b.Key));
                sb.Append('{');
                for (int i = 0; i < members.Count; i++)
                {
                    if (i > 0) { sb.Append(','); }
                    EmitString(members[i].Key, sb);
                    sb.Append(':');
                    Emit(members[i].Value, sb);
                }
                sb.Append('}');
                return;
            }
            default:
                throw new JcsException("未知 JSON 值类型：" + el.ValueKind);
        }
    }

    /// <summary>最小转义（JCS §3.2.2.2）；未配对代理在此 fail-closed。</summary>
    private static void EmitString(string s, StringBuilder sb)
    {
        sb.Append('"');
        for (int i = 0; i < s.Length; i++)
        {
            char c = s[i];
            switch (c)
            {
                case '"': sb.Append("\\\""); continue;
                case '\\': sb.Append("\\\\"); continue;
                case '\b': sb.Append("\\b"); continue;
                case '\f': sb.Append("\\f"); continue;
                case '\n': sb.Append("\\n"); continue;
                case '\r': sb.Append("\\r"); continue;
                case '\t': sb.Append("\\t"); continue;
            }
            if (c < (char)0x20)
            {
                sb.Append("\\u").Append(((int)c).ToString("x4", CultureInfo.InvariantCulture));
                continue;
            }
            if (char.IsSurrogate(c))
            {
                if (!char.IsHighSurrogate(c) || i + 1 >= s.Length || !char.IsLowSurrogate(s[i + 1]))
                {
                    throw new JcsException("未配对的 UTF-16 代理（I-JSON 不许）");
                }
                sb.Append(c).Append(s[i + 1]);
                i++;
                continue;
            }
            sb.Append(c);
        }
        sb.Append('"');
    }

    /// <summary>ES Number::toString(x)（RFC 8785 §3.2.2.3）。</summary>
    internal static string EcmaNumber(string raw)
    {
        if (!double.TryParse(raw, NumberStyles.Float, CultureInfo.InvariantCulture, out double v))
        {
            throw new JcsException("数字不可解析为 binary64：" + raw);
        }
        return EcmaNumber(v);
    }

    internal static string EcmaNumber(double v)
    {
        if (double.IsNaN(v) || double.IsInfinity(v))
        {
            throw new JcsException("数字非有限（I-JSON 不许）");
        }
        if (v == 0.0)
        {
            return "0";   // 覆盖 -0.0：IEEE 下 -0.0 == 0.0
        }
        bool neg = v < 0;
        // .NET Core 3.0+ 的 R 即最短往返（Ryu）；与 ES 的 s/k/n 选择规则同源。
        string repr = Math.Abs(v).ToString("R", CultureInfo.InvariantCulture);
        string mantissa = repr;
        int exp = 0;
        int e = repr.IndexOfAny(new[] { 'E', 'e' });
        if (e >= 0)
        {
            mantissa = repr[..e];
            exp = int.Parse(repr[(e + 1)..], CultureInfo.InvariantCulture);
        }
        int dot = mantissa.IndexOf('.');
        int intLen = dot >= 0 ? dot : mantissa.Length;
        // mantissa = d.ddd ⇒ 值 = 0.digits × 10^n，n = 指数 + 1
        int n = exp + intLen;
        string digits = dot >= 0 ? mantissa.Remove(dot, 1) : mantissa;
        int k = digits.Length;

        var sb = new StringBuilder();
        if (neg) { sb.Append('-'); }
        if (k <= n && n <= 21)
        {
            sb.Append(digits);
            sb.Append('0', n - k);
        }
        else if (0 < n && n <= 21)
        {
            sb.Append(digits, 0, n).Append('.').Append(digits, n, k - n);
        }
        else if (-6 < n && n <= 0)
        {
            sb.Append("0.").Append('0', -n).Append(digits);
        }
        else
        {
            sb.Append(digits[0]);
            if (k > 1) { sb.Append('.').Append(digits, 1, k - 1); }
            int m = n - 1;
            sb.Append('e').Append(m >= 0 ? '+' : '-').Append(Math.Abs(m));
        }
        return sb.ToString();
    }
}
