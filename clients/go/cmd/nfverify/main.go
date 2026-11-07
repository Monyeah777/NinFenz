// nfverify：CCOS 七调用的 Go 侧命令行（ABI 的第二实现）。
//
// 用法：
//
//	nfverify verify  --bundle 证据.zip [--key-file K] [--revocations R] [--anchor A] [--at T]
//	nfverify check   --object 文件 --policy 策略.json
//	nfverify label   --ir IR.json
//	nfverify attest  --subject 文件 [--key-file K] [--producer P] [--issued-at T]
//	nfverify replay  --bundle 证据.zip
//	nfverify diff    --a a.json --b b.json
//	nfverify resolve --root 仓库 --object 相对路径 [--decl 声明件]
//
// 退出码与仓内同口径：0 ok · 1 invalid · 2 revoked · 3 expired · 4 用法错。
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"

	"github.com/ninfenz/nfverify/nfverify"
)

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "用法：nfverify {verify|check|label|attest|replay|diff|resolve} ...")
		os.Exit(4)
	}
	sub := os.Args[1]
	args := os.Args[2:]
	switch sub {
	case "verify":
		os.Exit(cmdVerify(args))
	case "check":
		os.Exit(cmdCheck(args))
	case "label":
		os.Exit(cmdLabel(args))
	case "attest":
		os.Exit(cmdAttest(args))
	case "replay":
		os.Exit(cmdReplay(args))
	case "diff":
		os.Exit(cmdDiff(args))
	case "resolve":
		os.Exit(cmdResolve(args))
	default:
		fmt.Fprintf(os.Stderr, "未知子命令：%s（修复指引：可用 verify/check/label/attest/replay/diff/resolve）\n", sub)
		os.Exit(4)
	}
}

func emit(asJSON bool, v any, human func()) {
	if asJSON {
		body, _ := json.MarshalIndent(v, "", "  ")
		fmt.Println(string(body))
		return
	}
	human()
}

func cmdVerify(args []string) int {
	fs := flag.NewFlagSet("verify", flag.ContinueOnError)
	bundle := fs.String("bundle", "", "证据容器（zip；三形态由 schema 判）")
	keyFile := fs.String("key-file", "", "hmac 校验密钥文件")
	revFile := fs.String("revocations", "", "外部吊销表 JSON")
	anchorFile := fs.String("anchor", "", "外部锚点 JSON")
	at := fs.String("at", "", "判定时点（UTC 秒级）")
	policy := fs.String("policy-digest", "", "期望策略摘要（64 hex）")
	asJSON := fs.Bool("json", false, "输出 JSON")
	if err := fs.Parse(args); err != nil {
		return 4
	}
	if *bundle == "" {
		fmt.Fprintln(os.Stderr, "用法：nfverify verify --bundle <证据容器.zip>")
		return 4
	}
	data, err := os.ReadFile(*bundle)
	if err != nil {
		fmt.Fprintf(os.Stderr, "读不到证据容器：%v\n", err)
		return 4
	}
	opts := nfverify.Options{At: *at, PolicyDigest: *policy}
	if *keyFile != "" {
		key, errKey := os.ReadFile(*keyFile)
		if errKey != nil {
			fmt.Fprintf(os.Stderr, "读不到密钥：%v\n", errKey)
			return 4
		}
		opts.Key = trimSpace(key)
	}
	if *revFile != "" {
		opts.Revocations = loadObject(*revFile)
	}
	if *anchorFile != "" {
		opts.Anchor = loadObject(*anchorFile)
	}
	res, err := nfverify.VerifyAny(data, opts)
	if err != nil {
		fmt.Fprintf(os.Stderr, "✗ %v（修复指引：确认输入是证据容器 zip）\n", err)
		return 4
	}
	emit(*asJSON, res.Map(), func() {
		fmt.Printf("判定：%s · 强度：%s · 成员 %d 件\n", res.Verdict, res.Level, res.Count)
		for _, issue := range res.Issues {
			fmt.Fprintf(os.Stderr, "  [FAIL] %s\n", issue)
		}
	})
	return nfverify.ExitCode(res.Verdict)
}

