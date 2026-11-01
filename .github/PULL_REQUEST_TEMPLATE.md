## 改动域（勾选）
- [ ] 协议层（01–07 / 08 / 09 方案）——是否触发 01 §7 V2 bump：是 / 否
- [ ] 代码层（desktop/ scripts/）——desktop 只有 core + tests + scripts；GUI 端壳已于 2026-09-09 退役移出
- [ ] 社区领域包 community/
- [ ] 工程治理（docs/meta/ROADMAP.md / CHANGELOG / CONTRIBUTING / .github / verify.sh）

## 门禁自检（提交前全过）
- [ ] `bash verify.sh` → PASS / WARN / FAIL
- [ ] `cd desktop && python3 -m unittest discover -s tests -q` → Ran N tests
- [ ] `python3 -m compileall -q desktop/src scripts`
- [ ] `changes/unreleased/<日期或主题>.md` 已写（`type:` / `note:` 两行——发布收口由 `nf release` 归档进 CHANGELOG，不再手改 CHANGELOG）

## 贡献者条款
- [ ] 提交已 `git commit -s` 签署 DCO（`Signed-off-by:`；见 CONTRIBUTING 贡献者条款）

## 变更摘要
（一句话 + 关键文件列表）

## 关联 Issue
Fixes # / Closes #
