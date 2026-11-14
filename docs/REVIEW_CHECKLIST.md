# 人工审查清单（REVIEW CHECKLIST）

> ⛔ 操作指令：本件是 §13B.4 CQ-B / §13C.3 人工审查的清单与记录模板；CQ2 起按本件执行，记录落 `results/cq/review-records/`（未建前不得声称已人工审查）。
> 状态：v1（G0 · 2026-11-14）· 依据：`NF-Final-方案-2026-11-13.md` §13B / §13C（IEEE 1028 / ISO 20246 思想）

## 角色与独立性

- 作者（改动者）· 主持人（moderator，仅高风险 inspection）· 审查者（≥1；P0/P1 高风险 ≥2）· 记录员。
- P0/P1 审查者不得是唯一作者；AI reviewer 只作 advisory，不能替代人类签署。
- 冲突利益披露；高风险变更（信任/治理/密钥/链/权限/MCP）用 **Inspection**（记录+分级+签署），其余可走 Technical review / Walkthrough。

## 入口 / 出口

- 入口：小 CL（建议 ≤400 行有效 diff）、自审、测试绿、契约/ADR/文档就绪、风险标签。
- 出口：P0/P1 清零或有 owner/ACCEPTED-RISK；测试补充；记录归档；签署。

## 每类工件清单

### Python（desktop/src、scripts/）

- [ ] 输入校验：外部输入/文件路径/JSON 字段先校验后使用；未知字段 fail-closed。
- [ ] 异常：不吞错（裸 `except: pass` 零容忍）；错误消息带修复指引。
- [ ] 路径/写入：`core.paths.validate_path`；写入用原子写；不越界。
- [ ] 并发/资源：文件/进程/临时目录释放；超时与上限；不 TOCTOU。
- [ ] 日志/证据：不写秘密/正文；只存 digest/相对路径。
- [ ] 复杂度：新函数 CC≤15、长度≤200；存量热点登记（`docs/QUALITY_DEBT.md`）。
- [ ] 测试：新分支有测试；负例/变异能红；断言独立于实现。

### Rust / .NET（engine/）

- [ ] unsafe/边界/panic；错误传播；FFI 互操作；依赖固定。
- [ ] nullability/async/异常；分析器；与 Python 侧计数同步（parity）。

### Shell / CI（verify.sh、.github/）

- [ ] 引用/退出码/pipefail；权限最小化；action 钉 SHA；秘密不进日志；不可信 PR 不跑秘密。

### Schema / 契约（protocol/）

- [ ] 兼容性：未知必填拒绝、未知可选透传；版本化；正/反样例；示例可解析。

### 文档（docs/、README、site、llms.txt）

- [ ] 命令实测；声明有代码/测试锚点；禁用词只在否定语境；链接在场。

## 审查记录模板

```json
{
  "review_id": "RV-YYYYMMDD-01",
  "type": "inspection|technical|walkthrough|management|audit",
  "change": "<commit/文件清单>",
  "participants": ["author", "reviewer1", "reviewer2"],
  "checklist": ["python", "schema"],
  "findings": [{"id": "F-001", "severity": "P1", "file": "x.py", "line": 10,
                 "evidence": "...", "fix": "...", "status": "open"}],
  "disposition": "approved|changes-requested",
  "signed_by": "<human>"
}
```

## 门禁与产物

- CQ2 起每条 P0/P1 变更必须有本清单记录；记录归档后由 `test_cq_scan_contract.py` 校验结构（记录目录未建时不得自称已审查）。
- 人工审查抽样与工具效度（precision/recall）登记在 `results/cq/measurement-validity.md`（CQ6）。
