# zero_slice 原型（P0）

从 v2 增量补丁附录 P 内联的参考实现落盘，用于在移植 Rust/Kotlin 前锁定导入会话语义。

- `nf_zero_slice.py`：Markdown/纯文本结构解析、spec 映射、exceptions、会话状态机、reset/undo、DraftStore、to_project。
- `test_zero_slice.py`：14 个单元测试。
- `fixtures/`：真实 brief 与匹配/不匹配 spec。

运行：

```bash
cd app/prototypes/zero_slice
python -m unittest -v test_zero_slice.py
python nf_zero_slice.py --file fixtures/brief.md --spec fixtures/brief-spec.json
```

限制：仅 Markdown/纯文本；删除草稿的 5 秒撤销未实现 trash；不替代 Android UI。
