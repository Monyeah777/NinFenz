# 失败考古（FAILURE ARCHAEOLOGY，§4A R4）

> ⛔ 操作指令：本件是 §4A R4 失败考古的人读结果；机读真源 `results/reverse/failures.json`（`nf-reverse-failures/1`），判据 `desktop/tests/test_reverse_failures.py`（**引用 commit 必须真实存在、skip 计数实时重算**）。失败模式→触发→现有防护→缺口→测试建议；缺口进 R6。
> 状态：v1（2026-11-14 · G0 §4A R4）· 前置：`COUPLING.md`（R3）、`BEHAVIOR.md`（R2）

## 1. 统计（2026-11-14）

| 项 | 值 |
|---|---|
| 窗口止于 `31ce09a61` 的近 400 提交中 fix/hotfix/security/refreeze/修复 命中 | 48 |
| 近 600 提交中 revert | 1（`5ee793678` 回到全绿主干） |
| 测试面 skip 文件（环境条件） | 29 |
| 文档已知坑段（AGENTS.md 等） | 4 类 |

## 2. 失败模式（13 项）

| 编号 | 模式 | 类别 | 触发 | 现有防护 | 缺口 | 状态 |
|---|---|---|---|---|---|---|
| F-01 | CI 假绿：`| tee` 未开 pipefail | 默认放行 | 管道吞失败 | 全链路 pipefail | R4-01 无机检 | covered |
| F-02 | required-skip 放行盲区 | 默认放行 | required job 被 skip | gate always + 显式依赖 | R4-02 | covered |
| F-03 | upload-artifact 漏隐藏件 | CI/供应链 | `.*` 被默认排除 | 非隐藏命名 + 契约 | R4-03 | partial |
| F-04 | runner 拉包 403 假红 | 环境 | 网络瞬断 | Acquire::Retries=3 | — | covered |
| F-05 | Docker 基座未钉 digest | CI/供应链 | 镜像漂移 | digest 固定 | — | covered |
| F-06 | 冻结行数上限上调未评审 | 契约错 | 扩面上限抬高 | 评审 + 提交说明 | R4-04 无机器记录 | partial |
| F-07 | SAST 漂移只比总数 | 契约错 | 键级漂移 | 逐键比对 | R4-05 其他 ratchet 未核 | partial |
| F-08 | 存档许可/失效引用错误 | 证据 | 对外面与仓内不一致 | 契约判据 + 许可审计 | — | covered |
| F-09 | verify_report 基准日漂移 | 证据 | 当天日期构建 | 提交件基准日 | — | covered |
| F-10 | 死链/坏链/活文档漂移 | 文档 | 导航面引用不存在 | 链接判据 + 路由契约 | R4-06 | covered |
| F-11 | 路径逃逸「虚假保证」 | 边界 | ../、符号链接、大小写 | validate_path + 负例 | R4-07 5 处变体 | partial |
| F-12 | 生成区手改 / 重算未重批准 / 译件不同步 | 契约错 | 误改生成物/漏 approve/漏 locales | 纪律 + 自动失效 + 重签 | R4-08 前两条靠人读 | partial |
| F-13 | 未跑完写成全绿（台账造假） | 证据 | check12 超时 | 三件套取证纪律 | R4-09 无机检 | partial |

## 3. 文档与代码不一致（DoD ≥3，本件 5 条）

| 编号 | 不一致 | 证据 | 处置 | 状态 |
|---|---|---|---|---|
| INC-01 | 曾写「路径逃逸被 validatePath 拦截」而实现不存在 | `AGENTS.md`、`core/paths.py` | 只写真实载体（已落） | fixed |
| INC-02 | 重算后批准失效，但顺序未由 schema 强制 | `docs/release.md`、`release_gate.py` | 写入 release_policy + 判据 | mitigated |
| INC-03 | docs/ 混放生成物/冻结件/普通文档，误改风险 | `AGENTS.md`、`docs/verification-cards.md` | 生成器 + 等价判据 + 冻结摘要 | mitigated |
| INC-04 | 译件需三处同步，漏一处即过期 | `protocol/locales.json`、`locales.py` | source_sha256 过期判据 + check34 | mitigated |
| INC-05 | skip 面可能掩盖失败（28 文件为环境条件） | `test_attest.py`、`test_cross_lang_matrix.py` | 必须写理由；关键面另设必跑门禁 | mitigated |

## 4. 缺口（R4-01…R4-09，全部进 R6 不变量候选）

CI pipefail 机检、skip 等价判据、隐藏件命名、基线上调评审记录、其他 ratchet 键级比对、生成区链接判据、路径包含性 5 处变体、生成区手改/重批准纪律、PASS 声明与执行对应。

## 5. 复核命令

```bash
python -m pytest desktop/tests/test_reverse_failures.py -q
git log -400 --oneline | grep -icE "fix|hotfix|security|修复|refreeze|revert"
grep -rl "skipif\|@unittest.skip\|xfail" desktop/tests --include="*.py" | wc -l
```

## 6. 交接（R5–R6）

- R5 同行对照：只作机制借鉴（STRATEGY §3），重点借「CI 假绿/漂移/供应链」检测机制。
- R6：R4-01…R4-09 + R3 C-01…C-03 + R1 G-01…G-05 → 机检不变量与反例（每条要么有测试要么 `UNOBSERVABLE`）。
