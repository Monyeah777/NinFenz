"""生成块落盘助手：把 `// >>> GENERATED` 段写进独立文件 `src/generated/<module>_gen.rs`。

背景：原先各 `tools/gen_*.py` 把生成段内联改写进 `src/<module>.rs` 的 `#[cfg(test)] mod tests`
区，生成数据把主文件撑到上万行（审计 C-001/C-009/C-012/C-005 命中）。现在生成段落在
`src/generated/<module>_gen.rs`（审计按 `*_gen.rs` / `generated/**` 的生成面排除），
主文件只留一条顶层挂载：

    #[cfg(test)]
    #[path = "generated/<module>_gen.rs"]
    mod <module>_gen;

挂载声明必须放在主文件**模块顶层**（不能放进 `mod tests` 里）：`#[path]` 在 inline mod 中按
「源文件目录 + inline 模块名」解析，会指到 `src/<module>/tests/<module>_gen.rs`，落不了仓。

生成文件结构：

    //! 生成文件（勿手改）……
    mod tests {
        use super::super::*;
        <生成块原文，缩进/行数保持原样>
    }

包一层 `mod tests` 有两个作用：① 生成块里的 `#[test]` 照旧在测试模块里（可见面 = 主模块）；
② 与原先「在 `mod tests` 内」的缩进层级一致，迁移时可以直接沿用原文件里的块字节。

幂等（关键）：`write_gen_block` 先按 **token 归一**（忽略空白与列表尾随逗号）比较新旧块，
**内容一致就原样保留在盘块**（不重写），只有真源确实变了才整块替换。这样：
- 生成文件不必依赖 rustfmt 版本（仓库里的块排版来自历史 rustfmt，重排只会制造无关 churn）；
- 生成器跑 N 次输出逐字节一致；`cargo fmt` 之后再跑生成器也不会把排版翻回去。

用法（各生成器尾部）：

    from _gen_target import ensure_mount, write_gen_block
    ensure_mount(ROOT, '<module>')
    write_gen_block(ROOT, '<module>', BEGIN, END, block)
"""
from __future__ import annotations

import pathlib

#: 生成文件所在子目录（相对 `src/`）。放子目录有两个理由：`src/output_forms_gen.rs` 已被同名
#: 手写模块占用（`<module>_gen.rs` 在 src/ 顶层会撞名）；且审计把 `generated/**` 与 `*_gen.rs`
#: 都视为生成面，放这里两条排除规则都命中。
GEN_DIR = 'generated'

#: 生成文件固定头部：文档 + 测试模块外壳（生成块原样落在模块体内）。
HEADER = """//! 生成文件（勿手改）：由 `engine/rust/tools/gen_*.py` 重跑覆盖；手工区在主文件。
//!
//! 主文件 `engine/rust/src/{module}.rs` 以
//! `#[cfg(test)] #[path = "generated/{module}_gen.rs"] mod {module}_gen;` 挂载本模块。
//!
//! 本文件保留生成块的原始缩进与行数（含用例字面量里的花括号），仅供阅读对账；
//! 行数/复杂度门禁按 `*_gen.rs` / `generated/**` 的生成面排除，不计入 C-001/C-005/C-009。

mod tests {{
    use super::super::*;
"""

#: 测试模块外壳的收尾。
FOOTER = '}' + chr(10)

#: 主文件挂载声明（模块顶层；`#[path]` 相对 `src/` 解析）。
MOUNT = """#[cfg(test)]
#[path = "generated/{module}_gen.rs"]
mod {module}_gen;
"""

#: 生成块在生成文件里的锚点（外壳里 `use super::super::*;` 之后）。
ANCHOR = '    use super::super::*;' + chr(10)


def gen_path(root, module):
    """`src/generated/<module>_gen.rs` 的路径（root 为仓库根）。"""
    return pathlib.Path(root) / 'engine' / 'rust' / 'src' / GEN_DIR / (module + '_gen.rs')


