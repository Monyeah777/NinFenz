package nfverify

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

type labelVector struct {
	ID       string         `json:"id"`
	Desc     string         `json:"desc"`
	IR       map[string]any `json:"ir"`
	Expected struct {
		OK       bool     `json:"ok"`
		Level    string   `json:"level"`
		Missing  []string `json:"missing"`
		Warnings int      `json:"warnings"`
	} `json:"expected"`
}

type labelVectorDoc struct {
	Count   int           `json:"count"`
	Vectors []labelVector `json:"vectors"`
}

func labelVectorFile(t *testing.T) string {
	t.Helper()
	if p := os.Getenv("NF_LABEL_VECTORS"); p != "" {
		return p
	}
	for _, p := range []string{
		filepath.Join("..", "..", "..", "results", "ccos", "label_verdict_vectors.json"),
		filepath.Join("..", "..", "results", "ccos", "label_verdict_vectors.json"),
	} {
		if _, err := os.Stat(p); err == nil {
			return p
		}
	}
	t.Skip("找不到 cc_label 向量集（用 NF_LABEL_VECTORS 指定）")
	return ""
}

// TestLabelVectors 是 Go 侧 cc_label 声明层的合格判据：ok / level / missing 逐例相符。
func TestLabelVectors(t *testing.T) {
	raw, err := os.ReadFile(labelVectorFile(t))
	if err != nil {
		t.Fatalf("读向量集失败：%v", err)
	}
	var doc labelVectorDoc
	if err := json.Unmarshal(raw, &doc); err != nil {
		t.Fatalf("向量集不是合法 JSON：%v", err)
	}
	if len(doc.Vectors) == 0 {
		t.Fatal("向量集为空")
	}
	for _, v := range doc.Vectors {
		v := v
		t.Run(v.ID, func(t *testing.T) {
			res := ValidateLabel(v.IR)
			if res.OK != v.Expected.OK || res.Level != v.Expected.Level {
				t.Fatalf("判定不符：期望 ok=%v level=%s，实得 ok=%v level=%s（issues=%v）",
					v.Expected.OK, v.Expected.Level, res.OK, res.Level, res.Issues)
			}
			if !sameStringSet(res.Missing, v.Expected.Missing) {
				t.Fatalf("缺项不符：期望 %v，实得 %v", v.Expected.Missing, res.Missing)
			}
			if len(res.Warnings) != v.Expected.Warnings {
				t.Fatalf("warning 数不符：期望 %d，实得 %d", v.Expected.Warnings,
					len(res.Warnings))
			}
		})
	}
}

func sameStringSet(a, b []string) bool {
	if len(a) != len(b) {
		return false
	}
	seen := map[string]int{}
	for _, x := range a {
		seen[x]++
	}
	for _, y := range b {
		seen[y]--
		if seen[y] < 0 {
			return false
		}
	}
	return true
}
