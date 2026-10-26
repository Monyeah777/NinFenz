# RustPython parser vendor provenance

These directories are source snapshots of the crates.io packages below. They
are compiled only through local path dependencies so every Rust entry point
(`nf-rs`, PyO3, and fuzz) resolves the same parser graph.

| Directory | Upstream package | Version | Upstream commit |
| --- | --- | --- | --- |
| `rustpython-parser` | `rustpython-parser` | 0.4.0 | `8dd2aea26778d8d6917770f8e32bea1b9cdc0ae8` |
| `rustpython-ast` | `rustpython-ast` | 0.4.0 | `8dd2aea26778d8d6917770f8e32bea1b9cdc0ae8` |
| `rustpython-literal` | `rustpython-literal` | 0.4.0 | `8dd2aea26778d8d6917770f8e32bea1b9cdc0ae8` |

The upstream project is <https://github.com/RustPython/Parser>. The package
metadata declares MIT; the repository's license terms and copyright notices
remain in force.

## Local security changes

The crates.io release selects `malachite-bigint` and depends on the
unmaintained `paste` and `unic-*` families. OSV reports those transitive
packages as vulnerable/unmaintained even though `rustpython-parser` 0.4.0 is
the latest published parser release.

This snapshot makes only the dependency substitutions needed to remove that
risk while preserving the parser API:

- `malachite-bigint` is replaced by the parser's existing `num-bigint` backend.
- `unic-ucd-ident` is replaced by `unicode-ident`.
- `unic-emoji-char` is replaced by `unicode-properties`' emoji table.
- `unic-ucd-category` is replaced by `unicode-general-category`.
- Parser, AST, and literal crates are linked by local paths.

The Unicode replacements use current Unicode property tables. Consumers must
therefore tolerate the additive recognition of code points assigned by newer
Unicode versions; no grammar or AST shape is changed.

## Refresh procedure

When upstream publishes a maintained parser release, update these snapshots
from that exact package version, reapply or upstream the substitutions, and run:

```text
cargo check --locked
cargo test --locked
cargo check --locked        # from pyo3/
cargo +nightly check --locked  # from fuzz/
```

Then rescan all three lockfiles with OSV. Keep changes in a dedicated commit so
the vendored delta remains auditable.
