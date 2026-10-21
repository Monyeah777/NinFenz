# NinFenz · ドキュメント生成工房（仕様駆動）<sub>Spec-driven documentation workshop</sub>

<!-- nf:locales --> [简体中文](README.md) | [English](README.en.md) | **[日本语](README.ja.md)**

<p align="left">
  <a href="https://github.com/Monyeah777/NinFenz/actions/workflows/ci-verify.yml"><img src="https://github.com/Monyeah777/NinFenz/actions/workflows/ci-verify.yml/badge.svg" alt="ci-verify ゲート" height="20"></a>
  <a href="https://glama.ai/mcp/servers/Monyeah777/NinFenz/score"><img src="https://glama.ai/mcp/servers/Monyeah777/NinFenz/badges/score.svg" alt="Glama code quality score AAA" height="20"></a>
</p>

> **唯一の公式リポジトリ**：https://github.com/Monyeah777/NinFenz ｜ npm `ninfenz` ｜ GitHub Packages `@monyeah777/ninfenz`
> 他アカウントの同名リポジトリは**無断のミラー**であり、本プロジェクトを代表しません（Issue/PR も受け付けません）。

**サイト（公開）**: https://ninfenz.dev · machine entry [llms.txt](https://raw.githubusercontent.com/Monyeah777/NinFenz/main/llms.txt)

**NF ターミナル（TUI）** —— 全画面の人間向け入口（標準ライブラリのみ）。メニューと各アクションは `nf` CLI の実コマンドの制御された呼び出し元です。キー操作は一流ターミナルの慣例に従います（`Tab` でパネル切替、`↑↓` で移動、`/` で絞り込み、`?` でキー一覧）。詳細は [tui/README.md](tui/README.md) を参照。

![NF ターミナル TUI デモ（枠線は閲覧者のフォントに依存しません）](site/assets/demo.gif)

> MIT License · オリジナルのオープンソース · 派生・引用の際は出典を明記してください

NF は**コンテンツ契約層（content contract layer）**です——「AI が長文コンテンツを安定して産出する」ためのプロトコル・品質ゲート・資産基準を定義します。プロトコル自体はドメイン中立・モデル非依存です。

**別名と検索語**：NF · NinFenz · 宁封子 · コンテンツ契約層（content contract layer）· 仕様駆動のコンテンツ工場 · 長文生成プロトコル · 組立型コンテンツ生産 · モジュール／パイプライン／資産 · 品質ゲート · ドメインパック · MCP 接続。

**そうではないもの**：モデルではなく、プロンプトテンプレート集でもなく、特定ベンダーの SDK でもありません——プロトコル本体はドメイン中立・モデル非依存で、MCP は接続可能なプロトコルの一つにすぎません。

`bash verify.sh`（現在の基準値は下部の生成領域「品質証憑」行を参照） · `python scripts/nf.py --version`

## ⚡ AI / エージェントの方へ

- これは何か：仕様駆動のドキュメント工場。モジュール／パイプライン／資産を搭載 → 検証 → 出力。
- 入口チェーン：`docs/agent/AGENT_START.md`（着手）→ `docs/agent/AI_ROUTING.md`（経路選択）→ `docs/meta/DEEP_DIVE.md`（深く理解する）。
- 機械証憑：`bash verify.sh`（現在の基準値は下部の生成領域「品質証憑」行。`nf stats --write` が書き込みます）。機械向け入口一覧は `llms.txt`。言語面は `README.en.md` · `README.ja.md`（三面の機読事実と言語切替行は check34 の言語面スキャンが常時検証。登録表 = `protocol/locales.json`）。
- 設計意図を知る：[docs/meta/DEEP_DIVE.md](docs/meta/DEEP_DIVE.md) を参照。

## クイックスタート

最初の一歩：[`docs/quickstart.md`](docs/quickstart.md) の 6 ステップを順にコピー＆ペースト。ワンコマンドで自己検査する場合は `bash scripts/quickstart_check.sh`（判定：終了コード 0 · 実時間 ≤ 300 秒 · 文書ステップ数 == スクリプトステップ数）。

作者・開発者向け（5 分）：

1. `bash verify.sh`
2. `python scripts/nf.py shell`（対話ターミナル。シェル退役後の人間向け入口。詳細は `docs/terminal.md`）
3. `python scripts/nf.py demo`
4. `python scripts/nf.py --help`
5. `python scripts/nf.py doctor`
6. `python scripts/nf.py completion bash`

AI による組立：

1. `docs/agent/AGENT_START.md` を読む
2. `docs/agent/agent_组装指令包_v0.2.md` を読む（`v0.2.md` は同一ファイル）
3. 必要に応じて 01/02/06/07 と `community/` のパッケージを取得
4. 「完全版」を組み立て、`##7` のセルフチェックを通す
5. `nf assemble "<要件>" --build --dest <ディレクトリ>`（組立コマンド：単一ファイルの「完全版」を直接生成）
6. `nf assemble "<要件>" --check <out.md>`

### よくある質問（FAQ）

