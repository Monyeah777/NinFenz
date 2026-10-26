# 内容件样例（干净）

> 用途：`desktop/tests/fixtures/security/` 下的**干净**样本（扫描器零 findings 的基线件）。
> 本件属显式测试样本白名单（`content_security.TEST_SAMPLE_ALLOWLIST`），但内容本身不含恶意片段。

## 1. 正常正文

这是一份用于回归测试的普通内容件：标题、段落、表格、围栏代码块齐备。

| 字段 | 说明 |
|---|---|
| 来源 | 本仓自撰（2026-10-26） |
| 用途 | 扫描器「干净件 0 findings」判据 |

### 1.1 围栏代码块（成对）

```text
普通示例文本：调用接口前先校验输入。
```

- 外部链接用 https 且写真实域名：<https://github.com/Monyeah777/NinFenz>
- 不写明文凭据、不写可执行片段、不写超长单行。

## 2. 结论

本件应被扫描器判为 0 findings（无 critical / 无 warn / 无不可判定）。
