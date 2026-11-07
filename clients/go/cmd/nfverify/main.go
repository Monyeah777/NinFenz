// nfverify：CCOS 证据包的 Go 侧复验命令行（ABI 的 cc_verify 最小实现）。
//
// 用法：
//   nfverify --bundle 证据包.zip [--key-file K] [--revocations R.json]
//            [--anchor A.json] [--at 2030-01-01T00:00:00Z] [--json]
//
// 退出码与仓内 CLI 同口径：0 ok · 1 invalid · 2 revoked · 3 expired · 4 用法错。
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"

	"github.com/ninfenz/nfverify/nfverify"
)

func main() {
	bundle := flag.String("bundle", "", "证据包 .zip（自包含）")
	keyFile := flag.String("key-file", "", "校验 hmac 级信封所需的密钥文件")
	revFile := flag.String("revocations", "", "外部吊销表 JSON（nf-revocation/1）")
	anchorFile := flag.String("anchor", "", "外部锚点 JSON（{count, head}）")
	at := flag.String("at", "", "判定时点（UTC 秒级；缺省 = 视为未到期）")
	policy := flag.String("policy-digest", "", "期望策略摘要（64 hex）")
	asJSON := flag.Bool("json", false, "输出结构化 JSON")
	flag.Parse()

	if *bundle == "" {
		fmt.Fprintln(os.Stderr, "用法：nfverify --bundle <证据包.zip> [--key-file ...]")
		os.Exit(4)
	}
	data, err := os.ReadFile(*bundle)
	if err != nil {
		fmt.Fprintf(os.Stderr, "读不到证据包：%v\n", err)
		os.Exit(4)
	}
	opts := nfverify.Options{At: *at, PolicyDigest: *policy}
	if *keyFile != "" {
		key, err := os.ReadFile(*keyFile)
		if err != nil {
			fmt.Fprintf(os.Stderr, "读不到密钥：%v\n", err)
			os.Exit(4)
		}
		opts.Key = trimSpace(key)
	}
	if *revFile != "" {
		opts.Revocations = loadObject(*revFile)
	}
	if *anchorFile != "" {
		opts.Anchor = loadObject(*anchorFile)
	}
	res, err := nfverify.VerifyBundle(data, opts)
	if err != nil {
		fmt.Fprintf(os.Stderr, "✗ %v（修复指引：确认输入是 nf evidence pack 产出的 .zip）\n", err)
		os.Exit(4)
	}
	if *asJSON {
		body, _ := json.MarshalIndent(res.Map(), "", "  ")
		fmt.Println(string(body))
	} else {
		fmt.Printf("判定：%s · 强度：%s · 成员 %d 件\n", res.Verdict, res.Level, res.Count)
		for _, issue := range res.Issues {
			fmt.Fprintf(os.Stderr, "  [FAIL] %s\n", issue)
		}
	}
	os.Exit(nfverify.ExitCode(res.Verdict))
}

func loadObject(path string) map[string]any {
	data, err := os.ReadFile(path)
	if err != nil {
		fmt.Fprintf(os.Stderr, "读不到 JSON：%v\n", err)
		os.Exit(4)
	}
	var doc map[string]any
	if err := json.Unmarshal(data, &doc); err != nil {
		fmt.Fprintf(os.Stderr, "不是合法 JSON 对象：%v\n", err)
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