- **NF とは？** コンテンツ契約層です。「AI が長文を安定して産出する」ことをプロトコル＋品質ゲート＋資産基準として定義し、産出物を搭載可能・検証可能・再現可能にします。
- **NF は MCP サーバーですか？** 必須ではありません。プロトコルと資産はすべてプレーンテキストで、clone または直リンクで搭載できます。`nf serve` が追加で MCP 接続面を提供します。
- **対応モデルは？** モデル非依存です。テキストを読める AI ならどれでもプロトコルに従って組立・搭載できます。特定モデルや特定接続プロトコルに縛られません。
- **ネット接続は必須？** 不要です。リポジトリ自体が markdown 原稿です。`bash verify.sh` はローカルのみで完結し、オフラインで実行できます。
- **産出物の合格判定は？** 判定は内部チェーンのみ：verify ゲート（静的に検証可能）＋五次元の縦深自己評価＋実戦例。外部評価は品質の裏付けとして用いません。
- **引用方法は？** MIT ライセンス。引用時は出典を明記してください。機読メタデータはリポジトリ直下の引用ファイル（`CITATION.cff`）にあります。
- **輸出・コンプライアンスは？** 暗号は標準ライブラリと外部 `ssh-keygen` のみ（独自アルゴリズムなし）。輸出管理の読み方は `docs/EXPORT.md` にあります。

## 機能と資産

<!-- nf:stats:begin -->
**公式コア**：13 モジュール · 3 パイプライン（P00 / P01 / P90） · コアプロトコル 01–07
**コミュニティ規模**：111 登録パッケージ · 363 資産ファイル · 101 概念グラフ · 100 ドメインパック／1200 細分類 · 標準カタログ 370 件（到達可能 332 ／ 不可達 38 · 機関 194 · 206 依存辺） · 標準バインディング 1200 件
**品質証憑**：verify v2.30 · check1-42 · PASS=76（bash verify.sh の単一入口。期待基準は quality_baseline.EXPECTED_*） · 所蔵 3 件

分层：data 148 · eng 38 · form 29 · gov 71 · iface 84 （標準カタログ layer 別）

> 本区は python scripts/nf.py stats --write が生成します（手改禁止）。口径と実算真源は protocol/repo_stats.json。
<!-- nf:stats:end -->

## プロトコルチェーンと文書ナビ

| 層 | 入口 |
|---|---|
| 方向 | `STRATEGY.md` |
| プロトコル | `01_核心协议.md` · `02_联动注册表.md` · `06_Agent执行协议.md` · `07_官方核心出厂与社区预设导航.md` · `protocol/WORLD_MODEL.md` |
| ライブラリ | `03_管线库/` · `04_模块库/` · `05_资产库/` |
| コミュニティ | `community/README.md` · `community/模板制作指令包.md` |
| AI | `docs/agent/AGENT_START.md` · `docs/agent/AI_ROUTING.md` · `docs/meta/DEEP_DIVE.md` |
| ツール | `docs/mcp.md` · `docs/terminal.md` · `docs/layers.md` · `docs/release.md` · `scripts/nf.py` · `tui/nf.py` · `verify.sh` |
| 接続面 | `integrations/README.md`（MCP / LSP / CLI / TUI / 図書館 / Skill / npm / Rust / .NET / A2A） |
| 書庫 | `library/INDEX.md` · `docs/agent/ROUTES.md` |

## バージョン

**`ninfenz` 1.0.5** をそのまま導入できます（npm と GitHub Packages の同時公開）:

```bash
npm i -g ninfenz@latest   # 導入・更新
nf --version             # 現在のバージョン
nf stats                 # ゲートとリポジトリの状態
```

同じリポジトリから 3 本のバージョン系列を独立して出しています:

| 系列 | 現在 | 何を決めるか |
|---|---|---|
| **コンテンツ / プロトコル** | **v0.93** | テンプレート・ドメインパック・仕様 —「何を生成できるか」 |
| **コマンドラインツール** | **1.0.5** | `nf` コマンド / npm パッケージ / MCP サーバー —「どう使うか」 |
| **品質ゲート** | `nf stats` を参照 | 自己検査の状態 —「壊れていないか」 |

直近 3 つのコンテンツ版（番号ではなく**追加された機能**で）:

| バージョン | 日付 | この版で増えたもの |
|---|---|---|
| v0.93 | 2026-10-05 | 知識層の検索、ターミナル形態、デジタル資産契約（資産を横断再利用） |
| v0.92 | 2026-09-10 | 世界状態モデル：決定的な抽象状態＋スロット（同じ入力なら同じ出力） |
| v0.82 | 2026-09-09 | 品質纵深 45 項目＋基盤層 A |

リリース規則（2026-10-20 以降）：コンテンツ系列は `v0.xx` —— 小さな更新は現行版に統合、小さな突破は **+0.01**、革新的な突破は **+0.1**。CLI 系列は
`1.0.x` で独立。リリースごとに `CHANGELOG.md` を更新し、タグは**機能を含むコミット**に打ちます。

