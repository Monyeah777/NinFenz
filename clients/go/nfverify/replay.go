package nfverify

import "encoding/hex"

const ReplaySchema = "nf-replay/1"

// ReplayStep 一步复算（trace 不含时间戳：同输入两次逐字节一致）。
type ReplayStep struct {
	Step    string
	Rule    string
	Subject string
	Input   string
	Output  string
}

// ReplayEntry 一个成员的复算轨迹。
type ReplayEntry struct {
	Path   string
	Digest string
	Leaf   string
	Steps  []ReplayStep
}

// ReplayResult cc_replay 的输出：把每一成员的「字节 → sha256 → 叶 → 折叠」逐算出来。
type ReplayResult struct {
	Schema         string
	Kind           string
	Entries        []ReplayEntry
	RecomputedRoot string
	RecomputedHead string
	OK             bool
	Issues         []string
}

// Map 稳定 JSON 面。
func (r *ReplayResult) Map() map[string]any {
	entries := make([]any, 0, len(r.Entries))
	for _, e := range r.Entries {
		steps := make([]any, 0, len(e.Steps))
		for _, s := range e.Steps {
			steps = append(steps, map[string]any{
				"step": s.Step, "rule": s.Rule, "subject": s.Subject,
				"input": s.Input, "output": s.Output,
			})
		}
		entries = append(entries, map[string]any{
			"path": e.Path, "digest": e.Digest, "leaf": e.Leaf, "steps": steps,
		})
	}
	return map[string]any{
		"schema": r.Schema, "kind": r.Kind, "entries": entries,
		"recomputed_root": r.RecomputedRoot, "recomputed_head": r.RecomputedHead,
		"ok": r.OK, "issues": r.Issues,
	}
}

// Replay 对证据容器做「可重放轨迹」：逐成员算字节摘要、叶、包含证明折叠与链头。
// ok = 每一步都复算得出且与记录一致（篡改必在叶/折叠处断掉）。
func Replay(data []byte, opts Options) (*ReplayResult, error) {
	src, err := openZip(data)
	if err != nil {
		return nil, err
	}
	res := &ReplayResult{Schema: ReplaySchema, Kind: "bundle", Issues: []string{}}
	doc := parseDoc(src.read(BundleEntry))
	if doc == nil || asString(doc["schema"]) != EvidenceSchema {
		return nil, UsageError
	}
	entries := mapList(doc["entries"])
	payloads := map[string][]byte{}
	leaves := [][]byte{}
	for _, e := range entries {
		rel, errRel := safeRel(firstNonEmpty(asString(e["path"]), asString(e["id"])))
		if errRel != nil {
			res.Issues = append(res.Issues, errRel.Error())
			continue
		}
		payloads[rel] = src.find(rel)
		item := ReplayEntry{Path: rel}
		data := payloads[rel]
		if data == nil {
			res.Issues = append(res.Issues, "缺 payload："+rel)
			continue
		}
		digest := shaHex(data)
		item.Digest = digest
		item.Steps = append(item.Steps, ReplayStep{
			Step: "digest", Rule: "sha256", Subject: rel, Input: "bytes",
			Output: digest})
		leaf := leafOf(rel, digest)
		item.Leaf = hex.EncodeToString(leaf)
		item.Steps = append(item.Steps, ReplayStep{
			Step: "leaf", Rule: "rfc6962-leaf", Subject: rel + " + " + digest,
			Output: item.Leaf})
		folded := hex.EncodeToString(foldLeaf(leaf, asList(e["proof"])))
		item.Steps = append(item.Steps, ReplayStep{
			Step: "proof", Rule: "inclusion-fold", Subject: rel, Output: folded})
		if folded != asString(doc["root"]) {
			res.Issues = append(res.Issues, "折叠不到根："+rel)
		}
		if item.Leaf != asString(e["leaf"]) {
			res.Issues = append(res.Issues, "叶与记录不符："+rel)
		}
		if digest != asString(e["digest"]) {
			res.Issues = append(res.Issues, "摘要与记录不符："+rel)
		}
		leaves = append(leaves, leaf)
		res.Entries = append(res.Entries, item)
	}
	res.RecomputedRoot = hex.EncodeToString(merkleRoot(leaves))
	res.RecomputedHead = chainHead(entries)
	if res.RecomputedRoot != asString(doc["root"]) {
		res.Issues = append(res.Issues, "重算根与记录不符")
	}
	if res.RecomputedHead != asString(asMap(doc["chain"])["head"]) {
		res.Issues = append(res.Issues, "重算链头与记录不符")
	}
	res.OK = len(res.Issues) == 0
	return res, nil
}
