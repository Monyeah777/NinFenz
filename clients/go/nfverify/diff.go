package nfverify

import (
	"bytes"
	"crypto/sha256"
	"encoding/json"
	"sort"
	"strings"
)

const DiffSchema = "nf-contract-diff/1"

// cc_diff 的 Go 侧实现：两份 JSON 文档 → 字段级差异 + 兼容判定。
// 口径与真源 core/contract_history.py 的 _json_shape/_json_diff 逐字对齐：
// 指针形如 $.a.b 与 $.list[0]，值形态形如 "object"/"array"/"str:\"x\"/int:1/bool:true。
// 只有 JSON 契约这一路移植；Markdown 契约签名（knowledge_sig）未移植，见 README。

// Change 一条字段级差异。
type Change struct {
	Pointer string
	From    string
	To      string
	Kind    string
}

// DiffResult cc_diff 的输出。
type DiffResult struct {
	Schema  string
	Verdict string
	Impact  string
	Channel string
	DigestA string
	DigestB string
	Changes []Change
}

// Map 稳定 JSON 面。
func (r *DiffResult) Map() map[string]any {
	changes := make([]any, 0, len(r.Changes))
	for _, c := range r.Changes {
		var from, to any
		if c.From != "" {
			from = c.From
		}
		if c.To != "" {
			to = c.To
		}
		changes = append(changes, map[string]any{
			"pointer": c.Pointer, "from": from, "to": to, "kind": c.Kind,
		})
	}
	return map[string]any{
		"schema": r.Schema, "verdict": r.Verdict, "impact": r.Impact,
		"digest_a": r.DigestA, "digest_b": r.DigestB, "changes": changes,
	}
}

// DiffJSON 比较两份 JSON 文档字节 → delta（不可解析即用法错）。
func DiffJSON(a, b []byte) (*DiffResult, error) {
	va, errA := decodeJSON(a)
	vb, errB := decodeJSON(b)
	if errA != nil || errB != nil {
		return nil, UsageError
	}
	shapeA := map[string]string{}
	shapeB := map[string]string{}
	jsonShape(va, "$", shapeA)
	jsonShape(vb, "$", shapeB)
	res := &DiffResult{Schema: DiffSchema, DigestA: shaHex(a), DigestB: shaHex(b)}
	pointers := map[string]bool{}
	for p := range shapeA {
		pointers[p] = true
	}
	for p := range shapeB {
		pointers[p] = true
	}
	list := make([]string, 0, len(pointers))
	for p := range pointers {
		list = append(list, p)
	}
	sort.Strings(list)
	added, removed, changed := 0, 0, 0
	typeChanged := false
	requiredAdded := false
	versionChanged := false
	for _, p := range list {
		before, okA := shapeA[p]
		after, okB := shapeB[p]
		switch {
		case okA && !okB:
			res.Changes = append(res.Changes, Change{Pointer: p, From: before, Kind: "移除"})
			removed++
		case !okA && okB:
			res.Changes = append(res.Changes, Change{Pointer: p, To: after, Kind: "新增"})
			added++
			if strings.Contains(p, ".required[") {
				requiredAdded = true
			}
		case before != after:
			res.Changes = append(res.Changes, Change{Pointer: p, From: before, To: after,
				Kind: "变更"})
			changed++
			if strings.SplitN(before, ":", 2)[0] != strings.SplitN(after, ":", 2)[0] {
				typeChanged = true
			}
			if isVersionPointer(p) {
				versionChanged = true
			}
		}
	}
	switch {
	case removed > 0 || typeChanged || requiredAdded || versionChanged:
		res.Impact = "bump"
		res.Verdict = "破坏（结构移除、类型/版本变化或必填项增加）"
	case added > 0:
		res.Impact = "additive"
		res.Verdict = "兼容（字段级新增）"
	default:
		res.Impact = "editorial"
		res.Verdict = "兼容（编辑性变更）"
	}
	return res, nil
}

func isVersionPointer(pointer string) bool {
	tail := pointer
	if idx := strings.LastIndex(pointer, "."); idx >= 0 {
		tail = pointer[idx+1:]
	}
	switch tail {
	case "$id", "$schema", "schema", "version", "schema_version":
		return true
	}
	return false
}

func jsonShape(v any, pointer string, out map[string]string) {
	switch t := v.(type) {
	case map[string]any:
		out[pointer] = "object"
		keys := make([]string, 0, len(t))
		for k := range t {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		for _, k := range keys {
			jsonShape(t[k], pointer+"."+k, out)
		}
	case []any:
		out[pointer] = "array"
		for i, item := range t {
			jsonShape(item, pointer+"["+itoa(i)+"]", out)
		}
	case bool:
		if t {
			out[pointer] = "bool:true"
		} else {
			out[pointer] = "bool:false"
		}
	case nil:
		out[pointer] = "null"
	case json.Number:
		raw := t.String()
		if strings.ContainsAny(raw, ".eE") {
			out[pointer] = "float:" + raw
		} else {
			out[pointer] = "int:" + raw
		}
	case string:
		out[pointer] = "str:" + pyJSONString(t)
	default:
		out[pointer] = "null"
	}
}

// pyJSONString 与 Python json.dumps(ensure_ascii=False) 的字符串形态对齐（不转义 HTML）。
func pyJSONString(s string) string {
	var buf bytes.Buffer
	enc := json.NewEncoder(&buf)
	enc.SetEscapeHTML(false)
	if err := enc.Encode(s); err != nil {
		return "\"\""
	}
	return strings.TrimRight(buf.String(), "\n")
}

func decodeJSON(raw []byte) (any, error) {
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber()
	var v any
	if err := dec.Decode(&v); err != nil {
		return nil, err
	}
	return v, nil
}

var _ = sha256.Sum256
