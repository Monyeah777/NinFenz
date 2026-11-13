# Locales and localization (locales)
> ⛔ Operating instruction: this file is the **declaration** of the language and localization policy; the judge lives in check34 (core/locales.py). Read it and run it.
> Last updated: 2026-11-13

## What this is

NF has two language surfaces: the **entry surface** (README.md / README.en.md / README.ja.md) and the **document surface** (docs/<lang>/...). The source of truth is protocol/locales.json: per-language entry, code owner, coverage declaration, and document translations with their **source digest**.

## Rules (all machine-checked)

1. **Entry surface**: every entry must carry the same machine-fact anchors, the language switcher line (enumerating all present languages), aligned H2 structure, and every .md file referenced by the canonical entry.
2. **Document surface**: a translation path must **mirror** the source (docs/<lang>/<source-relative-path>); each translation records source_sha256, so **any source edit marks it stale**.
3. **Honest coverage**: a locale declared coverage=entry must not ship document translations; coverage=entry+guides must ship every translation the registry declares.
4. **Undeclared is red**: a file under docs/<lang>/ that the registry does not declare fails the gate (no unmanaged second language surface).

## Adding a translation

(1) write the translation at docs/<lang>/<source-relative-path>;
(2) register its path in protocol/locales.json under docs[].translations;
(3) run python scripts/nf.py locales --write to re-sign the source digest;
(4) run python scripts/nf.py locales to self-check - stale / non-mirrored / missing locale / undeclared all turn red.

## Status check (2026-11-13 · read from the registry)

| Surface | Current value | How to re-check |
|---|---|---|
| Languages | **3** (zh / en / ja), all coverage=entry+guides | protocol/locales.json: locales |
| Entry surface | **3 files** (README.md / README.en.md / README.ja.md) | registry entry + file presence |
| Document translations | **12 files** = 6 guides x 2 languages | docs[].translations |
| Guide list | release / locales / mcp / terminal / layers / **lsp** (6) | docs[].path |
| Code owners | all 3 languages registered | locales[].codeowner |
| Judge | check34 + test_locales **12 cases** | verify.sh / pytest |

> Index only; numbers are read from nf locales.

## Reproduction and citation

```bash
python scripts/nf.py locales          # reconcile languages/translations + staleness
python scripts/nf.py locales --write  # re-sign translation source digests (after editing source)
python -m pytest desktop/tests/test_locales.py -q   # 12 cases
```

- Rule of thumb: "3 entry languages + 12 document translations; editing a source makes them stale" is the long-term rule.

## Status and boundaries

- Entry surface: **3 languages** (Chinese / English / Japanese). The document surface covers **6** guides: release, localization, MCP access, terminal, abstraction ladder, **LSP** (12 translations).
- The rest of the documentation is still single-language - **explicitly declared** by the registry, not silently monolingual; new translations follow the four steps above.
- No external translation platform and **no machine translation**: content quality is the translator's responsibility; the judge only guarantees that what is declared exists and is not stale.
- Language owners live in the registry's codeowner field (same meaning as Home Assistant codeowners).
