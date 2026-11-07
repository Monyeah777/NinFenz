package nfverify

import (
	"crypto/sha256"
	"errors"
	"fmt"
	"os"
	"regexp"
	"strings"
	"unicode/utf8"
)

// 策略词表（封闭集，与真源 core/check_policy.py 逐字对齐）：
// 新增类别 = 破坏性变更，因为它会让「同一策略」在不同版本判出不同结论。
var CheckKinds = []string{"utf8", "regex_present", "regex_absent", "count_at_least",
	"digest_pin"}
var CheckSeverities = []string{"fail", "warn"}
var CheckFields = []string{"bytes", "lines", "chars"}

const PolicySchema = "nf-check-policy/1"
const CheckResultSchema = "nf-check-result/1"

// CheckFinding 单条规则的判定。
type CheckFinding struct {
	Rule     string
	Kind     string
	Severity string
	OK       bool
	Detail   string
	Fix      string
}

// CheckResult 单对象体检结论（cc_check 的判定面）。
type CheckResult struct {
	Schema       string
	Verdict      string
	PolicyID     string
	PolicyDigest string
	ObjectPath   string
	ObjectSHA256 string
	ObjectBytes  int
	Findings     []CheckFinding
	Failed       int
	Warned       int
}

// Map 稳定 JSON 面。
func (r *CheckResult) Map() map[string]any {
	findings := make([]any, 0, len(r.Findings))
	for _, f := range r.Findings {
		findings = append(findings, map[string]any{
			"rule": f.Rule, "kind": f.Kind, "severity": f.Severity,
			"ok": f.OK, "detail": f.Detail, "fix": f.Fix,
		})
	}
	return map[string]any{
		"schema": r.Schema, "verdict": r.Verdict, "policy_id": r.PolicyID,
		"policy_digest": r.PolicyDigest,
		"object": map[string]any{"path": r.ObjectPath, "sha256": r.ObjectSHA256,
			"bytes": r.ObjectBytes},
		"findings": findings, "failed": r.Failed, "warned": r.Warned,
	}
}

// ValidatePolicy 策略形状校验 → 问题列表（空 = 合法；每条都给可执行指引）。
func ValidatePolicy(policy map[string]any) []string {
	issues := []string{}
	if policy == nil {
		return []string{"策略顶层应为对象（修复指引：请给 " + PolicySchema + " 的 JSON 对象）"}
	}
	if asString(policy["schema"]) != PolicySchema {
		issues = append(issues, "策略 schema 不匹配（修复指引：请补 schema 为 "+
			PolicySchema+"）")
	}
	rules, ok := policy["rules"].([]any)
	if !ok || len(rules) == 0 {
		return append(issues, "策略缺 rules（修复指引：请至少给一条规则；空策略不能判任何结论）")
	}
	seen := map[string]bool{}
	for idx, raw := range rules {
		where := fmt.Sprintf("第 %d 条规则", idx+1)
		rule, okRule := raw.(map[string]any)
		if !okRule {
			issues = append(issues, where+"不是对象（修复指引：请写成规则对象）")
			continue
		}
		rid := strings.TrimSpace(asString(rule["id"]))
		if rid == "" {
			issues = append(issues, where+"缺 id（修复指引：请给唯一 id，结论里要按 id 定位）")
		} else if seen[rid] {
			issues = append(issues, "规则 id 重复："+rid+"（修复指引：请改成唯一 id）")
		} else {
			seen[rid] = true
		}
		kind := asString(rule["kind"])
		if !containsString(CheckKinds, kind) {
			issues = append(issues, where+"的 kind 不在词表（修复指引：可选 "+
				strings.Join(CheckKinds, ", ")+"；不要自造 DSL）")
		}
		sev := asString(rule["severity"])
		if sev == "" {
			sev = "fail"
		}
		if !containsString(CheckSeverities, sev) {
			issues = append(issues, where+"的 severity 不在词表（修复指引：fail 或 warn）")
		}
		if strings.TrimSpace(asString(rule["fix"])) == "" {
			issues = append(issues, where+"缺 fix（修复指引：每条规则都必须写修复指引）")
		}
		if kind == "regex_present" || kind == "regex_absent" {
			pat := asString(rule["pattern"])
			if pat == "" {
				issues = append(issues, where+"缺 pattern（修复指引：请给正则字符串）")
			} else if _, err := regexp.Compile(pat); err != nil {
				issues = append(issues, where+"的 pattern 不是合法正则："+err.Error()+
					"（修复指引：请修正正则后重跑）")
			}
		}
		if kind == "count_at_least" {
			if !containsString(CheckFields, asString(rule["field"])) {
				issues = append(issues, where+"的 field 不在词表（修复指引：可选 "+
					strings.Join(CheckFields, ", ")+"）")
			}
			n, okN := intValue(rule["n"])
			if !okN || n < 0 {
				issues = append(issues, where+"的 n 应为非负整数（修复指引：请给整数下界）")
			}
		}
		if kind == "digest_pin" && !isLowerHexLen(asString(rule["sha256"]), 64) {
			issues = append(issues, where+"的 sha256 应为 64 位十六进制（修复指引：请钉完整摘要）")
		}
	}
	return issues
}

