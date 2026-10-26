# 内容件样例（干净）

> 用途：`desktop/tests/fixtures/privacy/` 下的**干净**样本（隐私扫描器零 findings 的基线件）。
> 本件属显式测试样本白名单（`privacy_scan.TEST_SAMPLE_ALLOWLIST`），但内容本身不含 PII、
> 本机路径或凭据。

## 1. 正常正文

这是一份用于回归测试的普通内容件：标题、段落、表格、围栏代码块齐备。

| 字段 | 说明 |
|---|---|
| 来源 | 本仓自撰（2026-10-26） |
| 用途 | 「干净件 0 findings」判据 |

### 1.1 围栏代码块（成对）

```text
普通示例文本：调用接口前先校验输入。
```

- 外部链接用 https 且写真实域名：<https://github.com/Monyeah777/NinFenz>
- 不写真实邮箱/手机号/身份证/银行卡，不写本机绝对路径。

## 2. 结论

本件应被隐私扫描器判为 0 findings（无 critical / 无 warn / 无不可判定）。
