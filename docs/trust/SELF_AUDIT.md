# Trust Fabric 自审计（G1 收口）
> ⛔ 操作指令：本件由自扫描生成（机器可读件 results/trust/SELF_AUDIT.json 是同批真源）；复核命令在文末，勿当资料阅读。
> 状态：G1 收口报告（2026-11-14）· 上位：`docs/trust/THREAT_MODEL.md` 与 `results/trust/CLAIM_MATRIX.md`
> ⚠️ 边界：本报告只证明「在给定扫描规则下，trust 面没有已知 P0 / 未过分声明 / 判据可复核」；**不是**认证、合规或「不可抵赖」背书。
> 最后更新：2026-11-14 · 复核：`python scripts/trust_self_audit.py --check`（与机器可读件逐字段一致）

## 结论（G1 退出判据）

| 判据 | 结果 | 证据 |
|---|---|---|
| P0 = 0 | ✅ | `stop.p0 = 0`；S1/S2/S3/S7/S8/S10 全绿 |
| P1 全部有 owner（或已修） | ✅ 4 条 TODO 有 owner + 1 条已修 | `stop.p1_open_with_owner = 4`；`findings` |
| UNSUPPORTED claims = 0 | ✅ | `stop.claims_unsupported = 0`；CLAIM_MATRIX 无 UNSUPPORTED |
| 单 claim 验证 O(log n) | ✅ | `test_trust_bundle.py`（只读一条 claim + proof 长度 ≤ log n） |
| 删除/重排矩阵 | ✅ | `test_trust_bundle.py` / `test_trust_process.py` 篡改矩阵 |
| check45 接线 | ✅ | `verify.sh` check45；`test_trust_gate45.py` 变异必红 |
| 静态全量门禁 | ✅ | `bash verify.sh --checks-only` PASS=77 WARN=2 FAIL=0 |
| .NET parity | ⚠️ 未跑 | 本机无 .NET SDK（BASELINE ENV-01），如实记录不写 ok |

## 维度体检（S0–S12）

| 维度 | 状态 | 判据 / 证据 |
|---|---|---|
| S0_requirements | amber | FR/NFR 已落地部分有代码+测试；claim #16（DSSE/PAE）已随 WP-20 转 SUPPORTED；剩 4 条 TODO（删尾/typed entity/model card/跨语言 parity）留 G2–G4，均有 owner |
| S1_code_holes | green | trust 路径 TODO/FIXME/NotImplemented/pass 命中 0 |
| S2_judgement_holes | green | 裸 except 0；默认放行形状 0（本轮修掉 2 处 `policy_ok` 缺省 True，见 F-001） |
| S3_crypto | green | 无 md5/sha1/random/time.time/datetime.now；摘要统一 SHA-256 |
| S4_chain_order | green | bundle Merkle 根/包含证明 + nf-process/1 prev 链删除/重排负例 |
| S5_types_compat | green | 7 件 schema 未知字段/封闭词表负例；schema 名带 /1 版本 |
| S6_test_gaps | amber | 属性测试/模糊测试未接（P2，owner 已登记） |
| S7_doc_overclaim | green | trust 文档禁用词命中全部为否定/边界语境（自扫描分类） |
| S8_deps | green | trust 面 import 仅 stdlib + core（自扫描用 sys.stdlib_module_names 判定） |
| S9_path_dos | green | proof 深度上限 64、schema maxItems、无路径穿越面（纯函数） |
| S10_privacy | green | 证据只含摘要/相对路径；无密钥/令牌标记 |
| S11_observability | green | 错误消息带修复指引；`nf-verify/1` 缺项码 + exit 0/1/2 |
| S12_unknown | amber | 红队角色剩 4 个未跑；跨语言 parity 留 G4（P2，owner 已登记） |

## 发现清单（P0/P1/P2）

| ID | 维度 | 级别 | 状态 | 证据 | 修复 / 归属 |
|---|---|---|---|---|---|
| F-001 | S2_judgement_holes | P1 | fixed | gate.py 与 trust_vectors.py 的 level 判定用 `case.get("policy_ok", True)` 缺省放行 | 改显式布尔（缺失即拒）；`test_trust_gate45.py` |
| F-002 | S0_requirements | P1 | open | claim #15 删尾检测 TODO（G2） | 链头签名 + RFC3161 锚；owner Monyeah777（维护者） |
| F-003 | S0_requirements | P1 | open | claim #18 typed entity 组合面 TODO（G3） | 类型注册表 + 组合 admissibility；owner 同上 |
| F-004 | S0_requirements | P1 | open | claim #19 model card 绑定 TODO（G3） | `nf-model-card/1` 与 AI 证据绑定；owner 同上 |
| F-005 | S0_requirements | P1 | open | claim #21 跨语言 parity TODO（G4） | Go/.NET 独立 verifier 跑同一向量集；owner 同上 |
| F-006 | S6_test_gaps | P2 | open | 属性测试/模糊测试未接 | G2 前补随机 bundle/链篡改不变量；owner 同上 |
| F-007 | S12_unknown | P2 | open | 红队角色剩 4 个未跑 | 按轮次轮换并写入威胁模型；owner 同上 |
| F-008 | S12_unknown | P2 | open | 跨语言 parity 未接 | G4 补独立 verifier；owner 同上 |

## 本轮扫描命令（可复跑）

```bash
python scripts/trust_self_audit.py --check          # 机器件与重算逐字段一致（忽略 head/scanned_at）
python scripts/trust_self_audit.py --write          # 重扫并写机器件
grep -RInE 'TODO|FIXME|NotImplemented' desktop/src/core/trust scripts/trust_*.py
grep -RInE 'md5|sha1|random\.|time\.time|datetime\.now' desktop/src/core/trust
python -m pytest desktop/tests/test_trust_self_audit_contract.py -q
```

## 不改写的历史结论

- 本报告不回溯改 G0 的 `results/trust/BASELINE.md` 判定；基线是**审计当时**的实读，后续状态以本报告与各阶段交接为准。
- 本版按 G2/WP-20 更新：claim #16（DSSE/PAE）已转 SUPPORTED（`trust/dsse.py` + `test_trust_dsse.py`），对应 P1 从 5 条降为 4 条。
- 「全量 bash verify.sh（3100+ 测试）」本轮未跑，如实记；静态面全量与受影响面全量分别取证（见上表与各 WP 记录）。CI 的 full 档是唯一发布结论口径。
