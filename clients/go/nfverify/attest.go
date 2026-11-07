package nfverify

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
)

// cc_attest 的 Go 侧实现：造信封（digest_only / hmac-sha256 级）并验证。
// 与真源同口径：信封摘要 = sha256(canonical{schema,subject,producer,issued_at[,decision]})；
// hmac 级 = hmac-sha256(key, envelope_digest)。

// Attest 造一份 nf-attest/1 信封（不写盘：返回信封与摘要）。
func Attest(subjectPath string, data []byte, key []byte, producer, issuedAt string) (map[string]any, error) {
	base := map[string]any{
		"schema":    AttestSchema,
		"subject":   map[string]any{"path": subjectPath, "sha256": shaHex(data)},
		"producer":  producer,
		"issued_at": issuedAt,
	}
	body, err := canonicalJSON(base)
	if err != nil {
		return nil, err
	}
	env := map[string]any{}
	for k, v := range base {
		env[k] = v
	}
	digest := shaHex(body)
	env["envelope_digest"] = digest
	if len(key) > 0 {
		mac := hmac.New(sha256.New, key)
		mac.Write([]byte(digest))
		env["signature"] = map[string]any{"scheme": "hmac-sha256",
			"mac": hex.EncodeToString(mac.Sum(nil))}
	}
	return env, nil
}

// AttestVerdict 信封验证结论。
type AttestVerdict struct {
	OK       bool
	Verdict  string
	Level    string
	Digest   string
	Issues   []string
	Warnings []string
}

// Map 稳定 JSON 面。
func (v *AttestVerdict) Map() map[string]any {
	return map[string]any{
		"ok": v.OK, "verdict": v.Verdict, "level": v.Level,
		"subject_digest": v.Digest, "issues": v.Issues, "warnings": v.Warnings,
	}
}

// VerifyAttestDoc 校验单份信封：信封自洽 + 主体摘要 + 签名（有则必过，缺密钥 fail-closed）。
func VerifyAttestDoc(env map[string]any, data []byte, key []byte) *AttestVerdict {
	res := &AttestVerdict{Verdict: "invalid", Level: "none", Issues: []string{},
		Warnings: []string{}}
	if env == nil || asString(env["schema"]) != AttestSchema {
		res.Issues = append(res.Issues, "信封 schema 不匹配（修复指引：需要 "+AttestSchema+"）")
		return res
	}
	subject := asMap(env["subject"])
	path := asString(subject["path"])
	payloads := map[string][]byte{norm(path): data}
	level, why := envelopeOK(env, payloads, key)
	if level == "" {
		res.Issues = append(res.Issues, why)
		return res
	}
	res.OK = true
	res.Verdict = "ok"
	res.Level = level
	res.Digest = asString(env["envelope_digest"])
	return res
}
