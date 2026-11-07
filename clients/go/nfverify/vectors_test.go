package nfverify

import (
	"encoding/base64"
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

// 向量集：与真源、零依赖 Python 复验器共用的同一份 JSON。
// 路径可用 NF_VECTORS 覆盖（CI/异机复验时指到别处）。
func vectorFile(t *testing.T) string {
	t.Helper()
	if p := os.Getenv("NF_VECTORS"); p != "" {
		return p
	}
	candidates := []string{
		filepath.Join("..", "..", "..", "results", "ccos", "evidence_verdict_vectors.json"),
		filepath.Join("..", "..", "results", "ccos", "evidence_verdict_vectors.json"),
	}
	for _, p := range candidates {
		if _, err := os.Stat(p); err == nil {
			return p
		}
	}
	t.Skipf("找不到向量集（用 NF_VECTORS 指定）：%v", candidates)
	return ""
}

type vector struct {
	ID         string         `json:"id"`
	Desc       string         `json:"desc"`
	BundleB64  string         `json:"bundle_b64"`
	BundleSHA  string         `json:"bundle_sha256"`
	Expected   map[string]any `json:"expected"`
	KeyB64     string         `json:"key_b64"`
	At         string         `json:"at"`
	Special    string         `json:"special"`
	Revocations map[string]any `json:"revocations"`
	Anchor     map[string]any  `json:"anchor"`
}

type vectorDoc struct {
	Schema  string   `json:"schema"`
	Count   int      `json:"count"`
	Vectors []vector `json:"vectors"`
}

// TestVectorsConformance 是这套 Go 实现的**唯一**合格判据：向量集逐条的判定与退出码必须相符。
// 它证明「同一份证据，Go 侧与 Python 侧得出同一结论」——ABI 不绑定语言。
func TestVectorsConformance(t *testing.T) {
	raw, err := os.ReadFile(vectorFile(t))
	if err != nil {
		t.Fatalf("读向量集失败：%v", err)
	}
	var doc vectorDoc
	if err := json.Unmarshal(raw, &doc); err != nil {
		t.Fatalf("向量集不是合法 JSON：%v", err)
	}
	if len(doc.Vectors) == 0 {
		t.Fatal("向量集为空（判据面被缩小）")
	}
	for _, v := range doc.Vectors {
		v := v
		t.Run(v.ID, func(t *testing.T) {
			bundle, err := base64.StdEncoding.DecodeString(v.BundleB64)
			if err != nil {
				t.Fatalf("bundle_b64 坏：%v", err)
			}
			if v.BundleSHA != "" && shaHex(bundle) != v.BundleSHA {
				t.Fatalf("bundle 字节与 sha256 记录不符（向量集被改）")
			}
			opts := Options{Revocations: v.Revocations, Anchor: v.Anchor, At: v.At}
			if v.KeyB64 != "" {
				key, err := base64.StdEncoding.DecodeString(v.KeyB64)
				if err != nil {
					t.Fatalf("key_b64 坏：%v", err)
				}
				opts.Key = key
			}
			res, err := VerifyAny(bundle, opts)
			wantVerdict, _ := v.Expected["verdict"].(string)
			wantCode := int(v.Expected["exit_code"].(float64))
			gotCode := 0
			gotVerdict := "invalid"
			if errorsIsUsage(err) {
				gotCode = 4
			} else if err != nil {
				gotCode = 1
				gotVerdict = "invalid"
			} else {
				gotVerdict = res.Verdict
				gotCode = ExitCode(res.Verdict)
			}
			if gotVerdict != wantVerdict || gotCode != wantCode {
				t.Fatalf("判定不符：期望 %s/%d，实得 %s/%d（issues=%v）",
					wantVerdict, wantCode, gotVerdict, gotCode,
					func() []string {
						if res == nil {
							return nil
						}
						return res.Issues
					}())
			}
		})
	}
}

func errorsIsUsage(err error) bool {
	return err != nil && err == UsageError
}
