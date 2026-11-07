package nfverify

import (
	"encoding/base64"
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

func readVectorDoc(t *testing.T, env, name string) map[string]any {
	t.Helper()
	var path string
	if p := os.Getenv(env); p != "" {
		path = p
	} else {
		for _, cand := range []string{
			filepath.Join("..", "..", "..", "results", "ccos", name),
			filepath.Join("..", "..", "results", "ccos", name),
		} {
			if _, err := os.Stat(cand); err == nil {
				path = cand
				break
			}
		}
	}
	if path == "" {
		t.Skipf("找不到向量集 %s（用 %s 指定）", name, env)
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("读向量集失败：%v", err)
	}
	var doc map[string]any
	if err := json.Unmarshal(raw, &doc); err != nil {
		t.Fatalf("向量集不是合法 JSON：%v", err)
	}
	return doc
}

// TestAttestVectors cc_attest：造信封 + 验信封，判据看 ok / level。
func TestAttestVectors(t *testing.T) {
	doc := readVectorDoc(t, "NF_ATTEST_VECTORS", "attest_envelope_vectors.json")
	vectors := asList(doc["vectors"])
	if len(vectors) == 0 {
		t.Fatal("向量集为空")
	}
	for _, rawVec := range vectors {
		vec := asMap(rawVec)
		t.Run(asString(vec["id"]), func(t *testing.T) {
			data, err := base64.StdEncoding.DecodeString(asString(vec["subject_b64"]))
			if err != nil {
				t.Fatalf("subject_b64 坏：%v", err)
			}
			var key []byte
			if kb := asString(vec["key_b64"]); kb != "" {
				key, err = base64.StdEncoding.DecodeString(kb)
				if err != nil {
					t.Fatalf("key_b64 坏：%v", err)
				}
			}
			env := asMap(vec["envelope"])
			want := asMap(vec["expected"])
			res := VerifyAttestDoc(env, data, key)
			if res.OK != want["ok"].(bool) {
				t.Fatalf("判定不符：期望 ok=%v，实得 %v（issues=%v）", want["ok"], res.OK,
					res.Issues)
			}
			if asString(want["level"]) != res.Level {
				t.Fatalf("强度不符：期望 %v，实得 %s", want["level"], res.Level)
			}
		})
	}
}

// TestReplayVectors cc_replay：轨迹必须可复算（entries / 根 / 链头）。
func TestReplayVectors(t *testing.T) {
	doc := readVectorDoc(t, "NF_REPLAY_VECTORS", "replay_trace_vectors.json")
	vectors := asList(doc["vectors"])
	if len(vectors) == 0 {
		t.Fatal("向量集为空")
	}
	for _, rawVec := range vectors {
		vec := asMap(rawVec)
		t.Run(asString(vec["id"]), func(t *testing.T) {
			bundle, err := base64.StdEncoding.DecodeString(asString(vec["bundle_b64"]))
			if err != nil {
				t.Fatalf("bundle_b64 坏：%v", err)
			}
			want := asMap(vec["expected"])
			res, err := Replay(bundle, Options{})
			if err != nil {
				t.Fatalf("replay 失败：%v", err)
			}
			if res.OK != want["ok"].(bool) {
				t.Fatalf("ok 不符：期望 %v，实得 %v（issues=%v）", want["ok"], res.OK,
					res.Issues)
			}
			if itoa(len(res.Entries)) != asString(want["entries"]) {
				t.Fatalf("entries 不符：期望 %v，实得 %d", want["entries"], len(res.Entries))
			}
			if res.RecomputedRoot != asString(want["root"]) {
				t.Fatalf("重算根不符")
			}
			if res.RecomputedHead != asString(want["head"]) {
				t.Fatalf("重算链头不符")
			}
		})
	}
}
