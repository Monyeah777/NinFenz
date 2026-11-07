# 标注 IR v0（`cc_label` 的声明层）
> ⛔ 操作指令：阅读即执行——本文含可直接执行的命令与判定，勿当资料阅读。
> 最后更新：2026-11-05
> **Status**: v0 已实装**声明层**（`core/label_ir.py` + `nf label ir|validate`）+ **载体层
> （`core/label_carrier.py`：PNG iTXt / JPEG APP15 / WebP NFLA / MP4 free 盒 / PDF 尾部注释；
> `core/label_watermark.py`：PNG 像素水印）**（`nf label embed|extract`）

## 是什么 / 不是什么

`nf-label/1` 是一份**纯数据 IR**：描述「某对象按某个标准**应当**带哪些标识」，并校验声明的形状与
档位齐备度。它**不**写载体、**不**读载体、**不**证明文件里真的带标识——载体写入在
`core/label_carrier.py`（PNG iTXt / JPEG APP15，只证读回/内容面不变/结构合法/对象绑定），
任何「已写入水印/已嵌入元数据」的宣称都不可证。

## 规则表（GB 45438 分类 · v0 映射）

| id | 面 | kind | 从哪档起必需 | 要求 |
|---|---|---|---|---|
| E1 | 显式 | text | minimal | `where`（start/end/ui）+ `value` |
| E2 | 显式 | audio | full | `value`（可听提示） |
| E3 | 显式 | metadata | full | `key` + `value`（生成合成声明字段） |
| I1 | 隐式 | watermark | full | `algorithm` + `value` |
| I2 | 隐式 | metadata | minimal | `key` + `value`（文件元数据字段） |

v0 映射**待按标准原文复核**：本表给的是「哪几类要求」而不是条款号；换标准要改 `STANDARD` 并补判据。

## 怎么用

```bash
# 组装 IR（不给 --items 就是空声明，靠校验面把缺口暴露出来）
nf label ir 产出/海报.png --level minimal --items items.json --out 产出/海报.label.json

# 校验（退出码：ok=0 / invalid=1 / 用法错=4）
nf label validate 产出/海报.label.json
```

`items.json` 是声明项数组，每项带 `face`（explicit/implicit）+ `kind` + 该 kind 的必填字段。

## 判定（可证）

| 检查 | 不过 |
|---|---|
| schema == `nf-label/1`、standard == 当前标准、level ∈ {minimal, full} | invalid |
| `object.path` 非空、`object.digest` 为 64 位十六进制 sha256 | invalid |
| `explicit` / `implicit` 是数组，且每项 kind 在该面允许集合内 | invalid |
| `carrier.embedded` 是布尔 | invalid |
| 档位必需的每条规则都有匹配声明项（kind 相符 + 必填字段非空） | invalid（列出缺哪几条） |
| `carrier.embedded=true` 但本仓无写入子系统 | **ok + warning**（不当成功，只如实提示自称） |


## sidecar 回退载体（v0 已实装）

嵌入载体做不到时，ABI 允许回退 sidecar：把标注 IR 写到对象旁的 `<对象>.label.json`，**与对象摘要绑定**。
`nf-label-sidecar/1` 的 `embedded` **恒为 false**（常量，不是参数）——它证明「这份声明与这份对象对得上」，
不证明「对象里真的带标识」。

```bash
nf label write --object 产出/海报.png --ir 产出/海报.label.json   # 写旁车（绑定摘要）
nf label read 产出/海报.png                                      # 读旁车 + 对账
nf label list                                                    # 清点仓内全部旁车
```

| 检查 | 不过 |
|---|---|
| 旁车在场且 schema == `nf-label-sidecar/1` | invalid |
| 旁车内 IR 通过 `nf-label/1` 校验 | invalid |
| **对象摘要 == 旁车绑定摘要** | invalid（「对象已被改动，标签声明已过期」） |
| 对象可读（被删/权限不足） | invalid |

写盘走 `atomic_write`：半截旁车会让读者读到假声明。读判据只读旁车 + 对象摘要，不联网、不猜。


## 载体（v0 已实装：PNG / JPEG / WebP / MP4 / PDF + PNG 水印）

`nf label embed` 按 magic 选载体，`--mode` 选写入面：

