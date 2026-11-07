package nfverify

import (
	"errors"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strings"
)

// cc_resolve 的 Go 侧实现：对象 → 认领它的契约集（方向与「声明 → 文件清单」相反）。
//
// 口径与真源 core/asset_contract.contracts_for_path 对齐：
// - 声明件 protocol/asset_contracts.json，四面（data/code/script/index）；
// - 每条 spec 要么 path（单件）要么 glob（对**受跟踪件**匹配，段级 glob：** 零或多段）；
// - 命中就记 {face, id, files(该 spec 命中件数), digest(spec 的规范 JSON sha256)}；
// - closure_closed / unclaimed **显式出现**：未被认领时必须给 false，不用空数组糊过去。

const ContractDeclRel = "protocol/asset_contracts.json"
const ContractSchema = "nf-asset-contracts/1"
const ResolveSchema = "nf-contract-resolve/1"

var ContractFaces = []string{"code", "data", "index", "script"}

// Contract 命中的一份契约。
type Contract struct {
	Face   string
	ID     string
	Files  int
	Digest string
}

// ResolveResult cc_resolve 输出。
type ResolveResult struct {
	Schema        string
	Object        string
	Contracts     []Contract
	ClosureClosed bool
	Unclaimed     bool
}

// Map 稳定 JSON 面。
func (r *ResolveResult) Map() map[string]any {
	hits := make([]any, 0, len(r.Contracts))
	for _, c := range r.Contracts {
		hits = append(hits, map[string]any{
			"face": c.Face, "id": c.ID, "files": c.Files, "digest": c.Digest,
		})
	}
	return map[string]any{
		"schema": r.Schema, "object": r.Object, "contracts": hits,
		"closure_closed": r.ClosureClosed, "unclaimed": r.Unclaimed,
	}
}

// Resolve 在 repoRoot 里解析 objectRel 该守哪些契约（声明件用默认路径）。
func Resolve(repoRoot, objectRel string) (*ResolveResult, error) {
	return ResolveWithDecl(repoRoot, filepath.Join(repoRoot, ContractDeclRel), objectRel)
}

// ResolveWithDecl 允许指定声明件路径（判据要能指向夹具，不依赖活的仓库声明）。
func ResolveWithDecl(repoRoot, declPath, objectRel string) (*ResolveResult, error) {
	raw, err := os.ReadFile(declPath)
	if err != nil {
		return nil, errors.New("契约声明不可读（修复指引：先跑 nf asset contract --export）")
	}
	doc, errDoc := decodeJSON(raw)
	if errDoc != nil {
		return nil, errors.New("契约声明不是合法 JSON（修复指引：修好语法）")
	}
	decl := asMap(doc)
	if decl == nil || asString(decl["schema"]) != ContractSchema {
		return nil, errors.New("契约声明 schema 不匹配（修复指引：改为声明件当前形态）")
	}
	target := strings.TrimLeft(strings.ReplaceAll(objectRel, "\\", "/"), "/")
	tracked := trackedFiles(repoRoot)
	res := &ResolveResult{Schema: ResolveSchema, Object: target, Contracts: []Contract{}}
	for _, face := range ContractFaces {
		for _, rawSpec := range asList(decl[face]) {
			spec := asMap(rawSpec)
			if spec == nil {
				continue
			}
			files := expandSpec(repoRoot, spec, tracked)
			if !containsString(files, target) {
				continue
			}
			body, errCanon := canonicalJSON(spec)
			if errCanon != nil {
				continue
			}
			res.Contracts = append(res.Contracts, Contract{Face: face,
				ID: asString(spec["id"]), Files: len(files), Digest: shaHex(body)})
		}
	}
	res.ClosureClosed = len(res.Contracts) > 0
	res.Unclaimed = !res.ClosureClosed
	return res, nil
}

func expandSpec(root string, spec map[string]any, tracked []string) []string {
	if p := asString(spec["path"]); p != "" {
		rel := strings.ReplaceAll(p, "\\", "/")
		if info, err := os.Stat(filepath.Join(root, rel)); err == nil && !info.IsDir() {
			return []string{rel}
		}
		return nil
	}
	pat := asString(spec["glob"])
	if pat == "" {
		return nil
	}
	out := []string{}
	if tracked != nil {
		for _, rel := range tracked {
			if MatchRel(rel, pat) {
				out = append(out, rel)
			}
		}
		sort.Strings(out)
		return out
	}
	matches, err := filepath.Glob(filepath.Join(root, filepath.FromSlash(pat)))
	if err != nil {
		return nil
	}
	for _, m := range matches {
		if info, errInfo := os.Stat(m); errInfo == nil && !info.IsDir() {
			if rel, errRel := filepath.Rel(root, m); errRel == nil {
				out = append(out, filepath.ToSlash(rel))
			}
		}
	}
	sort.Strings(out)
	return out
}

// trackedFiles 用 git ls-files 取受跟踪件（与真源同口径：构建产物不算契约面）。
// 失败返回 nil（调用方退回文件系统 glob，不因此中断）。
func trackedFiles(root string) []string {
	out, err := exec.Command("git", "-C", root, "ls-files", "-z").Output()
	if err != nil {
		return nil
	}
	parts := strings.Split(string(out), "\x00")
	rels := make([]string, 0, len(parts))
	for _, p := range parts {
		if p != "" {
			rels = append(rels, p)
		}
	}
	return rels
}

// MatchRel 仓库相对路径是否匹配段级 glob（** 零或多段；* 段内任意；? 单字符；不区分大小写）。
func MatchRel(rel, pattern string) bool {
	segs := splitSegs(rel)
	parts := splitSegs(pattern)
	return matchParts(segs, parts)
}

func splitSegs(s string) []string {
	raw := strings.Split(strings.ReplaceAll(s, "\\", "/"), "/")
	out := make([]string, 0, len(raw))
	for _, part := range raw {
		if part != "" {
			out = append(out, part)
		}
	}
	return out
}

func matchParts(segs, parts []string) bool {
	var step func(si, pi int) bool
	step = func(si, pi int) bool {
		if pi >= len(parts) {
			return si >= len(segs)
		}
		if parts[pi] == "**" {
			if step(si, pi+1) {
				return true
			}
			return si < len(segs) && step(si+1, pi)
		}
		if si >= len(segs) {
			return false
		}
		if !matchSegment(strings.ToLower(segs[si]), strings.ToLower(parts[pi])) {
			return false
		}
		return step(si+1, pi+1)
	}
	return step(0, 0)
}

// matchSegment 单段 glob：* 任意（段内）、? 单字符。
func matchSegment(text, pattern string) bool {
	var match func(ti, pi int) bool
	match = func(ti, pi int) bool {
		for pi < len(pattern) {
			switch pattern[pi] {
			case '*':
				for pi < len(pattern) && pattern[pi] == '*' {
					pi++
				}
				if pi >= len(pattern) {
					return true
				}
				for k := ti; k <= len(text); k++ {
					if match(k, pi) {
						return true
					}
				}
				return false
			case '?':
				if ti >= len(text) {
					return false
				}
				ti++
				pi++
			default:
				if ti >= len(text) || text[ti] != pattern[pi] {
					return false
				}
				ti++
				pi++
			}
		}
		return ti == len(text)
	}
	return match(0, 0)
}