// PolicyDigest 策略摘要：判据版本随结论走。
func PolicyDigest(policy map[string]any) string {
	body, err := canonicalJSON(policy)
	if err != nil {
		return ""
	}
	sum := sha256.Sum256(body)
	return hexOf(sum[:])
}

func hexOf(b []byte) string {
	const digits = "0123456789abcdef"
	out := make([]byte, 0, len(b)*2)
	for _, x := range b {
		out = append(out, digits[x>>4], digits[x&0x0f])
	}
	return string(out)
}

// Check 单对象体检：对象字节 + 策略 → verdict（封闭词表；warn 只记不改判）。
func Check(path string, policy map[string]any) (*CheckResult, error) {
	if issues := ValidatePolicy(policy); len(issues) > 0 {
		return nil, errors.New("策略不合法：" + issues[0])
	}
	raw, err := readAll(path)
	if err != nil {
		return nil, err
	}
	text, utf8ok := decodeUTF8(raw)
	digest := shaHex(raw)
	res := &CheckResult{Schema: CheckResultSchema, PolicyID: asString(policy["id"]),
		PolicyDigest: PolicyDigest(policy), ObjectPath: strings.ReplaceAll(path, "\\", "/"),
		ObjectSHA256: digest, ObjectBytes: len(raw)}
	for _, rawRule := range policy["rules"].([]any) {
		rule := rawRule.(map[string]any)
		ok, detail := checkOne(rule, raw, text, utf8ok, digest)
		sev := asString(rule["severity"])
		if sev == "" {
			sev = "fail"
		}
		res.Findings = append(res.Findings, CheckFinding{
			Rule: asString(rule["id"]), Kind: asString(rule["kind"]), Severity: sev,
			OK: ok, Detail: detail, Fix: asString(rule["fix"])})
		if !ok && sev == "fail" {
			res.Failed++
		}
		if !ok && sev == "warn" {
			res.Warned++
		}
	}
	res.Verdict = "ok"
	if res.Failed > 0 {
		res.Verdict = "invalid"
	}
	return res, nil
}

func checkOne(rule map[string]any, raw []byte, text string, utf8ok bool, digest string) (bool, string) {
	switch asString(rule["kind"]) {
	case "utf8":
		if !utf8ok {
			return false, "不是合法 UTF-8 文本"
		}
		return true, "UTF-8 自检通过"
	case "regex_present", "regex_absent":
		if !utf8ok {
			return false, "对象不是 UTF-8 文本，正则类规则无从判定"
		}
		re, err := regexp.Compile(asString(rule["pattern"]))
		if err != nil {
			return false, "pattern 不是合法正则"
		}
		hit := re.MatchString(text)
		if asString(rule["kind"]) == "regex_present" {
			if hit {
				return true, "命中要求的内容"
			}
			return false, "缺要求的内容（pattern 未命中）"
		}
		if !hit {
			return true, "未出现禁止内容"
		}
		return false, "出现了禁止内容（pattern 命中）"
	case "count_at_least":
		field := asString(rule["field"])
		n, _ := intValue(rule["n"])
		var actual int
		switch field {
		case "bytes":
			actual = len(raw)
		case "lines":
			actual = len(strings.Split(strings.ReplaceAll(text, "\r\n", "\n"), "\n"))
			if utf8ok && text == "" {
				actual = 0
			}
		case "chars":
			actual = len([]rune(text))
		}
		return actual >= n, fmt.Sprintf("%s=%d（下界 %d）", field, actual, n)
	case "digest_pin":
		want := strings.ToLower(asString(rule["sha256"]))
		return digest == want, map[bool]string{true: "摘要=一致", false: "摘要=不符"}[digest == want]
	}
	return false, "未知规则类别"
}

func containsString(list []string, v string) bool {
	for _, item := range list {
		if item == v {
			return true
		}
	}
	return false
}

func isLowerHexLen(s string, n int) bool {
	if len(s) != n {
		return false
	}
	for _, r := range strings.ToLower(s) {
		if !(r >= '0' && r <= '9') && !(r >= 'a' && r <= 'f') {
			return false
		}
	}
	return true
}

func readAll(path string) ([]byte, error) {
	return os.ReadFile(path)
}

// decodeUTF8 判断字节是否为合法 UTF-8 文本（非文本不让整条判定崩掉：由 utf8 规则判否）。
func decodeUTF8(raw []byte) (string, bool) {
	if !utf8.Valid(raw) {
		return "", false
	}
	return string(raw), true
}