| 格式 | 写入面 | 载体机制 | 承诺 |
|---|---|---|---|
| PNG | `--mode text`（缺省） | `iTXt` 块（keyword = `AIGC`，UTF-8） | 读回 + **不改像素** + 结构合法 |
| PNG | `--mode watermark` | 像素最低位帧（24×24 块冗余 × 多数表决） | 读回 + **删掉文本块仍在** + 扛裁剪/重存；**不**扛 JPEG/缩放 |
| JPEG | `text` | `APP15` 段（`AIGC\0` + JSON） | 读回 + 扫描数据原样 + 段结构合法 |
| WebP | `text` | RIFF 尾部私有块 `NFLA`（同步 RIFF 长度） | 读回 + 媒体块逐字节不变 + 解码器可开 |
| MP4 | `text` | 顶层 `free` 盒（尾部追加） | 读回 + 原始盒逐字节保留 |
| PDF | `text` | `%%EOF` 后注释行（base64） | 读回 + 原文件前缀逐字节保留 |

**WebP/MP4/PDF 的承诺比图片弱**：不是写元数据，而是**在容器尾部追加可忽略块**——旧解码器照样能开，
要删也只要截掉尾部。这三条都只证明「可读回 + 媒体字节没被碰」，不证明「别人删不掉」。

```bash
nf label embed --object 产出/海报.png  --ir 产出/海报.label.json            # 文本块（不改像素）
nf label embed --object 产出/海报.png  --ir 产出/海报.label.json \
            --mode watermark --out 产出/海报.wm.png                      # 像素水印（删块仍在）
nf label embed --object 产出/片段.mp4  --ir 产出/片段.label.json            # MP4 free 盒
nf label embed --object 产出/报告.pdf  --ir 产出/报告.label.json            # PDF 尾部注释
nf label extract 产出/海报.wm.png                                          # auto：先文本块，再水印
```

**水印的边界（判据里写成期望行为）**：低位水印扛得住裁剪、无偏噪声与无损重存；
**扛不住** JPEG 重编码 / 缩放 / 截屏——有损变换改的就是低位。`test_label_watermark.py` 里
「JPEG 转码后读不回」是断言通过的**期望行为**，避免下次有人把它当 bug 修。
水印帧只带 IR 的摘要帧（版本/标准/对象摘要前缀/条目名/条数），不是整份 IR。

## 与 `cc_label` 的关系

`nf label embed` 按 magic 选载体：**PNG → `iTXt` 块**（keyword = `AIGC`，UTF-8）、
**JPEG → `APP15` 段**（`AIGC\0` + JSON）。`nf label extract` 读回。纯标准库实现，
**只承诺三件能自证的事**：

| 承诺 | 判据 |
|---|---|
| 写进去能读回（同 IR、JSON 语义等价） | `nf label extract` 返回同档位/同声明项 |
| **不改像素** | PNG：所有 IDAT 块拼接后 sha256 一致；JPEG：SOS 到 EOF 的原始字节 sha256 一致 |
| 写后仍是结构合法的文件 | PNG：每块 CRC + 签名 + IHDR 首 / IEND 尾；JPEG：段边界/长度合法、SOI 起、含 SOS |

```bash
nf label embed --object 产出/海报.png  --ir 产出/海报.label.json   # 缺省落 海报.png.labeled.png，不改输入
nf label embed --object 产出/照片.jpg  --ir 产出/照片.label.json   # JPEG 走 APP15，扫描数据原样保留
nf label extract 产出/海报.png.labeled.png
```

**边界**：这是**可见文本载体**（任何人都能剥掉 iTXt 块或 APP15 段），不是水印——抗裁剪/抗转码/
抗截屏都不承诺；MP4/PDF/WebP 等格式没有实测，一律走 `nf label write` 的 sidecar 回退，不宣称已嵌入。
真仓图标（多 IDAT / 辅助块）与真 JPEG 的往返各有判据；JPEG 另有一条「Pillow 在场时解码后像素一致」的
附加判据（环境无 Pillow 则跳过，不冒充已验）。

## 与 `cc_label` 的关系

`cc_label(obj, contract)` 要返回 `{label: {contract, standard, fields, carrier, embedded}}`。v0 做实两块：
**声明层**（IR 形状与齐备度）+ **sidecar 回退**（把声明落到对象旁并与摘要绑定）；`embedded` **恒为
false**，无法证「对象里真的带标识」。因此 ABI 里 `cc_label` 记为 `partial`，不升级为 `implemented`。

## 复核

```bash
python -m unittest desktop.tests.test_label_ir   # 16 项：档位/形状/自称提示/CLI 往返
```
