package nfverify

import (
	"encoding/base64"
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

type checkVector struct {
	ID        string         `json:"id"`
	Desc      string         `json:"desc"`
	ObjectB64 string         `json:"object_b64"`
	ObjectSHA string         `json:"object_sha256"`
	Policy    map[string]any `json:"policy"`
	Expected  map[string]any `json:"expected"`
}

type checkVectorDoc struct {
	Schema  string        `json:"schema"`
	Count   int           `json:"count"`
	Vectors []checkVector `json:"vectors"`
}

func checkVectorFile(t *testing.T) string {
	t.Helper()
	if p := os.Getenv("NF_CHECK_VECTORS"); p != "" {
		return p
	}
	for _, p := range []string{
		filepath.Join("..", "..", "..", "results", "ccos", "check_verdict_vectors.json"),
		filepath.Join("..", "..", "results", "ccos", "check_verdict_vectors.json"),
	} {
		if _, err := os.Stat(p); err == nil {
			return p
		}
	}
	t.Skip("找不到 cc_check 向量集（用 NF_CHECK_VECTORS 指定）")
	return ""
}

// TestCheckVectors 是 Go 侧 cc_check 的合格判据：verdict / failed / warned / 逐条 ok 必须逐例相符。
func TestCheckVectors(t *testing.T) {
	raw, err := os.ReadFile(checkVectorFile(t))
	if err != nil {
		t.Fatalf("读向量集失败：%v", err)
	}
	var doc checkVectorDoc
	if err := json.Unmarshal(raw, &doc); err != nil {
		t.Fatalf("向量集不是合法 JSON：%v", err)
	}
	if len(doc.Vectors) == 0 {
		t.Fatal("向量集为空（判据面被缩小）")
	}
	for _, v := range doc.Vectors {
		v := v
		t.Run(v.ID, func(t *testing.T) {
			data, err := base64.StdEncoding.DecodeString(v.ObjectB64)
			if err != nil {
				t.Fatalf("object_b64 坏：%v", err)
			}
			if v.ObjectSHA != "" && shaHex(data) != v.ObjectSHA {
				t.Fatalf("对象字节与 sha256 记录不符（向量集被改）")
			}
			dir := t.TempDir()
			obj := filepath.Join(dir, "obj.bin")
			if err := os.WriteFile(obj, data, 0o600); err != nil {
				t.Fatalf("落盘失败：%v", err)
			}
			res, err := Check(obj, v.Policy)
			rejected, _ := v.Expected["rejected"].(bool)
			if rejected {
				if err == nil {
					t.Fatalf("坏策略必须被拒绝，却返回了判定 %s", res.Verdict)
				}
				return
			}
			if err != nil {
				t.Fatalf("体检失败：%v", err)
			}
			wantVerdict, _ := v.Expected["verdict"].(string)
			if res.Verdict != wantVerdict {
				t.Fatalf("判定不符：期望 %s，实得 %s（failed=%d warned=%d）",
					wantVerdict, res.Verdict, res.Failed, res.Warned)
			}
			wantCode := int(v.Expected["exit_code"].(float64))
			if ExitCode(res.Verdict) != wantCode {
				t.Fatalf("退出码不符：期望 %d，实得 %d", wantCode, ExitCode(res.Verdict))
			}
			if v.ID == "warn_does_not_flip" && res.Warned == 0 {
				t.Fatalf("warn 面没被记到（warned=0），判据面漏了")
			}
		})
	}
}
