package nfverify

import (
	"archive/zip"
	"bytes"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"io"
	"sort"
	"strconv"
	"strings"
)

type zipSource struct {
	files map[string][]byte
	names []string
}

func openZip(data []byte) (*zipSource, error) {
	zr, err := zip.NewReader(bytes.NewReader(data), int64(len(data)))
	if err != nil {
		return nil, UsageError
	}
	src := &zipSource{files: map[string][]byte{}}
	seen := map[string]bool{}
	for _, f := range zr.File {
		name := f.Name
		if seen[name] {
			return nil, errors.New("包内有重名成员（zip 歧义：判定不可复算）（修复指引：重新 pack）")
		}
		seen[name] = true
		rc, err := f.Open()
		if err != nil {
			return nil, errors.New("成员不可安全读取（修复指引：容器结构歧义或压缩不受支持）")
		}
		body, err := io.ReadAll(io.LimitReader(rc, MaxMemberBytes+1))
		rc.Close()
		if err != nil {
			return nil, errors.New("成员读取失败（修复指引：重新 pack）")
		}
		if len(body) > MaxMemberBytes {
			return nil, errors.New("成员超过单件上限（修复指引：拒绝解包超限成员——防 zip 炸弹）")
		}
		src.files[name] = body
		src.names = append(src.names, name)
	}
	sort.Strings(src.names)
	return src, nil
}

func (s *zipSource) read(name string) []byte { return s.files[norm(name)] }

// find 成员实体查找：先按原相对路径，再退化到 payload/ 前缀（与真源同口径）。
func (s *zipSource) find(rel string) []byte {
	if data := s.read(rel); data != nil {
		return data
	}
	return s.read(PayloadDir + rel)
}

func asList(v any) []any {
	if list, ok := v.([]any); ok {
		return list
	}
	return nil
}

func asMap(v any) map[string]any {
	if m, ok := v.(map[string]any); ok {
		return m
	}
	return nil
}

// VerifyBundle 复验一份证据包（zip 字节）→ (结果, 用法级错误)。
// 用法级错误（UsageError / 容器结构拒收）对应 CLI 的退出码 4 或 1：
// 前者是「输入不是证据包」，后者是「容器面已判死但仍是包」。
func VerifyBundle(data []byte, opts Options) (*Result, error) {
	src, err := openZip(data)
	if err != nil {
		return nil, err
	}
	raw := src.read(BundleEntry)
	if raw == nil {
		return nil, UsageError
	}
	doc := parseDoc(raw)
	if doc == nil || asString(doc["schema"]) != EvidenceSchema {
		return nil, UsageError
	}
	return verifyBundleDoc(src, doc, opts), nil
}

// verifyBundleDoc 对已解析的 bundle 清单做全部判定（三形态出口共用同一套四词判定）。
func verifyBundleDoc(src *zipSource, doc map[string]any, opts Options) *Result {
	res := newResult()
	entriesRaw := asList(doc["entries"])
	entries := make([]map[string]any, 0, len(entriesRaw))
	for _, item := range entriesRaw {
		if e := asMap(item); e != nil {
			entries = append(entries, e)
		}
	}
	res.Count = len(entries)
	res.Root = asString(doc["root"])
	chain := asMap(doc["chain"])
	if chain != nil {
		res.Head = asString(chain["head"])
	}
	res.ExpiresAt = asString(doc["expires_at"])

	// 链段必填且自洽（与真源同口径）：缺证据 ≠ 证据成立
	if chain == nil {
		res.Issues = append(res.Issues, "缺 chain 段（证据包必须带链头）")
		return res
	}
	if res.Head == "" {
		res.Issues = append(res.Issues, "chain.head 为空")
		return res
	}
	if asString(chain["count"]) != itoa(len(entries)) {
		res.Issues = append(res.Issues, "chain.count 不符")
		return res
	}
	if len(entries) == 0 {
		res.Issues = append(res.Issues, "证据包为空")
		return res
	}

	payloads, leaves, ok := verifyMembers(src, entries, res)
	if !ok {
		return res
	}
	root := hex.EncodeToString(merkleRoot(leaves))
	if root != res.Root {
		res.Issues = append(res.Issues, "根不一致（" + root[:16] + "）")
		return res
	}
	for _, e := range entries {
		leaf, err := hex.DecodeString(asString(e["leaf"]))
		if err != nil {
			res.Issues = append(res.Issues, "叶不可解析")
			return res
		}
		folded := hex.EncodeToString(foldLeaf(leaf, asList(e["proof"])))
		if folded != res.Root {
			res.Issues = append(res.Issues, "包含证明不折叠到根")
		}
	}
	if len(res.Issues) > 0 {
		return res
	}
	if chainHead(entries) != res.Head {
		res.Issues = append(res.Issues, "透明日志链头不一致（条目顺序被插删/改序）")
		return res
	}
	if !checkAnchor(entries, doc, opts.Anchor, res) {
		return res
	}
	listed := map[string]bool{}
	for _, e := range entries {
		rel := norm(asString(e["path"]))
		if rel == "" {
			rel = norm(asString(e["id"]))
		}
		listed[PayloadDir+rel] = true
	}
	for _, name := range src.names {
		if strings.HasPrefix(name, PayloadDir) && !listed[name] {
			res.Issues = append(res.Issues, "包内多出未登记成员："+name)
		}
	}
	if len(res.Issues) > 0 {
		return res
	}
	verifyEnvelopes(src, doc, payloads, opts.Key, res)
	if len(res.Issues) > 0 {
		return res
	}
	checkDecision(src, doc, payloads, res, opts.PolicyDigest)
	if len(res.Issues) > 0 {
		return res
	}
	rev := opts.Revocations
	if rev == nil {
		embedded, errMsg := embeddedRev(src)
		if errMsg != "" {
			res.Issues = append(res.Issues, errMsg)
			return res
		}
		rev = embedded
	}
	judge(res, entries, rev, opts.At)
	return res
}