func cmdCheck(args []string) int {
	fs := flag.NewFlagSet("check", flag.ContinueOnError)
	obj := fs.String("object", "", "体检对象（单个文件）")
	policyPath := fs.String("policy", "", "nf-check-policy/1 策略 JSON")
	asJSON := fs.Bool("json", false, "输出 JSON")
	if err := fs.Parse(args); err != nil {
		return 4
	}
	if *obj == "" || *policyPath == "" {
		fmt.Fprintln(os.Stderr, "用法：nfverify check --object <文件> --policy <策略.json>")
		return 4
	}
	policy, err := loadJSONObject(*policyPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "策略不可读：%v\n", err)
		return 4
	}
	res, err := nfverify.Check(*obj, policy)
	if err != nil {
		fmt.Fprintf(os.Stderr, "✗ %v\n", err)
		return 4
	}
	emit(*asJSON, res.Map(), func() {
		fmt.Printf("判定：%s · 规则 %d · 失败 %d · warn %d\n", res.Verdict,
			len(res.Findings), res.Failed, res.Warned)
		for _, f := range res.Findings {
			if !f.OK {
				fmt.Fprintf(os.Stderr, "  [%s] %s：%s\n", f.Severity, f.Rule, f.Detail)
			}
		}
	})
	if res.Verdict == "ok" {
		return 0
	}
	return 1
}

func cmdLabel(args []string) int {
	fs := flag.NewFlagSet("label", flag.ContinueOnError)
	irPath := fs.String("ir", "", "nf-label/1 IR JSON")
	asJSON := fs.Bool("json", false, "输出 JSON")
	if err := fs.Parse(args); err != nil {
		return 4
	}
	if *irPath == "" {
		fmt.Fprintln(os.Stderr, "用法：nfverify label --ir <IR.json>")
		return 4
	}
	doc, err := loadJSONObject(*irPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "IR 不可读：%v\n", err)
		return 4
	}
	res := nfverify.ValidateLabel(doc)
	emit(*asJSON, res.Map(), func() {
		fmt.Printf("判定：%s · 档位 %s · 已满足 %d · 缺 %d\n", res.Verdict, res.Level,
			len(res.Applied), len(res.Missing))
		for _, issue := range res.Issues {
			fmt.Fprintf(os.Stderr, "  [FAIL] %s\n", issue)
		}
	})
	if res.OK {
		return 0
	}
	return 1
}

func cmdAttest(args []string) int {
	fs := flag.NewFlagSet("attest", flag.ContinueOnError)
	subject := fs.String("subject", "", "被证文件")
	keyFile := fs.String("key-file", "", "hmac 密钥文件（不给 = digest_only 级）")
	producer := fs.String("producer", "nfverify-go", "签发方标识")
	issuedAt := fs.String("issued-at", "", "签发时刻（UTC 秒级；缺省用固定占位）")
	asJSON := fs.Bool("json", false, "输出 JSON")
	if err := fs.Parse(args); err != nil {
		return 4
	}
	if *subject == "" {
		fmt.Fprintln(os.Stderr, "用法：nfverify attest --subject <文件> [--key-file K]")
		return 4
	}
	data, err := os.ReadFile(*subject)
	if err != nil {
		fmt.Fprintf(os.Stderr, "读不到被证文件：%v\n", err)
		return 4
	}
	var key []byte
	if *keyFile != "" {
		key, err = os.ReadFile(*keyFile)
		if err != nil {
			fmt.Fprintf(os.Stderr, "读不到密钥：%v\n", err)
			return 4
		}
		key = trimSpace(key)
	}
	stamp := *issuedAt
	if stamp == "" {
		stamp = "2026-01-01T00:00:00Z"
	}
	env, err := nfverify.Attest(*subject, data, key, *producer, stamp)
	if err != nil {
		fmt.Fprintf(os.Stderr, "✗ %v\n", err)
		return 4
	}
	emit(*asJSON, env, func() {
		fmt.Printf("信封已生成：%v · 主体 %s\n", env["envelope_digest"], *subject)
	})
	return 0
}

func cmdReplay(args []string) int {
	fs := flag.NewFlagSet("replay", flag.ContinueOnError)
	bundle := fs.String("bundle", "", "证据容器")
	asJSON := fs.Bool("json", false, "输出 JSON")
	if err := fs.Parse(args); err != nil {
		return 4
	}
	if *bundle == "" {
		fmt.Fprintln(os.Stderr, "用法：nfverify replay --bundle <证据容器.zip>")
		return 4
	}
	data, err := os.ReadFile(*bundle)
	if err != nil {
		fmt.Fprintf(os.Stderr, "读不到证据容器：%v\n", err)
		return 4
	}
	res, err := nfverify.Replay(data, nfverify.Options{})
	if err != nil {
		fmt.Fprintf(os.Stderr, "✗ %v\n", err)
		return 4
	}
	emit(*asJSON, res.Map(), func() {
		fmt.Printf("轨迹：%d 成员 · ok=%v · 根 %s\n", len(res.Entries), res.OK,
			res.RecomputedRoot[:16])
		for _, issue := range res.Issues {
			fmt.Fprintf(os.Stderr, "  [FAIL] %s\n", issue)
		}
	})
	if res.OK {
		return 0
	}
	return 1
}

