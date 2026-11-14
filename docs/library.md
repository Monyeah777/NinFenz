# 云端图书馆机器面（library）
> ⛔ 操作指令：阅读即执行——本文含可直接执行的命令与判定，勿当资料阅读。
> 最后更新：2026-11-13
> **复核（2026-11-13）**：真源/投影分层、分级门、状态与取代链**复核不变**；补可核现状：
> 馆藏 **3 件**（全部 `active`）· 分级声明 3/3（teen 1 / general 2）· 许可：MIT 2 / 未声明 1（如实缺口）·
> `library verify` 绿（条目 3 · 在役 3 · WARN 0）· 分级词表 **4 值**（`library/intake.json: rating.vocabulary`）·
> MCP 取用 3 面（`library_search` / `library_read` / `nf://repo/library/{编号}`）。见「§现状对照」。

## 是什么

`library/` 是 NF 对 AI 的知识面：条目按 NF 编号归档，任何 AI 凭编号可取。本条目的
**唯一真相源 = 条目文件头的 YAML frontmatter**；`INDEX.md` 的生成区与 `ALIAS.md`
都是**投影**（由脚本重生成，手改会被覆盖）。

## 怎么用

```bash
python scripts/nf.py library ls                     # 列条目（编号/状态/许可/标题）
python scripts/nf.py library show NF-1              # 看单条 frontmatter（大小写不敏感）
python scripts/nf.py library search "雨天"           # 正文级检索（倒排 + 中文子串 + 排序）
python scripts/nf.py library reindex                # 重生成 INDEX 生成区 + ALIAS
python scripts/nf.py library verify                 # frontmatter 真源 + 投影一致（门禁同语义）
python scripts/nf.py library deprecate|restore|supersede <编号…>
```

## 边界

- 条目 schema 见 `library/INDEX.md` 投稿须知；`license` 由 `nf license` 双源校验。
- 状态 `active / deprecated / superseded`（取代链须指向真实条目）；未收窄信息**留空而非猜**。
- 机器取用面另有 MCP：`library_search` / `library_read` / `nf://repo/library/{编号}`。

## 现状对照（2026-11-13 · 以真源实读为准）

| 面 | 现值 | 复核方式 |
|---|---|---|
| 馆藏条目 | **3 件**（NF-1 · NF-TECHDOC-… · NF-WORLDCAMPUS-…） | `nf library ls` |
| 状态 | active 3 / deprecated 0 / superseded 0 | 同上 |
| 分级声明 | 3/3（teen 1 · general 2） | 条目 frontmatter `rating` + `library verify` |
| 分级词表 | **4 值**（general / teen / mature / unrated） | `library/intake.json: rating.vocabulary` |
| 许可 | MIT 2 / **未声明 1**（如实缺口，不猜） | `nf license` 双源校验 |
| 投影 | `INDEX.md` 生成区 + `ALIAS.md` | `nf library reindex` 重生成 |
| 门禁 | `library verify` 绿（WARN 0） | 条目 3 · 在役 3 |

> 本表只作「当时 → 现行」导航；手改 `INDEX.md`/`ALIAS.md` 会被重生成覆盖，真源始终是条目 frontmatter。

## 复现与引用口径

```bash
python scripts/nf.py library ls       # 3 件 + 状态/许可/标题
python scripts/nf.py library verify   # frontmatter 真源 + 投影一致（退出码即门禁）
python -m pytest desktop/tests/test_library.py -q
```

- 引用本文时：「真源 = 条目 frontmatter；INDEX/ALIAS 是投影」= 长期口径；数字以 `library ls` 实读为准。
- 未声明许可/分级**不猜**：缺字段即 FAIL，`unrated` 必须显式写。

## 内容分级（2026-09-21 收口）

每件馆藏须在 frontmatter 声明 `rating`（真源），投影到登记表「分级」列：

```bash
python scripts/nf.py library reindex    # 重生成登记表（含分级列）
python scripts/nf.py library verify     # 含分级声明判据（缺字段即 FAIL）
```

词表来自 `library/intake.json: rating.vocabulary`（**按声明判，不写死在代码里**）：
`general` / `teen` / `mature` / `unrated`——`unrated` 是**显式声明未分级**，不是缺省。
本门只判「声明在场且合规」，不替投稿人做适龄判断。