def gen_text(root, module):
    """读生成文件正文；不存在时返回空骨架（头部 + 收尾，等 `save_gen` 落盘）。"""
    path = gen_path(root, module)
    if path.exists():
        return path.read_text(encoding='utf-8')
    return HEADER.format(module=module) + FOOTER


def save_gen(root, module, text):
    """写生成文件（UTF-8 / LF）；父目录缺则建。"""
    path = gen_path(root, module)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8', newline='')


def tokens(text):
    """切成 token：字符串字面量整体一个 token，其余非空白字符逐个（排版差异被吃掉）。"""
    out = []
    i = 0
    n = len(text)
    bs = chr(92)
    while i < n:
        c = text[i]
        if c == 'r':
            j = i + 1
            k = 0
            while j < n and text[j] == '#':
                k += 1
                j += 1
            if j < n and text[j] == '"':
                end = '"' + '#' * k
                m = text.find(end, j + 1)
                if m >= 0:
                    out.append(text[i:m + len(end)])
                    i = m + len(end)
                    continue
        if c == '"':
            j = i + 1
            while j < n:
                if text[j] == bs:
                    j += 2
                    continue
                if text[j] == '"':
                    j += 1
                    break
                j += 1
            out.append(text[i:j])
            i = j
            continue
        if c == "'":
            # char 字面量（排除生命周期 'a）；两者都不含排版差异，按普通字符处理即可。
            if i + 2 < n and (text[i + 2] == "'" or text[i + 1] == bs):
                j = i + 1
                while j < n:
                    if text[j] == bs:
                        j += 2
                        continue
                    if text[j] == "'":
                        j += 1
                        break
                    j += 1
                out.append(text[i:j])
                i = j
                continue
        if c.isspace():
            i += 1
            continue
        out.append(c)
        i += 1
    return out


def norm(text):
    """token 归一：忽略空白与列表/元组的尾随逗号（`,)` / `,]` / `,}` 里的那个逗号）。"""
    toks = tokens(text)
    out = []
    for idx, tok in enumerate(toks):
        if tok == ',' and idx + 1 < len(toks) and toks[idx + 1] in (')', ']', '}'):
            continue
        out.append(tok)
    return chr(0).join(out)


def write_gen_block(root, module, begin, end, block):
    """把 `block`（含 BEGIN/END 标记）写进 `src/generated/<module>_gen.rs` 的对应区间。

    - 标记已在且 token 归一后内容一致：**原样保留在盘块**（幂等，且不抖排版）
    - 标记已在但内容变了：原位替换（真源刷新）
    - 标记不在：插到测试模块外壳收尾之前（首次落段）
    """
    text = gen_text(root, module)
    body = text[:-len(FOOTER)] if text.endswith(FOOTER) else text
    if begin in body:
        a = body.index(begin)
        b = body.index(end, a) + len(end)
        existing = body[a:b]
        if norm(existing) == norm(block):
            return gen_path(root, module)
        body = body[:a] + block + body[b:]
    else:
        if not body.endswith(chr(10)):
            body += chr(10)
        body += block
    if not body.endswith(chr(10)):
        body += chr(10)
    save_gen(root, module, body + FOOTER)
    return gen_path(root, module)


def ensure_mount(root, module):
    """主文件缺 `#[path = "generated/<module>_gen.rs"]` 挂载时补一条（幂等）；返回是否补写。"""
    main = pathlib.Path(root) / 'engine' / 'rust' / 'src' / (module + '.rs')
    text = main.read_text(encoding='utf-8')
    if ('#[path = "%s/%s_gen.rs"]' % (GEN_DIR, module)) in text:
        return False
    if not text.endswith(chr(10)):
        text += chr(10)
    text += chr(10) + MOUNT.format(module=module)
    main.write_text(text, encoding='utf-8', newline='')
    return True
