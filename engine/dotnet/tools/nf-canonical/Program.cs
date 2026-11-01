// nf-canonical CLI：--file <输入.json> → 标准输出规范化字节（**无尾换行**）。
//
// 退出码（与 Rust 侧 nf-canonical 逐条一致，供对拍器按 rc 判"拒绝"语义）：
//   0 成功；1 输入不是合法 JSON；2 用法/规则不支持/读不到文件。
using System.Text;
using Nf.Canonical;

namespace Nf.Canonical;

internal static class Program
{
    private static int Main(string[] args)
    {
        var utf8 = new UTF8Encoding(false);
        try
        {
            Console.OutputEncoding = utf8;
        }
        catch (IOException)
        {
            // 输出被重定向到管道时个别平台不允许改编码；字节写出不依赖它。
        }

        string? file = null;
        string rule = "jcs";
        bool selfTest = false;
        for (int i = 0; i < args.Length; i++)
        {
            switch (args[i])
            {
                case "--file":
                    file = i + 1 < args.Length ? args[++i] : null;
                    break;
                case "--rule":
                    rule = i + 1 < args.Length ? args[++i] : string.Empty;
                    break;
                case "--self-test":
                    selfTest = true;
                    break;
                default:
                    Console.Error.WriteLine("未知参数：" + args[i] + "（用法：nf-canonical --file <输入.json>）");
                    return 2;
            }
        }
        if (selfTest)
        {
            return SelfTest();
        }
        if (file is null)
        {
            Console.Error.WriteLine("缺 --file（用法：nf-canonical --file <输入.json>）");
            return 2;
        }
        if (rule != "jcs")
        {
            Console.Error.WriteLine("暂不支持的规则：" + rule + "（当前只有 jcs）");
            return 2;
        }

        byte[] raw;
        try
        {
            raw = File.ReadAllBytes(file);
        }
        catch (Exception exc) when (exc is IOException or UnauthorizedAccessException)
        {
            Console.Error.WriteLine("读不到 " + file + "：" + exc.Message);
            return 2;
        }

        byte[] outBytes;
        try
        {
            outBytes = Jcs.Canonicalize(raw);
        }
        catch (JcsException exc)
        {
            Console.Error.WriteLine("输入不是合法 JSON：" + exc.Message);
            return 1;
        }
        using Stream stdout = Console.OpenStandardOutput();
        stdout.Write(outBytes, 0, outBytes.Length);
        stdout.Flush();
        return 0;
    }

    // ---------------------------------------------------------------- self-test
    private static void AssertCanon(string input, string expected)
    {
        byte[] got = Jcs.Canonicalize(new UTF8Encoding(false).GetBytes(input));
        string g = new UTF8Encoding(false).GetString(got);
        if (g != expected)
        {
            throw new InvalidOperationException("规范化不符：输入 " + input + " → 得到 " + g + "，期望 " + expected);
        }
        if (g.EndsWith('\n'))
        {
            throw new InvalidOperationException("输出不得带尾换行：" + input);
        }
    }

    private static void AssertRejected(string input)
    {
        try
        {
            Jcs.Canonicalize(new UTF8Encoding(false).GetBytes(input));
        }
        catch (JcsException)
        {
            return;
        }
        throw new InvalidOperationException("应被拒但通过了：" + input);
    }

    private static int SelfTest()
    {
        var checks = 0;
        void Case(string name, Action body)
        {
            body();
            checks++;
            Console.WriteLine("  ok " + name);
        }

        try
        {
            Case("basic-ascii", () => AssertCanon("{\"c\":\"xy\",\"a\":[2,1.5,true,null],\"b\":1}",
                                                  "{\"a\":[2,1.5,true,null],\"b\":1,\"c\":\"xy\"}"));
            Case("utf16-key-order", () => AssertCanon(
                "{\"\\ud83d\\ude00\":1,\"\\ue000\":2}",
                "{\"" + char.ConvertFromUtf32(0x1F600) + "\":1,\"\uE000\":2}"));
            Case("number-ecmascript", () => AssertCanon(
                "[1,1.5,-0,1e-7,1e21,1e-6,100000000000000000000]",
                "[1,1.5,0,1e-7,1e+21,0.000001,100000000000000000000]"));
            Case("number-fixed-vs-exp", () => AssertCanon("[0.5,1e-6,1e-7,2.5e22]",
                                                          "[0.5,0.000001,1e-7,2.5e+22]"));
            Case("escape-minimal", () => AssertCanon("\"a\\/b\"", "\"a/b\""));
            Case("escape-control", () => AssertCanon("\"\\u0001\"", "\"\\u0001\""));
            Case("cjk-raw", () => AssertCanon("\"中\"", "\"中\""));
            Case("reject-dup-key", () => AssertRejected("{\"a\":1,\"a\":2}"));
            Case("reject-trailing-comma", () => AssertRejected("[1,]"));
            Case("reject-nan", () => AssertRejected("NaN"));
            Case("reject-leading-zero", () => AssertRejected("01"));
            Case("reject-lone-surrogate", () => AssertRejected("\"\\ud800\""));
            Case("reject-trailing-content", () => AssertRejected("{\"a\":1} x"));
            Case("reject-infinity", () => AssertRejected("Infinity"));
            Case("reject-empty", () => AssertRejected(string.Empty));
            Case("reject-object-trailing-comma", () => AssertRejected("{\"a\":1,}"));
        }
        catch (Exception exc)
        {
            Console.Error.WriteLine("self-test 失败（已过 " + checks + " 例）：" + exc.Message);
            return 1;
        }
        Console.WriteLine("self-test OK（" + checks + " 例）");
        return 0;
    }
}
