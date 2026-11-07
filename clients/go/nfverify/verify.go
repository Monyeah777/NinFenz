// Package nfverify 是 CCOS 证据包（nf-evidence/1）的 Go 侧零依赖复验器。
//
// 定位：与仓内真源（desktop/src/core/evidence.py）和零依赖 Python 复验器
// （scripts/nf_verify.py）同口径——同一份向量集（results/ccos/evidence_verdict_vectors.json）
// 三者必须给出同样的四词判定与退出码。它证明的是「ABI 不绑定语言」：任何人拿一个
// Go 工具链就能独立复验，不必信任本仓的 Python 实现。
//
// 只做读者侧判定：成员未改 + 证明到根 + 链头自洽 + 信封自洽 + 吊销/时效。
// 不判断内容质量、不判断真实性、不联网。
package nfverify

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"strings"
)

const (
	EvidenceSchema   = "nf-evidence/1"
	AttestSchema     = "nf-attest/1"
	RevocationSchema = "nf-revocation/1"
	BundleEntry      = "bundle.json"
	PayloadDir       = "payload/"

	// 容器面上限（与真源同口径）：验证器收的是不可信输入，不能按声明无限解包
	MaxMemberBytes = 16 * 1024 * 1024
	MaxTotalBytes  = 96 * 1024 * 1024
)

// 判定词表（稳定面）
const (
	VerdictOK      = "ok"
	VerdictInvalid = "invalid"
	VerdictRevoked = "revoked"
	VerdictExpired = "expired"
)

// UsageError 表示输入不是证据包（用法级，不是判定级）
var UsageError = errors.New("usage")

// ExitCode 判定 → 进程退出码（与本仓 CLI 一致；4 = 用法错，不属于判定）
func ExitCode(verdict string) int {
	switch verdict {
	case VerdictOK:
		return 0
	case VerdictRevoked:
		return 2
	case VerdictExpired:
		return 3
	default:
		return 1
	}
}

// Result 复验结论（字段名即 JSON 面，避免结构体标签）
type Result struct {
	Kind         string
	Verdict      string
	Level        string
	Root         string
	Head         string
	Count        int
	Issues       []string
	Warnings     []string
	ExpiresAt    string
	RevokedBy    any
	AnchorRef    any
	AnchorOK     bool
	Decision     any
	DecisionStat string
}

// Map 稳定 JSON 面（键排序由 encoding/json 负责）
func (r *Result) Map() map[string]any {
	return map[string]any{
		"kind": r.Kind, "verdict": r.Verdict, "level": r.Level, "root": r.Root,
		"head": r.Head, "count": r.Count, "issues": r.Issues, "warnings": r.Warnings,
		"expires_at": r.ExpiresAt, "revoked_by": r.RevokedBy, "anchor_ref": r.AnchorRef,
		"anchor_verified": r.AnchorOK, "decision": r.Decision,
		"decision_status": r.DecisionStat,
	}
}

// Options 复验参数（与 CLI 旗标一一对应）
type Options struct {
	Key          []byte
	Revocations  map[string]any
	Anchor       map[string]any
	At           string
	PolicyDigest string
}

func newResult() *Result {
	return &Result{Kind: "bundle", Verdict: VerdictInvalid, Level: "none",
		Issues: []string{}, Warnings: []string{}, DecisionStat: "absent"}
}

// canonicalJSON 与真源同口径：键排序、紧凑分隔符、不转义非 ASCII。
func canonicalJSON(v any) ([]byte, error) {
	var buf bytes.Buffer
	enc := json.NewEncoder(&buf)
	enc.SetEscapeHTML(false)
	if err := enc.Encode(v); err != nil {
		return nil, err
	}
	return bytes.TrimRight(buf.Bytes(), "\n"), nil
}

func shaHex(data []byte) string {
	sum := sha256.Sum256(data)
	return hex.EncodeToString(sum[:])
}

func leafOf(id, digest string) []byte {
	body, _ := canonicalJSON(map[string]any{"id": id, "digest": digest})
	sum := sha256.Sum256(append([]byte{0x00}, body...))
	return sum[:]
}

func nodeHash(left, right []byte) []byte {
	h := sha256.New()
	h.Write([]byte{0x01})
	h.Write(left)
	h.Write(right)
	return h.Sum(nil)
}

// merkleRoot RFC 6962 风格：空集 → nil；单叶 → 该叶；否则切到最大的 2 的幂。
func merkleRoot(leaves [][]byte) []byte {
	switch len(leaves) {
	case 0:
		return nil
	case 1:
		return leaves[0]
	}
	mid := 1
	for mid*2 < len(leaves) {
		mid *= 2
	}
	return nodeHash(merkleRoot(leaves[:mid]), merkleRoot(leaves[mid:]))
}

func foldLeaf(leaf []byte, proof []any) []byte {
	cur := leaf
	for _, raw := range proof {
		step, ok := raw.(map[string]any)
		if !ok {
			return nil
		}
		sib, err := hex.DecodeString(asString(step["hash"]))
		if err != nil {
			return nil
		}
		if asString(step["side"]) == "left" {
			cur = nodeHash(sib, cur)
		} else {
			cur = nodeHash(cur, sib)
		}
	}
	return cur
}

// chainHead 透明日志链头：SHA-256(NODE_PREFIX | prev | leaf) 逐节折叠。
func chainHead(entries []map[string]any) string {
	prev := strings.Repeat("0", 64)
	for _, e := range entries {
		h := sha256.New()
		h.Write([]byte("\x01nf-node:"))
		for _, part := range []string{prev, asString(e["leaf"])} {
			h.Write([]byte("|"))
			h.Write([]byte(part))
		}
		prev = hex.EncodeToString(h.Sum(nil))
	}
	return prev
}

func asString(v any) string {
	switch t := v.(type) {
	case string:
		return t
	case json.Number:
		return t.String()
	case nil:
		return ""
	default:
		return fmt.Sprintf("%v", t)
	}
}

func norm(rel string) string {
	return strings.TrimLeft(strings.ReplaceAll(rel, "\\", "/"), "/")
}

// safeRel 仓相对路径安全闸门：拒绝空段/单点/双点/盘符/首尾空白。
func safeRel(rel string) (string, error) {
	clean := norm(rel)
	if clean == "" {
		return "", errors.New("成员路径为空（修复指引：成员必须有仓相对路径）")
	}
	for _, part := range strings.Split(clean, "/") {
		if part == "" || part == "." || part == ".." {
			return "", fmt.Errorf("成员路径不安全：%s（修复指引：路径段不许是空串/单点/双点）", clean)
		}
		if strings.Contains(part, ":") {
			return "", fmt.Errorf("成员路径含盘符/备用流写法：%s（修复指引：只接受仓内 POSIX 相对路径）", clean)
		}
		if strings.TrimSpace(part) != part {
			return "", fmt.Errorf("成员路径含首尾空白：%q（修复指引：去掉不可见字符）", clean)
		}
	}
	return clean, nil
}

func parseDoc(raw []byte) map[string]any {
	var doc map[string]any
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber()
	if err := dec.Decode(&doc); err != nil {
		return nil
	}
	return doc
}