func itoa(n int) string { return strconv.Itoa(n) }

func verifyMembers(src *zipSource, entries []map[string]any, res *Result) (map[string][]byte, [][]byte, bool) {
	payloads := map[string][]byte{}
	leaves := [][]byte{}
	for _, e := range entries {
		rel, err := safeRel(firstNonEmpty(asString(e["path"]), asString(e["id"])))
		if err != nil {
			res.Issues = append(res.Issues, err.Error())
			continue
		}
		data := src.find(rel)
		if data == nil {
			res.Issues = append(res.Issues, "缺 payload："+rel)
			continue
		}
		digest := shaHex(data)
		payloads[rel] = data
		if want := asString(e["digest"]); digest != want {
			res.Issues = append(res.Issues, "成员摘要不符："+rel)
		}
		leaf := hex.EncodeToString(leafOf(rel, digest))
		if leaf != asString(e["leaf"]) {
			res.Issues = append(res.Issues, "叶复算不符："+rel)
		}
		leaves = append(leaves, leafOf(rel, digest))
	}
	return payloads, leaves, len(res.Issues) == 0
}

func firstNonEmpty(values ...string) string {
	for _, v := range values {
		if v != "" {
			return v
		}
	}
	return ""
}

func checkAnchor(entries []map[string]any, doc map[string]any, anchor map[string]any, res *Result) bool {
	declared := asMap(doc["anchor"])
	if declared != nil && len(declared) > 0 {
		res.AnchorRef = map[string]any{"count": declared["count"], "head": declared["head"]}
	}
	if anchor == nil || len(anchor) == 0 {
		if res.AnchorRef != nil {
			res.Warnings = append(res.Warnings, "包声明了外部锚点但未提供锚点材料（无法证明未被截断）")
		}
		return true
	}
	cnt, okCnt := intValue(anchor["count"])
	head := asString(anchor["head"])
	if !okCnt || cnt < 0 || head == "" {
		res.Issues = append(res.Issues, "锚点材料形状不对（需要 {count: 非负整数, head: 非空字符串}）")
		return false
	}
	if res.AnchorRef != nil {
		ref := asMap(res.AnchorRef)
		refCnt, _ := intValue(ref["count"])
		if refCnt != cnt || asString(ref["head"]) != head {
			res.Issues = append(res.Issues, "包内 anchor 与外部锚点不一致")
			return false
		}
	}
	if len(entries) < cnt {
		res.Issues = append(res.Issues, "证据包被截断：锚点记录 "+itoa(cnt)+" 条")
		return false
	}
	if chainHead(entries[:cnt]) != head {
		res.Issues = append(res.Issues, "与外部锚点不符：该位置的链头不一致")
		return false
	}
	res.AnchorOK = true
	return true
}

func intValue(v any) (int, bool) {
	switch t := v.(type) {
	case float64:
		return int(t), true
	case int:
		return t, true
	case interface{ Int64() (int64, error) }:
		n, err := t.Int64()
		return int(n), err == nil
	default:
		enc := strings.TrimSpace(asString(v))
		if enc == "" {
			return 0, false
		}
		n, err := strconv.Atoi(enc)
		return n, err == nil
	}
}

