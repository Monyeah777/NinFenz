# 独立 Benchmark

> 这些是 24 H 的直接 benchmark（非 10 Trials）；证据与 trials/ 同等可复算。

| H | 脚本 | 结果 |
|---|---|---|
| H1.1 | `python app/scripts/bench_h11.py` | 30 双栏 PDF ×5 页；阅读顺序 1.0；表格 F1 1.0；脚注 1.0 |
| H1.2 | `python app/scripts/bench_h12.py` | 30/30 账本一致；0 silent loss；page/bbox 100% |
| H2.1 | `python app/scripts/bench_h21.py` | 30 份 md/docx/epub/pdf；往返 parity 1.0 |
| H2.3 | `python app/scripts/bench_h23.py` | 50/50 修复；0 不可恢复；0 块丢失 |
| H4.4 | `python app/scripts/bench_h44.py` | 10×5×3；parity 1.0；EPUBCheck 0 error |
| H5.1 | `python app/scripts/bench_h51.py` | 20 文档；EPUBCheck/Open XML/PDF-UA/WCAG 0 |
| H5.3 | `python app/scripts/bench_h53.py` | 3 格式 ×3 应用；27/27 打开；0 缺字 |
