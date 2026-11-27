using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;

namespace Nf.Engine;

/// <summary>供应链表单形状：in-toto / SPDX / SLSA / CycloneDX / VC / C2PA / CID。</summary>
public static partial class Interop
{
    private static readonly HashSet<string> TypeMap = new(StringComparer.Ordinal)
    {
        "string", "integer", "number", "boolean", "object", "array",
    };

    private static string PyText(object? v) => v switch
    {
        null => "None",
        string s => s,
        bool b => b ? "True" : "False",
        long l => l.ToString(CultureInfo.InvariantCulture),
        int i => i.ToString(CultureInfo.InvariantCulture),
        _ => PyScalar.PyRepr(v),
    };

    private static bool PyTruthy(object? v) => v switch
    {
        null => false,
        bool b => b,
        string s => s.Length > 0,
        long l => l != 0,
        double d => d != 0,
        List<object?> list => list.Count > 0,
        Dictionary<string, object?> map => map.Count > 0,
        _ => true,
    };

    /// <summary>协议层回执 → in-toto Statement v1。</summary>
    public static Dictionary<string, object?> Intoto(string root)
    {
        var rec = ReadJson(root, ReceiptsRel);
        var entries = Entries(rec);
        var subject = entries.Select(e => (object?)new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["name"] = Str(e, "path"),
            ["digest"] = new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["sha256"] = Str(e, "digest"),
            },
        }).ToList();
        return new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["_type"] = "https://in-toto.io/Statement/v1",
            ["subject"] = subject,
            ["predicateType"] = "https://ninfenz.dev/attestation/protocol-receipts/v1",
            ["predicate"] = new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["algorithm"] = rec.GetValueOrDefault("algorithm") ?? "",
                ["root"] = rec.GetValueOrDefault("root") ?? "",
                ["count"] = rec.GetValueOrDefault("count") ?? (long)subject.Count,
                ["scope"] = rec.GetValueOrDefault("scope") ?? "",
                ["note"] = "派生自 protocol/RECEIPTS.json；inclusion proof 留在原回执单根内。",
            },
        };
    }

    /// <summary>依赖登记面 → SPDX 2.3 风格 SBOM。</summary>
    public static Dictionary<string, object?> Sbom(string root)
    {
        var nfVersion = "0.0.0";
        var verifyPath = Path.Combine(root, "verify.sh");
        if (File.Exists(verifyPath))
        {
            var m = VerifyVersionRe.Match(StrictUtf8.GetString(File.ReadAllBytes(verifyPath)));
            if (m.Success) nfVersion = m.Groups[1].Value;
        }
        var (hard, soft) = PurityTables.Entries;
        var pinned = PinnedVersions(root);

        var packages = new List<object?>
        {
            new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["SPDXID"] = "SPDXRef-Package-ninfenz",
                ["name"] = "NinFenz",
                ["versionInfo"] = nfVersion,
                ["downloadLocation"] = "NOASSERTION",
                ["licenseConcluded"] = LicenseName,
                ["licenseDeclared"] = LicenseName,
                ["copyrightText"] = "NOASSERTION",
            },
        };
        var deps = new List<(string Pkg, string Rel)>();
        foreach (var (name, why) in hard.OrderBy(kv => kv.Key, StringComparer.Ordinal))
        {
            var pkg = $"SPDXRef-Dependency-{name}";
            var package = new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["SPDXID"] = pkg,
                ["name"] = name,
                ["downloadLocation"] = "NOASSERTION",
                ["licenseConcluded"] = "NOASSERTION",
                ["comment"] = $"硬依赖（登记）：{why}",
            };
            AddPinnedMetadata(package, name, pinned, spdx: true);
            packages.Add(package);
            deps.Add((pkg, "DEPENDENCY_OF"));
        }
        foreach (var (name, why) in soft.OrderBy(kv => kv.Key, StringComparer.Ordinal))
        {
            var pkg = $"SPDXRef-Optional-{name}";
            var package = new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["SPDXID"] = pkg,
                ["name"] = name,
                ["downloadLocation"] = "NOASSERTION",
                ["licenseConcluded"] = "NOASSERTION",
                ["comment"] = $"软依赖（可选，须 try/except 守卫）：{why}",
            };
            AddPinnedMetadata(package, name, pinned, spdx: true);
            packages.Add(package);
            deps.Add((pkg, "OPTIONAL_DEPENDENCY_OF"));
        }

        var maxDate = DeclaredMaxDate(root);
        var relationships = new List<object?>
        {
            new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["spdxElementId"] = "SPDXRef-DOCUMENT",
                ["relatedSpdxElement"] = "SPDXRef-Package-ninfenz",
                ["relationshipType"] = "DESCRIBES",
            },
        };
        relationships.AddRange(deps.Select(d => (object?)new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["spdxElementId"] = d.Pkg,
            ["relatedSpdxElement"] = "SPDXRef-Package-ninfenz",
            ["relationshipType"] = d.Rel,
        }));

        return new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["spdxVersion"] = "SPDX-2.3",
            ["dataLicense"] = "CC0-1.0",
            ["SPDXID"] = "SPDXRef-DOCUMENT",
            ["name"] = "ninfenz-sbom",
            ["documentNamespace"] = $"https://ninfenz.dev/spdx/{nfVersion}",
            ["creationInfo"] = new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["creators"] = new List<object?> { "Tool: nf interop --kind sbom" },
                ["created"] = maxDate.Length > 0 ? $"{maxDate}T00:00:00Z" : "",
                ["comment"] = "由纯度扫描登记面（HARD_ALLOW / SOFT_IMPORTS）实时派生；" +
                              "created = 仓内声明日期最大值（非墙钟，保确定性）",
            },
            ["comment"] = "派生面非真源；created = max(仓内声明日期: " +
                          "score_baseline / provenance / approvals)（保确定性，非墙钟）。",
            ["packages"] = packages,
            ["relationships"] = relationships,
        };
    }

    /// <summary>SLSA Provenance v1（从本地门禁事实派生，不宣称外部构建）。</summary>
    public static Dictionary<string, object?> Slsa(string root)
    {
        var rec = ReadJson(root, ReceiptsRel);
        var (wantChecks, wantPass) = Baseline(root);
        var version = "";
        var verifyPath = Path.Combine(root, "verify.sh");
        if (File.Exists(verifyPath))
        {
            var m = VerifyVersionRe.Match(StrictUtf8.GetString(File.ReadAllBytes(verifyPath)));
            version = m.Success ? m.Groups[1].Value : "";
        }
        var subjects = Entries(rec).Select(e => (object?)new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["name"] = Str(e, "path"),
            ["digest"] = new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["sha256"] = Str(e, "digest"),
            },
        }).ToList();
        var names = Entries(rec).Select(e => Str(e, "path")).ToList();
        return new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["_type"] = "https://in-toto.io/Statement/v1",
            ["subject"] = subjects,
            ["predicateType"] = "https://slsa.dev/provenance/v1",
            ["predicate"] = new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["buildDefinition"] = new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["buildType"] = "https://ninfenz.dev/buildtypes/local-gate/v1",
                    ["externalParameters"] = new Dictionary<string, object?>(StringComparer.Ordinal)
                    {
                        ["gate"] = "verify.sh",
                        ["gateVersion"] = version,
                        ["declaredBaseline"] = $"check1-{wantChecks} PASS={wantPass}",
                        ["note"] = "参数取自仓内声明件（不引入新真源）",
                    },
                    ["internalParameters"] = new Dictionary<string, object?>(StringComparer.Ordinal)
                    {
                        ["repoRoot"] = "relative",
                    },
                    ["resolvedDependencies"] = names.Select(n => (object?)new Dictionary<string, object?>(StringComparer.Ordinal)
                    {
                        ["uri"] = $"nf://repo/{n}",
                    }).ToList(),
                },
                ["runDetails"] = new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["builder"] = new Dictionary<string, object?>(StringComparer.Ordinal)
                    {
                        ["id"] = "https://ninfenz.dev/builder/verify-sh",
                    },
                    ["metadata"] = new Dictionary<string, object?>(StringComparer.Ordinal)
                    {
                        ["invocationId"] = Short(Str(rec, "root"), 16),
                        ["note"] = "本地门禁执行事实；**不构成 SLSA 等级声明**（无远程 builder）",
                    },
                },
            },
        };
    }

    /// <summary>CycloneDX 1.5（与 SPDX 面同源不同形；serialNumber 由内容寻址派生）。</summary>
    public static Dictionary<string, object?> Cyclonedx(string root)
    {
        var sbom = Sbom(root);
        var (hard, soft) = PurityTables.Entries;
        var pinned = PinnedVersions(root);
        var ns = sbom.GetValueOrDefault("documentNamespace") as string ?? "";
        var seed = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(ns))).ToLowerInvariant();
        var serial = $"urn:uuid:{seed[..8]}-{seed[8..12]}-{seed[12..16]}-{seed[16..20]}-{seed[20..32]}";

        var components = new List<object?>();
        foreach (var (name, why) in hard.OrderBy(kv => kv.Key, StringComparer.Ordinal))
        {
            var component = new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["type"] = "library", ["bom-ref"] = $"dep:{name}", ["name"] = name,
                ["scope"] = "required", ["description"] = $"硬依赖（登记）：{why}",
            };
            AddPinnedMetadata(component, name, pinned, spdx: false);
            components.Add(component);
        }
        foreach (var (name, why) in soft.OrderBy(kv => kv.Key, StringComparer.Ordinal))
        {
            var component = new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["type"] = "library", ["bom-ref"] = $"opt:{name}", ["name"] = name,
                ["scope"] = "optional", ["description"] = $"软依赖（可选，须守卫）：{why}",
            };
            AddPinnedMetadata(component, name, pinned, spdx: false);
            components.Add(component);
        }

        var packages = (sbom.GetValueOrDefault("packages") as List<object?>) ?? new List<object?>();
        var firstPkg = packages.Count > 0 ? packages[0] as Dictionary<string, object?> : null;
        var versionInfo = firstPkg is null ? "0.0.0" : (firstPkg.GetValueOrDefault("versionInfo") as string ?? "0.0.0");
        var creationInfo = (sbom.GetValueOrDefault("creationInfo") as Dictionary<string, object?>) ?? new(StringComparer.Ordinal);

        return new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["bomFormat"] = "CycloneDX",
            ["specVersion"] = "1.5",
            ["serialNumber"] = serial,
            ["version"] = 1L,
            ["metadata"] = new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["timestamp"] = creationInfo.GetValueOrDefault("created") ?? "",
                ["component"] = new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["type"] = "application",
                    ["bom-ref"] = $"pkg:nf/ninfenz@{versionInfo}",
                    ["name"] = "NinFenz",
                    ["licenses"] = new List<object?>
                    {
                        new Dictionary<string, object?>(StringComparer.Ordinal)
                        {
                            ["license"] = new Dictionary<string, object?>(StringComparer.Ordinal) { ["id"] = LicenseName },
                        },
                    },
                },
                ["tools"] = new List<object?>
                {
                    new Dictionary<string, object?>(StringComparer.Ordinal)
                    {
                        ["vendor"] = "NinFenz", ["name"] = "nf interop --kind cyclonedx", ["version"] = "1.0.0",
                    },
                },
                ["properties"] = new List<object?>
                {
                    new Dictionary<string, object?>(StringComparer.Ordinal)
                    {
                        ["name"] = "nf:source", ["value"] = "purity_scan 依赖登记面（纯派生）",
                    },
                    new Dictionary<string, object?>(StringComparer.Ordinal)
                    {
                        ["name"] = "nf:note", ["value"] = "与 SPDX 面同源；timestamp 取仓内声明日期最大值（非墙钟）。",
                    },
                },
            },
            ["components"] = components,
        };
    }

    /// <summary>W3C VC 2.0 形状（未签名——状态写进注记，不宣称可验证）。</summary>
    public static Dictionary<string, object?> Vc(string root)
    {
        var rec = ReadJson(root, ReceiptsRel);
        var rep = ReadJson(root, "protocol/conformance_report.json");
        var approvals = new List<Dictionary<string, object?>>();
        var adir = Path.Combine(root, "protocol", "approvals");
        if (Directory.Exists(adir))
        {
            foreach (var name in Directory.GetFiles(adir, "*.json").Select(f => Path.GetFileName(f) ?? "")
                         .OrderBy(n => n, StringComparer.Ordinal))
            {
                var a = ReadJson(root, $"protocol/approvals/{name}");
                if (a.Count > 0) approvals.Add(a);
            }
        }
        var first = approvals.Count > 0 ? approvals[0] : null;
        var issuer = first is null ? "" : (first.GetValueOrDefault("approved_by") as string ?? "");
        if (issuer.Length == 0) issuer = "NinFenz";
        var validFrom = first is null ? "" : (first.GetValueOrDefault("approved_at") as string ?? "");

        return new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["@context"] = new List<object?>
            {
                "https://www.w3.org/ns/credentials/v2",
                "https://ninfenz.dev/ns/credentials/v1",
            },
            ["type"] = new List<object?> { "VerifiableCredential", "NfConformanceCredential" },
            ["issuer"] = issuer,
            ["validFrom"] = validFrom,
            ["credentialSubject"] = new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["id"] = "nf:conformance_report",
                ["verdict"] = rep.GetValueOrDefault("verdict") as string ?? "",
                ["contracts"] = (long)((rep.GetValueOrDefault("contracts") as List<object?>)?.Count ?? 0),
                ["receiptRoot"] = rec.GetValueOrDefault("root") as string ?? "",
                ["receiptCount"] = ToLong(rec.GetValueOrDefault("count")),
            },
            ["x-nf-proof-status"] = "unsigned（本仓签名走 ssh 外挂锚 nf attest；未接 JWS/Data Integrity " +
                                    "签名套件——形状可读，不可验证，勿当凭证使用）",
            ["x-nf-note"] = "派生自 protocol/conformance_report.json + protocol/RECEIPTS.json + " +
                            "protocol/approvals/*（纯派生，不新增真源）",
        };
    }

    /// <summary>C2PA JSON 清单形状（未封装/未签名；哈希硬绑定用回执摘要口径）。</summary>
    public static Dictionary<string, object?> C2pa(string root)
    {
        var rec = ReadJson(root, ReceiptsRel);
        var sample = Entries(rec).FirstOrDefault(e => Str(e, "path").Length > 0);
        var assertions = new List<object?>
        {
            new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["label"] = "c2pa.actions",
                ["data"] = new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["actions"] = new List<object?>
                    {
                        new Dictionary<string, object?>(StringComparer.Ordinal)
                        {
                            ["action"] = "c2pa.created",
                            ["digitalSourceType"] = "http://cv.iptc.org/newscodes/digitalsourcetype/digitalCapture",
                        },
                    },
                },
            },
        };
        if (sample is not null)
        {
            assertions.Add(new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["label"] = "c2pa.hash.data",
                ["data"] = new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["alg"] = "sha256",
                    ["hash"] = Str(sample, "digest"),
                    ["name"] = Str(sample, "path"),
                },
            });
        }
        return new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["claim_generator"] = "NinFenz/1.0 (nf interop --kind c2pa)",
            ["claim_generator_info"] = new List<object?>
            {
                new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["name"] = "NinFenz", ["version"] = "1.0.0",
                },
            },
            ["title"] = "NinFenz 协议层内容清单",
            ["format"] = "application/json",
            ["assertions"] = assertions,
            ["x-nf-package-status"] = "未封装（无 JUMBF/CBOR 容器）、未签名（无 X.509 证书链）——" +
                                      "只出 JSON 清单形状，不得当作可验证内容凭证",
            ["x-nf-source"] = "protocol/RECEIPTS.json（回执摘要）",
        };
    }

    /// <summary>回执 → CIDv1（multibase base32 / raw codec / sha2-256）。</summary>
    public static Dictionary<string, object?> Cid(string root)
    {
        var rec = ReadJson(root, ReceiptsRel);
        var entries = new List<object?>();
        foreach (var e in Entries(rec))
        {
            var d = Str(e, "digest");
            entries.Add(new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["path"] = Str(e, "path"),
                ["sha256"] = d,
                ["cid"] = Sha256Re.IsMatch(d) ? Cidv1RawSha256(d) : "",
            });
        }
        return new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["schema"] = "nf-cid-index/1",
            ["multibase"] = "base32 (lowercase, no padding, prefix 'b')",
            ["codec"] = "raw (0x71)",
            ["multihash"] = "sha2-256 (0x12)",
            ["entries"] = entries,
            ["x-nf-note"] = "派生自 protocol/RECEIPTS.json；CID 可被 multiformats 生态直接校验。",
        };
    }

    /// <summary>CIDv1 raw codec + sha2-256（base32 小写去填充，前缀 'b'）。</summary>
    public static string Cidv1RawSha256(string digestHex)
    {
        var raw = Convert.FromHexString(digestHex);
        var payload = new byte[4 + raw.Length];
        payload[0] = 0x01;   // CID 版本 1
        payload[1] = 0x71;   // raw codec
        payload[2] = 0x12;   // sha2-256
        payload[3] = 0x20;   // 32 字节
        raw.CopyTo(payload, 4);
        return "b" + Base32Lower(payload);
    }

    /// <summary>RFC 4648 base32（无填充、小写）——Python <c>base64.b32encode(...).lower().rstrip("=")</c> 等价。</summary>
    private static string Base32Lower(byte[] data)
    {
        const string alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
        var sb = new StringBuilder();
        int bits = 0, value = 0;
        foreach (var b in data)
        {
            value = (value << 8) | b;
            bits += 8;
            while (bits >= 5)
            {
                sb.Append(alphabet[(value >> (bits - 5)) & 31]);
                bits -= 5;
            }
        }
        if (bits > 0) sb.Append(alphabet[(value << (5 - bits)) & 31]);
        return sb.ToString().ToLowerInvariant();
    }
}
