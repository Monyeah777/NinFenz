# protocol/generated/test_vectors/ · 跨语言契约向量（P-C1 起）

> 用途：跨语言契约对拍（scripts/cross_lang_verify.py）的**黄金向量**。
> 与 protocol/generated/ 的其它件不同：这些不是 schema 派生件，而是**规范派生的手写契约**；
> 生成器留在内部档案 .rivet/private_archive/gen_cross_lang_vectors.py（本仓纪律：计划期工具不入公开面，产物入库）。

## 清单（schema nf-test-vectors/1）

| 文件 | 内容 | 判据 |
|---|---|---|
| harness.json | P-C0 走通件：算术自证 + 工具链探针（probe 只探在场，不比对输出） | 结构形状 |
| jcs_basic.json | P-C1 单条真契约向量（jcs_conformance 的子集） | 三实现逐字节 |
| jcs_conformance.json | 8 条 JCS 正例（键序 / ES 数字形态 / 最小转义 / 嵌套排序） | 三实现逐字节 |
| jcs_reject.json | 6 条 L4 负例（重复键 / 尾随逗号 / 前导零 / 非有限数 / 孤立代理 / 尾随内容） | 三实现均须非零退出且无标准输出 |
| ratchet.json | 覆盖棘轮基线：各实现覆盖的 spec_clause 集合（只增不减，§16.3） | 常驻判据 |
| jcs_input.json 等 | 输入夹具（生成器产出，勿手改） | — |

## 向量字段

    id           向量标识（清单内唯一；jcs_basic 刻意与 conformance 同名——它是子集）
    spec_clause  绑定的规范条款（RFC 8785 §x.y）；覆盖棘轮按它计数
    level        L0 结构 / L1 规范字节 / L2 数值等价 / L3 语义等价 / L4 对抗
    input        输入夹具（仓库相对路径）
    compare_rule byte（折 CRLF 后逐字节）| jcs（用 RFC 8785 本体归一后比）
    expect       ok | fail（fail = 各实现都必须非零退出且无标准输出）
    expected     ok 时的期望文本
    langs        {python|rust|csharp: {cmd: [...], build: [...]?}}

## 工具链与产物姿态

- 语言的键就是**工具链声明**，cmd[0] 只是称呼——对拍器会把首元素换成解析到的可执行文件
  （本机 cargo/dotnet 常不在 PATH；且 PATH 上可能有"有宿主无 SDK"的 dotnet 壳，故解析按
  "真跑一次探针"判可用）；
- Rust / C# 侧需先构建：构建步骤由向量的 build 字段声明（失败 = FAIL，exe 缺席 = UNKNOWN）；
- 常驻判据（desktop/tests/test_cross_lang_matrix.py）**不构建**：产物缺席即 skip（照 test_rust_fastlane 的既有纪律）。

## 与 D-10 的边界

仓库内部口径是 **nf-canonical/1**（键按码点序，整数浮点保留 .0），**不是** RFC 8785。
两者用**规则名**分开：scripts/jcs.py --rule nf 是内部口径，--rule jcs 是 RFC 8785。
本目录的向量一律走 jcs 规则；内外部口径的分歧本身由 desktop/tests/test_jcs_spec_gap.py 钉死。
内部口径**不得**对外当 RFC 8785 承诺。
