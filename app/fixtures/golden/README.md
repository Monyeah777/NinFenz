# golden 夹具（Rust 参考实现生成，Python/Android/Desktop 复核）

契约：app/docs/CONTRACT.md `10、app/docs/CLI.md `6。本目录是逐字节回归真源：Python app/tests/test_golden.py 与 Kotlin/Desktop 测试都按这里的 request.json + expected.json 对拍。

## 生成

从 app/core 运行（release 二进制即可）：

~~~bash
cd app/core
cargo run --release -- golden-gen --out ../fixtures/golden
# 或从仓库根：
./app/core/target/release/nf-app-core.exe golden-gen --out app/fixtures/golden
~~~

golden-gen 是隐藏子命令：会重写本目录（fixtures/ + golden/）。它是确定性的——同一二进制连续跑两次产物逐字节一致（tests/golden.rs::golden_regeneration_matches_committed 会重生成到临时目录并与本目录全量比对）。

## 复核

~~~bash
cd app/core
cargo test --offline --test golden
~~~

逐 case 用 nf-app-core <op> --in - 跑 request.json，断言：进程退出码 == expected.json 的信封 exit；stdout 逐字节 == expected.json。expected.json = CLI 响应信封的 canonical 字节 + 单个 LF。

## 布局

~~~text
app/fixtures/golden/
  fixtures/                 # 手写最小输入（无随机、无时间戳）
    import/sample.{md,txt,yaml,json,html}
    protocol/demo-protocol.json
    graph/{demo-graph,cycle-graph}.json
    spec/demo-spec.json
    project/demo-project.json
    pack-v1/ pack-v2/ pack-v1-tampered/     # 含 nf-pack.json（tree 由核心算）
    overlay/demo-overlay.json
  golden/<case>/
    meta.json               # {"op": "...", "case": "..."}
    request.json            # 请求体原样 JSON（负例含 float，故不按 canonical 写）
    expected.json           # 响应信封 canonical 字节 + LF
~~~

27 个 case：canonical(+float 负例)、pack-hash、pack-verify(+tampered 负例)、import-sniff、import-markdown/yaml、import-unsupported(负例)、map-suggest、protocol-validate/render、graph-validate(+cycle 负例)、graph-compile、spec-validate、assemble、validate-l0/l1、export-md/zip、pack-diff、pack-merge、overlay-apply、ccos-build-task/import-result、project-validate。

## 目录所有权（与 Python 侧共存）

本目录由两条 golden 线共用，互不覆盖：

| 子树 | owner | 内容 |
|---|---|---|
| fixtures/ + golden/ | Rust 核心（本 README 描述的 golden-gen 产物） | 27 个 case，request/expected 原始字节 |
| ops/ | Python 控制面（app/cli/tools/bless_golden.py --bless） | Python 侧 15 个 case（sha256 钉 stdout） |

`golden-gen` 只重写 `fixtures/` 与 `golden/`（并清理临时 `out/`），**从不删除 `ops/`**（tests/golden.rs::golden_gen_preserves_ops_subtree 钉住）。Python 侧只读 `ops/`。双方复核命令：核心 `cargo test --test golden`；Python `python app/tests/test_golden.py`。

## 注意

- request.json 里的相对路径（fixtures/...、out/...）以本目录为 cwd 解析；复核测试以本目录为 cwd 启动二进制，并在 app/core/target/golden-out/ 建临时 out_dir（工作区内，避开本机 ENV-01 写盘限制）。
- 写盘 op 的响应不含绝对路径（只有相对 path/sha256/size 或 tree），所以 expected 可跨机器逐字节一致。
- 不要手工改 expected：先人工确认契约变化，再改核心后用 golden-gen 重生成，并把 diff 连同契约改动一起评审。
