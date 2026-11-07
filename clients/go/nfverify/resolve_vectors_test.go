package nfverify

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

// TestResolveVectors cc_resolve：夹具目录 + 声明件 → 认领契约集必须逐例相符。
func TestResolveVectors(t *testing.T) {
	doc := readVectorDoc(t, "NF_RESOLVE_VECTORS", "resolve_contract_vectors.json")
	vectors := asList(doc["vectors"])
	if len(vectors) == 0 {
		t.Fatal("向量集为空")
	}
	for _, rawVec := range vectors {
		vec := asMap(rawVec)
		t.Run(asString(vec["id"]), func(t *testing.T) {
			root := t.TempDir()
			for _, rawFile := range asList(vec["files"]) {
				rel := asString(rawFile)
				full := filepath.Join(root, filepath.FromSlash(rel))
				if err := os.MkdirAll(filepath.Dir(full), 0o755); err != nil {
					t.Fatalf("建目录失败：%v", err)
				}
				if err := os.WriteFile(full, []byte("x"), 0o600); err != nil {
					t.Fatalf("落盘失败：%v", err)
				}
			}
			declPath := filepath.Join(root, "decl.json")
			declBody, err := json.Marshal(vec["decl"])
			if err != nil {
				t.Fatalf("声明序列化失败：%v", err)
			}
			if err := os.WriteFile(declPath, declBody, 0o600); err != nil {
				t.Fatalf("声明落盘失败：%v", err)
			}
			res, err := ResolveWithDecl(root, declPath, asString(vec["object"]))
			if err != nil {
				t.Fatalf("resolve 失败：%v", err)
			}
			want := asMap(vec["expected"])
			ids := make([]string, 0, len(res.Contracts))
			for _, c := range res.Contracts {
				ids = append(ids, c.ID)
			}
			wantIDs := []string{}
			for _, rawID := range asList(want["ids"]) {
				wantIDs = append(wantIDs, asString(rawID))
			}
			if !sameStringSet(ids, wantIDs) {
				t.Fatalf("认领集不符：期望 %v，实得 %v", wantIDs, ids)
			}
			if res.ClosureClosed != want["closure_closed"].(bool) {
				t.Fatalf("closure_closed 不符：期望 %v，实得 %v", want["closure_closed"],
					res.ClosureClosed)
			}
			if res.Unclaimed != want["unclaimed"].(bool) {
				t.Fatalf("unclaimed 不符：期望 %v，实得 %v", want["unclaimed"], res.Unclaimed)
			}
		})
	}
}