func embeddedRev(src *zipSource) (map[string]any, string) {
	raw := src.read("revocations.json")
	if raw == nil {
		return nil, ""
	}
	doc := parseDoc(raw)
	if doc == nil {
		return nil, "包内吊销表不可解析（坏件不能当「无吊销」）"
	}
	if asString(doc["schema"]) != RevocationSchema {
		return nil, "包内吊销表 schema 不匹配（期望 " + RevocationSchema + "）"
	}
	return doc, ""
}

func judge(res *Result, entries []map[string]any, rev map[string]any, at string) {
	if hit := revHit(rev, entries); hit != nil {
		res.Verdict = VerdictRevoked
		res.RevokedBy = hit
		res.Issues = append(res.Issues, "证据已被吊销")
		return
	}
	if exp := res.ExpiresAt; exp != "" {
		now := at
		if now == "" {
			now = "9999-12-31T23:59:59Z"
		}
		if now > exp {
			res.Verdict = VerdictExpired
			res.Issues = append(res.Issues, "证据已过期：有效期至 "+exp)
			return
		}
	}
	res.Verdict = VerdictOK
}

func revHit(rev map[string]any, entries []map[string]any) any {
	if rev == nil || asString(rev["schema"]) != RevocationSchema {
		return nil
	}
	items := asList(rev["revoked"])
	if items == nil {
		return nil
	}
	digests := map[string]bool{}
	paths := map[string]bool{}
	for _, e := range entries {
		digests[asString(e["digest"])] = true
		paths[norm(firstNonEmpty(asString(e["path"]), asString(e["id"])))] = true
	}
	for _, raw := range items {
		item := asMap(raw)
		if item == nil {
			continue
		}
		if dig := asString(item["digest"]); dig != "" && digests[dig] {
			return item
		}
		if pat := norm(asString(item["path"])); pat != "" && paths[pat] {
			return item
		}
	}
	return nil
}

