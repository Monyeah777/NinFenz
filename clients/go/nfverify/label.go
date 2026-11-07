package nfverify

import (
	"regexp"
	"sort"
	"strings"
)

// cc_label 的声明层（IR 校验）在 Go 侧的第二实现。
// 载体写入/读取不在 Go 侧（PNG/JPEG/WebP 编解码与像素水印是另一件工程），见 README 覆盖面表。

const LabelSchema = "nf-label/1"
const LabelStandard = "GB 45438-2025"

var LabelLevels = []string{"minimal", "full"}

// labelRule 与真源 RULES 表逐条对齐：一条规则 = 一个可被「声明项」满足的最小要求。
type labelRule struct {
	ID       string
	Face     string
	Kind     string
	Level    string
	Required []string
}

var labelRules = []labelRule{
	{"E1", "explicit", "text", "minimal", []string{"where", "value"}},
	{"E2", "explicit", "audio", "full", []string{"value"}},
	{"E3", "explicit", "metadata", "full", []string{"key", "value"}},
	{"I1", "implicit", "watermark", "full", []string{"algorithm", "value"}},
	{"I2", "implicit", "metadata", "minimal", []string{"key", "value"}},
}

var labelKinds = map[string][]string{
	"explicit": {"audio", "metadata", "text"},
	"implicit": {"metadata", "watermark"},
}

var hex64 = regexp.MustCompile("^[0-9a-f]{64}$")

// LabelResult IR 校验结论（cc_label 的声明面）。
type LabelResult struct {
	OK       bool
	Verdict  string
	Level    string
	Applied  []string
	Issues   []string
	Warnings []string
	Missing  []string
}

// Map 稳定 JSON 面。
func (r *LabelResult) Map() map[string]any {
	applied := make([]any, 0, len(r.Applied))
	for _, a := range r.Applied {
		applied = append(applied, a)
	}
	return map[string]any{
		"ok": r.OK, "verdict": r.Verdict, "level": r.Level,
		"applied": applied, "issues": r.Issues, "warnings": r.Warnings,
		"missing": r.Missing,
	}
}

// ValidateLabel 校验 nf-label/1 IR（形状 + 档位必需项）。与真源同口径：
// 缺项进 issues 与 missing，载体自称写入只给 warning（不假装已证明）。
func ValidateLabel(doc map[string]any) *LabelResult {
	res := &LabelResult{Verdict: "invalid", Level: "none",
		Issues: []string{}, Warnings: []string{}, Missing: []string{}}
	if doc == nil {
		res.Issues = append(res.Issues, "IR 顶层应为对象（修复指引：不是数组/标量）")
		return res
	}
	if asString(doc["schema"]) != LabelSchema {
		res.Issues = append(res.Issues, "schema 不匹配（修复指引：期望 "+LabelSchema+"）")
	}
	if asString(doc["standard"]) != LabelStandard {
		res.Issues = append(res.Issues, "standard 不匹配（修复指引：v0 只认 "+LabelStandard+"）")
	}
	level := asString(doc["level"])
	if !containsString(LabelLevels, level) {
		res.Issues = append(res.Issues, "level 非法（修复指引：可用 minimal, full）")
	}
	checkLabelObject(doc, res)
	checkLabelItems(doc, res)
	if containsString(LabelLevels, level) {
		res.Level = level
		explicit := mapList(doc["explicit"])
		implicit := mapList(doc["implicit"])
		for _, rule := range labelRules {
			if level == "minimal" && rule.Level != "minimal" {
				continue
			}
			pool := explicit
			if rule.Face == "implicit" {
				pool = implicit
			}
			if !labelCovered(pool, rule) {
				res.Missing = append(res.Missing, rule.ID)
				res.Issues = append(res.Issues, "缺 "+rule.ID+"（修复指引：补对应声明项，或把档位降到 minimal）")
				continue
			}
			res.Applied = append(res.Applied, rule.ID)
		}
	}
	res.OK = len(res.Issues) == 0
	if res.OK {
		res.Verdict = "ok"
	}
	return res
}

func checkLabelObject(doc map[string]any, res *LabelResult) {
	obj := asMap(doc["object"])
	if obj == nil {
		res.Issues = append(res.Issues, "缺 object 段（修复指引：需要 {path, digest}）")
		return
	}
	if strings.TrimSpace(asString(obj["path"])) == "" {
		res.Issues = append(res.Issues, "object.path 缺失或为空（修复指引：请给对象路径）")
	}
	digest := strings.ToLower(strings.TrimSpace(asString(obj["digest"])))
	if !hex64.MatchString(digest) {
		res.Issues = append(res.Issues, "object.digest 必须是 64 位十六进制 sha256（修复指引：请用 nf label ir 生成）")
	}
}

func checkLabelItems(doc map[string]any, res *LabelResult) {
	faces := []string{"explicit", "implicit"}
	for _, face := range faces {
		raw, ok := doc[face]
		if !ok || raw == nil {
			res.Issues = append(res.Issues, "缺 "+face+" 列表（修复指引：没有就写空数组，不要省略字段）")
			continue
		}
		items, isList := raw.([]any)
		if !isList {
			res.Issues = append(res.Issues, "缺 "+face+" 列表（修复指引：没有就写空数组，不要省略字段）")
			continue
		}
		allowed := labelKinds[face]
		for idx, it := range items {
			item := asMap(it)
			if item == nil {
				res.Issues = append(res.Issues, face+"["+itoa(idx)+"] 应为对象（修复指引：声明项是键值对）")
				continue
			}
			if !containsString(allowed, asString(item["kind"])) {
				sorted := append([]string{}, allowed...)
				sort.Strings(sorted)
				res.Issues = append(res.Issues, face+"["+itoa(idx)+"].kind 非法（修复指引：可用 "+
					strings.Join(sorted, ", ")+"）")
			}
		}
	}
	carrier := asMap(doc["carrier"])
	if carrier == nil {
		res.Issues = append(res.Issues, "缺 carrier 段（修复指引：需要 {embedded: bool, producer}）")
		return
	}
	embedded, okBool := carrier["embedded"].(bool)
	if !okBool {
		res.Issues = append(res.Issues, "carrier.embedded 必须是布尔值（修复指引：true 表示自称已写入载体）")
		return
	}
	if embedded {
		res.Warnings = append(res.Warnings,
			"carrier.embedded=true 只是自称：本判定无法证明标识真的写进了文件")
	}
}

func labelCovered(pool []map[string]any, rule labelRule) bool {
	for _, item := range pool {
		if asString(item["kind"]) != rule.Kind {
			continue
		}
		okAll := true
		for _, field := range rule.Required {
			if strings.TrimSpace(asString(item[field])) == "" {
				okAll = false
				break
			}
		}
		if okAll {
			return true
		}
	}
	return false
}
