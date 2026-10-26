# 内容件样例（显式测试样本 · 合成 PII）

> 用途：`desktop/tests/fixtures/privacy/` 下的**合成**样本 —— 自证扫描器抓得住 PII。
> 本路径在 `privacy_scan.TEST_SAMPLE_ALLOWLIST` 内：默认扫描**跳过并登记**，显式传参扫描时
> findings 仍逐条报出（`allowlisted: true`）但不计入退出码。
> 本件只含**保留域**合成邮箱（example.org）；真实 PII/本机路径/凭据样本由单测在临时目录
> **拼接构造**（仓库内不留真实形态串，避免撞 `test_leak_surface` 与本门禁自身）。

## 1. 合成邮箱（保留域 → 判 warn）

- 合规联系人：compliance@example.org
- 数据保护官：dpo@example.org

## 2. 判据落点

上述邮箱命中的是 `pii_email`（保留域 → `warn`）；若换成非保留域的真实邮箱则判 `critical`。
细节见 `docs/security/airgap-and-privacy.md`。
