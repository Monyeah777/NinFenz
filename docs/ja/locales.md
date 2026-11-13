# 言語面とローカライズ（locales）
> ⛔ 操作指示：本ファイルは言語面・ローカライズ方針の**宣言件**です。判据は check34（core/locales.py）。読んだら実行してください。
> 最終更新：2026-11-13

## これは何か

NF の言語面は二層あります：**入口面**（README.md / README.en.md / README.ja.md）と**文書面**（docs/<lang>/…）。
真源は protocol/locales.json：言語ごとの入口・責任者（codeowner）・被覆宣言、および文書訳と**原文摘要**です。

## 規則（すべて機検）

1. **入口面**：各面は同じ機械可読アンカー群 + 言語切替行（在场する全言語を列挙）+ H2 構造の一致 + canonical が参照する .md 件の網羅を満たすこと。
2. **文書面**：訳のパスは原文を**ミラー**すること（docs/<lang>/<原文相対パス>）。各訳は source_sha256 を登録し、**原文が変われば即「期限切れ」**。
3. **被覆の誠実さ**：coverage=entry の言語は文書訳を持ってはならない。coverage=entry+guides は登録表が宣言する全訳を備えること。
4. **未宣言は赤**：docs/<lang>/ に登録のない訳を置くと FAIL（管理されない第二言語面を作らない）。

## 訳を足す手順

(1) docs/<lang>/<原文相対パス> に訳を書く；
(2) protocol/locales.json の docs[].translations に path を登録する；
(3) python scripts/nf.py locales --write で原文摘要を再署名する；
(4) python scripts/nf.py locales で自検——期限切れ・非ミラー・言語欠落・未宣言はすべて赤になります。

## 現状対照（2026-11-13 · 登録表からの実読）

| 面 | 現値 | 再確認方法 |
|---|---|---|
| 言語 | **3 言語**（zh / en / ja）、いずれも coverage=entry+guides | protocol/locales.json: locales |
| 入口面 | **3 件**（README.md / README.en.md / README.ja.md） | 登録表 entry + ファイル在场 |
| 文書訳 | **12 件** = 6 ガイド x 2 言語 | docs[].translations |
| ガイド一覧 | release / locales / mcp / terminal / layers / **lsp**（6 件） | docs[].path |
| 責任者 | 3 言語すべて codeowner 登録済み | locales[].codeowner |
| 判定 | check34 + test_locales **12 例** | verify.sh / pytest |

> 索引のみ。数値は nf locales の実読が真。

## 再現と引用の口径

```bash
python scripts/nf.py locales          # 言語/訳の突合 + 期限切れ検出
python scripts/nf.py locales --write  # 訳の原文摘要を再署名（原文変更後は必須）
python -m pytest desktop/tests/test_locales.py -q   # 12 例
```

- 引用時の口径：「入口 3 言語 + 文書 12 訳、原文を変えれば期限切れ」が長期口径。

## 現状と境界

- 入口面は **3 言語**（中文 / English / 日本語）。文書面は **6 件**のガイドを被覆：リリース / ローカライズ / MCP 接続 / ターミナル / 抽象階段 / **LSP**（計 12 訳）。
- その他の文書は依然として単言語——**登録表が明示的に宣言**しており、黙った単言語ではありません。新しい訳は上の四手順で追加します。
- 外部翻訳プラットフォームは導入せず、**機械翻訳もしません**：内容品質は訳者の責任で、判据は「宣言されたものが在场し、期限切れでない」ことだけを保証します。
- 言語面の責任者は登録表の codeowner（Home Assistant の codeowners と同義）。