func cmdDiff(args []string) int {
	fs := flag.NewFlagSet("diff", flag.ContinueOnError)
	a := fs.String("a", "", "文档 A（JSON）")
	b := fs.String("b", "", "文档 B（JSON）")
	asJSON := fs.Bool("json", false, "输出 JSON")
	if err := fs.Parse(args); err != nil {
		return 4
	}
	if *a == "" || *b == "" {
		fmt.Fprintln(os.Stderr, "用法：nfverify diff --a <a.json> --b <b.json>")
		return 4
	}
	rawA, err := os.ReadFile(*a)
	if err != nil {
		fmt.Fprintf(os.Stderr, "读不到 A：%v\n", err)
		return 4
	}
	rawB, err := os.ReadFile(*b)
	if err != nil {
		fmt.Fprintf(os.Stderr, "读不到 B：%v\n", err)
		return 4
	}
	res, err := nfverify.DiffJSON(rawA, rawB)
	if err != nil {
		fmt.Fprintf(os.Stderr, "✗ 两份文档必须都是合法 JSON\n")
		return 4
	}
	emit(*asJSON, res.Map(), func() {
		fmt.Printf("影响：%s · 判定：%s · 差异 %d 条\n", res.Impact, res.Verdict,
			len(res.Changes))
		for _, c := range res.Changes {
			fmt.Printf("  %-6s %s\n", c.Kind, c.Pointer)
		}
	})
	return 0
}

func cmdResolve(args []string) int {
	fs := flag.NewFlagSet("resolve", flag.ContinueOnError)
	root := fs.String("root", ".", "仓库根")
	obj := fs.String("object", "", "对象（仓库相对路径）")
	decl := fs.String("decl", "", "契约声明件（缺省 = <root>/protocol/asset_contracts.json）")
	asJSON := fs.Bool("json", false, "输出 JSON")
	if err := fs.Parse(args); err != nil {
		return 4
	}
	if *obj == "" {
		fmt.Fprintln(os.Stderr, "用法：nfverify resolve --root <仓库> --object <相对路径>")
		return 4
	}
	var res *nfverify.ResolveResult
	var err error
	if *decl != "" {
		res, err = nfverify.ResolveWithDecl(*root, *decl, *obj)
	} else {
		res, err = nfverify.Resolve(*root, *obj)
	}
	if err != nil {
		fmt.Fprintf(os.Stderr, "✗ %v\n", err)
		return 4
	}
	emit(*asJSON, res.Map(), func() {
		fmt.Printf("对象 %s：认领契约 %d 份（closure_closed=%v）\n", res.Object,
			len(res.Contracts), res.ClosureClosed)
		for _, c := range res.Contracts {
			fmt.Printf("  %s/%s（覆盖 %d 件）\n", c.Face, c.ID, c.Files)
		}
		if res.Unclaimed {
			fmt.Println("  未被任何契约认领——注意：这不是「查过没问题」，而是声明面没覆盖它")
		}
	})
	if res.ClosureClosed {
		return 0
	}
	return 1
}

func loadJSONObject(path string) (map[string]any, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var doc map[string]any
	if err := json.Unmarshal(raw, &doc); err != nil {
		return nil, err
	}
	return doc, nil
}

func loadObject(path string) map[string]any {
	doc, err := loadJSONObject(path)
	if err != nil {
		fmt.Fprintf(os.Stderr, "读不到 JSON：%v\n", err)
		os.Exit(4)
	}
	return doc
}

func trimSpace(raw []byte) []byte {
	start, end := 0, len(raw)
	for start < end && (raw[start] == ' ' || raw[start] == '\n' || raw[start] == '\r' || raw[start] == '\t') {
		start++
	}
	for end > start && (raw[end-1] == ' ' || raw[end-1] == '\n' || raw[end-1] == '\r' || raw[end-1] == '\t') {
		end--
	}
	return raw[start:end]
}