func verifyEnvelopes(src *zipSource, doc map[string]any, payloads map[string][]byte, key []byte, res *Result) {
	names := asList(doc["attestations"])
	if len(names) == 0 {
		res.Issues = append(res.Issues, "包内无 attestation")
		return
	}
	levels := []string{}
	covered := map[string]bool{}
	bad := []string{}
	for _, rawName := range names {
		name := asString(rawName)
		raw := src.read(name)
		if raw == nil {
			bad = append(bad, name+"：缺该信封")
			continue
		}
		env := parseDoc(raw)
		if env == nil {
			bad = append(bad, name+"：不是合法 JSON")
			continue
		}
		level, why := envelopeOK(env, payloads, key)
		if level == "" {
			bad = append(bad, name+"："+why)
			continue
		}
		levels = append(levels, level)
		subject := asMap(env["subject"])
		covered[norm(asString(subject["path"]))] = true
	}
	if len(bad) > 0 {
		res.Issues = append(res.Issues, "信封未全部通过校验："+strings.Join(bad, "；"))
		return
	}
	want := map[string]bool{}
	for _, e := range asList(doc["entries"]) {
		entry := asMap(e)
		if entry == nil {
			continue
		}
		want[norm(firstNonEmpty(asString(entry["path"]), asString(entry["id"])))] = true
	}
	missing := []string{}
	for rel := range want {
		if !covered[rel] {
			missing = append(missing, rel)
		}
	}
	sort.Strings(missing)
	if len(missing) > 0 {
		res.Issues = append(res.Issues, "成员缺信封："+strings.Join(missing, ", "))
		return
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
}

func envelopeOK(env map[string]any, payloads map[string][]byte, key []byte) (string, string) {
	if env == nil || asString(env["schema"]) != AttestSchema {
		return "", "信封 schema 不匹配"
	}
	base := map[string]any{
		"schema": env["schema"], "subject": env["subject"],
		"producer": env["producer"], "issued_at": env["issued_at"],
	}
	if decision := asMap(env["decision"]); decision != nil && len(decision) > 0 {
		base["decision"] = decision
	}
	body, err := canonicalJSON(base)
	if err != nil {
		return "", "信封摘要计算失败"
	}
	if asString(env["envelope_digest"]) != shaHex(body) {
		return "", "信封摘要不一致（信封被改）"
	}
	subject := asMap(env["subject"])
	rel := norm(asString(subject["path"]))
	data, ok := payloads[rel]
	if !ok {
		return "", "信封指向的成员不在证据里：" + rel
	}
	if shaHex(data) != asString(subject["sha256"]) {
		return "", "信封主体与成员不同源：" + rel
	}
	sig := asMap(env["signature"])
	if sig == nil || len(sig) == 0 {
		return "digest_only", ""
	}
	if asString(sig["scheme"]) != "hmac-sha256" {
		return "", "信封签名方案需外部验证器（本零依赖验证器 fail-closed）"
	}
	if key == nil {
		return "", "hmac 级缺密钥（fail-closed，不降级）"
	}
	mac := hmac.New(sha256.New, key)
	mac.Write([]byte(asString(env["envelope_digest"])))
	want := hex.EncodeToString(mac.Sum(nil))
	if !hmac.Equal([]byte(want), []byte(asString(sig["mac"]))) {
		return "", "hmac 签名不匹配（密钥不符或信封被改）"
	}
	return "hmac-sha256", ""
}

func decisionIssues(decision map[string]any, payloads map[string][]byte) []string {
	issues := []string{}
	if decision == nil || len(decision) == 0 {
		return []string{"decision 必须是非空对象"}
	}
	allowed := map[string]bool{"syscall": true, "policy_digest": true,
		"verdict": true, "object_sha256": true}
	for k := range decision {
		if !allowed[k] {
			issues = append(issues, "decision 含未知字段")
			break
		}
	}
	if asString(decision["syscall"]) != "cc_check" {
		issues = append(issues, "decision.syscall 只支持 cc_check（v0）")
	}
	for _, key := range []string{"policy_digest", "object_sha256"} {
		val := asString(decision[key])
		if len(val) != 64 || !isLowerHex(val) {
			issues = append(issues, "decision."+key+" 须为 64 位十六进制")
		}
	}
	if asString(decision["verdict"]) != "ok" {
		issues = append(issues, "decision.verdict 只允许 ok（v0）")
	}
	obj := asString(decision["object_sha256"])
	found := false
	for _, data := range payloads {
		if shaHex(data) == obj {
			found = true
			break
		}
	}
	if !found {
		issues = append(issues, "decision.object_sha256 不在成员摘要里")
	}
	return issues
}

func isLowerHex(s string) bool {
	for _, r := range s {
		if !(r >= '0' && r <= '9') && !(r >= 'a' && r <= 'f') {
			return false
		}
	}
	return true
}

func checkDecision(src *zipSource, doc map[string]any, payloads map[string][]byte, res *Result, expected string) {
	envs := []map[string]any{}
	for _, rawName := range asList(doc["attestations"]) {
		raw := src.read(asString(rawName))
		if raw == nil {
			continue
		}
		if env := parseDoc(raw); env != nil {
			envs = append(envs, env)
		}
	}
	decision := asMap(doc["decision"])
	if decision == nil {
		for _, env := range envs {
			if d := asMap(env["decision"]); d != nil {
				res.Issues = append(res.Issues, "信封带 decision 但清单未声明（声明面被删）")
				return
			}
		}
		if expected != "" {
			res.Warnings = append(res.Warnings, "包内无 decision，无法比对策略（只证字节与信封）")
		}
		return
	}
	if issues := decisionIssues(decision, payloads); len(issues) > 0 {
		res.Issues = append(res.Issues, issues...)
		return
	}
	obj := asString(decision["object_sha256"])
	matched := 0
	signed := false
	for _, env := range envs {
		subject := asMap(env["subject"])
		if asString(subject["sha256"]) != obj {
			continue
		}
		matched++
		bound := asMap(env["decision"])
		if bound == nil || !sameJSON(bound, decision) {
			res.Issues = append(res.Issues, "decision 声明面与信封绑定面不一致（换策略/删块）")
			return
		}
		if sig := asMap(env["signature"]); sig != nil && len(sig) > 0 {
			signed = true
		}
	}
	if matched == 0 {
		res.Issues = append(res.Issues, "decision 找不到主体摘要相符的信封")
		return
	}
	res.Decision = decision
	if signed {
		res.DecisionStat = "bound"
	} else {
		res.DecisionStat = "declared"
	}
	if expected != "" {
		if strings.ToLower(expected) != asString(decision["policy_digest"]) {
			res.Issues = append(res.Issues, "decision.policy_digest 与期望策略不符")
		}
	}
}

func sameJSON(a, b map[string]any) bool {
	left, err1 := canonicalJSON(a)
	right, err2 := canonicalJSON(b)
	if err1 != nil || err2 != nil {
		return false
	}
	return bytes.Equal(left, right)
}
