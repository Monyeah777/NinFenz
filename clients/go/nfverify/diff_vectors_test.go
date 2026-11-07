package nfverify

import (
	"encoding/json"
	"os"
	"testing"
)

// TestDiffVectors cc_diff：impact / verdict / 差异指针集必须逐例相符。
func TestDiffVectors(t *testing.T) {
	doc := readVectorDoc(t, "NF_DIFF_VECTORS", "diff_delta_vectors.json")
	vectors := asList(doc["vectors"])
	if len(vectors) == 0 {
		t.Fatal("向量集为空")
	}
	for _, rawVec := range vectors {
		vec := asMap(rawVec)
		t.Run(asString(vec["id"]), func(t *testing.T) {
			a, errA := json.Marshal(vec["a"])
			b, errB := json.Marshal(vec["b"])
			if errA != nil || errB != nil {
				t.Fatalf("文档序列化失败：%v %v", errA, errB)
			}
			res, err := DiffJSON(a, b)
			if err != nil {
				t.Fatalf("diff 失败：%v", err)
			}
			want := asMap(vec["expected"])
			if res.Impact != asString(want["impact"]) {
				t.Fatalf("impact 不符：期望 %v，实得 %s", want["impact"], res.Impact)
			}
			if res.Verdict != asString(want["verdict"]) {
				t.Fatalf("verdict 不符：期望 %v，实得 %s", want["verdict"], res.Verdict)
			}
			wantChanges := asList(want["changes"])
			if len(wantChanges) != len(res.Changes) {
				t.Fatalf("差异条数不符：期望 %d，实得 %d", len(wantChanges), len(res.Changes))
			}
			for i, rawChange := range wantChanges {
				wc := asMap(rawChange)
				if res.Changes[i].Pointer != asString(wc["pointer"]) ||
					res.Changes[i].Kind != asString(wc["kind"]) {
					t.Fatalf("第 %d 条差异不符：期望 %v/%v，实得 %s/%s", i+1,
						wc["pointer"], wc["kind"], res.Changes[i].Pointer, res.Changes[i].Kind)
				}
			}
		})
	}
}

var _ = os.Getenv
