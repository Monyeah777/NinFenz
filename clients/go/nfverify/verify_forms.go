package nfverify

import (
	"encoding/hex"
	"sort"
	"strings"
)

const (
	ReceiptsSchema  = "nf-receipts/1"
	AttestSetSchema = "nf-attest-set/1"
)

// VerifyAny 是 cc_verify 的三形态统一入口：形态由**文档 schema** 判，不看扩展名。
// 返回的用法级错误（UsageError）对应 CLI 退出码 4：输入根本不是证据容器。
func VerifyAny(data []byte, opts Options) (*Result, error) {
	src, err := openZip(data)
	if err != nil {
		return nil, err
	}
	if raw := src.read(BundleEntry); raw != nil {
		if doc := parseDoc(raw); doc != nil && asString(doc["schema"]) == EvidenceSchema {
			return verifyBundleDoc(src, doc, opts), nil
		}
	}
	for _, name := range src.names {
		if !strings.HasSuffix(name, ".json") {
			continue
		}
		doc := parseDoc(src.read(name))
		if doc == nil {
			continue
		}
		switch asString(doc["schema"]) {
		case ReceiptsSchema:
			return verifyReceipts(src, doc, opts), nil
		case AttestSchema, AttestSetSchema:
			return verifyAttest(src, doc, opts), nil
		}
	}
	return nil, UsageError
}

// verifyReceipts 回执形态：成员摘要 → 叶 → 根 → 每条包含证明 → 吊销/时效。
func verifyReceipts(src *zipSource, doc map[string]any, opts Options) *Result {
	res := newResult()
	res.Kind = "receipts"
	entries := mapList(doc["entries"])
	res.Count = len(entries)
	res.Root = asString(doc["root"])
	res.ExpiresAt = asString(doc["expires_at"])
	if len(entries) == 0 {
		res.Issues = append(res.Issues, "回执为空")
		return res
	}
	_, leaves, ok := verifyMembers(src, entries, res)
	if !ok {
		return res
	}
	if hex.EncodeToString(merkleRoot(leaves)) != res.Root {
		res.Issues = append(res.Issues, "根不一致")
		return res
	}
	for _, e := range entries {
		leaf, err := hex.DecodeString(asString(e["leaf"]))
		if err != nil {
			res.Issues = append(res.Issues, "叶不可解析")
			break
		}
		if hex.EncodeToString(foldLeaf(leaf, asList(e["proof"]))) != res.Root {
			res.Issues = append(res.Issues, "包含证明不折叠到根："+
				norm(firstNonEmpty(asString(e["id"]), asString(e["path"]))))
		}
	}
	if len(res.Issues) > 0 {
		return res
	}
	res.Level = "receipts_only"
	judge(res, entries, opts.Revocations, opts.At)
	return res
}

// verifyAttest 信封形态：每份信封自洽（含 hmac）+ 每个成员被覆盖 → 吊销/时效。
func verifyAttest(src *zipSource, doc map[string]any, opts Options) *Result {
	res := newResult()
	res.Kind = "attest"
	isSet := asString(doc["schema"]) == AttestSetSchema
	envs := []map[string]any{}
	if isSet {
		envs = mapList(doc["attestations"])
	} else {
		envs = []map[string]any{doc}
	}
	res.Count = len(envs)
	if len(envs) == 0 {
		res.Issues = append(res.Issues, "信封集为空")
		return res
	}
	payloads := map[string][]byte{}
	for _, env := range envs {
		subject := asMap(env["subject"])
		rel := norm(asString(subject["path"]))
		data := src.find(rel)
		if data == nil {
			res.Issues = append(res.Issues, "缺成员实体："+rel)
			continue
		}
		payloads[rel] = data
	}
	if len(res.Issues) > 0 {
		return res
	}
	levels := []string{}
	bad := []string{}
	for _, env := range envs {
		level, why := envelopeOK(env, payloads, opts.Key)
		if level == "" {
			bad = append(bad, why)
			continue
		}
		levels = append(levels, level)
	}
	if len(bad) > 0 {
		res.Issues = append(res.Issues, "信封未全部通过校验："+strings.Join(bad, "；"))
		return res
	}
	order := map[string]int{"digest_only": 0, "hmac-sha256": 1}
	best := ""
	for _, lv := range levels {
		if order[lv] > order[best] {
			best = lv
		}
	}
	if best == "" {
		best = levels[0]
	}
	res.Level = best
	entries := []map[string]any{}
	names := make([]string, 0, len(payloads))
	for rel := range payloads {
		names = append(names, rel)
	}
	sort.Strings(names)
	for _, rel := range names {
		entries = append(entries, map[string]any{
			"path": rel, "digest": shaHex(payloads[rel]),
		})
	}
	judge(res, entries, opts.Revocations, opts.At)
	return res
}

func mapList(v any) []map[string]any {
	out := []map[string]any{}
	for _, raw := range asList(v) {
		if m := asMap(raw); m != nil {
			out = append(out, m)
		}
	}
	return out
}
